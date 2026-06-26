from pydantic import BaseModel, Field

from axis_api.audit import AuditEventCreate
from axis_api.connector_credential_leases import (
    ConnectorCredentialLeaseQuery,
    ManufacturingConnectorCredentialLeaseRegistry,
    build_connector_credential_lease_registry,
)
from axis_api.connector_egress_policies import (
    ConnectorEgressPolicyQuery,
    ManufacturingConnectorEgressPolicyRegistry,
    build_connector_egress_policy_registry,
)
from axis_api.connector_runs import (
    ConnectorSyncCheckpointClaimQuery,
    ConnectorSyncCheckpointQuery,
    ManufacturingConnectorSyncCheckpointRegistry,
    build_connector_sync_checkpoint_claim_registry,
    build_connector_sync_checkpoint_registry,
)
from axis_api.demo import OverviewMetric, OverviewStatus
from axis_api.persistence import AxisPersistenceRepository

READ_AUDIT_EVENT_TYPE = "connector.evidence_invariants_read"


class ConnectorEvidenceInvariantQuery(BaseModel):
    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    connector_id: str | None = Field(default=None, min_length=1)
    limit: int = Field(default=100, ge=1, le=200)


class ConnectorEvidenceInvariantItem(BaseModel):
    evidence_type: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    parent_id: str | None = None
    audit_event_id: str | None = None
    reason: str = Field(min_length=1)
    detail: str = Field(min_length=1)


class ManufacturingConnectorEvidenceInvariantReport(BaseModel):
    tenant_id: str = Field(min_length=1)
    plant_name: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    registry_status: OverviewStatus
    metrics: list[OverviewMetric] = Field(default_factory=list)
    invariant_counts: dict[str, int] = Field(default_factory=dict)
    invariants: list[ConnectorEvidenceInvariantItem] = Field(default_factory=list)
    report_notes: list[str] = Field(default_factory=list)


