from __future__ import annotations

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECK_SCRIPT = REPO_ROOT / "services" / "api" / "scripts" / "check_helm_profile_renders.py"
HELPERS_TEMPLATE = REPO_ROOT / "infra" / "helm" / "limes-axis" / "templates" / "_helpers.tpl"

RELEASE_LABELS = {
    "app.kubernetes.io/name": "limes-axis",
    "app.kubernetes.io/instance": "limes-axis",
}


def load_render_module():
    assert CHECK_SCRIPT.exists(), "Helm profile render checker is missing"
    spec = importlib.util.spec_from_file_location("check_helm_profile_renders", CHECK_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rendered_manifest(*, profile: str, tenancy_mode: str, egress_mode: str) -> str:
    return f"""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: limes-axis-api
  annotations:
    limes-axis.io/profile: {profile}
  labels:
    app.kubernetes.io/component: api
spec:
  template:
    metadata:
      annotations:
        limes-axis.io/profile: {profile}
    spec:
      containers:
        - name: api
          env:
            - name: AXIS_DEPLOYMENT_TENANCY_MODE
              value: {tenancy_mode}
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: limes-axis-config
data:
  AXIS_TENANT_ADMISSION_MODE: "registered_only"
  AXIS_DEPLOYMENT_TENANCY_MODE: "{tenancy_mode}"
  AXIS_DEPLOYMENT_NETWORK_EGRESS_MODE: "{egress_mode}"
  AXIS_EXTERNAL_MODEL_EGRESS_ENABLED: "false"
  AXIS_CONNECTOR_SYNC_EXECUTION_ENABLED: "false"
  AXIS_OIDC_AUTH_REQUIRED: "true"
  AXIS_OIDC_SESSION_COOKIE_SECURE: "true"
  AXIS_DEPLOYMENT_CUSTOMER_ISOLATION_CONFIGURED: "false"
  AXIS_DEPLOYMENT_DATA_RESIDENCY_CONFIGURED: "false"
  AXIS_DEPLOYMENT_OPERATOR_ACCESS_RUNBOOK_CONFIGURED: "false"
  AXIS_DEPLOYMENT_BREAK_GLASS_APPROVAL_CONFIGURED: "false"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: limes-axis-web
  annotations:
    limes-axis.io/profile: {profile}
  labels:
    app.kubernetes.io/component: web
---
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: limes-axis
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: limes-axis-api
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: limes-axis-api
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: limes-axis
spec:
  podSelector: {{}}
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector: {{}}
# rendered egressMode: {egress_mode}
"""


def local_only_values() -> dict:
    return {
        "networkPolicy": {
            "dnsPort": 53,
            "localOnly": {
                "dns": {
                    "mode": "cluster",
                    "namespace": "kube-system",
                    "podSelector": {"k8s-app": "kube-dns"},
                },
                "services": [
                    {
                        "name": "identity-validation",
                        "state": "local",
                        "podSelector": {"app.kubernetes.io/name": "keycloak"},
                        "ports": [{"protocol": "TCP", "port": 8080}],
                    },
                    {
                        "name": "operational-database",
                        "state": "local",
                        "ipBlock": {"cidr": "10.0.0.0/8"},
                        "ports": [{"protocol": "TCP", "port": 5432}],
                    },
                    {
                        "name": "workflow-engine",
                        "state": "local",
                        "namespace": "axis-workflow",
                        "podSelector": {"app.kubernetes.io/name": "temporal"},
                        "ports": [{"protocol": "TCP", "port": 7233}],
                    },
                    {
                        "name": "model-inference",
                        "state": "omitted",
                        "reason": "No compatible local inference runtime is qualified.",
                    },
                ],
            },
        }
    }


def dns_rule() -> dict:
    return {
        "to": [
            {
                "namespaceSelector": {
                    "matchLabels": {"kubernetes.io/metadata.name": "kube-system"}
                },
                "podSelector": {"matchLabels": {"k8s-app": "kube-dns"}},
            }
        ],
        "ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}],
    }


def declared_service_rules() -> list[dict]:
    return [
        {
            "to": [{"podSelector": {"matchLabels": {"app.kubernetes.io/name": "keycloak"}}}],
            "ports": [{"protocol": "TCP", "port": 8080}],
        },
        {
            "to": [{"ipBlock": {"cidr": "10.0.0.0/8"}}],
            "ports": [{"protocol": "TCP", "port": 5432}],
        },
        {
            "to": [
                {
                    "namespaceSelector": {
                        "matchLabels": {"kubernetes.io/metadata.name": "axis-workflow"}
                    },
                    "podSelector": {"matchLabels": {"app.kubernetes.io/name": "temporal"}},
                }
            ],
            "ports": [{"protocol": "TCP", "port": 7233}],
        },
    ]


def policy_with(rules: list[dict]) -> dict:
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "spec": {"podSelector": {"matchLabels": dict(RELEASE_LABELS)}, "egress": rules},
    }


