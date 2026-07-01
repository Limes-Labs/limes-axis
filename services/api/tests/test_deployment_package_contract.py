from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECK_SCRIPT = REPO_ROOT / "services" / "api" / "scripts" / "check_deployment_package.py"


def load_check_module():
    assert CHECK_SCRIPT.exists(), "deployment package checker is missing"
    spec = importlib.util.spec_from_file_location("check_deployment_package", CHECK_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_deployment_package_static_contract_passes() -> None:
    checker = load_check_module()

    results = checker.run_static_checks(REPO_ROOT)

    failures = [f"{result.name}: {result.detail}" for result in results if not result.ok]
    assert failures == []


def test_deployment_package_declares_critical_chart_files() -> None:
    checker = load_check_module()

    required_files = checker.required_chart_files()

    assert "infra/helm/limes-axis/Chart.yaml" in required_files
    assert "infra/helm/limes-axis/values.yaml" in required_files
    assert "infra/helm/limes-axis/templates/api-deployment.yaml" in required_files
    assert "infra/helm/limes-axis/templates/api-service.yaml" in required_files
    assert "infra/helm/limes-axis/templates/web-deployment.yaml" in required_files
    assert "infra/helm/limes-axis/templates/web-service.yaml" in required_files
    assert "infra/helm/limes-axis/templates/hpa.yaml" in required_files
    assert "infra/helm/limes-axis/templates/poddisruptionbudget.yaml" in required_files
    assert "infra/helm/limes-axis/templates/ingress.yaml" in required_files
    assert "infra/helm/limes-axis/templates/configmap.yaml" in required_files
    assert "infra/helm/limes-axis/templates/secret-example.yaml" in required_files
    assert "infra/helm/limes-axis/templates/externalsecret.yaml" in required_files
    assert "infra/helm/limes-axis/templates/networkpolicy.yaml" in required_files
    assert "infra/helm/limes-axis/templates/NOTES.txt" in required_files


def test_deployment_package_externalizes_state_and_secrets() -> None:
    checker = load_check_module()

    required_terms = checker.required_chart_terms()

    assert "AXIS_POSTGRES_DSN" in required_terms
    assert "AXIS_TYPEDB_ADDRESS" in required_terms
    assert "AXIS_TEMPORAL_ADDRESS" in required_terms
    assert "AXIS_CONNECTOR_EXPORT_OBJECT_STORE_ROOT" in required_terms
    assert "AXIS_CONNECTOR_EXPORT_OBJECT_STORE_ADAPTER" in required_terms
    assert "AXIS_CONNECTOR_EXPORT_S3_ENDPOINT" in required_terms
    assert "AXIS_CONNECTOR_EXPORT_S3_BUCKET" in required_terms
    assert "AXIS_CONNECTOR_EXPORT_S3_ACCESS_KEY" in required_terms
    assert "AXIS_CONNECTOR_EXPORT_S3_SECRET_KEY" in required_terms
    assert "AXIS_CONNECTOR_EXPORT_S3_OBJECT_LOCK_ENABLED" in required_terms
    assert "AXIS_CONNECTOR_EXPORT_S3_RETENTION_DAYS" in required_terms
    assert "AXIS_OIDC_ISSUER" in required_terms
    assert "existingSecret" in required_terms
    assert "REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE" in required_terms
    assert "ExternalSecret" in required_terms
    assert "external-secrets.io/v1" in required_terms
    assert "secretStoreRef" in required_terms
    assert "refreshPolicy" in required_terms
    assert "refreshInterval" in required_terms
    assert "creationPolicy" in required_terms
    assert "deletionPolicy" in required_terms
    assert "remoteRef" in required_terms
    assert "networking.k8s.io/v1" in required_terms
    assert "ingressClassName" in required_terms
    assert "tls:" in required_terms
    assert "pathType" in required_terms
    assert "autoscaling/v2" in required_terms
    assert "HorizontalPodAutoscaler" in required_terms
    assert "scaleTargetRef" in required_terms
    assert "averageUtilization" in required_terms
    assert "policy/v1" in required_terms
    assert "PodDisruptionBudget" in required_terms
    assert "minAvailable" in required_terms
    assert "nodeSelector" in required_terms
    assert "affinity" in required_terms
    assert "tolerations" in required_terms
    assert "topologySpreadConstraints" in required_terms


def test_deployment_package_ha_controls_are_optional_and_target_api_and_web() -> None:
    values = (REPO_ROOT / "infra" / "helm" / "limes-axis" / "values.yaml").read_text(
        encoding="utf-8"
    )
    hpa_template = (
        REPO_ROOT / "infra" / "helm" / "limes-axis" / "templates" / "hpa.yaml"
    ).read_text(encoding="utf-8")
    pdb_template = (
        REPO_ROOT
        / "infra"
        / "helm"
        / "limes-axis"
        / "templates"
        / "poddisruptionbudget.yaml"
    ).read_text(encoding="utf-8")

    assert "autoscaling:" in values
    assert "pdb:" in values
    assert "{{- if .Values.api.autoscaling.enabled -}}" in hpa_template
    assert "{{- if .Values.web.autoscaling.enabled -}}" in hpa_template
    assert "kind: HorizontalPodAutoscaler" in hpa_template
    assert "name: {{ include \"limes-axis.fullname\" . }}-api" in hpa_template
    assert "name: {{ include \"limes-axis.fullname\" . }}-web" in hpa_template
    assert "{{- if .Values.api.pdb.enabled -}}" in pdb_template
    assert "{{- if .Values.web.pdb.enabled -}}" in pdb_template
    assert "kind: PodDisruptionBudget" in pdb_template
    assert "app.kubernetes.io/component: api" in pdb_template
    assert "app.kubernetes.io/component: web" in pdb_template


def test_deployment_package_scheduling_controls_are_configurable_per_workload() -> None:
    values = (REPO_ROOT / "infra" / "helm" / "limes-axis" / "values.yaml").read_text(
        encoding="utf-8"
    )
    api_template = (
        REPO_ROOT / "infra" / "helm" / "limes-axis" / "templates" / "api-deployment.yaml"
    ).read_text(encoding="utf-8")
    web_template = (
        REPO_ROOT / "infra" / "helm" / "limes-axis" / "templates" / "web-deployment.yaml"
    ).read_text(encoding="utf-8")

    for field in (
        "nodeSelector:",
        "affinity:",
        "tolerations:",
        "topologySpreadConstraints:",
    ):
        assert field in values
        assert field in api_template
        assert field in web_template

    assert "{{- with .Values.api.nodeSelector }}" in api_template
    assert "{{- with .Values.api.affinity }}" in api_template
    assert "{{- with .Values.api.tolerations }}" in api_template
    assert "{{- with .Values.api.topologySpreadConstraints }}" in api_template
    assert "{{- with .Values.web.nodeSelector }}" in web_template
    assert "{{- with .Values.web.affinity }}" in web_template
    assert "{{- with .Values.web.tolerations }}" in web_template
    assert "{{- with .Values.web.topologySpreadConstraints }}" in web_template


def test_deployment_package_ingress_is_optional_and_routes_api_and_web() -> None:
    values = (REPO_ROOT / "infra" / "helm" / "limes-axis" / "values.yaml").read_text(
        encoding="utf-8"
    )
    template = (
        REPO_ROOT / "infra" / "helm" / "limes-axis" / "templates" / "ingress.yaml"
    ).read_text(encoding="utf-8")

    assert "ingress:" in values
    assert "enabled: false" in values
    assert "{{- if .Values.ingress.enabled -}}" in template
    assert "apiVersion: networking.k8s.io/v1" in template
    assert "ingressClassName:" in template
    assert "secretName:" in template
    assert "name: {{ include \"limes-axis.fullname\" $ }}-api" in template
    assert "name: {{ include \"limes-axis.fullname\" $ }}-web" in template


def test_deployment_package_external_secret_is_optional_and_targets_runtime_secret() -> None:
    values = (REPO_ROOT / "infra" / "helm" / "limes-axis" / "values.yaml").read_text(
        encoding="utf-8"
    )
    template = (
        REPO_ROOT / "infra" / "helm" / "limes-axis" / "templates" / "externalsecret.yaml"
    ).read_text(encoding="utf-8")

    assert "externalSecret:" in values
    assert "enabled: false" in values
    assert "{{- if .Values.secrets.externalSecret.enabled -}}" in template
    assert "name: {{ .Values.secrets.existingSecret | quote }}" in template
    assert "secretStoreRef:" in template
    assert "remoteRef:" in template


def test_deployment_docs_are_public_safe_and_do_not_claim_certification() -> None:
    checker = load_check_module()

    required_terms = checker.required_docs_terms()

    assert "helm upgrade --install" in required_terms
    assert "external Postgres" in required_terms
    assert "OIDC" in required_terms
    assert "S3-compatible object storage" in required_terms
    assert "External Secrets Operator" in required_terms
    assert "HorizontalPodAutoscaler" in required_terms
    assert "PodDisruptionBudget" in required_terms
    assert "topologySpreadConstraints" in required_terms
    assert "not a production certification" in required_terms
