import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from axis_api.audit import AuditEventCreate
from axis_api.audit_signing import (
    AuditLedgerSignatureProof,
    AuditLedgerSigner,
    canonical_ledger_signature_payload,
    unsigned_audit_ledger_signature,
)
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
from axis_api.models import AuditEvent
from axis_api.permissions import PermissionDecision, PermissionRequest, evaluate_permission
from axis_api.persistence import (
    ApprovalRecordCreate,
    AxisPersistenceRepository,
    ConnectorEvidenceSnapshotExportRequestCreate,
)

READ_AUDIT_EVENT_TYPE = "connector.evidence_invariants_read"
SNAPSHOT_AUDIT_EVENT_TYPE = "connector.evidence_invariants.snapshot_persisted"
SNAPSHOT_REQUIRED_SCOPE = "connectors:evidence:snapshot"
SNAPSHOT_EXPORT_AUDIT_EVENT_TYPE = "connector.evidence_invariant_snapshots_exported"
SNAPSHOT_EXPORT_REQUEST_AUDIT_EVENT_TYPE = "connector.evidence_snapshot_export.requested"
SNAPSHOT_EXPORT_REQUEST_REQUIRED_SCOPE = "connectors:evidence:snapshot:export:request"
SNAPSHOT_READ_AUDIT_EVENT_TYPE = "connector.evidence_invariant_snapshots_read"
SNAPSHOT_READ_REQUIRED_SCOPE = "connectors:evidence:snapshot:read"
REPORT_HASH_ALGORITHM = "sha256-canonical-json-v1"
SNAPSHOT_EXPORT_REQUEST_STATUS = "approval_required"
SNAPSHOT_EXPORT_REQUEST_EXPORT_STATUS = "not_exported"
SNAPSHOT_EXPORT_REQUEST_STORAGE_STATUS = "not_written"
SNAPSHOT_EXPORT_REQUEST_WORKFLOW_SIGNAL_STATUS = "pending_approval_decision"
SNAPSHOT_EXPORT_REQUEST_REDACTION_POLICY = "connector-snapshot-public-safe"


def _default_export_request_controls() -> list[str]:
    return [
        "approval_required",
        "workflow_signal_required",
        "idempotency_enforced",
        "public_safe_bundle_only",
    ]


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


class ConnectorEvidenceInvariantSnapshotRequest(BaseModel):
    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    snapshot_id: str = Field(
        min_length=1,
        max_length=180,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    )
    connector_id: str | None = Field(default=None, min_length=1)
    requested_by: str = Field(min_length=1, max_length=160)
    actor_scopes: list[str] = Field(default_factory=list)
    idempotency_key: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=240)
    limit: int = Field(default=100, ge=1, le=200)
    notes: list[str] = Field(default_factory=list)


class ConnectorEvidenceInvariantSnapshotRecord(BaseModel):
    tenant_id: str = Field(min_length=1)
    snapshot_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    connector_id: str | None = None
    requested_by: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    invariant_count: int = Field(ge=0)
    invariant_counts: dict[str, int] = Field(default_factory=dict)
    subject_ids: list[str] = Field(default_factory=list)
    report_digest_sha256: str = Field(min_length=64, max_length=64)
    report_hash_algorithm: str = Field(min_length=1)
    permission_decision: PermissionDecision
    audit_event_id: UUID | None = None
    audit_event_type: str = Field(min_length=1)
    idempotent_replay: bool = False
    notes: list[str] = Field(default_factory=list)


class ConnectorEvidenceInvariantSnapshotQuery(BaseModel):
    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    connector_id: str | None = Field(default=None, min_length=1)
    snapshot_id: str | None = Field(default=None, min_length=1)
    idempotency_key: str | None = Field(default=None, min_length=1)
    limit: int = Field(default=100, ge=1, le=200)


class ConnectorEvidenceInvariantSnapshotExportQuery(ConnectorEvidenceInvariantSnapshotQuery):
    export_reason: str = Field(default="connector-evidence-review", min_length=1, max_length=120)
    format: str = Field(default="json", pattern="^json$")


class ConnectorEvidenceInvariantSnapshotExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    export_request_id: str = Field(
        min_length=1,
        max_length=180,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    )
    idempotency_key: str = Field(min_length=1, max_length=200)
    requested_by: str = Field(min_length=1, max_length=160)
    actor_scopes: list[str] = Field(default_factory=list)
    owner_role: str = Field(min_length=1, max_length=160)
    risk_level: str = Field(min_length=1, max_length=40)
    approval_id: str = Field(min_length=1, max_length=160)
    workflow_id: str = Field(min_length=1, max_length=160)
    connector_id: str | None = Field(default=None, min_length=1)
    snapshot_id: str | None = Field(default=None, min_length=1)
    snapshot_idempotency_key: str | None = Field(default=None, min_length=1)
    export_reason: str = Field(default="connector-evidence-review", min_length=1, max_length=120)
    format: str = Field(default="json", pattern="^json$")
    limit: int = Field(default=100, ge=1, le=200)
    controls: list[str] = Field(default_factory=_default_export_request_controls)
    notes: list[str] = Field(default_factory=list)


class ConnectorEvidenceInvariantSnapshotExportRequestFilter(BaseModel):
    connector_id: str | None = None
    snapshot_id: str | None = None
    idempotency_key: str | None = None
    limit: int = Field(ge=1)


class ConnectorEvidenceInvariantSnapshotExportRequestRecord(BaseModel):
    tenant_id: str = Field(min_length=1)
    export_request_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    status: str = Field(min_length=1)
    export_status: str = Field(min_length=1)
    storage_status: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    owner_role: str = Field(min_length=1)
    risk_level: str = Field(min_length=1)
    approval_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    snapshot_filter: ConnectorEvidenceInvariantSnapshotExportRequestFilter
    export_reason: str = Field(min_length=1)
    format: str = Field(min_length=1)
    requested_snapshot_count: int = Field(ge=0)
    snapshot_checksum_sha256: str = Field(min_length=64, max_length=64)
    redaction_policy: str = Field(min_length=1)
    controls: list[str] = Field(default_factory=list)
    permission_decision: PermissionDecision
    workflow_signal_status: str = Field(min_length=1)
    audit_event_id: UUID | None = None
    audit_event_type: str = Field(min_length=1)
    notes: list[str] = Field(default_factory=list)
    created_at: datetime
    idempotent_replay: bool = False


class ConnectorEvidenceInvariantSnapshotHistory(BaseModel):
    tenant_id: str = Field(min_length=1)
    plant_name: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    history_status: OverviewStatus
    metrics: list[OverviewMetric] = Field(default_factory=list)
    snapshots: list[ConnectorEvidenceInvariantSnapshotRecord] = Field(default_factory=list)
    history_notes: list[str] = Field(default_factory=list)


class ConnectorEvidenceInvariantSnapshotExportManifest(BaseModel):
    export_id: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    record_count: int = Field(ge=0)
    format: str = Field(min_length=1)
    redaction_policy: str = Field(min_length=1)
    checksum_sha256: str = Field(min_length=64, max_length=64)
    integrity_chain_tip_sha256: str = Field(min_length=64, max_length=64)
    connector_id: str | None = None
    snapshot_id: str | None = None
    idempotency_key: str | None = None


class ConnectorEvidenceInvariantSnapshotIntegrityProof(BaseModel):
    algorithm: str = Field(min_length=1)
    verification_status: str = Field(min_length=1)
    record_count: int = Field(ge=0)
    chain_tip_sha256: str = Field(min_length=64, max_length=64)
    snapshot_hashes: list[str] = Field(default_factory=list)


class ConnectorEvidenceInvariantSnapshotExportBundle(BaseModel):
    tenant_id: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    format: str = Field(min_length=1)
    export_reason: str = Field(min_length=1)
    filters: ConnectorEvidenceInvariantSnapshotQuery
    manifest: ConnectorEvidenceInvariantSnapshotExportManifest
    integrity_proof: ConnectorEvidenceInvariantSnapshotIntegrityProof
    ledger_signature: AuditLedgerSignatureProof
    snapshots: list[ConnectorEvidenceInvariantSnapshotRecord] = Field(default_factory=list)
    export_notes: list[str] = Field(default_factory=list)


