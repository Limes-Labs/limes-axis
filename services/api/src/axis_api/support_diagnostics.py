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


class SupportModelSummary(BaseModel):
    enabled: bool
    coverage: str = Field(min_length=1)
    severity_response_minutes: dict[str, int]
    escalation_channels: list[str]
    customer_runbook_configured: bool
    status_page_configured: bool
    incident_review_required: bool


class SupportCommitmentSummary(BaseModel):
    signed_commitment_configured: bool
    named_staffing_model_configured: bool
    customer_incident_operations_configured: bool
    legal_sla_terms_configured: bool


class SupportDiagnosticsPayload(BaseModel):
    deployment: SupportDeploymentSummary
    identity: SupportIdentitySummary
    support_model: SupportModelSummary
    support_commitments: SupportCommitmentSummary
    external_model_egress_enabled: bool
    live_connector_execution_enabled: bool
    audit_ledger_signing_configured: bool
    object_store_adapter: str = Field(min_length=1)
    object_store_worm_retention_enabled: bool
    object_store_retention_mode: str = Field(min_length=1)
    object_store_retention_days: int = Field(ge=0)


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


def _support_slo_targets(settings: Settings) -> dict[str, int]:
    return {
        "S1": max(0, settings.support_s1_response_minutes),
        "S2": max(0, settings.support_s2_response_minutes),
        "S3": max(0, settings.support_s3_response_minutes),
        "S4": max(0, settings.support_s4_response_minutes),
    }


def _https_configured(value: str | None) -> bool:
    return bool(value) and value.startswith("https://")


def _support_slo_targets_ready(targets: dict[str, int]) -> bool:
    ordered_targets = [targets["S1"], targets["S2"], targets["S3"], targets["S4"]]
    return all(target > 0 for target in ordered_targets) and ordered_targets == sorted(
        ordered_targets
    )


def _support_model_summary(settings: Settings) -> SupportModelSummary:
    escalation_channels = [
        channel.strip()
        for channel in settings.support_escalation_channels
        if channel.strip()
    ]
    return SupportModelSummary(
        enabled=settings.support_model_enabled,
        coverage=settings.support_coverage,
        severity_response_minutes=_support_slo_targets(settings),
        escalation_channels=escalation_channels,
        customer_runbook_configured=_https_configured(settings.support_customer_runbook_url),
        status_page_configured=_https_configured(settings.support_status_page_url),
        incident_review_required=settings.support_incident_review_required,
    )


def _support_commitment_summary(settings: Settings) -> SupportCommitmentSummary:
    return SupportCommitmentSummary(
        signed_commitment_configured=settings.support_signed_commitment_configured,
        named_staffing_model_configured=settings.support_named_staffing_model_configured,
        customer_incident_operations_configured=(
            settings.support_customer_incident_operations_configured
        ),
        legal_sla_terms_configured=settings.support_legal_sla_terms_configured,
    )


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
    support_model = _support_model_summary(settings)
    support_slo_targets_ready = _support_slo_targets_ready(
        support_model.severity_response_minutes
    )
    support_escalation_ready = len(support_model.escalation_channels) >= 2
    production_support_model_ready = all(
        (
            support_model.enabled,
            support_model.coverage == "24x7",
            support_slo_targets_ready,
            support_escalation_ready,
            support_model.customer_runbook_configured,
            support_model.status_page_configured,
            support_model.incident_review_required,
        )
    )
    support_commitments = _support_commitment_summary(settings)
    production_support_commitments_ready = all(
        (
            support_commitments.signed_commitment_configured,
            support_commitments.named_staffing_model_configured,
            support_commitments.customer_incident_operations_configured,
            support_commitments.legal_sla_terms_configured,
        )
    )
    production_support_ready = (
        deployment_readiness_report.production_ready
        and production_support_model_ready
        and production_support_commitments_ready
    )
    support_blockers = _dedupe(
        [
            *deployment_readiness_report.production_blockers,
            *([] if production_support_model_ready else ["production_support_model"]),
            *(
                []
                if production_support_commitments_ready
                else ["production_support_commitments"]
            ),
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
            production_support_model_ready,
            "Production support model is ready.",
            "Production support model, escalation paths and SLOs remain Enterprise work.",
        ),
        _support_check(
            "production_support_commitments",
            production_support_commitments_ready,
            (
                "Signed support commitments, staffing model, customer incident "
                "operations and SLA terms are configured."
            ),
            (
                "Signed support commitments, named staffing, customer incident "
                "operations and legal SLA terms remain Enterprise work."
            ),
        ),
        _support_check(
            "support_slo_targets",
            support_slo_targets_ready,
            "Severity response targets are configured and ordered from S1 to S4.",
            "Configure positive S1-S4 response targets ordered from shortest to longest.",
        ),
        _support_check(
            "support_escalation_channels",
            support_escalation_ready,
            "Escalation channel classes are configured without personal contact data.",
            "Configure at least two escalation channel classes for production support.",
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
            support_model=support_model,
            support_commitments=support_commitments,
            external_model_egress_enabled=settings.external_model_egress_enabled,
            live_connector_execution_enabled=live_connector_execution_enabled,
            audit_ledger_signing_configured=bool(settings.audit_ledger_signing_secret),
            object_store_adapter=deployment_readiness_report.capabilities.object_store_adapter,
            object_store_worm_retention_enabled=(
                deployment_readiness_report.capabilities.object_store_worm_retention_enabled
            ),
            object_store_retention_mode=(
                deployment_readiness_report.capabilities.object_store_retention_mode
            ),
            object_store_retention_days=(
                deployment_readiness_report.capabilities.object_store_retention_days
            ),
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
            "It is not a signed customer support contract, SLA or compliance attestation.",
        ],
    )
