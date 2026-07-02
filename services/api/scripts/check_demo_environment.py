from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import NamedTuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


class CheckResult(NamedTuple):
    name: str
    ok: bool
    detail: str


def required_openapi_paths() -> tuple[str, ...]:
    return (
        "/health",
        "/ready",
        "/identity/oidc/readiness",
        "/identity/oidc/onboarding",
        "/identity/oidc/authorize",
        "/identity/oidc/callback",
        "/identity/oidc/logout",
        "/identity/session/logout",
        "/deployment/readiness",
        "/support/diagnostics",
        "/demo/manufacturing/overview",
        "/demo/manufacturing/workflows",
        "/demo/manufacturing/workflows/runs",
        "/demo/manufacturing/operations",
        "/demo/manufacturing/operations/snapshot",
        "/demo/manufacturing/demo-readiness",
        "/demo/manufacturing/operations/daily-brief",
        "/demo/manufacturing/operations/risk-scenarios/quality",
        "/demo/manufacturing/operations/risk-scenarios/maintenance",
        "/demo/manufacturing/operations/risk-scenarios/supplier-delay",
        "/demo/manufacturing/agents",
        "/demo/manufacturing/actions",
        "/demo/manufacturing/approvals",
        "/demo/manufacturing/audit",
        "/demo/manufacturing/model-routing",
        "/demo/manufacturing/ontology",
        "/demo/manufacturing/connectors",
        "/demo/manufacturing/connectors/manifests",
        "/demo/manufacturing/connectors/configurations",
        "/demo/manufacturing/connectors/credential-handles",
        "/demo/manufacturing/connectors/credential-leases",
        "/demo/manufacturing/connectors/egress-policies",
        "/demo/manufacturing/connectors/evidence-invariants",
        "/demo/manufacturing/connectors/evidence-invariants/snapshots",
        "/demo/manufacturing/connectors/evidence-invariants/snapshots/export",
        "/demo/manufacturing/connectors/evidence-invariants/snapshots/export-requests",
        "/demo/manufacturing/connectors/runs",
        "/demo/manufacturing/connectors/runs/checkpoints",
        "/demo/manufacturing/connectors/runs/checkpoints/claims",
        "/demo/manufacturing/connectors/ontology-proposals",
        "/demo/manufacturing/connectors/file-csv/preview",
        "/demo/manufacturing/connectors/external-db/preview",
        "/demo/manufacturing/simulation/replay",
        "/demo/manufacturing/simulation/replay/outputs",
    )


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _json(path: Path) -> dict[str, object]:
    return json.loads(_read_text(path))


def _make_targets(makefile_text: str) -> set[str]:
    return {
        match.group(1)
        for match in re.finditer(r"^([A-Za-z0-9_.-]+):(?:\s|$)", makefile_text, re.MULTILINE)
    }


def check_make_targets(repo_root: Path) -> list[CheckResult]:
    required_targets = {
        "dev-stack-up",
        "dev-stack-down",
        "demo-stack-up",
        "demo-stack-down",
        "demo-db-upgrade",
        "demo-api",
        "demo-web",
        "demo-check",
        "demo-check-live",
        "demo-verify",
    }
    makefile = repo_root / "Makefile"
    if not makefile.exists():
        return [CheckResult("makefile.demo_targets", False, "Makefile is missing.")]

    targets = _make_targets(_read_text(makefile))
    missing = sorted(required_targets - targets)
    return [
        CheckResult(
            "makefile.demo_targets",
            not missing,
            "all demo targets are present" if not missing else f"missing: {', '.join(missing)}",
        )
    ]


def check_backup_restore_targets(repo_root: Path) -> list[CheckResult]:
    required_targets = {
        "demo-backup-plan",
        "demo-backup-local",
        "demo-restore-local",
    }
    makefile = repo_root / "Makefile"
    if not makefile.exists():
        return [CheckResult("makefile.backup_restore_targets", False, "Makefile is missing.")]

    targets = _make_targets(_read_text(makefile))
    missing = sorted(required_targets - targets)
    return [
        CheckResult(
            "makefile.backup_restore_targets",
            not missing,
            "backup and restore demo targets are present"
            if not missing
            else f"missing: {', '.join(missing)}",
        )
    ]