def build_connector_evidence_invariant_report(
    repository: AxisPersistenceRepository,
    query: ConnectorEvidenceInvariantQuery,
) -> ManufacturingConnectorEvidenceInvariantReport:
    checkpoints = build_connector_sync_checkpoint_registry(
        repository,
        ConnectorSyncCheckpointQuery(
            tenant_id=query.tenant_id,
            connector_id=query.connector_id,
            limit=query.limit,
        ),
    )
    claims = build_connector_sync_checkpoint_claim_registry(
        repository,
        ConnectorSyncCheckpointClaimQuery(
            tenant_id=query.tenant_id,
            connector_id=query.connector_id,
            limit=query.limit,
        ),
    )
    leases = build_connector_credential_lease_registry(
        repository,
        ConnectorCredentialLeaseQuery(
            tenant_id=query.tenant_id,
            connector_id=query.connector_id,
            limit=query.limit,
        ),
    )
    policies = build_connector_egress_policy_registry(
        repository,
        ConnectorEgressPolicyQuery(
            tenant_id=query.tenant_id,
            connector_id=query.connector_id,
            limit=query.limit,
        ),
    )
    invariants = (
        [
            ConnectorEvidenceInvariantItem(
                evidence_type="checkpoint",
                subject_id=invariant.checkpoint_id,
                parent_id=_checkpoint_parent_id(checkpoints, invariant.checkpoint_id),
                audit_event_id=invariant.audit_event_id,
                reason=invariant.reason,
                detail=invariant.detail,
            )
            for invariant in checkpoints.evidence_invariants
        ]
        + [
            ConnectorEvidenceInvariantItem(
                evidence_type="checkpoint_claim",
                subject_id=invariant.claim_id,
                parent_id=invariant.checkpoint_id,
                audit_event_id=invariant.audit_event_id,
                reason=invariant.reason,
                detail=invariant.detail,
            )
            for invariant in claims.claim_evidence_invariants
        ]
        + [
            ConnectorEvidenceInvariantItem(
                evidence_type="credential_lease",
                subject_id=invariant.lease_id,
                parent_id=_lease_parent_id(leases, invariant.lease_id),
                audit_event_id=invariant.audit_event_id,
                reason=invariant.reason,
                detail=invariant.detail,
            )
            for invariant in leases.lease_evidence_invariants
        ]
        + [
            ConnectorEvidenceInvariantItem(
                evidence_type="egress_policy",
                subject_id=invariant.policy_id,
                parent_id=_policy_parent_id(policies, invariant.policy_id),
                audit_event_id=invariant.audit_event_id,
                reason=invariant.reason,
                detail=invariant.detail,
            )
            for invariant in policies.policy_evidence_invariants
        ]
    )
    counts = {
        "checkpoint": len(checkpoints.evidence_invariants),
        "checkpoint_claim": len(claims.claim_evidence_invariants),
        "credential_lease": len(leases.lease_evidence_invariants),
        "egress_policy": len(policies.policy_evidence_invariants),
    }
    return ManufacturingConnectorEvidenceInvariantReport(
        tenant_id=query.tenant_id,
        plant_name="Ravenna Works",
        scenario="Plant Operations Cockpit",
        registry_status=OverviewStatus.WATCH if invariants else OverviewStatus.READY,
        metrics=[
            OverviewMetric(
                label="Evidence Invariants",
                value=str(len(invariants)),
                detail=(
                    "Public-safe connector evidence issues across checkpoints, "
                    "claims, leases and policies"
                ),
                status=OverviewStatus.WATCH if invariants else OverviewStatus.READY,
            ),
            OverviewMetric(
                label="Evidence Surfaces",
                value=str(sum(1 for count in counts.values() if count > 0)),
                detail="Connector evidence surfaces with at least one invariant",
                status=OverviewStatus.WATCH if invariants else OverviewStatus.READY,
            ),
        ],
        invariant_counts=counts,
        invariants=invariants,
        report_notes=[
            "Aggregated report composes persisted connector evidence registries.",
            "Report reads are audit-backed and exclude secret refs, DSNs and endpoint refs.",
        ],
    )


def read_connector_evidence_invariant_report(
    repository: AxisPersistenceRepository,
    query: ConnectorEvidenceInvariantQuery,
    *,
    actor_id: str,
) -> ManufacturingConnectorEvidenceInvariantReport:
    report = build_connector_evidence_invariant_report(repository, query)
    repository.append_audit_event(
        AuditEventCreate(
            tenant_id=query.tenant_id,
            actor_id=actor_id,
            event_type=READ_AUDIT_EVENT_TYPE,
            payload={
                "connector_id": query.connector_id,
                "limit": query.limit,
                "returned_invariant_count": len(report.invariants),
                "invariant_counts": report.invariant_counts,
                "subject_ids": [invariant.subject_id for invariant in report.invariants],
            },
        )
    )
    return report


def _checkpoint_parent_id(
    report: ManufacturingConnectorSyncCheckpointRegistry,
    checkpoint_id: str,
) -> str | None:
    checkpoint = next(
        (
            candidate
            for candidate in report.checkpoints
            if candidate.checkpoint_id == checkpoint_id
        ),
        None,
    )
    return checkpoint.run_id if checkpoint is not None else None


def _lease_parent_id(
    report: ManufacturingConnectorCredentialLeaseRegistry,
    lease_id: str,
) -> str | None:
    lease = next(
        (candidate for candidate in report.leases if candidate.lease_id == lease_id),
        None,
    )
    return lease.handle_id if lease is not None else None


def _policy_parent_id(
    report: ManufacturingConnectorEgressPolicyRegistry,
    policy_id: str,
) -> str | None:
    policy = next(
        (candidate for candidate in report.policies if candidate.policy_id == policy_id),
        None,
    )
    return policy.connection_profile_id if policy is not None else None
