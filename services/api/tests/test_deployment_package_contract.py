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
    assert "infra/helm/limes-axis/templates/tests/smoke-test.yaml" in required_files
    assert "infra/helm/limes-axis/templates/NOTES.txt" in required_files


def test_deployment_package_declares_rollout_rehearsal_tooling() -> None:
    checker = load_check_module()

    assert (
        "services/api/scripts/rehearse_deployment_rollout.py"
        in checker.required_deployment_scripts()
    )
    assert (
        "services/api/scripts/rehearse_production_backup.py"
        in checker.required_deployment_scripts()
    )
    assert (
        "services/api/scripts/rehearse_production_restore.py"
        in checker.required_deployment_scripts()
    )
    assert (
        "services/api/scripts/rehearse_typedb_recovery.py"
        in checker.required_deployment_scripts()
    )
    assert (
        "services/api/scripts/rehearse_object_storage_recovery.py"
        in checker.required_deployment_scripts()
    )
    assert (
        "services/api/scripts/rehearse_temporal_recovery.py"
        in checker.required_deployment_scripts()
    )
    assert (
        "services/api/scripts/rehearse_secret_rotation.py"
        in checker.required_deployment_scripts()
    )
    assert (
        "services/api/scripts/rehearse_ha_restart.py"
        in checker.required_deployment_scripts()
    )
    assert "services/api/scripts/rehearse_load.py" in checker.required_deployment_scripts()
    assert "deployment-rollout-rehearsal-plan" in checker.required_make_targets()
    assert "deployment-rollout-rehearsal" in checker.required_make_targets()
    assert "deployment-backup-rehearsal-plan" in checker.required_make_targets()
    assert "deployment-backup-rehearsal" in checker.required_make_targets()
    assert "deployment-restore-rehearsal-plan" in checker.required_make_targets()
    assert "deployment-restore-rehearsal" in checker.required_make_targets()
    assert "deployment-typedb-recovery-rehearsal-plan" in checker.required_make_targets()
    assert "deployment-typedb-recovery-rehearsal" in checker.required_make_targets()
    assert "deployment-object-storage-recovery-rehearsal-plan" in checker.required_make_targets()
    assert "deployment-object-storage-recovery-rehearsal" in checker.required_make_targets()
    assert "deployment-temporal-recovery-rehearsal-plan" in checker.required_make_targets()
    assert "deployment-temporal-recovery-rehearsal" in checker.required_make_targets()
    assert "deployment-secret-rotation-rehearsal-plan" in checker.required_make_targets()
    assert "deployment-secret-rotation-rehearsal" in checker.required_make_targets()
    assert "deployment-ha-rehearsal-plan" in checker.required_make_targets()
    assert "deployment-ha-rehearsal" in checker.required_make_targets()
    assert "deployment-load-rehearsal-plan" in checker.required_make_targets()
    assert "deployment-load-rehearsal" in checker.required_make_targets()


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
    assert "AXIS_OIDC_CLIENT_ID" in required_terms
    assert "AXIS_OIDC_CLIENT_SECRET" in required_terms
    assert "AXIS_OIDC_AUTHORIZATION_URL" in required_terms
    assert "AXIS_OIDC_TOKEN_URL" in required_terms
    assert "AXIS_OIDC_SESSION_COOKIE_SIGNING_SECRET" in required_terms
    assert "AXIS_OIDC_SESSION_COOKIE_SECURE" in required_terms
    assert "AXIS_API_RATE_LIMIT_ENABLED" in required_terms
    assert "AXIS_API_RATE_LIMIT_REQUESTS" in required_terms
    assert "AXIS_API_RATE_LIMIT_WINDOW_SECONDS" in required_terms
    assert "AXIS_API_RATE_LIMIT_PATHS" in required_terms
    assert "AXIS_SUPPORT_MODEL_ENABLED" in required_terms
    assert "AXIS_SUPPORT_COVERAGE" in required_terms
    assert "AXIS_SUPPORT_S1_RESPONSE_MINUTES" in required_terms
    assert "AXIS_SUPPORT_ESCALATION_CHANNELS" in required_terms
    assert "AXIS_SUPPORT_CUSTOMER_RUNBOOK_URL" in required_terms
    assert "AXIS_SUPPORT_STATUS_PAGE_URL" in required_terms
    assert "AXIS_SUPPORT_INCIDENT_REVIEW_REQUIRED" in required_terms
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
    assert "certManager:" in required_terms
    assert "cert-manager.io/cluster-issuer" in required_terms
    assert "cert-manager.io/issuer-kind" in required_terms
    assert "cert-manager.io/issuer-group" in required_terms
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
    assert "strategy:" in required_terms
    assert "rollingUpdate" in required_terms
    assert "maxUnavailable" in required_terms
    assert "maxSurge" in required_terms
    assert "revisionHistoryLimit" in required_terms
    assert "terminationGracePeriodSeconds" in required_terms
    assert "lifecycle:" in required_terms
    assert "helm.sh/hook" in required_terms
    assert "hook-delete-policy" in required_terms
    assert "tests:" in required_terms
    assert "smoke:" in required_terms
    assert "busybox" in required_terms
    assert "wget" in required_terms


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