def check_compose_services(repo_root: Path) -> list[CheckResult]:
    compose_file = repo_root / "infra" / "docker" / "docker-compose.yml"
    required_services = ("postgres", "typedb", "temporal", "temporal-ui", "minio", "keycloak")
    if not compose_file.exists():
        return [CheckResult("docker.compose_services", False, "docker-compose.yml is missing.")]

    compose_text = _read_text(compose_file)
    missing = [
        service
        for service in required_services
        if not re.search(rf"^\s{{2}}{re.escape(service)}:\s*$", compose_text, re.MULTILINE)
    ]
    return [
        CheckResult(
            "docker.compose_services",
            not missing,
            "all local runtime services are declared"
            if not missing
            else f"missing: {', '.join(missing)}",
        )
    ]


def check_openapi_contract(repo_root: Path) -> list[CheckResult]:
    openapi_file = repo_root / "docs" / "openapi.json"
    if not openapi_file.exists():
        return [CheckResult("openapi.demo_paths", False, "docs/openapi.json is missing.")]

    document = _json(openapi_file)
    paths = document.get("paths")
    if not isinstance(paths, dict):
        return [CheckResult("openapi.demo_paths", False, "OpenAPI document has no paths object.")]

    missing = sorted(path for path in required_openapi_paths() if path not in paths)
    return [
        CheckResult(
            "openapi.demo_paths",
            not missing,
            "critical demo routes are present" if not missing else f"missing: {', '.join(missing)}",
        )
    ]


def check_demo_docs(repo_root: Path) -> list[CheckResult]:
    docs_file = repo_root / "docs" / "demo-readiness.md"
    readme_file = repo_root / "README.md"
    plan_file = repo_root / "plan.md"
    results: list[CheckResult] = []

    if not docs_file.exists():
        results.append(
            CheckResult("docs.demo_readiness", False, "docs/demo-readiness.md is missing.")
        )
    else:
        docs_text = _read_text(docs_file)
        normalized_docs_text = docs_text.casefold()
        required_phrases = (
            "SME feedback demo",
            "Enterprise evaluation demo",
            "No browser-local mock data",
            "OIDC readiness",
            "Current limitations",
            "Acceptance checklist",
        )
        missing = [
            phrase for phrase in required_phrases if phrase.casefold() not in normalized_docs_text
        ]
        results.append(
            CheckResult(
                "docs.demo_readiness",
                not missing,
                "demo readiness runbook is explicit"
                if not missing
                else f"missing phrases: {', '.join(missing)}",
            )
        )

    if not readme_file.exists():
        results.append(CheckResult("docs.readme_demo_link", False, "README.md is missing."))
    else:
        readme_text = _read_text(readme_file)
        results.append(
            CheckResult(
                "docs.readme_demo_link",
                "docs/demo-readiness.md" in readme_text,
                "README links the demo readiness runbook"
                if "docs/demo-readiness.md" in readme_text
                else "README does not link docs/demo-readiness.md",
            )
        )

    if not plan_file.exists():
        results.append(CheckResult("docs.plan_demo_tracking", False, "plan.md is missing."))
    else:
        plan_text = _read_text(plan_file)
        phrase = "Add repeatable demo environment runbook and automated readiness checks"
        results.append(
            CheckResult(
                "docs.plan_demo_tracking",
                phrase in plan_text,
                "plan tracks demo environment readiness"
                if phrase in plan_text
                else f"plan.md does not contain: {phrase}",
            )
        )

    return results


