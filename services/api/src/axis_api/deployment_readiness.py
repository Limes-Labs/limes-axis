from __future__ import annotations

from pydantic import BaseModel, Field

from axis_api.config import Settings
from axis_api.object_storage import build_object_store_readiness


class DeploymentReadinessCheck(BaseModel):
    check_id: str = Field(min_length=1)
    status: str = Field(pattern="^(ready|action_required)$")
    production_required: bool
    detail: str = Field(min_length=1)


class DeploymentReadinessCapabilities(BaseModel):
    external_model_egress_enabled: bool
    connector_sync_execution_enabled: bool
    external_db_sync_execution_enabled: bool
    external_db_live_query_preflight_enabled: bool
    credential_lease_execution_enabled: bool
    credential_lease_provider_adapters_enabled: bool
    audit_ledger_signing_configured: bool
    object_store_adapter: str = Field(min_length=1)
    object_store_bucket_configured: bool
    object_store_endpoint_configured: bool
    object_store_credentials_configured: bool
    object_store_secure_transport: bool
    object_store_worm_retention_enabled: bool
    object_store_retention_mode: str = Field(min_length=1)
    object_store_retention_days: int = Field(ge=0)
    object_store_legal_hold_enabled: bool


class DeploymentReadinessReport(BaseModel):
    status: str = Field(pattern="^(ready|action_required)$")
    environment: str = Field(min_length=1)
    profile: str = Field(min_length=1)
    production_ready: bool
    demo_safe: bool
    capabilities: DeploymentReadinessCapabilities
    production_blockers: list[str]
    checks: list[DeploymentReadinessCheck]
    notes: list[str] = Field(default_factory=list)


def _deployment_profile(environment: str) -> str:
    normalized = environment.strip().casefold()
    if normalized in {"development", "dev", "local", "test"}:
        return "local_demo"
    if normalized in {"production", "prod"}:
        return "production"
    return normalized or "unspecified"


def _check(
    check_id: str,
    ok: bool,
    ready_detail: str,
    action_detail: str,
    *,
    production_required: bool = True,
) -> DeploymentReadinessCheck:
    return DeploymentReadinessCheck(
        check_id=check_id,
        status="ready" if ok else "action_required",
        production_required=production_required,
        detail=ready_detail if ok else action_detail,
    )


def _public_object_store_missing_requirements(requirements: list[str]) -> str:
    public_terms: list[str] = []
    credentials_missing = False
    for requirement in requirements:
        if requirement in {"access key", "secret key"}:
            credentials_missing = True
            continue
        public_terms.append(requirement)
    if credentials_missing:
        public_terms.append("credentials")
    return ", ".join(public_terms)


def build_deployment_readiness_report(
    settings: Settings,
    *,
    oidc_readiness_report: dict[str, object],
) -> DeploymentReadinessReport:
    profile = _deployment_profile(settings.environment)
    live_connector_execution_enabled = any(
        (
            settings.connector_sync_execution_enabled,
            settings.external_db_sync_execution_enabled,
            settings.external_db_live_query_preflight_enabled,
            settings.credential_lease_execution_enabled,
            settings.credential_lease_provider_adapters_enabled,
        )
    )
    audit_signing_configured = bool(settings.audit_ledger_signing_secret)
    object_store_readiness = build_object_store_readiness(settings)
    public_object_store_missing_requirements = _public_object_store_missing_requirements(
        object_store_readiness.missing_requirements
    )

    capabilities = DeploymentReadinessCapabilities(
        external_model_egress_enabled=settings.external_model_egress_enabled,
        connector_sync_execution_enabled=settings.connector_sync_execution_enabled,
        external_db_sync_execution_enabled=settings.external_db_sync_execution_enabled,
        external_db_live_query_preflight_enabled=settings.external_db_live_query_preflight_enabled,
        credential_lease_execution_enabled=settings.credential_lease_execution_enabled,
        credential_lease_provider_adapters_enabled=settings.credential_lease_provider_adapters_enabled,
        audit_ledger_signing_configured=audit_signing_configured,
        object_store_adapter=object_store_readiness.adapter,
        object_store_bucket_configured=object_store_readiness.bucket_configured,
        object_store_endpoint_configured=object_store_readiness.endpoint_configured,
        object_store_credentials_configured=object_store_readiness.credentials_configured,
        object_store_secure_transport=object_store_readiness.secure_transport,
        object_store_worm_retention_enabled=object_store_readiness.worm_retention_enabled,
        object_store_retention_mode=object_store_readiness.retention_mode,
        object_store_retention_days=object_store_readiness.retention_days,
        object_store_legal_hold_enabled=object_store_readiness.legal_hold_enabled,
    )

    checks = [
        _check(
            "oidc_enterprise_sso",
            bool(oidc_readiness_report.get("enterprise_sso_ready")),
            "OIDC is configured for enterprise SSO evaluation.",
            (
                "OIDC is not enterprise-ready; require auth, HTTPS issuer, "
                "explicit JWKS and asymmetric algorithms."
            ),
        ),
        _check(
            "external_model_egress_disabled",
            not settings.external_model_egress_enabled,
            "External model egress is disabled by default.",
            (
                "External model egress is enabled; require tenant policy, "
                "audit and data-classification controls."
            ),
        ),
        _check(
            "live_connector_execution_disabled",
            not live_connector_execution_enabled,
            "Live connector execution flags are disabled by default.",
            (
                "One or more live connector execution flags are enabled; require "
                "provider policy bundles and support runbooks."
            ),
        ),
        _check(
            "audit_ledger_signing_configured",
            audit_signing_configured,
            "Audit ledger signing is configured.",
            "Audit ledger signing is not configured; evidence exports remain unsigned.",
        ),
        _check(
            "production_object_store_adapter",
            object_store_readiness.production_ready,
            (
                "S3-compatible object storage is configured with endpoint, bucket, "
                "credentials, secure transport and WORM retention."
            ),
            (
                "S3/MinIO WORM retention is not production-ready; missing "
                f"{public_object_store_missing_requirements}."
            ),
        ),
    ]
    production_blockers = [
        check.check_id
        for check in checks
        if check.production_required and check.status != "ready"
    ]
    production_ready = not production_blockers
    demo_safe = (
        profile == "local_demo"
        and not settings.external_model_egress_enabled
        and not live_connector_execution_enabled
    )
    return DeploymentReadinessReport(
        status="ready" if production_ready else "action_required",
        environment=settings.environment,
        profile=profile,
        production_ready=production_ready,
        demo_safe=demo_safe,
        capabilities=capabilities,
        production_blockers=production_blockers,
        checks=checks,
        notes=[
            "This report is a deployment posture gate, not a production certification.",
            (
                "Production readiness remains blocked until the listed "
                "production blockers are resolved."
            ),
        ],
    )