def smoke_fixture_rule() -> dict:
    return {
        "to": [{"podSelector": {"matchLabels": dict(RELEASE_LABELS)}}],
        "ports": [{"protocol": "TCP", "port": 8000}, {"protocol": "TCP", "port": 3000}],
    }


def test_profile_render_checker_invokes_helm_template_for_every_profile(monkeypatch) -> None:
    checker = load_render_module()
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs):
        calls.append(command)
        profile_path = Path(command[-1])
        contract = checker.PROFILE_RENDER_CONTRACTS[str(profile_path.relative_to(REPO_ROOT))]
        return subprocess.CompletedProcess(
            command,
            0,
            rendered_manifest(
                profile=contract.profile,
                tenancy_mode=contract.tenancy_mode,
                egress_mode=contract.network_mode,
            ),
            "",
        )

    monkeypatch.setattr(checker.subprocess, "run", fake_run)

    results = checker.run_render_checks(REPO_ROOT, helm_binary="helm")

    assert [result.ok for result in results] == [True, True, True, True]
    assert len(calls) == 4
    for command in calls:
        assert command[:3] == ["helm", "template", "limes-axis"]
        assert str(REPO_ROOT / "infra" / "helm" / "limes-axis") in command
        assert "-f" in command
        assert command[-1].startswith(str(REPO_ROOT / "infra" / "helm" / "limes-axis" / "profiles"))


def test_profile_render_checker_rejects_missing_contract_terms(monkeypatch) -> None:
    checker = load_render_module()

    def fake_run(command: list[str], **kwargs):
        return subprocess.CompletedProcess(
            command,
            0,
            "kind: Deployment\nmetadata:\n  name: limes-axis-api\n",
            "",
        )

    monkeypatch.setattr(checker.subprocess, "run", fake_run)

    results = checker.run_render_checks(REPO_ROOT, helm_binary="helm")

    assert len(results) == 4
    assert all(not result.ok for result in results)
    assert all("rendered manifest missing required terms" in result.detail for result in results)


def test_profile_render_checker_rejects_rendered_local_secret_material(monkeypatch) -> None:
    checker = load_render_module()

    def fake_run(command: list[str], **kwargs):
        profile_path = Path(command[-1])
        contract = checker.PROFILE_RENDER_CONTRACTS[str(profile_path.relative_to(REPO_ROOT))]
        manifest = (
            rendered_manifest(
                profile=contract.profile,
                tenancy_mode=contract.tenancy_mode,
                egress_mode=contract.network_mode,
            )
            + """
---
apiVersion: v1
kind: Secret
metadata:
  name: limes-axis-runtime
stringData:
  AXIS_POSTGRES_DSN: REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE
"""
        )
        return subprocess.CompletedProcess(command, 0, manifest, "")

    monkeypatch.setattr(checker.subprocess, "run", fake_run)

    results = checker.run_render_checks(REPO_ROOT, helm_binary="helm")

    assert len(results) == 4
    assert all(not result.ok for result in results)
    assert all(
        "rendered manifest contains forbidden secret material" in result.detail
        for result in results
    )


def test_profile_render_checker_reports_missing_helm_binary(monkeypatch) -> None:
    checker = load_render_module()

    def fake_run(command: list[str], **kwargs):
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(checker.subprocess, "run", fake_run)

    results = checker.run_render_checks(REPO_ROOT, helm_binary="not-helm")

    assert len(results) == 4
    assert all(not result.ok for result in results)
    assert all("Helm binary not found" in result.detail for result in results)


def test_egress_checks_report_missing_helm_binary(monkeypatch) -> None:
    checker = load_render_module()

    def fake_run(command: list[str], **kwargs):
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(checker.subprocess, "run", fake_run)

    results = checker.run_egress_checks(REPO_ROOT, helm_binary="not-helm")

    assert [result.name for result in results] == [
        "deployment.local_only_egress",
        "deployment.smoke_fixture_egress",
    ]
    assert all(not result.ok for result in results)


