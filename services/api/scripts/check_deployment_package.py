from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import NamedTuple


class CheckResult(NamedTuple):
    name: str
    ok: bool
    detail: str


def required_chart_files() -> tuple[str, ...]:
    return (
        "infra/helm/limes-axis/Chart.yaml",
        "infra/helm/limes-axis/values.yaml",
        "infra/helm/limes-axis/templates/_helpers.tpl",
        "infra/helm/limes-axis/templates/serviceaccount.yaml",
        "infra/helm/limes-axis/templates/configmap.yaml",
        "infra/helm/limes-axis/templates/secret-example.yaml",
        "infra/helm/limes-axis/templates/externalsecret.yaml",
        "infra/helm/limes-axis/templates/ingress.yaml",
        "infra/helm/limes-axis/templates/hpa.yaml",
        "infra/helm/limes-axis/templates/poddisruptionbudget.yaml",
        "infra/helm/limes-axis/templates/api-deployment.yaml",
        "infra/helm/limes-axis/templates/api-service.yaml",
        "infra/helm/limes-axis/templates/web-deployment.yaml",
        "infra/helm/limes-axis/templates/web-service.yaml",
        "infra/helm/limes-axis/templates/networkpolicy.yaml",
        "infra/helm/limes-axis/templates/tests/smoke-test.yaml",
        "infra/helm/limes-axis/templates/NOTES.txt",
    )


def required_deployment_scripts() -> tuple[str, ...]:
    return (
        "services/api/scripts/rehearse_deployment_rollout.py",
        "services/api/scripts/rehearse_production_backup.py",
        "services/api/scripts/rehearse_production_restore.py",
        "services/api/scripts/rehearse_typedb_recovery.py",
        "services/api/scripts/rehearse_object_storage_recovery.py",
        "services/api/scripts/rehearse_temporal_recovery.py",
        "services/api/scripts/rehearse_secret_rotation.py",
        "services/api/scripts/rehearse_ha_restart.py",
        "services/api/scripts/rehearse_load.py",
        "services/api/scripts/rehearse_tls_readiness.py",
    )


def required_make_targets() -> tuple[str, ...]:
    return (
        "deployment-check",
        "deployment-rollout-rehearsal-plan",
        "deployment-rollout-rehearsal",
        "deployment-ha-rehearsal-plan",
        "deployment-ha-rehearsal",
        "deployment-load-rehearsal-plan",
        "deployment-load-rehearsal",
        "deployment-tls-readiness-plan",
        "deployment-tls-readiness",
        "deployment-backup-rehearsal-plan",
        "deployment-backup-rehearsal",
        "deployment-restore-rehearsal-plan",
        "deployment-restore-rehearsal",
        "deployment-typedb-recovery-rehearsal-plan",
        "deployment-typedb-recovery-rehearsal",
        "deployment-object-storage-recovery-rehearsal-plan",
        "deployment-object-storage-recovery-rehearsal",
        "deployment-temporal-recovery-rehearsal-plan",
        "deployment-temporal-recovery-rehearsal",
        "deployment-secret-rotation-rehearsal-plan",
        "deployment-secret-rotation-rehearsal",
    )