class ConnectorEvidenceInvariantSnapshotPermissionDenied(PermissionError):
    def __init__(self, decision: PermissionDecision) -> None:
        super().__init__(decision.reason)
        self.decision = decision


class ConnectorEvidenceInvariantSnapshotConflict(ValueError):
    def __init__(self, snapshot_id: str, reason: str) -> None:
        super().__init__(reason)
        self.snapshot_id = snapshot_id
        self.reason = reason


class ConnectorEvidenceInvariantSnapshotExportRequestConflict(ValueError):
    def __init__(self, export_request_id: str, reason: str) -> None:
        super().__init__(reason)
        self.export_request_id = export_request_id
        self.reason = reason


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


def persist_connector_evidence_invariant_snapshot(
    repository: AxisPersistenceRepository,
    request: ConnectorEvidenceInvariantSnapshotRequest,
) -> ConnectorEvidenceInvariantSnapshotRecord:
    permission_decision = _evaluate_snapshot_permission(request)
    existing_replay = _find_snapshot_by_idempotency_key(repository, request)
    if existing_replay is not None:
        if (
            existing_replay.payload.get("snapshot_id") != request.snapshot_id
            or existing_replay.payload.get("connector_id") != request.connector_id
        ):
            raise ConnectorEvidenceInvariantSnapshotConflict(
                str(existing_replay.payload.get("snapshot_id") or request.snapshot_id),
                "idempotency_conflict",
            )
        return _snapshot_record_from_audit_event(existing_replay, idempotent_replay=True)

    existing_snapshot = _find_snapshot_by_id(repository, request)
    if existing_snapshot is not None:
        raise ConnectorEvidenceInvariantSnapshotConflict(
            request.snapshot_id,
            "snapshot_id_already_exists",
        )

    report = build_connector_evidence_invariant_report(
        repository,
        ConnectorEvidenceInvariantQuery(
            tenant_id=request.tenant_id,
            connector_id=request.connector_id,
            limit=request.limit,
        ),
    )
    subject_ids = [invariant.subject_id for invariant in report.invariants]
    report_payload = _snapshot_report_payload(report)
    report_digest = _canonical_sha256(report_payload)
    audit_payload = {
        "snapshot_id": request.snapshot_id,
        "connector_id": request.connector_id,
        "idempotency_key": request.idempotency_key,
        "reason": request.reason,
        "required_scope": SNAPSHOT_REQUIRED_SCOPE,
        "permission_decision": permission_decision.model_dump(),
        "invariant_count": len(report.invariants),
        "invariant_counts": report.invariant_counts,
        "subject_ids": subject_ids,
        "report_digest_sha256": report_digest,
        "report_hash_algorithm": REPORT_HASH_ALGORITHM,
        "report_reason_ids": [invariant.reason for invariant in report.invariants],
        "notes": request.notes,
    }
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=request.tenant_id,
            actor_id=request.requested_by,
            event_type=SNAPSHOT_AUDIT_EVENT_TYPE,
            payload=audit_payload,
        )
    )
    return _snapshot_record_from_audit_event(audit_event)


def read_connector_evidence_invariant_snapshot_history(
    repository: AxisPersistenceRepository,
    query: ConnectorEvidenceInvariantSnapshotQuery,
    *,
    actor_id: str,
    actor_scopes: list[str],
) -> ConnectorEvidenceInvariantSnapshotHistory:
    _evaluate_snapshot_history_permission(query, actor_id, actor_scopes)
    snapshots = _snapshot_records_for_query(repository, query)
    snapshot_ids = [snapshot.snapshot_id for snapshot in snapshots]
    repository.append_audit_event(
        AuditEventCreate(
            tenant_id=query.tenant_id,
            actor_id=actor_id,
            event_type=SNAPSHOT_READ_AUDIT_EVENT_TYPE,
            payload={
                "connector_id": query.connector_id,
                "snapshot_id": query.snapshot_id,
                "idempotency_key": query.idempotency_key,
                "limit": query.limit,
                "returned_snapshot_count": len(snapshots),
                "snapshot_ids": snapshot_ids,
            },
        )
    )
    return ConnectorEvidenceInvariantSnapshotHistory(
        tenant_id=query.tenant_id,
        plant_name="Ravenna Works",
        scenario="Plant Operations Cockpit",
        history_status=OverviewStatus.READY if snapshots else OverviewStatus.WATCH,
        metrics=[
            OverviewMetric(
                label="Evidence Snapshots",
                value=str(len(snapshots)),
                detail="Persisted connector evidence snapshot audit artifacts",
                status=OverviewStatus.READY if snapshots else OverviewStatus.WATCH,
            )
        ],
        snapshots=snapshots,
        history_notes=[
            "Snapshot history is read from append-only audit events.",
            "History reads return public-safe snapshot metadata only.",
        ],
    )


