from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import NamedTuple

import yaml


class ProfileRenderContract(NamedTuple):
    tenancy_mode: str
    network_mode: str
    profile: str


class RenderCheckResult(NamedTuple):
    name: str
    ok: bool
    detail: str


CHART_DIRECTORY = "infra/helm/limes-axis"
LOCAL_ONLY_PROFILE = "infra/helm/limes-axis/profiles/local-only.yaml"

PROFILE_RENDER_CONTRACTS: dict[str, ProfileRenderContract] = {
    "infra/helm/limes-axis/profiles/single-tenant-managed.yaml": ProfileRenderContract(
        tenancy_mode="single_tenant_managed",
        network_mode="restricted",
        profile="single-tenant-managed",
    ),
    "infra/helm/limes-axis/profiles/private-cloud.yaml": ProfileRenderContract(
        tenancy_mode="private_cloud",
        network_mode="restricted",
        profile="private-cloud",
    ),
    "infra/helm/limes-axis/profiles/on-prem-offline.yaml": ProfileRenderContract(
        tenancy_mode="on_prem",
        network_mode="offline",
        profile="on-prem-offline",
    ),
    LOCAL_ONLY_PROFILE: ProfileRenderContract(
        tenancy_mode="on_prem",
        network_mode="local_only",
        profile="local-only",
    ),
}

FORBIDDEN_RENDER_SECRET_TERMS = (
    "REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE",
)

# An allow rule covering every address would make the profile indistinguishable
# from an allow-all policy, so rendering it must fail the check.
ALL_ADDRESS_CIDRS = ("0.0.0.0/0", "::/0")

# Mirrors "limes-axis.requiredLocalOnlyServices" in templates/_helpers.tpl. The
# names follow issue #869 dependency ids so the rendered graph stays traceable
# to docs/runtime-dependencies.local-profile.json.
REQUIRED_LOCAL_SERVICES = (
    "identity-validation",
    "operational-database",
    "workflow-engine",
    "artifact-object-store",
    "model-inference",
)

SMOKE_DISABLED_ARGS = ("--set", "tests.smoke.enabled=false")


def _profile_render_terms(contract: ProfileRenderContract) -> tuple[str, ...]:
    return (
        "kind: Deployment",
        "app.kubernetes.io/component: api",
        "app.kubernetes.io/component: web",
        "kind: ExternalSecret",
        "external-secrets.io/v1",
        "kind: HorizontalPodAutoscaler",
        "kind: PodDisruptionBudget",
        "kind: NetworkPolicy",
        f"limes-axis.io/profile: {contract.profile}",
        f'AXIS_DEPLOYMENT_TENANCY_MODE: "{contract.tenancy_mode}"',
        f'AXIS_DEPLOYMENT_NETWORK_EGRESS_MODE: "{contract.network_mode}"',
        'AXIS_TENANT_ADMISSION_MODE: "registered_only"',
        'AXIS_DEPLOYMENT_CUSTOMER_ISOLATION_CONFIGURED: "false"',
        'AXIS_DEPLOYMENT_DATA_RESIDENCY_CONFIGURED: "false"',
        'AXIS_DEPLOYMENT_OPERATOR_ACCESS_RUNBOOK_CONFIGURED: "false"',
        'AXIS_DEPLOYMENT_BREAK_GLASS_APPROVAL_CONFIGURED: "false"',
        'AXIS_OIDC_AUTH_REQUIRED: "true"',
        'AXIS_OIDC_SESSION_COOKIE_SECURE: "true"',
        'AXIS_EXTERNAL_MODEL_EGRESS_ENABLED: "false"',
        'AXIS_CONNECTOR_SYNC_EXECUTION_ENABLED: "false"',
    )


def _missing_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    return [term for term in terms if term not in text]


def _forbidden_secret_terms(text: str) -> list[str]:
    normalized = f"\n{text.replace('\\r\\n', '\\n')}\n"
    forbidden = [term for term in FORBIDDEN_RENDER_SECRET_TERMS if term in text]
    if "\nkind: Secret\n" in normalized:
        forbidden.append("kind: Secret")
    return forbidden


def _helm_template(
    repo_root: Path,
    relative_profile: str,
    *,
    helm_binary: str,
    extra_args: tuple[str, ...] = (),
) -> tuple[bool, str, str]:
    """Render one profile. Returns (ok, stdout, error_detail)."""
    chart_dir = repo_root / CHART_DIRECTORY
    profile_path = repo_root / relative_profile
    command = [
        helm_binary,
        "template",
        "limes-axis",
        str(chart_dir),
        "-f",
        str(profile_path),
        *extra_args,
    ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
        )
    except FileNotFoundError:
        return False, "", f"Helm binary not found: {helm_binary}"

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "helm template failed"
        return False, "", detail

    return True, completed.stdout, ""


