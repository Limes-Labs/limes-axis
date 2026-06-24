from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class Actor(Base):
    __tablename__ = "actors"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ApprovalRecord(Base):
    __tablename__ = "approval_records"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    approval_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    workflow_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    action_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    owner_role: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    risk_level: Mapped[str] = mapped_column(String(40), nullable=False)
    decision: Mapped[str | None] = mapped_column(String(40), nullable=True)
    decision_actor_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(String(600), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "approval_id", name="uq_approval_records_tenant_approval"),
    )


class ActionRun(Base):
    __tablename__ = "action_runs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    action_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    execution_mode: Mapped[str] = mapped_column(String(80), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    approval_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    workflow_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "action_id",
            "idempotency_key",
            name="uq_action_runs_tenant_action_idempotency",
        ),
    )


class DemoReferenceRecord(Base):
    __tablename__ = "demo_reference_records"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    surface: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    reference_id: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "surface",
            "reference_id",
            name="uq_demo_reference_records_tenant_surface_reference",
        ),
    )


class WorkflowRunRecord(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    workflow_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    owner_role: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    runtime: Mapped[str] = mapped_column(String(120), nullable=False)
    adapter: Mapped[str] = mapped_column(String(120), nullable=False)
    autonomy_level: Mapped[str] = mapped_column(String(8), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    eta: Mapped[str] = mapped_column(String(120), nullable=False)
    blocker: Mapped[str | None] = mapped_column(String(600), nullable=True)
    objective: Mapped[str] = mapped_column(String(1000), nullable=False)
    current_step: Mapped[str] = mapped_column(String(200), nullable=False)
    related_risk: Mapped[str] = mapped_column(String(160), nullable=False)
    related_assets: Mapped[list] = mapped_column(JSON, nullable=False)
    inputs: Mapped[list] = mapped_column(JSON, nullable=False)
    proposed_outputs: Mapped[list] = mapped_column(JSON, nullable=False)
    pending_signals: Mapped[list] = mapped_column(JSON, nullable=False)
    controls: Mapped[list] = mapped_column(JSON, nullable=False)
    audit_scope: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    replay_ready: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "workflow_id", name="uq_workflow_runs_tenant_workflow"),
    )


class WorkflowTimelineRecord(Base):
    __tablename__ = "workflow_timeline_events"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    workflow_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    result: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workflow_id",
            "sequence",
            name="uq_workflow_timeline_tenant_workflow_sequence",
        ),
    )


class ReplaySimulationOutput(Base):
    __tablename__ = "replay_simulation_outputs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    simulation_output_id: Mapped[str] = mapped_column(
        String(180),
        nullable=False,
        index=True,
    )
    workflow_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    artifact_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    required_scope: Mapped[str] = mapped_column(String(160), nullable=False)
    replay_mode: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    determinism_status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    output_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    retention_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    permission_decision: Mapped[dict] = mapped_column(JSON, nullable=False)
    artifact_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, nullable=False)
    audit_event_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    audit_event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(600), nullable=False)
    notes: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "simulation_output_id",
            name="uq_replay_simulation_outputs_tenant_output",
        ),
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_replay_simulation_outputs_tenant_idempotency",
        ),
    )


class ConnectorConfiguration(Base):
    __tablename__ = "connector_configurations"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    connector_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    sync_mode: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    runtime_boundary: Mapped[str] = mapped_column(String(160), nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    configuration_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    credential_ref_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    notes: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "connector_id",
            name="uq_connector_configurations_tenant_connector",
        ),
    )


class ConnectorManifestRecord(Base):
    __tablename__ = "connector_manifests"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    connector_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    runtime_boundary: Mapped[str] = mapped_column(String(160), nullable=False)
    registered_by: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    manifest_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    runtime_policy: Mapped[dict] = mapped_column(JSON, nullable=False)
    preview_sample: Mapped[dict] = mapped_column(JSON, nullable=False)
    audit_event_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    audit_event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    notes: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "connector_id",
            name="uq_connector_manifests_tenant_connector",
        ),
    )