def export_connector_evidence_invariant_snapshots(
    repository: AxisPersistenceRepository,
    query: ConnectorEvidenceInvariantSnapshotExportQuery,
    *,
    actor_id: str,
    actor_scopes: list[str],
    ledger_signer: AuditLedgerSigner | None = None,
) -> ConnectorEvidenceInvariantSnapshotExportBundle:
    _evaluate_snapshot_history_permission(query, actor_id, actor_scopes)
    snapshots = _snapshot_records_for_query(repository, query)
    checksum = _snapshots_checksum(snapshots)
    integrity_proof = _snapshot_integrity_proof(snapshots)
    manifest = ConnectorEvidenceInvariantSnapshotExportManifest(
        export_id=f"connector-evidence-snapshot-export-{checksum[:16]}",
        generated_at=datetime.now(UTC).isoformat(),
        tenant_id=query.tenant_id,
        record_count=len(snapshots),
        format=query.format,
        redaction_policy="connector-snapshot-public-safe",
        checksum_sha256=checksum,
        integrity_chain_tip_sha256=integrity_proof.chain_tip_sha256,
        connector_id=query.connector_id,
        snapshot_id=query.snapshot_id,
        idempotency_key=query.idempotency_key,
    )
    signature_payload = canonical_ledger_signature_payload(manifest, integrity_proof)
    ledger_signature = (
        ledger_signer.sign_payload(signature_payload)
        if ledger_signer is not None
        else unsigned_audit_ledger_signature(signature_payload)
    )
    snapshot_ids = [snapshot.snapshot_id for snapshot in snapshots]
    repository.append_audit_event(
        AuditEventCreate(
            tenant_id=query.tenant_id,
            actor_id=actor_id,
            event_type=SNAPSHOT_EXPORT_AUDIT_EVENT_TYPE,
            payload={
                "connector_id": query.connector_id,
                "snapshot_id": query.snapshot_id,
                "idempotency_key": query.idempotency_key,
                "limit": query.limit,
                "export_reason": query.export_reason,
                "export_id": manifest.export_id,
                "checksum_sha256": manifest.checksum_sha256,
                "signature_status": ledger_signature.verification_status,
                "exported_snapshot_count": len(snapshots),
                "snapshot_ids": snapshot_ids,
            },
        )
    )
    return ConnectorEvidenceInvariantSnapshotExportBundle(
        tenant_id=query.tenant_id,
        scenario="Plant Operations Cockpit",
        format=query.format,
        export_reason=query.export_reason,
        filters=ConnectorEvidenceInvariantSnapshotQuery(
            tenant_id=query.tenant_id,
            connector_id=query.connector_id,
            snapshot_id=query.snapshot_id,
            idempotency_key=query.idempotency_key,
            limit=query.limit,
        ),
        manifest=manifest,
        integrity_proof=integrity_proof,
        ledger_signature=ledger_signature,
        snapshots=snapshots,
        export_notes=[
            "Snapshot export bundle is tenant-scoped before optional filters are applied.",
            "Snapshots include public-safe invariant counts, subject ids and report digests only.",
            "Manifest checksum covers exported connector evidence snapshot metadata.",
            "Integrity proof links exported snapshots with a deterministic SHA-256 hash chain.",
        ],
    )