def _network_policy(rendered: str) -> dict | None:
    try:
        documents = list(yaml.safe_load_all(rendered))
    except yaml.YAMLError:
        return None
    for document in documents:
        if isinstance(document, dict) and document.get("kind") == "NetworkPolicy":
            return document
    return None


def _egress_rules(policy: dict) -> list[dict]:
    spec = policy.get("spec")
    if not isinstance(spec, dict):
        return []
    egress = spec.get("egress")
    if not isinstance(egress, list):
        return []
    return [rule for rule in egress if isinstance(rule, dict)]


def _local_only_values(repo_root: Path) -> dict:
    path = repo_root / LOCAL_ONLY_PROFILE
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _declared_local_destinations(values: dict) -> list[dict]:
    network_policy = values.get("networkPolicy") or {}
    local_only = network_policy.get("localOnly") or {}
    services = local_only.get("services") or []
    destinations: list[dict] = []
    for service in services:
        if (service.get("state") or "local") == "omitted":
            continue
        target: dict = {}
        if service.get("ipBlock"):
            target["ipBlock"] = {"cidr": service["ipBlock"]["cidr"]}
        else:
            if service.get("namespace"):
                target["namespaceSelector"] = {
                    "matchLabels": {"kubernetes.io/metadata.name": service["namespace"]}
                }
            if service.get("podSelector"):
                target["podSelector"] = {"matchLabels": service["podSelector"]}
        ports = [
            {"protocol": port.get("protocol", "TCP"), "port": port["port"]}
            for port in service.get("ports") or []
        ]
        destinations.append({"service": service["name"], "to": target, "ports": ports})
    return destinations


def _dns_port(values: dict) -> int:
    network_policy = values.get("networkPolicy") or {}
    port = network_policy.get("dnsPort", 53)
    return port if isinstance(port, int) else 53


def local_only_egress_problems(values: dict, policy: dict) -> list[str]:
    """Structural problems with a rendered local-only NetworkPolicy."""
    problems: list[str] = []
    rules = _egress_rules(policy)

    if not rules:
        return ["rendered local-only NetworkPolicy declares no egress rule"]

    # Acceptance criterion 1: no port-only rule and no all-address CIDR.
    for rule in rules:
        targets = rule.get("to")
        if not targets:
            problems.append(
                "rendered local-only egress contains a port-only rule without a destination"
            )
        for target in targets or []:
            if not isinstance(target, dict):
                continue
            cidr = (target.get("ipBlock") or {}).get("cidr")
            if cidr in ALL_ADDRESS_CIDRS:
                problems.append(
                    f"rendered local-only egress contains an all-address CIDR allow rule: {cidr}"
                )

    # Acceptance criterion 1: DNS must be scoped to the configured resolvers.
    dns_port = _dns_port(values)
    dns_rules = [
        rule
        for rule in rules
        if any(port.get("port") == dns_port for port in rule.get("ports") or [])
    ]
    if not dns_rules:
        problems.append("rendered local-only egress has no DNS rule for the configured dnsPort")
    for rule in dns_rules:
        if not rule.get("to"):
            problems.append("rendered local-only DNS rule is unrestricted")

    # Acceptance criterion 2: every declared local service is represented.
    for destination in _declared_local_destinations(values):
        if not _rule_covers(rules, destination):
            problems.append(
                "rendered local-only egress is missing a rule for declared local "
                f"service {destination['service']!r}"
            )
    return problems


def _rule_covers(rules: list[dict], destination: dict) -> bool:
    for rule in rules:
        if destination["to"] not in (rule.get("to") or []):
            continue
        rendered_ports = rule.get("ports") or []
        if all(port in rendered_ports for port in destination["ports"]):
            return True
    return False


def _canonical(rule: dict) -> str:
    return json.dumps(rule, sort_keys=True)


def smoke_fixture_problems(enabled_policy: dict, disabled_policy: dict) -> list[str]:
    """The smoke fixture must add exactly the bounded intra-release egress rule."""
    problems: list[str] = []
    enabled_rules = [_canonical(rule) for rule in _egress_rules(enabled_policy)]
    disabled_rules = [_canonical(rule) for rule in _egress_rules(disabled_policy)]

    removed = [rule for rule in disabled_rules if rule not in enabled_rules]
    if removed:
        problems.append(
            "disabling the smoke fixture changed egress rules other than the intra-release rule"
        )

    added = [rule for rule in enabled_rules if rule not in disabled_rules]
    if len(added) != 1:
        problems.append(
            "enabling the smoke fixture added "
            f"{len(added)} egress rules; expected only the bounded intra-release rule"
        )
        return problems

    added_rule = json.loads(added[0])
    targets = added_rule.get("to") or []
    release_labels = ((enabled_policy.get("spec") or {}).get("podSelector") or {}).get(
        "matchLabels"
    )
    rendered_labels = (targets[0].get("podSelector") or {}).get("matchLabels") if targets else None
    if len(targets) != 1 or rendered_labels != release_labels:
        problems.append(
            "the smoke fixture egress rule must target only the release's own pods"
        )
    if any("namespaceSelector" in target or "ipBlock" in target for target in targets):
        problems.append(
            "the smoke fixture egress rule must not widen egress to other namespaces or CIDRs"
        )
    return problems