def required_chart_terms() -> tuple[str, ...]:
    return (
        "AXIS_ENV",
        "AXIS_PUBLIC_BASE_URL",
        "AXIS_API_BASE_URL",
        "AXIS_CORS_ORIGINS",
        "AXIS_API_RATE_LIMIT_ENABLED",
        "AXIS_API_RATE_LIMIT_REQUESTS",
        "AXIS_API_RATE_LIMIT_WINDOW_SECONDS",
        "AXIS_API_RATE_LIMIT_PATHS",
        "AXIS_POSTGRES_DSN",
        "AXIS_TYPEDB_ADDRESS",
        "AXIS_TEMPORAL_ADDRESS",
        "AXIS_CONNECTOR_EXPORT_OBJECT_STORE_ROOT",
        "AXIS_OIDC_ISSUER",
        "AXIS_OIDC_AUDIENCE",
        "AXIS_OIDC_JWKS_URL",
        "AXIS_OIDC_AUTH_REQUIRED",
        "AXIS_OIDC_CLIENT_ID",
        "AXIS_OIDC_CLIENT_SECRET",
        "AXIS_OIDC_AUTHORIZATION_URL",
        "AXIS_OIDC_TOKEN_URL",
        "AXIS_OIDC_REDIRECT_URI",
        "AXIS_OIDC_END_SESSION_URL",
        "AXIS_OIDC_POST_LOGOUT_REDIRECT_URI",
        "AXIS_OIDC_SESSION_COOKIE_SIGNING_SECRET",
        "AXIS_OIDC_SESSION_COOKIE_TTL_SECONDS",
        "AXIS_OIDC_SESSION_COOKIE_SECURE",
        "AXIS_EXTERNAL_MODEL_EGRESS_ENABLED",
        "AXIS_CONNECTOR_SYNC_EXECUTION_ENABLED",
        "AXIS_AUDIT_LEDGER_SIGNING_SECRET",
        "AXIS_CONNECTOR_EXPORT_OBJECT_STORE_ADAPTER",
        "AXIS_CONNECTOR_EXPORT_S3_ENDPOINT",
        "AXIS_CONNECTOR_EXPORT_S3_BUCKET",
        "AXIS_CONNECTOR_EXPORT_S3_ACCESS_KEY",
        "AXIS_CONNECTOR_EXPORT_S3_SECRET_KEY",
        "AXIS_CONNECTOR_EXPORT_S3_OBJECT_LOCK_ENABLED",
        "AXIS_CONNECTOR_EXPORT_S3_RETENTION_DAYS",
        "AXIS_DR_RUNBOOK_CONFIGURED",
        "AXIS_DR_RPO_RTO_DEFINED",
        "AXIS_DR_REHEARSAL_EVIDENCE_CONFIGURED",
        "AXIS_DR_RESTORE_OWNER_CONFIGURED",
        "AXIS_DR_CUSTOMER_APPROVAL_CONFIGURED",
        "AXIS_DEPLOYMENT_NETWORK_POLICY_ENABLED",
        "AXIS_DEPLOYMENT_NETWORK_EGRESS_MODE",
        "AXIS_DEPLOYMENT_NETWORK_EGRESS_ALLOWLIST_CONFIGURED",
        "AXIS_DEPLOYMENT_TENANCY_MODE",
        "AXIS_DEPLOYMENT_CUSTOMER_ISOLATION_CONFIGURED",
        "AXIS_DEPLOYMENT_DATA_RESIDENCY_CONFIGURED",
        "AXIS_DEPLOYMENT_OPERATOR_ACCESS_RUNBOOK_CONFIGURED",
        "AXIS_DEPLOYMENT_BREAK_GLASS_APPROVAL_CONFIGURED",
        "AXIS_SUPPORT_MODEL_ENABLED",
        "AXIS_SUPPORT_COVERAGE",
        "AXIS_SUPPORT_S1_RESPONSE_MINUTES",
        "AXIS_SUPPORT_S2_RESPONSE_MINUTES",
        "AXIS_SUPPORT_S3_RESPONSE_MINUTES",
        "AXIS_SUPPORT_S4_RESPONSE_MINUTES",
        "AXIS_SUPPORT_ESCALATION_CHANNELS",
        "AXIS_SUPPORT_CUSTOMER_RUNBOOK_URL",
        "AXIS_SUPPORT_STATUS_PAGE_URL",
        "AXIS_SUPPORT_INCIDENT_REVIEW_REQUIRED",
        "AXIS_SUPPORT_SIGNED_COMMITMENT_CONFIGURED",
        "AXIS_SUPPORT_NAMED_STAFFING_MODEL_CONFIGURED",
        "AXIS_SUPPORT_CUSTOMER_INCIDENT_OPERATIONS_CONFIGURED",
        "AXIS_SUPPORT_LEGAL_SLA_TERMS_CONFIGURED",
        "NEXT_PUBLIC_AXIS_API_BASE_URL",
        "existingSecret",
        "REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE",
        "ExternalSecret",
        "external-secrets.io/v1",
        "secretStoreRef",
        "refreshPolicy",
        "refreshInterval",
        "creationPolicy",
        "deletionPolicy",
        "remoteRef",
        "networking.k8s.io/v1",
        "egressMode",
        "allowedEgressCidrs",
        "ipBlock",
        "ingressClassName",
        "tls:",
        "pathType",
        "certManager:",
        "cert-manager.io/cluster-issuer",
        "cert-manager.io/issuer-kind",
        "cert-manager.io/issuer-group",
        "autoscaling/v2",
        "HorizontalPodAutoscaler",
        "scaleTargetRef",
        "averageUtilization",
        "policy/v1",
        "PodDisruptionBudget",
        "minAvailable",
        "nodeSelector",
        "affinity",
        "tolerations",
        "topologySpreadConstraints",
        "strategy:",
        "rollingUpdate",
        "maxUnavailable",
        "maxSurge",
        "revisionHistoryLimit",
        "terminationGracePeriodSeconds",
        "lifecycle:",
        "helm.sh/hook",
        "hook-delete-policy",
        "tests:",
        "smoke:",
        "busybox",
        "wget",
    )