def test_deployment_package_rollout_controls_are_configurable_per_workload() -> None:
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
        "strategy:",
        "rollingUpdate:",
        "maxUnavailable:",
        "maxSurge:",
        "revisionHistoryLimit:",
        "terminationGracePeriodSeconds:",
        "lifecycle:",
    ):
        assert field in values
        assert field in api_template
        assert field in web_template

    assert "{{- with .Values.api.strategy }}" in api_template
    assert "revisionHistoryLimit: {{ .Values.api.revisionHistoryLimit }}" in api_template
    assert (
        "terminationGracePeriodSeconds: {{ .Values.api.terminationGracePeriodSeconds }}"
        in api_template
    )
    assert "{{- with .Values.api.lifecycle }}" in api_template
    assert "{{- with .Values.web.strategy }}" in web_template
    assert "revisionHistoryLimit: {{ .Values.web.revisionHistoryLimit }}" in web_template
    assert (
        "terminationGracePeriodSeconds: {{ .Values.web.terminationGracePeriodSeconds }}"
        in web_template
    )
    assert "{{- with .Values.web.lifecycle }}" in web_template


def test_deployment_package_helm_smoke_test_checks_api_and_web_services() -> None:
    values = (REPO_ROOT / "infra" / "helm" / "limes-axis" / "values.yaml").read_text(
        encoding="utf-8"
    )
    template = (
        REPO_ROOT
        / "infra"
        / "helm"
        / "limes-axis"
        / "templates"
        / "tests"
        / "smoke-test.yaml"
    ).read_text(encoding="utf-8")
    network_policy = (
        REPO_ROOT / "infra" / "helm" / "limes-axis" / "templates" / "networkpolicy.yaml"
    ).read_text(encoding="utf-8")

    for field in (
        "tests:",
        "smoke:",
        "enabled: true",
        "activeDeadlineSeconds:",
        "retryAttempts:",
        "requestTimeoutSeconds:",
        "podSecurityContext:",
        "securityContext:",
    ):
        assert field in values

    assert "{{- if .Values.tests.smoke.enabled -}}" in template
    assert "helm.sh/hook: test" in template
    assert "helm.sh/hook-delete-policy:" in template
    assert "image: {{ include \"limes-axis.smokeTestImage\" . | quote }}" in template
    assert "wget -q -O /dev/null" in template
    assert "{{ include \"limes-axis.fullname\" . }}-api" in template
    assert "{{ include \"limes-axis.fullname\" . }}-web" in template
    assert "/ready" in template
    assert "restartPolicy: Never" in template
    assert "{{- if .Values.tests.smoke.enabled }}" in network_policy
    assert "port: {{ .Values.api.service.port }}" in network_policy
    assert "port: {{ .Values.web.service.port }}" in network_policy


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