def _render_profile(
    repo_root: Path,
    relative_profile: str,
    *,
    helm_binary: str,
) -> RenderCheckResult:
    contract = PROFILE_RENDER_CONTRACTS[relative_profile]
    ok, rendered, detail = _helm_template(
        repo_root, relative_profile, helm_binary=helm_binary
    )
    if not ok:
        return RenderCheckResult(
            f"deployment.profile_render.{contract.profile}",
            False,
            detail,
        )

    forbidden_secret_terms = _forbidden_secret_terms(rendered)
    if forbidden_secret_terms:
        return RenderCheckResult(
            f"deployment.profile_render.{contract.profile}",
            False,
            "rendered manifest contains forbidden secret material: "
            f"{', '.join(forbidden_secret_terms)}",
        )

    missing = _missing_terms(rendered, _profile_render_terms(contract))
    return RenderCheckResult(
        f"deployment.profile_render.{contract.profile}",
        not missing,
        "profile overlay renders the expected Kubernetes deployment contract"
        if not missing
        else f"rendered manifest missing required terms: {', '.join(missing)}",
    )


def run_render_checks(
    repo_root: Path,
    *,
    helm_binary: str = "helm",
) -> list[RenderCheckResult]:
    repo_root = repo_root.resolve()
    return [
        _render_profile(repo_root, relative_profile, helm_binary=helm_binary)
        for relative_profile in PROFILE_RENDER_CONTRACTS
    ]


def _local_only_egress_check(repo_root: Path, *, helm_binary: str) -> RenderCheckResult:
    name = "deployment.local_only_egress"
    ok, rendered, detail = _helm_template(
        repo_root, LOCAL_ONLY_PROFILE, helm_binary=helm_binary
    )
    if not ok:
        return RenderCheckResult(name, False, detail)

    policy = _network_policy(rendered)
    if policy is None:
        return RenderCheckResult(name, False, "rendered manifest has no NetworkPolicy")

    problems = local_only_egress_problems(_local_only_values(repo_root), policy)
    return RenderCheckResult(
        name,
        not problems,
        "local-only profile renders only scoped DNS and explicit local destinations"
        if not problems
        else "; ".join(problems),
    )


def _smoke_fixture_check(repo_root: Path, *, helm_binary: str) -> RenderCheckResult:
    name = "deployment.smoke_fixture_egress"
    ok, enabled_rendered, detail = _helm_template(
        repo_root, LOCAL_ONLY_PROFILE, helm_binary=helm_binary
    )
    if not ok:
        return RenderCheckResult(name, False, detail)
    ok, disabled_rendered, detail = _helm_template(
        repo_root,
        LOCAL_ONLY_PROFILE,
        helm_binary=helm_binary,
        extra_args=SMOKE_DISABLED_ARGS,
    )
    if not ok:
        return RenderCheckResult(name, False, detail)

    enabled_policy = _network_policy(enabled_rendered)
    disabled_policy = _network_policy(disabled_rendered)
    if enabled_policy is None or disabled_policy is None:
        return RenderCheckResult(name, False, "rendered manifest has no NetworkPolicy")

    problems = smoke_fixture_problems(enabled_policy, disabled_policy)
    # The declared local destinations must survive with the fixture disabled, so
    # the smoke hook is never the reason the profile looks complete.
    problems.extend(
        f"smoke-disabled render: {problem}"
        for problem in local_only_egress_problems(_local_only_values(repo_root), disabled_policy)
    )
    return RenderCheckResult(
        name,
        not problems,
        "the smoke fixture only adds the bounded intra-release egress rule"
        if not problems
        else "; ".join(problems),
    )


def run_egress_checks(
    repo_root: Path,
    *,
    helm_binary: str = "helm",
) -> list[RenderCheckResult]:
    repo_root = repo_root.resolve()
    return [
        _local_only_egress_check(repo_root, helm_binary=helm_binary),
        _smoke_fixture_check(repo_root, helm_binary=helm_binary),
    ]


def run_all_checks(
    repo_root: Path,
    *,
    helm_binary: str = "helm",
) -> list[RenderCheckResult]:
    return run_render_checks(repo_root, helm_binary=helm_binary) + run_egress_checks(
        repo_root, helm_binary=helm_binary
    )


def _print_results(results: list[RenderCheckResult], *, json_output: bool) -> None:
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
    parser = argparse.ArgumentParser(
        description="Render Helm deployment profiles and verify public-safe contracts."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="Repository root to inspect.",
    )
    parser.add_argument(
        "--helm-binary",
        default="helm",
        help="Helm binary to execute.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)

    results = run_all_checks(args.repo_root, helm_binary=args.helm_binary)
    _print_results(results, json_output=args.json)
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