def test_local_only_egress_accepts_a_complete_bounded_graph() -> None:
    checker = load_render_module()

    policy = policy_with([dns_rule(), *declared_service_rules()])

    assert checker.local_only_egress_problems(local_only_values(), policy) == []


def test_local_only_egress_flags_a_port_only_rule() -> None:
    checker = load_render_module()

    policy = policy_with(
        [dns_rule(), *declared_service_rules(), {"ports": [{"protocol": "TCP", "port": 443}]}]
    )

    problems = checker.local_only_egress_problems(local_only_values(), policy)

    assert any("port-only rule" in problem for problem in problems)


def test_local_only_egress_flags_an_all_address_cidr() -> None:
    checker = load_render_module()

    rules = [dns_rule(), *declared_service_rules()]
    rules.append(
        {
            "to": [{"ipBlock": {"cidr": "0.0.0.0/0"}}],
            "ports": [{"protocol": "TCP", "port": 443}],
        }
    )

    problems = checker.local_only_egress_problems(local_only_values(), policy_with(rules))

    assert any("all-address CIDR allow rule" in problem for problem in problems)


def test_local_only_egress_flags_a_missing_declared_service() -> None:
    checker = load_render_module()

    rules = [dns_rule(), *declared_service_rules()[:-1]]

    problems = checker.local_only_egress_problems(local_only_values(), policy_with(rules))

    assert any("workflow-engine" in problem for problem in problems)


def test_local_only_egress_flags_an_unrestricted_dns_rule() -> None:
    checker = load_render_module()

    unrestricted_dns = {
        "ports": [{"protocol": "UDP", "port": 53}, {"protocol": "TCP", "port": 53}]
    }
    rules = [unrestricted_dns, *declared_service_rules()]

    problems = checker.local_only_egress_problems(local_only_values(), policy_with(rules))

    assert any("DNS rule is unrestricted" in problem for problem in problems)


def test_smoke_fixture_only_adds_the_bounded_intra_release_rule() -> None:
    checker = load_render_module()

    disabled = policy_with([dns_rule(), *declared_service_rules()])
    enabled = policy_with([dns_rule(), *declared_service_rules(), smoke_fixture_rule()])

    assert checker.smoke_fixture_problems(enabled, disabled) == []


def test_smoke_fixture_flags_an_unbounded_added_rule() -> None:
    checker = load_render_module()

    disabled = policy_with([dns_rule(), *declared_service_rules()])
    unbounded = {
        "to": [{"namespaceSelector": {}}],
        "ports": [{"protocol": "TCP", "port": 8000}],
    }
    enabled = policy_with([dns_rule(), *declared_service_rules(), unbounded])

    problems = checker.smoke_fixture_problems(enabled, disabled)

    assert any("release's own pods" in problem for problem in problems)
    assert any("must not widen egress" in problem for problem in problems)


def test_smoke_fixture_flags_more_than_one_added_rule() -> None:
    checker = load_render_module()

    disabled = policy_with([dns_rule()])
    enabled = policy_with([dns_rule(), *declared_service_rules(), smoke_fixture_rule()])

    problems = checker.smoke_fixture_problems(enabled, disabled)

    assert any("expected only the bounded intra-release rule" in problem for problem in problems)


def test_smoke_fixture_flags_a_rule_that_disappears_when_enabled() -> None:
    checker = load_render_module()

    disabled = policy_with([dns_rule(), declared_service_rules()[0]])
    enabled = policy_with([dns_rule(), smoke_fixture_rule()])

    problems = checker.smoke_fixture_problems(enabled, disabled)

    assert any(
        "changed egress rules other than the intra-release rule" in problem
        for problem in problems
    )


def test_required_local_services_match_the_chart_helper() -> None:
    checker = load_render_module()

    helper = HELPERS_TEMPLATE.read_text(encoding="utf-8")

    for service in checker.REQUIRED_LOCAL_SERVICES:
        assert service in helper, f"{service} is missing from the local-only chart helper"


@pytest.mark.skipif(shutil.which("helm") is None, reason="helm binary is required")
def test_all_render_checks_pass_for_the_shipped_profiles() -> None:
    checker = load_render_module()

    failures = [
        f"{result.name}: {result.detail}"
        for result in checker.run_all_checks(REPO_ROOT)
        if not result.ok
    ]

    assert not failures, failures