def record_connector_evidence_invariant_snapshot_export_request(
    repository: AxisPersistenceRepository,
    request: ConnectorEvidenceInvariantSnapshotExportRequest,
) -> ConnectorEvidenceInvariantSnapshotExportRequestRecord:
    permission_decision = _evaluate_snapshot_export_request_permission(request)
    existing_replay = (
        repository.get_connector_evidence_snapshot_export_request_by_idempotency_key(
            request.tenant_id,
            request.idempotency_key,
        )
    )
    if existing_replay is not None:
        if _export_request_fingerprint_from_record(
            existing_replay
        ) != _export_request_fingerprint_from_request(request):
            raise ConnectorEvidenceInvariantSnapshotExportRequestConflict(
                existing_replay.export_request_id,
                "idempotency_conflict",
            )
        return _snapshot_export_request_from_record(existing_replay, idempotent_replay=True)

    existing_request = repository.get_connector_evidence_snapshot_export_request(
        request.tenant_id,
        request.export_request_id,
    )
    if existing_request is not None:
        raise ConnectorEvidenceInvariantSnapshotExportRequestConflict(
            request.export_request_id,
            "export_request_id_already_exists",
        )

    query = ConnectorEvidenceInvariantSnapshotQuery(
        tenant_id=request.tenant_id,
        connector_id=request.connector_id,
        snapshot_id=request.snapshot_id,
        idempotency_key=request.snapshot_idempotency_key,
        limit=request.limit,
    )
    snapshots = _snapshot_records_for_query(repository, query)
    checksum = _snapshots_checksum(snapshots)
    snapshot_ids = [snapshot.snapshot_id for snapshot in snapshots]
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=request.tenant_id,
            actor_id=request.requested_by,
            event_type=SNAPSHOT_EXPORT_REQUEST_AUDIT_EVENT_TYPE,
            payload={
                "export_request_id": request.export_request_id,
                "idempotency_key": request.idempotency_key,
                "connector_id": request.connector_id,
                "snapshot_id": request.snapshot_id,
                "snapshot_idempotency_key": request.snapshot_idempotency_key,
                "limit": request.limit,
                "export_reason": request.export_reason,
                "format": request.format,
                "status": SNAPSHOT_EXPORT_REQUEST_STATUS,
                "export_status": SNAPSHOT_EXPORT_REQUEST_EXPORT_STATUS,
                "storage_status": SNAPSHOT_EXPORT_REQUEST_STORAGE_STATUS,
                "approval_id": request.approval_id,
                "workflow_id": request.workflow_id,
                "owner_role": request.owner_role,
                "risk_level": request.risk_level,
                "required_scope": SNAPSHOT_EXPORT_REQUEST_REQUIRED_SCOPE,
                "permission_decision": permission_decision.model_dump(),
                "requested_snapshot_count": len(snapshots),
                "snapshot_checksum_sha256": checksum,
                "snapshot_ids": snapshot_ids,
                "redaction_policy": SNAPSHOT_EXPORT_REQUEST_REDACTION_POLICY,
                "controls": request.controls,
                "workflow_signal_status": SNAPSHOT_EXPORT_REQUEST_WORKFLOW_SIGNAL_STATUS,
            },
        )
    )
    _ensure_export_request_approval_record(
        repository,
        request,
        requested_snapshot_count=len(snapshots),
        snapshot_checksum_sha256=checksum,
    )
    record = repository.create_connector_evidence_snapshot_export_request(
        ConnectorEvidenceSnapshotExportRequestCreate(
            tenant_id=request.tenant_id,
            export_request_id=request.export_request_id,
            idempotency_key=request.idempotency_key,
            status=SNAPSHOT_EXPORT_REQUEST_STATUS,
            export_status=SNAPSHOT_EXPORT_REQUEST_EXPORT_STATUS,
            storage_status=SNAPSHOT_EXPORT_REQUEST_STORAGE_STATUS,
            requested_by=request.requested_by,
            owner_role=request.owner_role,
            risk_level=request.risk_level,
            approval_id=request.approval_id,
            workflow_id=request.workflow_id,
            connector_id=request.connector_id,
            snapshot_id=request.snapshot_id,
            snapshot_idempotency_key=request.snapshot_idempotency_key,
            export_reason=request.export_reason,
            format=request.format,
            limit=request.limit,
            requested_snapshot_count=len(snapshots),
            snapshot_checksum_sha256=checksum,
            redaction_policy=SNAPSHOT_EXPORT_REQUEST_REDACTION_POLICY,
            controls=request.controls,
            permission_decision=permission_decision.model_dump(),
            workflow_signal_status=SNAPSHOT_EXPORT_REQUEST_WORKFLOW_SIGNAL_STATUS,
            audit_event_id=audit_event.id,
            audit_event_type=SNAPSHOT_EXPORT_REQUEST_AUDIT_EVENT_TYPE,
            notes=request.notes,
        )
    )
    return _snapshot_export_request_from_record(record)


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