class ConnectorCredentialHandle(Base):
    __tablename__ = "connector_credential_handles"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    connector_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    handle_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    secret_provider: Mapped[str] = mapped_column(String(120), nullable=False)
    secret_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    purpose: Mapped[str] = mapped_column(String(160), nullable=False)
    rotation_interval_days: Mapped[int] = mapped_column(Integer, nullable=False)
    last_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_rotation_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    created_by: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    labels: Mapped[dict] = mapped_column(JSON, nullable=False)
    notes: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "handle_id",
            name="uq_connector_credential_handles_tenant_handle",
        ),
    )


class ConnectorCredentialRotation(Base):
    __tablename__ = "connector_credential_rotations"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    handle_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    rotated_by: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    rotated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence_ref: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    notes: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ConnectorCredentialLease(Base):
    __tablename__ = "connector_credential_leases"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    connector_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    handle_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    lease_id: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    lease_mode: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    runtime_boundary: Mapped[str] = mapped_column(String(160), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    lease_purpose: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    secret_provider: Mapped[str] = mapped_column(String(120), nullable=False)
    secret_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    vault_kms_policy: Mapped[dict] = mapped_column(JSON, nullable=False)
    permission_decision: Mapped[dict] = mapped_column(JSON, nullable=False)
    lease_result: Mapped[dict] = mapped_column(JSON, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    renewal_due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    renewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    renewed_by: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    renewal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(600), nullable=True)
    audit_event_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    audit_event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    notes: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "lease_id",
            name="uq_connector_credential_leases_tenant_lease",
        ),
    )


class ConnectorEgressPolicy(Base):
    __tablename__ = "connector_egress_policies"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    connector_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    policy_id: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    connection_profile_id: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    egress_boundary: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    policy_mode: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    runtime_boundary: Mapped[str] = mapped_column(String(160), nullable=False)
    private_endpoint_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    policy_document: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, nullable=False)
    audit_event_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    audit_event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    notes: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "policy_id",
            name="uq_connector_egress_policies_tenant_policy",
        ),
    )


class ConnectorRun(Base):
    __tablename__ = "connector_runs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    connector_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    execution_mode: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    runtime_boundary: Mapped[str] = mapped_column(String(160), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    credential_handle_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    input_summary: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_summary: Mapped[dict] = mapped_column(JSON, nullable=False)
    audit_event_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    audit_event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    notes: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "run_id",
            name="uq_connector_runs_tenant_run",
        ),
    )


class ConnectorOntologyProposal(Base):
    __tablename__ = "connector_ontology_proposals"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    connector_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    proposal_id: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    source_run_id: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    source_file_name: Mapped[str] = mapped_column(String(240), nullable=False)
    mapping_profile: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    write_mode: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    graph_mutation_status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    proposed_by: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    ontology_type: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    field_summary: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, nullable=False)
    promotion_id: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    policy_id: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    policy_set_id: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    policy_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    policy_decision: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    promoted_by: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ontology_mutation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    audit_event_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    audit_event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    notes: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "proposal_id",
            name="uq_connector_ontology_proposals_tenant_proposal",
        ),
    )


class ConnectorOntologyPromotion(Base):
    __tablename__ = "connector_ontology_promotions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    connector_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    promotion_id: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    proposal_id: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    manual_import_id: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    promotion_mode: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    graph_mutation_status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    ontology_mutation: Mapped[dict] = mapped_column(JSON, nullable=False)
    permission_decision: Mapped[dict] = mapped_column(JSON, nullable=False)
    policy_id: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    policy_set_id: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    policy_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    policy_decision: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    audit_event_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    audit_event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    notes: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "promotion_id",
            name="uq_connector_ontology_promotions_tenant_promotion",
        ),
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_connector_ontology_promotions_tenant_idempotency",
        ),
    )