def check_backup_restore_runbook(repo_root: Path) -> list[CheckResult]:
    runbook_file = repo_root / "docs" / "backup-restore.md"
    if not runbook_file.exists():
        return [
            CheckResult("docs.backup_restore_runbook", False, "docs/backup-restore.md is missing.")
        ]

    runbook_text = _read_text(runbook_file)
    required_phrases = (
        "demo-backup-plan",
        "demo-backup-local",
        "demo-restore-local",
        "--confirm-restore",
        "postgres.dump",
        "minio-data.tar.gz",
        "typedb-data.tar.gz",
        "production disaster recovery",
    )
    normalized_runbook_text = runbook_text.casefold()
    missing = [
        phrase for phrase in required_phrases if phrase.casefold() not in normalized_runbook_text
    ]
    return [
        CheckResult(
            "docs.backup_restore_runbook",
            not missing,
            "backup and restore runbook is explicit"
            if not missing
            else f"missing phrases: {', '.join(missing)}",
        )
    ]


def run_static_checks(repo_root: Path) -> list[CheckResult]:
    repo_root = repo_root.resolve()
    checks: list[CheckResult] = []
    checks.extend(check_make_targets(repo_root))
    checks.extend(check_backup_restore_targets(repo_root))
    checks.extend(check_compose_services(repo_root))
    checks.extend(check_openapi_contract(repo_root))
    checks.extend(check_demo_docs(repo_root))
    checks.extend(check_backup_restore_runbook(repo_root))
    return checks


def _fetch_json(url: str) -> tuple[bool, str]:
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=5) as response:
            payload = response.read().decode("utf-8")
            json.loads(payload)
            return 200 <= response.status < 300, f"HTTP {response.status}"
    except HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except (OSError, URLError, json.JSONDecodeError) as exc:
        return False, str(exc)


def _fetch_text(url: str) -> tuple[bool, str]:
    request = Request(url, headers={"Accept": "text/html, */*"})
    try:
        with urlopen(request, timeout=5) as response:
            body = response.read().decode("utf-8", errors="replace")
            ok = 200 <= response.status < 300 and "Limes Axis" in body
            detail = f"HTTP {response.status}"
            if 200 <= response.status < 300 and "Limes Axis" not in body:
                detail += ", response did not include Limes Axis"
            return ok, detail
    except HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except (OSError, URLError) as exc:
        return False, str(exc)