def test_deployment_package_cert_manager_ingress_shim_is_optional() -> None:
    values = (REPO_ROOT / "infra" / "helm" / "limes-axis" / "values.yaml").read_text(
        encoding="utf-8"
    )
    template = (
        REPO_ROOT / "infra" / "helm" / "limes-axis" / "templates" / "ingress.yaml"
    ).read_text(encoding="utf-8")

    assert "certManager:" in values
    assert "enabled: false" in values
    assert "issuerName:" in values
    assert "issuerKind: ClusterIssuer" in values
    assert "issuerGroup: cert-manager.io" in values
    assert "{{- if .Values.ingress.certManager.enabled }}" in template
    assert (
        "required \"ingress.certManager.issuerName is required when certManager is enabled\""
        in template
    )
    assert "cert-manager.io/cluster-issuer:" in template
    assert "cert-manager.io/issuer:" in template
    assert "cert-manager.io/issuer-kind:" in template
    assert "cert-manager.io/issuer-group:" in template


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
    assert "authorization-code" in required_terms
    assert "HTTP-only" in required_terms
    assert "rate limiting" in required_terms
    assert "IdP onboarding" in required_terms
    assert "/identity/oidc/onboarding" in required_terms
    assert "/identity/oidc/logout" in required_terms
    assert "/identity/session/logout" in required_terms
    assert "oidc_browser_sessions" in required_terms
    assert "server-side session revocation" in required_terms
    assert "AXIS_OIDC_CLIENT_ID" in required_terms
    assert "AXIS_OIDC_END_SESSION_URL" in required_terms
    assert "AXIS_OIDC_POST_LOGOUT_REDIRECT_URI" in required_terms
    assert "AXIS_OIDC_SESSION_COOKIE_SIGNING_SECRET" in required_terms
    assert "S3-compatible object storage" in required_terms
    assert "External Secrets Operator" in required_terms
    assert "cert-manager" in required_terms
    assert "HorizontalPodAutoscaler" in required_terms
    assert "PodDisruptionBudget" in required_terms
    assert "topologySpreadConstraints" in required_terms
    assert "RollingUpdate" in required_terms
    assert "terminationGracePeriodSeconds" in required_terms
    assert "deployment-rollout-rehearsal" in required_terms
    assert "kubectl rollout status" in required_terms
    assert "helm rollback" in required_terms
    assert "helm test" in required_terms
    assert "production backup rehearsal" in required_terms
    assert "production restore rehearsal" in required_terms
    assert "TypeDB recovery rehearsal" in required_terms
    assert "pg_dump" in required_terms
    assert "pg_restore --list" in required_terms
    assert "AXIS_POSTGRES_RESTORE_DSN" in required_terms
    assert "AXIS_TYPEDB_RESTORE_DATABASE" in required_terms
    assert "database export" in required_terms
    assert "database import" in required_terms
    assert "object storage recovery rehearsal" in required_terms
    assert "AXIS_CONNECTOR_EXPORT_S3_RESTORE_BUCKET" in required_terms
    assert "AXIS_OBJECT_STORAGE_RECOVERY_IMAGE" in required_terms
    assert "mc alias set" in required_terms
    assert "mc cp" in required_terms
    assert "mc cat" in required_terms
    assert "Temporal recovery rehearsal" in required_terms
    assert "AXIS_TEMPORAL_RECOVERY_IMAGE" in required_terms
    assert "AXIS_TEMPORAL_RECOVERY_WORKFLOW_ID" in required_terms
    assert "operator namespace describe" in required_terms
    assert "workflow show --output json" in required_terms
    assert "secret rotation rehearsal" in required_terms
    assert "AXIS_SECRET_ROTATION_IMAGE" in required_terms
    assert "limes-axis.io/secret-rotation-target=staged" in required_terms
    assert "secret-rotation.summary.json" in required_terms
    assert "secret-rotation.sha256" in required_terms
    assert "HA restart rehearsal" in required_terms
    assert "deployment-ha-rehearsal-plan" in required_terms
    assert "kubectl rollout restart" in required_terms
    assert "kubectl wait --for=condition=available" in required_terms
    assert "load rehearsal" in required_terms
    assert "deployment-load-rehearsal-plan" in required_terms
    assert "fortio" in required_terms
    assert "kubectl create job" in required_terms
    assert "kubectl logs" in required_terms
    assert "support-readiness" in required_terms
    assert "AXIS_SUPPORT_MODEL_ENABLED" in required_terms
    assert "AXIS_SUPPORT_ESCALATION_CHANNELS" in required_terms
    assert "/ready" in required_terms
    assert "not a production certification" in required_terms