def required_docs_terms() -> tuple[str, ...]:
    return (
        "helm upgrade --install",
        "external Postgres",
        "OIDC",
        "authorization-code",
        "HTTP-only",
        "rate limiting",
        "IdP onboarding",
        "/identity/oidc/onboarding",
        "/identity/oidc/logout",
        "/identity/session/logout",
        "oidc_browser_sessions",
        "server-side session revocation",
        "AXIS_OIDC_CLIENT_ID",
        "AXIS_OIDC_END_SESSION_URL",
        "AXIS_OIDC_POST_LOGOUT_REDIRECT_URI",
        "AXIS_OIDC_SESSION_COOKIE_SIGNING_SECRET",
        "AXIS_OIDC_SESSION_COOKIE_TTL_SECONDS",
        "AXIS_OIDC_SESSION_COOKIE_SECURE=true",
        "oidc_secure_cookie_session",
        "bounded TTL",
        "HTTPS API/public/redirect URLs",
        "S3-compatible object storage",
        "External Secrets Operator",
        "cert-manager",
        "HorizontalPodAutoscaler",
        "PodDisruptionBudget",
        "topologySpreadConstraints",
        "RollingUpdate",
        "terminationGracePeriodSeconds",
        "deployment-rollout-rehearsal",
        "kubectl rollout status",
        "helm rollback",
        "helm test",
        "production backup rehearsal",
        "production restore rehearsal",
        "TypeDB recovery rehearsal",
        "pg_dump",
        "pg_restore --list",
        "AXIS_POSTGRES_RESTORE_DSN",
        "AXIS_TYPEDB_RESTORE_DATABASE",
        "database export",
        "database import",
        "object storage recovery rehearsal",
        "AXIS_CONNECTOR_EXPORT_S3_RESTORE_BUCKET",
        "AXIS_OBJECT_STORAGE_RECOVERY_IMAGE",
        "mc alias set",
        "mc cp",
        "mc cat",
        "Temporal recovery rehearsal",
        "AXIS_TEMPORAL_RECOVERY_IMAGE",
        "AXIS_TEMPORAL_RECOVERY_WORKFLOW_ID",
        "operator namespace describe",
        "workflow show --output json",
        "secret rotation rehearsal",
        "AXIS_SECRET_ROTATION_IMAGE",
        "limes-axis.io/secret-rotation-target=staged",
        "secret-rotation.summary.json",
        "secret-rotation.sha256",
        "HA restart rehearsal",
        "deployment-ha-rehearsal-plan",
        "kubectl rollout restart",
        "kubectl wait --for=condition=available",
        "load rehearsal",
        "deployment-load-rehearsal-plan",
        "fortio",
        "kubectl create job",
        "kubectl logs",
        "TLS readiness rehearsal",
        "deployment-tls-readiness-plan",
        "openssl s_client",
        "dig +short",
        "kubectl wait --for=condition=Ready",
        "support-readiness",
        "AXIS_SUPPORT_MODEL_ENABLED",
        "AXIS_SUPPORT_ESCALATION_CHANNELS",
        "AXIS_SUPPORT_SIGNED_COMMITMENT_CONFIGURED",
        "AXIS_SUPPORT_NAMED_STAFFING_MODEL_CONFIGURED",
        "AXIS_SUPPORT_CUSTOMER_INCIDENT_OPERATIONS_CONFIGURED",
        "AXIS_SUPPORT_LEGAL_SLA_TERMS_CONFIGURED",
        "production_support_commitments",
        "production_dr_procedures",
        "AXIS_DR_RUNBOOK_CONFIGURED",
        "AXIS_DR_RPO_RTO_DEFINED",
        "AXIS_DR_REHEARSAL_EVIDENCE_CONFIGURED",
        "AXIS_DR_RESTORE_OWNER_CONFIGURED",
        "AXIS_DR_CUSTOMER_APPROVAL_CONFIGURED",
        "network_egress_restricted",
        "AXIS_DEPLOYMENT_NETWORK_EGRESS_MODE",
        "AXIS_DEPLOYMENT_NETWORK_EGRESS_ALLOWLIST_CONFIGURED",
        "restricted mode",
        "offline mode",
        "deployment_tenancy_profile",
        "AXIS_DEPLOYMENT_TENANCY_MODE",
        "single_tenant_managed",
        "private_cloud",
        "on_prem",
        "AXIS_DEPLOYMENT_CUSTOMER_ISOLATION_CONFIGURED",
        "AXIS_DEPLOYMENT_DATA_RESIDENCY_CONFIGURED",
        "AXIS_DEPLOYMENT_OPERATOR_ACCESS_RUNBOOK_CONFIGURED",
        "AXIS_DEPLOYMENT_BREAK_GLASS_APPROVAL_CONFIGURED",
        "/ready",
        "not a production certification",
    )


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _make_targets(makefile_text: str) -> set[str]:
    return {
        match.group(1)
        for match in re.finditer(r"^([A-Za-z0-9_.-]+):(?:\s|$)", makefile_text, re.MULTILINE)
    }