def _fetch_operations_snapshot(api_url: str) -> tuple[bool, str]:
    request = Request(
        f"{api_url.rstrip('/')}/demo/manufacturing/operations/snapshot",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            domains = payload.get("domain_snapshots")
            metrics = payload.get("metrics")
            generation_boundary = payload.get("generation_boundary")
            ok = (
                200 <= response.status < 300
                and payload.get("tenant_id") == "tenant_demo_manufacturing"
                and isinstance(domains, list)
                and len(domains) > 0
                and isinstance(metrics, list)
                and len(metrics) > 0
                and generation_boundary == "persisted_manufacturing_operations_snapshot"
            )
            if ok:
                return True, f"HTTP {response.status}, {len(domains)} persisted domains"
            return False, f"HTTP {response.status}, invalid operations snapshot contract"
    except HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except (OSError, URLError, json.JSONDecodeError) as exc:
        return False, str(exc)


def _fetch_demo_readiness_report(api_url: str) -> tuple[bool, str]:
    request = Request(
        f"{api_url.rstrip('/')}/demo/manufacturing/demo-readiness",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            tracks = payload.get("tracks")
            checks = payload.get("checks")
            generation_boundary = payload.get("generation_boundary")
            readiness_status = payload.get("readiness_status")
            ok = (
                200 <= response.status < 300
                and payload.get("tenant_id") == "tenant_demo_manufacturing"
                and isinstance(tracks, list)
                and len(tracks) >= 2
                and isinstance(checks, list)
                and len(checks) >= 5
                and readiness_status in {"ready", "watch", "action_required"}
                and generation_boundary == "derived_from_persisted_demo_evidence"
            )
            if ok:
                return True, f"HTTP {response.status}, {len(checks)} readiness checks"
            return False, f"HTTP {response.status}, invalid demo readiness contract"
    except HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except (OSError, URLError, json.JSONDecodeError) as exc:
        return False, str(exc)


def _fetch_oidc_readiness_report(api_url: str) -> tuple[bool, str]:
    request = Request(
        f"{api_url.rstrip('/')}/identity/oidc/readiness",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            checks = payload.get("checks")
            token_binding = payload.get("token_binding")
            body_text = json.dumps(payload, sort_keys=True).casefold()
            ok = (
                200 <= response.status < 300
                and payload.get("status") in {"ready", "action_required"}
                and isinstance(payload.get("enterprise_sso_ready"), bool)
                and isinstance(payload.get("auth_required"), bool)
                and payload.get("jwks_source") in {"configured", "derived_from_issuer"}
                and isinstance(checks, list)
                and len(checks) >= 6
                and isinstance(token_binding, dict)
                and "secret" not in body_text
                and "password" not in body_text
            )
            if ok:
                return True, (
                    f"HTTP {response.status}, "
                    f"{payload.get('status')} enterprise_sso_ready="
                    f"{payload.get('enterprise_sso_ready')}"
                )
            return False, f"HTTP {response.status}, invalid OIDC readiness contract"
    except HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except (OSError, URLError, json.JSONDecodeError) as exc:
        return False, str(exc)


def _fetch_oidc_onboarding_report(api_url: str) -> tuple[bool, str]:
    request = Request(
        f"{api_url.rstrip('/')}/identity/oidc/onboarding",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            provider = payload.get("provider")
            client = payload.get("client")
            claims = payload.get("claims")
            body_text = json.dumps(payload, sort_keys=True).casefold()
            open_action_items = payload.get("open_action_items")
            ok = (
                200 <= response.status < 300
                and payload.get("status") in {"ready", "action_required"}
                and isinstance(payload.get("enterprise_sso_ready"), bool)
                and isinstance(provider, dict)
                and isinstance(provider.get("issuer"), str)
                and isinstance(provider.get("discovery_url"), str)
                and isinstance(provider.get("jwks_url"), str)
                and isinstance(client, dict)
                and client.get("auth_flow") == "authorization_code_pkce"
                and isinstance(client.get("redirect_uri"), str)
                and isinstance(client.get("post_logout_redirect_uri"), str)
                and isinstance(client.get("session_cookie_secure"), bool)
                and isinstance(claims, dict)
                and isinstance(claims.get("actor_claim"), str)
                and isinstance(claims.get("tenant_claim"), str)
                and isinstance(payload.get("required_redirect_uris"), list)
                and isinstance(payload.get("required_post_logout_redirect_uris"), list)
                and isinstance(open_action_items, list)
                and "client_secret" not in body_text
                and "access_token" not in body_text
                and "refresh_token" not in body_text
                and "id_token" not in body_text
                and "password" not in body_text
            )
            if ok:
                return True, (
                    f"HTTP {response.status}, "
                    f"{payload.get('status')} action_items={len(open_action_items)}"
                )
            return False, f"HTTP {response.status}, invalid OIDC onboarding contract"
    except HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except (OSError, URLError, json.JSONDecodeError) as exc:
        return False, str(exc)


def _fetch_deployment_readiness_report(api_url: str) -> tuple[bool, str]:
    request = Request(
        f"{api_url.rstrip('/')}/deployment/readiness",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            checks = payload.get("checks")
            capabilities = payload.get("capabilities")
            blockers = payload.get("production_blockers")
            body_text = json.dumps(payload, sort_keys=True).casefold()
            ok = (
                200 <= response.status < 300
                and payload.get("status") in {"ready", "action_required"}
                and isinstance(payload.get("production_ready"), bool)
                and isinstance(payload.get("demo_safe"), bool)
                and isinstance(blockers, list)
                and isinstance(checks, list)
                and len(checks) >= 5
                and isinstance(capabilities, dict)
                and capabilities.get("object_store_adapter")
                in {"local_filesystem", "s3_compatible"}
                and isinstance(capabilities.get("object_store_worm_retention_enabled"), bool)
                and isinstance(capabilities.get("object_store_retention_days"), int)
                and isinstance(capabilities.get("object_store_retention_mode"), str)
                and "secret" not in body_text
                and "password" not in body_text
            )
            if ok:
                return True, (
                    f"HTTP {response.status}, "
                    f"{payload.get('profile')} production_ready="
                    f"{payload.get('production_ready')}"
                )
            return False, f"HTTP {response.status}, invalid deployment readiness contract"
    except HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except (OSError, URLError, json.JSONDecodeError) as exc:
        return False, str(exc)


def _fetch_support_diagnostics_report(api_url: str) -> tuple[bool, str]:
    request = Request(
        f"{api_url.rstrip('/')}/support/diagnostics",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            diagnostics = payload.get("diagnostics")
            support_model = (
                diagnostics.get("support_model")
                if isinstance(diagnostics, dict)
                else None
            )
            support_commitments = (
                diagnostics.get("support_commitments")
                if isinstance(diagnostics, dict)
                else None
            )
            checks = payload.get("checks")
            support_artifacts = payload.get("support_artifacts")
            support_blockers = payload.get("support_blockers")
            body_text = json.dumps(payload, sort_keys=True).casefold()
            ok = (
                200 <= response.status < 300
                and payload.get("service") == "axis-api"
                and payload.get("status") in {"ready", "action_required"}
                and payload.get("safe_to_share") is True
                and isinstance(payload.get("demo_support_ready"), bool)
                and isinstance(payload.get("production_support_ready"), bool)
                and isinstance(support_blockers, list)
                and isinstance(diagnostics, dict)
                and isinstance(support_model, dict)
                and isinstance(support_model.get("severity_response_minutes"), dict)
                and isinstance(support_model.get("escalation_channels"), list)
                and isinstance(support_model.get("customer_runbook_configured"), bool)
                and isinstance(support_model.get("status_page_configured"), bool)
                and isinstance(support_commitments, dict)
                and isinstance(
                    support_commitments.get("signed_commitment_configured"), bool
                )
                and isinstance(
                    support_commitments.get("named_staffing_model_configured"), bool
                )
                and isinstance(
                    support_commitments.get(
                        "customer_incident_operations_configured"
                    ),
                    bool,
                )
                and isinstance(
                    support_commitments.get("legal_sla_terms_configured"), bool
                )
                and isinstance(checks, list)
                and len(checks) >= 8
                and isinstance(support_artifacts, list)
                and len(support_artifacts) >= 3
                and "secret" not in body_text
                and "password" not in body_text
            )
            if ok:
                return True, (
                    f"HTTP {response.status}, "
                    f"demo_support_ready={payload.get('demo_support_ready')} "
                    f"production_support_ready={payload.get('production_support_ready')}"
                )
            return False, f"HTTP {response.status}, invalid support diagnostics contract"
    except HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except (OSError, URLError, json.JSONDecodeError) as exc:
        return False, str(exc)


def _fetch_cors_no_store_preflight(api_url: str, web_url: str) -> tuple[bool, str]:
    request = Request(
        f"{api_url.rstrip('/')}/demo/manufacturing/overview",
        method="OPTIONS",
        headers={
            "Origin": web_url.rstrip("/"),
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "cache-control",
        },
    )
    try:
        with urlopen(request, timeout=5) as response:
            allowed_headers = response.headers.get("access-control-allow-headers", "")
            allowed_origin = response.headers.get("access-control-allow-origin", "")
            ok = (
                200 <= response.status < 300
                and web_url.rstrip("/") == allowed_origin
                and "cache-control" in allowed_headers.casefold()
            )
            detail = f"HTTP {response.status}"
            if ok:
                return True, detail
            return False, f"{detail}, cache-control/origin not allowed"
    except HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except (OSError, URLError) as exc:
        return False, str(exc)


def _demo_cors_origins(web_url: str) -> tuple[str, ...]:
    normalized = web_url.rstrip("/")
    origins = [normalized]
    parsed = urlsplit(normalized)
    if parsed.scheme in {"http", "https"} and parsed.hostname in {"localhost", "127.0.0.1"}:
        for host in ("localhost", "127.0.0.1"):
            next_start_origin = urlunsplit((parsed.scheme, f"{host}:3100", "", "", ""))
            if next_start_origin not in origins:
                origins.append(next_start_origin)
    return tuple(origins)


def _cors_check_name(origin: str, primary_web_url: str) -> str:
    if origin == primary_web_url.rstrip("/"):
        return "live.api_cors_no_store_preflight"
    parsed = urlsplit(origin)
    host = parsed.hostname or "unknown"
    port = parsed.port or parsed.scheme
    return f"live.api_cors_no_store_preflight.{host}_{port}"


def run_live_checks(api_url: str | None, web_url: str | None) -> list[CheckResult]:
    checks: list[CheckResult] = []
    if api_url:
        normalized = api_url.rstrip("/")
        health_ok, health_detail = _fetch_json(f"{normalized}/health")
        ready_ok, ready_detail = _fetch_json(f"{normalized}/ready")
        snapshot_ok, snapshot_detail = _fetch_operations_snapshot(normalized)
        demo_readiness_ok, demo_readiness_detail = _fetch_demo_readiness_report(normalized)
        oidc_readiness_ok, oidc_readiness_detail = _fetch_oidc_readiness_report(normalized)
        oidc_onboarding_ok, oidc_onboarding_detail = _fetch_oidc_onboarding_report(normalized)
        deployment_readiness_ok, deployment_readiness_detail = (
            _fetch_deployment_readiness_report(normalized)
        )
        support_diagnostics_ok, support_diagnostics_detail = (
            _fetch_support_diagnostics_report(normalized)
        )
        checks.append(CheckResult("live.api_health", health_ok, health_detail))
        checks.append(CheckResult("live.api_ready", ready_ok, ready_detail))
        checks.append(CheckResult("live.api_operations_snapshot", snapshot_ok, snapshot_detail))
        checks.append(
            CheckResult("live.api_demo_readiness", demo_readiness_ok, demo_readiness_detail)
        )
        checks.append(
            CheckResult("live.api_oidc_readiness", oidc_readiness_ok, oidc_readiness_detail)
        )
        checks.append(
            CheckResult(
                "live.api_oidc_onboarding",
                oidc_onboarding_ok,
                oidc_onboarding_detail,
            )
        )
        checks.append(
            CheckResult(
                "live.api_deployment_readiness",
                deployment_readiness_ok,
                deployment_readiness_detail,
            )
        )
        checks.append(
            CheckResult(
                "live.api_support_diagnostics",
                support_diagnostics_ok,
                support_diagnostics_detail,
            )
        )
        if web_url:
            for origin in _demo_cors_origins(web_url):
                cors_ok, cors_detail = _fetch_cors_no_store_preflight(normalized, origin)
                checks.append(CheckResult(_cors_check_name(origin, web_url), cors_ok, cors_detail))
    if web_url:
        normalized = web_url.rstrip("/")
        web_ok, web_detail = _fetch_text(normalized)
        checks.append(CheckResult("live.web_home", web_ok, web_detail))
    return checks


def _print_results(results: list[CheckResult], *, json_output: bool) -> None:
    if json_output:
        print(
            json.dumps(
                [
                    {"name": result.name, "ok": result.ok, "detail": result.detail}
                    for result in results
                ],
                indent=2,
                sort_keys=True,
            )
        )
        return

    for result in results:
        status = "OK" if result.ok else "FAIL"
        print(f"[{status}] {result.name}: {result.detail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Limes Axis demo environment readiness.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="Repository root to inspect.",
    )
    parser.add_argument("--api-url", help="Optional running Axis API base URL.")
    parser.add_argument("--web-url", help="Optional running governance console base URL.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)

    results = run_static_checks(args.repo_root)
    results.extend(run_live_checks(args.api_url, args.web_url))
    _print_results(results, json_output=args.json)
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