def _snapshots_checksum(snapshots: list[ConnectorEvidenceInvariantSnapshotRecord]) -> str:
    encoded_snapshots = json.dumps(
        [snapshot.model_dump(mode="json") for snapshot in snapshots],
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded_snapshots.encode("utf-8")).hexdigest()


def _snapshot_integrity_proof(
    snapshots: list[ConnectorEvidenceInvariantSnapshotRecord],
) -> ConnectorEvidenceInvariantSnapshotIntegrityProof:
    snapshot_hashes: list[str] = []
    chain_tip = "0" * 64
    for snapshot in snapshots:
        encoded_snapshot = json.dumps(
            snapshot.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        snapshot_hash = hashlib.sha256(encoded_snapshot.encode("utf-8")).hexdigest()
        chain_tip = hashlib.sha256(f"{chain_tip}:{snapshot_hash}".encode()).hexdigest()
        snapshot_hashes.append(snapshot_hash)

    return ConnectorEvidenceInvariantSnapshotIntegrityProof(
        algorithm="sha256-hash-chain-v1",
        verification_status="verified",
        record_count=len(snapshots),
        chain_tip_sha256=chain_tip,
        snapshot_hashes=snapshot_hashes,
    )


def _evaluate_snapshot_export_request_permission(
    request: ConnectorEvidenceInvariantSnapshotExportRequest,
) -> PermissionDecision:
    decision = evaluate_permission(
        PermissionRequest(
            tenant_id=request.tenant_id,
            actor_id=request.requested_by,
            actor_scopes=request.actor_scopes,
            required_scopes=[SNAPSHOT_EXPORT_REQUEST_REQUIRED_SCOPE],
            attributes={
                "connector_id": request.connector_id,
                "snapshot_id": request.snapshot_id,
                "approval_id": request.approval_id,
                "workflow_id": request.workflow_id,
                "risk_level": request.risk_level,
                "export_reason": request.export_reason,
                "storage_status": SNAPSHOT_EXPORT_REQUEST_STORAGE_STATUS,
            },
        )
    )
    if not decision.allowed:
        raise ConnectorEvidenceInvariantSnapshotPermissionDenied(decision)
    return decision


def _evaluate_snapshot_history_permission(
    query: ConnectorEvidenceInvariantSnapshotQuery,
    actor_id: str,
    actor_scopes: list[str],
) -> PermissionDecision:
    decision = evaluate_permission(
        PermissionRequest(
            tenant_id=query.tenant_id,
            actor_id=actor_id,
            actor_scopes=actor_scopes,
            required_scopes=[SNAPSHOT_READ_REQUIRED_SCOPE],
            attributes={
                "connector_id": query.connector_id,
                "snapshot_id": query.snapshot_id,
                "idempotency_key": query.idempotency_key,
            },
        )
    )
    if not decision.allowed:
        raise ConnectorEvidenceInvariantSnapshotPermissionDenied(decision)
    return decision


def _ensure_export_request_approval_record(
    repository: AxisPersistenceRepository,
    request: ConnectorEvidenceInvariantSnapshotExportRequest,
    *,
    requested_snapshot_count: int,
    snapshot_checksum_sha256: str,
) -> None:
    existing = repository.get_approval_record(request.tenant_id, request.approval_id)
    if existing is not None:
        return
    action_connector = request.connector_id or "tenant"
    repository.create_approval_record(
        ApprovalRecordCreate(
            tenant_id=request.tenant_id,
            approval_id=request.approval_id,
            workflow_id=request.workflow_id,
            action_id=f"connector_evidence_snapshot_export:{action_connector}",
            requested_by=request.requested_by,
            owner_role=request.owner_role,
            risk_level=request.risk_level,
            payload={
                "export_request_id": request.export_request_id,
                "idempotency_key": request.idempotency_key,
                "connector_id": request.connector_id,
                "snapshot_id": request.snapshot_id,
                "snapshot_idempotency_key": request.snapshot_idempotency_key,
                "export_reason": request.export_reason,
                "format": request.format,
                "limit": request.limit,
                "required_permission": SNAPSHOT_EXPORT_REQUEST_REQUIRED_SCOPE,
                "requested_snapshot_count": requested_snapshot_count,
                "snapshot_checksum_sha256": snapshot_checksum_sha256,
                "redaction_policy": SNAPSHOT_EXPORT_REQUEST_REDACTION_POLICY,
                "storage_status": SNAPSHOT_EXPORT_REQUEST_STORAGE_STATUS,
            },
        )
    )


def _snapshot_export_request_from_record(
    record,
    idempotent_replay: bool = False,
) -> ConnectorEvidenceInvariantSnapshotExportRequestRecord:
    return ConnectorEvidenceInvariantSnapshotExportRequestRecord(
        tenant_id=record.tenant_id,
        export_request_id=record.export_request_id,
        idempotency_key=record.idempotency_key,
        status=record.status,
        export_status=record.export_status,
        storage_status=record.storage_status,
        requested_by=record.requested_by,
        owner_role=record.owner_role,
        risk_level=record.risk_level,
        approval_id=record.approval_id,
        workflow_id=record.workflow_id,
        snapshot_filter=ConnectorEvidenceInvariantSnapshotExportRequestFilter(
            connector_id=record.connector_id,
            snapshot_id=record.snapshot_id,
            idempotency_key=record.snapshot_idempotency_key,
            limit=record.limit,
        ),
        export_reason=record.export_reason,
        format=record.format,
        requested_snapshot_count=record.requested_snapshot_count,
        snapshot_checksum_sha256=record.snapshot_checksum_sha256,
        redaction_policy=record.redaction_policy,
        controls=record.controls,
        permission_decision=PermissionDecision(**record.permission_decision),
        workflow_signal_status=record.workflow_signal_status,
        audit_event_id=record.audit_event_id,
        audit_event_type=record.audit_event_type,
        notes=record.notes,
        created_at=record.created_at,
        idempotent_replay=idempotent_replay,
    )


def _export_request_fingerprint_from_request(
    request: ConnectorEvidenceInvariantSnapshotExportRequest,
) -> dict:
    return {
        "export_request_id": request.export_request_id,
        "requested_by": request.requested_by,
        "owner_role": request.owner_role,
        "risk_level": request.risk_level,
        "approval_id": request.approval_id,
        "workflow_id": request.workflow_id,
        "connector_id": request.connector_id,
        "snapshot_id": request.snapshot_id,
        "snapshot_idempotency_key": request.snapshot_idempotency_key,
        "export_reason": request.export_reason,
        "format": request.format,
        "limit": request.limit,
        "controls": request.controls,
        "notes": request.notes,
    }


def _export_request_fingerprint_from_record(record) -> dict:
    return {
        "export_request_id": record.export_request_id,
        "requested_by": record.requested_by,
        "owner_role": record.owner_role,
        "risk_level": record.risk_level,
        "approval_id": record.approval_id,
        "workflow_id": record.workflow_id,
        "connector_id": record.connector_id,
        "snapshot_id": record.snapshot_id,
        "snapshot_idempotency_key": record.snapshot_idempotency_key,
        "export_reason": record.export_reason,
        "format": record.format,
        "limit": record.limit,
        "controls": record.controls,
        "notes": record.notes,
    }


def _evaluate_snapshot_permission(
    request: ConnectorEvidenceInvariantSnapshotRequest,
) -> PermissionDecision:
    decision = evaluate_permission(
        PermissionRequest(
            tenant_id=request.tenant_id,
            actor_id=request.requested_by,
            actor_scopes=request.actor_scopes,
            required_scopes=[SNAPSHOT_REQUIRED_SCOPE],
            attributes={
                "snapshot_id": request.snapshot_id,
                "connector_id": request.connector_id,
            },
        )
    )
    if not decision.allowed:
        raise ConnectorEvidenceInvariantSnapshotPermissionDenied(decision)
    return decision


def _snapshot_records_for_query(
    repository: AxisPersistenceRepository,
    query: ConnectorEvidenceInvariantSnapshotQuery,
) -> list[ConnectorEvidenceInvariantSnapshotRecord]:
    events = repository.list_audit_events(
        tenant_id=query.tenant_id,
        event_type=SNAPSHOT_AUDIT_EVENT_TYPE,
        limit=200,
    )
    records = [
        _snapshot_record_from_audit_event(event)
        for event in events
        if _snapshot_event_matches_query(event, query)
    ]
    return records[: query.limit]


def _snapshot_event_matches_query(
    event: AuditEvent,
    query: ConnectorEvidenceInvariantSnapshotQuery,
) -> bool:
    payload = event.payload
    return (
        (query.connector_id is None or payload.get("connector_id") == query.connector_id)
        and (query.snapshot_id is None or payload.get("snapshot_id") == query.snapshot_id)
        and (
            query.idempotency_key is None
            or payload.get("idempotency_key") == query.idempotency_key
        )
    )


def _find_snapshot_by_idempotency_key(
    repository: AxisPersistenceRepository,
    request: ConnectorEvidenceInvariantSnapshotRequest,
) -> AuditEvent | None:
    events = repository.list_audit_events(
        tenant_id=request.tenant_id,
        event_type=SNAPSHOT_AUDIT_EVENT_TYPE,
        limit=200,
    )
    return next(
        (
            event
            for event in events
            if event.payload.get("idempotency_key") == request.idempotency_key
        ),
        None,
    )


def _find_snapshot_by_id(
    repository: AxisPersistenceRepository,
    request: ConnectorEvidenceInvariantSnapshotRequest,
) -> AuditEvent | None:
    events = repository.list_audit_events(
        tenant_id=request.tenant_id,
        event_type=SNAPSHOT_AUDIT_EVENT_TYPE,
        limit=200,
    )
    return next(
        (
            event
            for event in events
            if event.payload.get("snapshot_id") == request.snapshot_id
        ),
        None,
    )


def _snapshot_record_from_audit_event(
    audit_event: AuditEvent,
    *,
    idempotent_replay: bool = False,
) -> ConnectorEvidenceInvariantSnapshotRecord:
    payload = audit_event.payload
    return ConnectorEvidenceInvariantSnapshotRecord(
        tenant_id=audit_event.tenant_id,
        snapshot_id=str(payload["snapshot_id"]),
        status="persisted",
        connector_id=payload.get("connector_id"),
        requested_by=audit_event.actor_id,
        idempotency_key=str(payload["idempotency_key"]),
        reason=str(payload["reason"]),
        invariant_count=int(payload["invariant_count"]),
        invariant_counts=dict(payload["invariant_counts"]),
        subject_ids=list(payload["subject_ids"]),
        report_digest_sha256=str(payload["report_digest_sha256"]),
        report_hash_algorithm=str(payload["report_hash_algorithm"]),
        permission_decision=PermissionDecision.model_validate(payload["permission_decision"]),
        audit_event_id=audit_event.id,
        audit_event_type=audit_event.event_type,
        idempotent_replay=idempotent_replay,
        notes=list(payload.get("notes") or []),
    )


def _snapshot_report_payload(report: ManufacturingConnectorEvidenceInvariantReport) -> dict:
    return {
        "tenant_id": report.tenant_id,
        "invariant_counts": report.invariant_counts,
        "invariants": [
            invariant.model_dump(mode="json")
            for invariant in sorted(
                report.invariants,
                key=lambda item: (item.evidence_type, item.subject_id, item.reason),
            )
        ],
    }


def _canonical_sha256(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


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