def _missing_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    normalized = text.casefold()
    return [term for term in terms if term.casefold() not in normalized]


def _chart_text(repo_root: Path) -> str:
    parts: list[str] = []
    for relative in required_chart_files():
        path = repo_root / relative
        if path.exists():
            parts.append(_read_text(path))
    return "\n".join(parts)


def check_make_target(repo_root: Path) -> list[CheckResult]:
    makefile = repo_root / "Makefile"
    if not makefile.exists():
        return [CheckResult("deployment.make_target", False, "Makefile is missing.")]

    targets = _make_targets(_read_text(makefile))
    missing = [target for target in required_make_targets() if target not in targets]
    return [
        CheckResult(
            "deployment.make_target",
            not missing,
            "deployment Makefile targets are present"
            if not missing
            else f"Makefile is missing deployment targets: {', '.join(missing)}",
        )
    ]


def check_deployment_scripts(repo_root: Path) -> list[CheckResult]:
    missing = [
        relative
        for relative in required_deployment_scripts()
        if not (repo_root / relative).exists()
    ]
    return [
        CheckResult(
            "deployment.scripts",
            not missing,
            "deployment rehearsal scripts are present"
            if not missing
            else f"missing: {', '.join(missing)}",
        )
    ]


def check_chart_files(repo_root: Path) -> list[CheckResult]:
    missing = [
        relative for relative in required_chart_files() if not (repo_root / relative).exists()
    ]
    return [
        CheckResult(
            "deployment.chart_files",
            not missing,
            "required Helm chart files are present"
            if not missing
            else f"missing: {', '.join(missing)}",
        )
    ]


def check_chart_metadata(repo_root: Path) -> list[CheckResult]:
    chart = repo_root / "infra" / "helm" / "limes-axis" / "Chart.yaml"
    if not chart.exists():
        return [CheckResult("deployment.chart_metadata", False, "Chart.yaml is missing.")]

    text = _read_text(chart)
    required = ("apiVersion: v2", "name: limes-axis", "type: application")
    missing = [term for term in required if term not in text]
    return [
        CheckResult(
            "deployment.chart_metadata",
            not missing,
            "Chart.yaml declares an application chart"
            if not missing
            else f"missing metadata: {', '.join(missing)}",
        )
    ]


def check_chart_terms(repo_root: Path) -> list[CheckResult]:
    text = _chart_text(repo_root)
    missing = _missing_terms(text, required_chart_terms())
    return [
        CheckResult(
            "deployment.chart_terms",
            not missing,
            "Helm chart covers Axis runtime configuration and externalized secrets"
            if not missing
            else f"missing terms: {', '.join(missing)}",
        )
    ]


