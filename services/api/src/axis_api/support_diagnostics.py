from __future__ import annotations

from pydantic import BaseModel, Field

from axis_api.config import Settings
from axis_api.deployment_readiness import DeploymentReadinessReport


class SupportDiagnosticsCheck(BaseModel):
    check_id: str = Field(min_length=1)
    status: str = Field(pattern="^(ready|action_required)$")
    detail: str = Field(min_length=1)


class SupportArtifact(BaseModel):
    label: str = Field(min_length=1)
    path: str = Field(min_length=1)


class SupportDeploymentSummary(BaseModel):
    profile: str = Field(min_length=1)
    demo_safe: bool
    production_ready: bool
    production_blockers: list[str]


class SupportIdentitySummary(BaseModel):
    readiness_status: str = Field(min_length=1)
    enterprise_sso_ready: bool
    oidc_auth_required: bool
    jwks_source: str = Field(min_length=1)
    jwks_url_configured: bool


class SupportDiagnosticsPayload(BaseModel):
    deployment: SupportDeploymentSummary
    identity: SupportIdentitySummary
    external_model_egress_enabled: bool
    live_connector_execution_enabled: bool
    audit_ledger_signing_configured: bool
    object_store_adapter: str = Field(min_length=1)


class SupportDiagnosticsReport(BaseModel):
    status: str = Field(pattern="^(ready|action_required)$")
    service: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    safe_to_share: bool
    demo_support_ready: bool
    production_support_ready: bool
    support_blockers: list[str]
    diagnostics: SupportDiagnosticsPayload
    checks: list[SupportDiagnosticsCheck]
    support_artifacts: list[SupportArtifact]
    redaction_policy: list[str]
    notes: list[str] = Field(default_factory=list)


def _support_check(
    check_id: str,
    ok: bool,
    ready_detail: str,
    action_detail: str,
) -> SupportDiagnosticsCheck:
    return SupportDiagnosticsCheck(
        check_id=check_id,
        status="ready" if ok else "action_required",
        detail=ready_detail if ok else action_detail,
    )


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        deduped.append(item)
        seen.add(item)
    return deduped


def build_support_diagnostics_report(
    settings: Settings,
    *,
    oidc_readiness_report: dict[str, object],
    deployment_readiness_report: DeploymentReadinessReport,
) -> SupportDiagnosticsReport:
    live_connector_execution_enabled = any(
        (
            settings.connector_sync_execution_enabled,
            settings.external_db_sync_execution_enabled,
            settings.external_db_live_query_preflight_enabled,
            settings.credential_lease_execution_enabled,
            settings.credential_lease_provider_adapters_enabled,
        )
    )
    demo_support_ready = (
        deployment_readiness_report.demo_safe
        and not settings.external_model_egress_enabled
        and not live_connector_execution_enabled
    )
    production_support_ready = False
    support_blockers = _dedupe(
        [
            *deployment_readiness_report.production_blockers,
            "production_support_model",
        ]
    )
    checks = [
        _support_check(
            "support_diagnostics_public_safe",
            True,
            "Support diagnostics omit bearer tokens, raw JWKS and credential material.",
            "Support diagnostics must not expose sensitive runtime material.",
        ),
        _support_check(
            "support_runbook_baseline",
            True,
            "Support operations baseline runbook is published in docs/support-operations.md.",
            "Support operations baseline runbook is missing.",
        ),
        _support_check(
            "demo_support_ready",
            demo_support_ready,
            "Local demo support diagnostics are ready for design-partner walkthroughs.",
            "Local demo support diagnostics need action before a walkthrough.",
        ),
        _support_check(
            "deployment_readiness_attached",
            True,
            "Deployment readiness posture is attached to the support bundle.",
            "Deployment readiness posture is missing from the support bundle.",
        ),
        _support_check(
            "production_support_model",
            production_support_ready,
            "Production support model is ready.",
            "Production support model, escalation paths and SLOs remain Enterprise work.",
        ),
    ]
    return SupportDiagnosticsReport(
        status="ready" if production_support_ready else "action_required",
        service="axis-api",
        environment=settings.environment,
        safe_to_share=True,
        demo_support_ready=demo_support_ready,
        production_support_ready=production_support_ready,
        support_blockers=support_blockers,
        diagnostics=SupportDiagnosticsPayload(
            deployment=SupportDeploymentSummary(
                profile=deployment_readiness_report.profile,
                demo_safe=deployment_readiness_report.demo_safe,
                production_ready=deployment_readiness_report.production_ready,
                production_blockers=deployment_readiness_report.production_blockers,
            ),
            identity=SupportIdentitySummary(
                readiness_status=str(oidc_readiness_report.get("status")),
                enterprise_sso_ready=bool(oidc_readiness_report.get("enterprise_sso_ready")),
                oidc_auth_required=bool(oidc_readiness_report.get("auth_required")),
                jwks_source=str(oidc_readiness_report.get("jwks_source")),
                jwks_url_configured=bool(oidc_readiness_report.get("jwks_url_configured")),
            ),
            external_model_egress_enabled=settings.external_model_egress_enabled,
            live_connector_execution_enabled=live_connector_execution_enabled,
            audit_ledger_signing_configured=bool(settings.audit_ledger_signing_secret),
            object_store_adapter=deployment_readiness_report.capabilities.object_store_adapter,
        ),
        checks=checks,
        support_artifacts=[
            SupportArtifact(label="Demo readiness runbook", path="docs/demo-readiness.md"),
            SupportArtifact(label="Deployment threat model", path="docs/threat-model.md"),
            SupportArtifact(label="Support operations runbook", path="docs/support-operations.md"),
        ],
        redaction_policy=[
            "bearer_tokens",
            "raw_jwks",
            "credential_material",
            "signing_material",
            "database_dsn",
        ],
        notes=[
            "This support bundle is intended for public-safe support triage and demos.",
            "It is not a production support contract, SLA or compliance attestation.",
        ],
    )