class ConnectorPromotionPolicy(Base):
    __tablename__ = "connector_promotion_policies"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    connector_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    policy_id: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    enforcement_mode: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    required_authoring_scope: Mapped[str] = mapped_column(String(160), nullable=False)
    required_scopes: Mapped[list] = mapped_column(JSON, nullable=False)
    required_manual_import_status: Mapped[str] = mapped_column(String(80), nullable=False)
    required_workflow_signal_status: Mapped[str] = mapped_column(String(80), nullable=False)
    allowed_risk_levels: Mapped[list] = mapped_column(JSON, nullable=False)
    allowed_ontology_types: Mapped[list] = mapped_column(JSON, nullable=False)
    review_window_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    permission_decision: Mapped[dict] = mapped_column(JSON, nullable=False)
    audit_event_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    audit_event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    revises_policy_id: Mapped[str | None] = mapped_column(
        String(180),
        nullable=True,
        index=True,
    )
    replaced_by_policy_id: Mapped[str | None] = mapped_column(
        String(180),
        nullable=True,
        index=True,
    )
    revision_idempotency_key: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        index=True,
    )
    revision_approval_id: Mapped[str | None] = mapped_column(
        String(180),
        nullable=True,
        index=True,
    )
    revision_decision: Mapped[str | None] = mapped_column(String(40), nullable=True)
    revision_workflow_signal_status: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )
    notes: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "policy_id",
            name="uq_connector_promotion_policies_tenant_policy",
        ),
        UniqueConstraint(
            "tenant_id",
            "revision_idempotency_key",
            name="uq_connector_promotion_policies_tenant_revision_idempotency",
        ),
    )


class ConnectorPromotionPolicySet(Base):
    __tablename__ = "connector_promotion_policy_sets"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    connector_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    policy_set_id: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    policy_set_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    activated_by: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    activation_scope: Mapped[str] = mapped_column(String(160), nullable=False)
    policy_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    permission_decision: Mapped[dict] = mapped_column(JSON, nullable=False)
    audit_event_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    audit_event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    activation_reason: Mapped[str] = mapped_column(String(600), nullable=False)
    replaces_policy_set_id: Mapped[str | None] = mapped_column(
        String(180),
        nullable=True,
        index=True,
    )
    replaced_by_policy_set_id: Mapped[str | None] = mapped_column(
        String(180),
        nullable=True,
        index=True,
    )
    replacement_approval_id: Mapped[str | None] = mapped_column(
        String(180),
        nullable=True,
        index=True,
    )
    replacement_decision: Mapped[str | None] = mapped_column(String(40), nullable=True)
    replacement_workflow_signal_status: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )
    replaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rollback_to_policy_set_id: Mapped[str | None] = mapped_column(
        String(180),
        nullable=True,
        index=True,
    )
    rollback_approval_id: Mapped[str | None] = mapped_column(
        String(180),
        nullable=True,
        index=True,
    )
    rollback_decision: Mapped[str | None] = mapped_column(String(40), nullable=True)
    rollback_workflow_signal_status: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )
    policy_revision_adoptions: Mapped[list] = mapped_column(JSON, nullable=False)
    notes: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "policy_set_id",
            name="uq_connector_promotion_policy_sets_tenant_set",
        ),
    )


class ConnectorManualImportRequest(Base):
    __tablename__ = "connector_manual_import_requests"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    connector_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    import_id: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    import_mode: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    owner_role: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    risk_level: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    approval_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    workflow_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    proposal_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    import_summary: Mapped[dict] = mapped_column(JSON, nullable=False)
    controls: Mapped[list] = mapped_column(JSON, nullable=False)
    graph_mutation_status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    workflow_signal_status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    decision: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    decision_actor_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    decision_note: Mapped[str | None] = mapped_column(String(600), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    workflow_signal: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    audit_event_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    audit_event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    notes: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "import_id",
            name="uq_connector_manual_import_requests_tenant_import",
        ),
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_connector_manual_import_requests_tenant_idempotency",
        ),
    )


class ManufacturingOperationRecord(Base):
    __tablename__ = "manufacturing_operation_records"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    record_id: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    record_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_system: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    owner_role: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    related_asset: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    workflow_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    risk_level: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "record_id",
            name="uq_manufacturing_operation_records_tenant_record",
        ),
    )


class ManufacturingDailyBrief(Base):
    __tablename__ = "manufacturing_daily_briefs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    brief_id: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(220), nullable=False, index=True)
    brief_date: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    required_scopes: Mapped[list] = mapped_column(JSON, nullable=False)
    source_record_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    summary_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    permission_decision: Mapped[dict] = mapped_column(JSON, nullable=False)
    audit_event_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    audit_event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "brief_id",
            name="uq_manufacturing_daily_briefs_tenant_brief",
        ),
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_manufacturing_daily_briefs_tenant_idempotency",
        ),
    )