def check_secret_boundaries(repo_root: Path) -> list[CheckResult]:
    values = repo_root / "infra" / "helm" / "limes-axis" / "values.yaml"
    if not values.exists():
        return [CheckResult("deployment.secret_boundaries", False, "values.yaml is missing.")]

    text = _read_text(values)
    forbidden_defaults = (
        "axis-axis",
        "postgresql+psycopg://axis:axis@",
        "MINIO_ROOT_PASSWORD",
        "KEYCLOAK_ADMIN_PASSWORD",
    )
    forbidden = [term for term in forbidden_defaults if term in text]
    has_secret_reference = "existingSecret:" in text and "createExample:" in text
    ok = not forbidden and has_secret_reference
    if forbidden:
        detail = f"values.yaml contains demo secret defaults: {', '.join(forbidden)}"
    elif not has_secret_reference:
        detail = "values.yaml must use existingSecret/createExample boundaries"
    else:
        detail = "runtime secrets are externalized from default values"
    return [CheckResult("deployment.secret_boundaries", ok, detail)]


def check_deployment_docs(repo_root: Path) -> list[CheckResult]:
    docs = repo_root / "docs" / "deployment.md"
    if not docs.exists():
        return [CheckResult("deployment.docs", False, "docs/deployment.md is missing.")]

    text = _read_text(docs)
    for runbook in (
        repo_root / "docs" / "deployment-rollout-rehearsal.md",
        repo_root / "docs" / "deployment-ha-rehearsal.md",
        repo_root / "docs" / "deployment-load-rehearsal.md",
        repo_root / "docs" / "deployment-tls-readiness.md",
    ):
        if runbook.exists():
            text = f"{text}\n{_read_text(runbook)}"
    missing = _missing_terms(text, required_docs_terms())
    return [
        CheckResult(
            "deployment.docs",
            not missing,
            "deployment guide is public-safe and explicit"
            if not missing
            else f"missing terms: {', '.join(missing)}",
        )
    ]


def check_public_doc_links(repo_root: Path) -> list[CheckResult]:
    checks: list[CheckResult] = []
    expectations = (
        (
            "deployment.readme_link",
            repo_root / "README.md",
            "docs/deployment.md",
        ),
        (
            "deployment.plan_tracking",
            repo_root / "plan.md",
            "Add initial Helm charts and production deployment guide baseline",
        ),
        (
            "deployment.demo_readiness_link",
            repo_root / "docs" / "demo-readiness.md",
            "deployment-check",
        ),
        (
            "deployment.rollout_rehearsal_link",
            repo_root / "docs" / "deployment.md",
            "deployment-rollout-rehearsal.md",
        ),
        (
            "deployment.load_rehearsal_link",
            repo_root / "docs" / "deployment.md",
            "deployment-load-rehearsal.md",
        ),
        (
            "deployment.tls_readiness_link",
            repo_root / "docs" / "deployment.md",
            "deployment-tls-readiness.md",
        ),
        (
            "deployment.threat_model_link",
            repo_root / "docs" / "threat-model.md",
            "infra/helm/limes-axis",
        ),
    )

    for name, path, expected in expectations:
        if not path.exists():
            checks.append(CheckResult(name, False, f"{path.name} is missing."))
            continue
        text = _read_text(path)
        checks.append(
            CheckResult(
                name,
                expected.casefold() in text.casefold(),
                f"{path.name} references {expected}"
                if expected.casefold() in text.casefold()
                else f"{path.name} does not reference {expected}",
            )
        )
    return checks


def run_static_checks(repo_root: Path) -> list[CheckResult]:
    repo_root = repo_root.resolve()
    checks: list[CheckResult] = []
    checks.extend(check_make_target(repo_root))
    checks.extend(check_deployment_scripts(repo_root))
    checks.extend(check_chart_files(repo_root))
    checks.extend(check_chart_metadata(repo_root))
    checks.extend(check_chart_terms(repo_root))
    checks.extend(check_secret_boundaries(repo_root))
    checks.extend(check_deployment_docs(repo_root))
    checks.extend(check_public_doc_links(repo_root))
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
    parser = argparse.ArgumentParser(description="Check Limes Axis deployment package.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="Repository root to inspect.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)

    results = run_static_checks(args.repo_root)
    _print_results(results, json_output=args.json)
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
