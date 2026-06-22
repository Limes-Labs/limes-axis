from datetime import datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from axis_api.audit import AuditEventCreate
from axis_api.models import (
    ActionRun,
    ApprovalRecord,
    AuditEvent,
    ConnectorConfiguration,
    ConnectorCredentialHandle,
    ConnectorCredentialRotation,
    ConnectorManualImportRequest,
    ConnectorOntologyPromotion,
    ConnectorOntologyProposal,
    ConnectorPromotionPolicy,
    ConnectorPromotionPolicySet,
    ConnectorRun,
    WorkflowRunRecord,
    WorkflowTimelineRecord,
    utc_now,
)


class PersistenceRecordNotFound(LookupError):
    pass


class ApprovalRecordCreate(BaseModel):
    tenant_id: str = Field(min_length=1)
    approval_id: str = Field(min_length=1)
    workflow_id: str | None = None
    action_id: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    owner_role: str = Field(min_length=1)
    risk_level: str = Field(min_length=1)
    payload: dict = Field(default_factory=dict)
    status: str = Field(default="pending", min_length=1)


class ApprovalDecisionRecord(BaseModel):
    tenant_id: str = Field(min_length=1)
    approval_id: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    decision_actor_id: str = Field(min_length=1)
    decision_note: str | None = None


class ActionRunCreate(BaseModel):
    tenant_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    execution_mode: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    payload: dict = Field(default_factory=dict)
    approval_id: str | None = None
    workflow_id: str | None = None
    status: str = Field(default="requested", min_length=1)


class ActionRunResultRecord(BaseModel):
    tenant_id: str = Field(min_length=1)
    action_run_id: UUID
    status: str = Field(min_length=1)
    result_payload: dict = Field(default_factory=dict)


class WorkflowRunCreate(BaseModel):
    tenant_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    state: str = Field(min_length=1)
    status: str = Field(min_length=1)
    owner_role: str = Field(min_length=1)
    runtime: str = Field(min_length=1)
    adapter: str = Field(min_length=1)
    autonomy_level: str = Field(pattern=r"^L[0-4]$")
    started_at: datetime
    eta: str = Field(min_length=1)
    blocker: str | None = None
    objective: str = Field(min_length=1)
    current_step: str = Field(min_length=1)
    related_risk: str = Field(min_length=1)
    related_assets: list[str] = Field(min_length=1)
    inputs: list[str] = Field(min_length=1)
    proposed_outputs: list[str] = Field(min_length=1)
    pending_signals: list[dict] = Field(default_factory=list)
    controls: list[str] = Field(min_length=1)
    audit_scope: str = Field(min_length=1)
    replay_ready: bool = False


class WorkflowTimelineEventCreate(BaseModel):
    tenant_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    event: str = Field(min_length=1)
    occurred_at: datetime
    actor: str = Field(min_length=1)
    result: str = Field(min_length=1)
    summary: str = Field(min_length=1)


class ConnectorConfigurationCreate(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    status: str = Field(default="configured_preview_only", min_length=1)
    sync_mode: str = Field(default="preview", min_length=1)
    runtime_boundary: str = Field(default="axis-connector-sandbox", min_length=1)
    created_by: str = Field(min_length=1)
    configuration_payload: dict = Field(default_factory=dict)
    credential_ref_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ConnectorCredentialHandleCreate(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    handle_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    status: str = Field(default="active", min_length=1)
    secret_provider: str = Field(min_length=1)
    secret_ref: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    rotation_interval_days: int = Field(ge=1, le=3660)
    last_rotated_at: datetime | None = None
    next_rotation_due_at: datetime | None = None
    created_by: str = Field(min_length=1)
    labels: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ConnectorCredentialRotationCreate(BaseModel):
    tenant_id: str = Field(min_length=1)
    handle_id: str = Field(min_length=1)
    rotated_by: str = Field(min_length=1)
    rotated_at: datetime
    evidence_ref: str = Field(min_length=1)
    status: str = Field(default="rotated", min_length=1)
    notes: list[str] = Field(default_factory=list)


class ConnectorRunCreate(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    status: str = Field(default="recorded_preview_only", min_length=1)
    execution_mode: str = Field(default="preview", min_length=1)
    runtime_boundary: str = Field(default="axis-connector-sandbox", min_length=1)
    requested_by: str = Field(min_length=1)
    credential_handle_ids: list[str] = Field(default_factory=list)
    input_summary: dict = Field(default_factory=dict)
    result_summary: dict = Field(default_factory=dict)
    audit_event_id: UUID | None = None
    audit_event_type: str = Field(default="connector.run.recorded", min_length=1)
    notes: list[str] = Field(default_factory=list)


class ConnectorOntologyProposalCreate(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    source_run_id: str | None = None
    source_file_name: str = Field(min_length=1)
    mapping_profile: str = Field(min_length=1)
    status: str = Field(default="proposed_from_preview", min_length=1)
    write_mode: str = Field(default="proposal_only", min_length=1)
    graph_mutation_status: str = Field(default="not_applied", min_length=1)
    proposed_by: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    node_type: str = Field(min_length=1)
    ontology_type: str = Field(min_length=1)
    field_summary: dict = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    promotion_id: str | None = None
    policy_id: str | None = None
    policy_set_id: str | None = None
    policy_ids: list[str] | None = None
    policy_decision: dict | None = None
    promoted_by: str | None = None
    ontology_mutation: dict | None = None
    audit_event_id: UUID | None = None
    audit_event_type: str = Field(default="connector.ontology_proposals.recorded", min_length=1)
    notes: list[str] = Field(default_factory=list)


class ConnectorOntologyPromotionCreate(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    promotion_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    manual_import_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    promotion_mode: str = Field(default="approved_manual_import", min_length=1)
    requested_by: str = Field(min_length=1)
    graph_mutation_status: str = Field(min_length=1)
    ontology_mutation: dict = Field(default_factory=dict)
    permission_decision: dict = Field(default_factory=dict)
    policy_id: str | None = None
    policy_set_id: str | None = None
    policy_ids: list[str] | None = None
    policy_decision: dict | None = None
    audit_event_id: UUID | None = None
    audit_event_type: str = Field(default="connector.ontology_promotion.applied", min_length=1)
    notes: list[str] = Field(default_factory=list)


class ConnectorOntologyPromotionResultRecord(BaseModel):
    tenant_id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    graph_mutation_status: str = Field(min_length=1)
    promotion_id: str = Field(min_length=1)
    promoted_by: str = Field(min_length=1)
    ontology_mutation: dict = Field(default_factory=dict)
    policy_id: str | None = None
    policy_set_id: str | None = None
    policy_ids: list[str] | None = None
    policy_decision: dict | None = None
    audit_event_id: UUID | None = None
    audit_event_type: str | None = None


class ConnectorPromotionPolicyCreate(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    status: str = Field(default="draft", min_length=1)
    enforcement_mode: str = Field(default="advisory", min_length=1)
    created_by: str = Field(min_length=1)
    required_authoring_scope: str = Field(
        default="connectors:promotion_policy:author",
        min_length=1,
    )
    required_scopes: list[str] = Field(min_length=1)
    required_manual_import_status: str = Field(min_length=1)
    required_workflow_signal_status: str = Field(min_length=1)
    allowed_risk_levels: list[str] = Field(min_length=1)
    allowed_ontology_types: list[str] = Field(min_length=1)
    review_window_hours: int = Field(ge=1, le=24 * 30)
    permission_decision: dict = Field(default_factory=dict)
    audit_event_id: UUID | None = None
    audit_event_type: str = Field(default="connector.promotion_policy.authored", min_length=1)
    revises_policy_id: str | None = None
    replaced_by_policy_id: str | None = None
    revision_idempotency_key: str | None = None
    revision_approval_id: str | None = None
    revision_decision: str | None = None
    revision_workflow_signal_status: str | None = None
    notes: list[str] = Field(default_factory=list)


class ConnectorPromotionPolicyEnableRecord(BaseModel):
    tenant_id: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    status: str = Field(default="enabled", min_length=1)
    enforcement_mode: str = Field(default="required", min_length=1)
    permission_decision: dict = Field(default_factory=dict)
    audit_event_id: UUID
    audit_event_type: str = Field(default="connector.promotion_policy.enabled", min_length=1)
    note: str | None = None


class ConnectorPromotionPolicySetCreate(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    policy_set_id: str = Field(min_length=1)
    policy_set_version: str = Field(min_length=1)
    status: str = Field(default="active", min_length=1)
    activated_by: str = Field(min_length=1)
    activation_scope: str = Field(
        default="connectors:promotion_policy_set:activate",
        min_length=1,
    )
    policy_ids: list[str] = Field(min_length=1)
    permission_decision: dict = Field(default_factory=dict)
    audit_event_id: UUID | None = None
    audit_event_type: str = Field(
        default="connector.promotion_policy_set.activated",
        min_length=1,
    )
    activation_reason: str = Field(min_length=1)
    replaces_policy_set_id: str | None = None
    replaced_by_policy_set_id: str | None = None
    replacement_approval_id: str | None = None
    replacement_decision: str | None = None
    replacement_workflow_signal_status: str | None = None
    replaced_at: datetime | None = None
    rollback_to_policy_set_id: str | None = None
    rollback_approval_id: str | None = None
    rollback_decision: str | None = None
    rollback_workflow_signal_status: str | None = None
    policy_revision_adoptions: list[dict] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ConnectorManualImportRequestCreate(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    import_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    status: str = Field(default="approval_required", min_length=1)
    import_mode: str = Field(default="manual_import_request", min_length=1)
    requested_by: str = Field(min_length=1)
    owner_role: str = Field(min_length=1)
    risk_level: str = Field(min_length=1)
    approval_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    proposal_ids: list[str] = Field(min_length=1)
    import_summary: dict = Field(default_factory=dict)
    controls: list[str] = Field(default_factory=list)
    graph_mutation_status: str = Field(default="not_applied", min_length=1)
    workflow_signal_status: str = Field(default="pending_approval_decision", min_length=1)
    decision: str | None = None
    decision_actor_id: str | None = None
    decision_note: str | None = None
    workflow_signal: dict | None = None
    audit_event_id: UUID | None = None
    audit_event_type: str = Field(default="connector.manual_import.requested", min_length=1)
    notes: list[str] = Field(default_factory=list)


class ConnectorManualImportDecisionRecord(BaseModel):
    tenant_id: str = Field(min_length=1)
    import_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    decision_actor_id: str = Field(min_length=1)
    decision_note: str | None = None
    workflow_signal_status: str = Field(min_length=1)
    workflow_signal: dict = Field(default_factory=dict)
    audit_event_id: UUID | None = None
    audit_event_type: str | None = None


class AxisPersistenceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def append_audit_event(self, event: AuditEventCreate) -> AuditEvent:
        audit_event = AuditEvent(
            tenant_id=event.tenant_id,
            actor_id=event.actor_id,
            event_type=event.event_type,
            payload=event.payload,
        )
        self.session.add(audit_event)
        self.session.flush()
        return audit_event

    def list_audit_events(
        self,
        tenant_id: str,
        event_type: str | None = None,
        actor_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        statement: Select[tuple[AuditEvent]] = select(AuditEvent).where(
            AuditEvent.tenant_id == tenant_id
        )
        if event_type is not None:
            statement = statement.where(AuditEvent.event_type == event_type)
        if actor_id is not None:
            statement = statement.where(AuditEvent.actor_id == actor_id)

        statement = statement.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(
            limit
        )
        return list(self.session.scalars(statement))

    def create_approval_record(self, record: ApprovalRecordCreate) -> ApprovalRecord:
        approval = ApprovalRecord(
            tenant_id=record.tenant_id,
            approval_id=record.approval_id,
            workflow_id=record.workflow_id,
            action_id=record.action_id,
            requested_by=record.requested_by,
            owner_role=record.owner_role,
            status=record.status,
            risk_level=record.risk_level,
            payload=record.payload,
        )
        self.session.add(approval)
        self.session.flush()
        return approval

    def get_approval_record(self, tenant_id: str, approval_id: str) -> ApprovalRecord | None:
        statement = select(ApprovalRecord).where(
            ApprovalRecord.tenant_id == tenant_id,
            ApprovalRecord.approval_id == approval_id,
        )
        return self.session.scalars(statement).first()

    def record_approval_decision(self, decision: ApprovalDecisionRecord) -> ApprovalRecord:
        approval = self.get_approval_record(decision.tenant_id, decision.approval_id)
        if approval is None:
            raise PersistenceRecordNotFound("Approval record not found")

        now = utc_now()
        approval.status = decision.decision
        approval.decision = decision.decision
        approval.decision_actor_id = decision.decision_actor_id
        approval.decision_note = decision.decision_note
        approval.decided_at = now
        approval.updated_at = now
        self.session.flush()
        return approval

    def list_approval_records(
        self,
        tenant_id: str,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ApprovalRecord]:
        statement: Select[tuple[ApprovalRecord]] = select(ApprovalRecord).where(
            ApprovalRecord.tenant_id == tenant_id
        )
        if status is not None:
            statement = statement.where(ApprovalRecord.status == status)

        statement = statement.order_by(ApprovalRecord.created_at.desc()).limit(limit)
        return list(self.session.scalars(statement))

    def create_action_run(self, record: ActionRunCreate) -> ActionRun:
        action_run = ActionRun(
            tenant_id=record.tenant_id,
            action_id=record.action_id,
            idempotency_key=record.idempotency_key,
            status=record.status,
            execution_mode=record.execution_mode,
            requested_by=record.requested_by,
            approval_id=record.approval_id,
            workflow_id=record.workflow_id,
            payload=record.payload,
        )
        self.session.add(action_run)
        self.session.flush()
        return action_run

    def get_action_run_by_idempotency_key(
        self,
        tenant_id: str,
        action_id: str,
        idempotency_key: str,
    ) -> ActionRun | None:
        statement = select(ActionRun).where(
            ActionRun.tenant_id == tenant_id,
            ActionRun.action_id == action_id,
            ActionRun.idempotency_key == idempotency_key,
        )
        return self.session.scalars(statement).first()

    def record_action_run_result(self, result: ActionRunResultRecord) -> ActionRun:
        statement = select(ActionRun).where(
            ActionRun.tenant_id == result.tenant_id,
            ActionRun.id == result.action_run_id,
        )
        action_run = self.session.scalars(statement).first()
        if action_run is None:
            raise PersistenceRecordNotFound("Action run not found")

        action_run.status = result.status
        action_run.result_payload = result.result_payload
        action_run.updated_at = utc_now()
        self.session.flush()
        return action_run

    def list_action_runs(
        self,
        tenant_id: str,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ActionRun]:
        statement: Select[tuple[ActionRun]] = select(ActionRun).where(
            ActionRun.tenant_id == tenant_id
        )
        if status is not None:
            statement = statement.where(ActionRun.status == status)

        statement = statement.order_by(ActionRun.created_at.desc()).limit(limit)
        return list(self.session.scalars(statement))

    def create_workflow_run(self, record: WorkflowRunCreate) -> WorkflowRunRecord:
        workflow_run = WorkflowRunRecord(
            tenant_id=record.tenant_id,
            workflow_id=record.workflow_id,
            name=record.name,
            domain=record.domain,
            state=record.state,
            status=record.status,
            owner_role=record.owner_role,
            runtime=record.runtime,
            adapter=record.adapter,
            autonomy_level=record.autonomy_level,
            started_at=record.started_at,
            eta=record.eta,
            blocker=record.blocker,
            objective=record.objective,
            current_step=record.current_step,
            related_risk=record.related_risk,
            related_assets=record.related_assets,
            inputs=record.inputs,
            proposed_outputs=record.proposed_outputs,
            pending_signals=record.pending_signals,
            controls=record.controls,
            audit_scope=record.audit_scope,
            replay_ready=record.replay_ready,
        )
        self.session.add(workflow_run)
        self.session.flush()
        return workflow_run

    def list_workflow_runs(
        self,
        tenant_id: str,
        state: str | None = None,
        limit: int = 100,
    ) -> list[WorkflowRunRecord]:
        statement: Select[tuple[WorkflowRunRecord]] = select(WorkflowRunRecord).where(
            WorkflowRunRecord.tenant_id == tenant_id
        )
        if state is not None:
            statement = statement.where(WorkflowRunRecord.state == state)

        statement = statement.order_by(WorkflowRunRecord.started_at.desc()).limit(limit)
        return list(self.session.scalars(statement))

    def append_workflow_timeline_event(
        self,
        event: WorkflowTimelineEventCreate,
    ) -> WorkflowTimelineRecord:
        timeline_event = WorkflowTimelineRecord(
            tenant_id=event.tenant_id,
            workflow_id=event.workflow_id,
            sequence=event.sequence,
            event=event.event,
            occurred_at=event.occurred_at,
            actor=event.actor,
            result=event.result,
            summary=event.summary,
        )
        self.session.add(timeline_event)
        self.session.flush()
        return timeline_event

    def list_workflow_timeline_events(
        self,
        tenant_id: str,
        workflow_id: str,
        limit: int = 100,
    ) -> list[WorkflowTimelineRecord]:
        statement: Select[tuple[WorkflowTimelineRecord]] = (
            select(WorkflowTimelineRecord)
            .where(
                WorkflowTimelineRecord.tenant_id == tenant_id,
                WorkflowTimelineRecord.workflow_id == workflow_id,
            )
            .order_by(WorkflowTimelineRecord.sequence.asc())
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def create_connector_configuration(
        self,
        record: ConnectorConfigurationCreate,
    ) -> ConnectorConfiguration:
        configuration = ConnectorConfiguration(
            tenant_id=record.tenant_id,
            connector_id=record.connector_id,
            display_name=record.display_name,
            status=record.status,
            sync_mode=record.sync_mode,
            runtime_boundary=record.runtime_boundary,
            created_by=record.created_by,
            configuration_payload=record.configuration_payload,
            credential_ref_ids=record.credential_ref_ids,
            notes=record.notes,
        )
        self.session.add(configuration)
        self.session.flush()
        return configuration

    def list_connector_configurations(
        self,
        tenant_id: str,
        connector_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ConnectorConfiguration]:
        statement: Select[tuple[ConnectorConfiguration]] = select(ConnectorConfiguration).where(
            ConnectorConfiguration.tenant_id == tenant_id
        )
        if connector_id is not None:
            statement = statement.where(ConnectorConfiguration.connector_id == connector_id)
        if status is not None:
            statement = statement.where(ConnectorConfiguration.status == status)

        statement = statement.order_by(
            ConnectorConfiguration.created_at.desc(),
            ConnectorConfiguration.id.desc(),
        ).limit(limit)
        return list(self.session.scalars(statement))

    def create_connector_credential_handle(
        self,
        record: ConnectorCredentialHandleCreate,
    ) -> ConnectorCredentialHandle:
        credential_handle = ConnectorCredentialHandle(
            tenant_id=record.tenant_id,
            connector_id=record.connector_id,
            handle_id=record.handle_id,
            display_name=record.display_name,
            status=record.status,
            secret_provider=record.secret_provider,
            secret_ref=record.secret_ref,
            purpose=record.purpose,
            rotation_interval_days=record.rotation_interval_days,
            last_rotated_at=record.last_rotated_at,
            next_rotation_due_at=record.next_rotation_due_at,
            created_by=record.created_by,
            labels=record.labels,
            notes=record.notes,
        )
        self.session.add(credential_handle)
        self.session.flush()
        return credential_handle

    def get_connector_credential_handle(
        self,
        tenant_id: str,
        handle_id: str,
    ) -> ConnectorCredentialHandle | None:
        statement = select(ConnectorCredentialHandle).where(
            ConnectorCredentialHandle.tenant_id == tenant_id,
            ConnectorCredentialHandle.handle_id == handle_id,
        )
        return self.session.scalars(statement).first()

    def list_connector_credential_handles(
        self,
        tenant_id: str,
        connector_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ConnectorCredentialHandle]:
        statement: Select[tuple[ConnectorCredentialHandle]] = select(
            ConnectorCredentialHandle
        ).where(ConnectorCredentialHandle.tenant_id == tenant_id)
        if connector_id is not None:
            statement = statement.where(ConnectorCredentialHandle.connector_id == connector_id)
        if status is not None:
            statement = statement.where(ConnectorCredentialHandle.status == status)

        statement = statement.order_by(
            ConnectorCredentialHandle.created_at.desc(),
            ConnectorCredentialHandle.id.desc(),
        ).limit(limit)
        return list(self.session.scalars(statement))

    def record_connector_credential_rotation(
        self,
        record: ConnectorCredentialRotationCreate,
    ) -> ConnectorCredentialRotation:
        handle = self.get_connector_credential_handle(record.tenant_id, record.handle_id)
        if handle is None:
            raise PersistenceRecordNotFound("Connector credential handle not found")

        rotation = ConnectorCredentialRotation(
            tenant_id=record.tenant_id,
            handle_id=record.handle_id,
            rotated_by=record.rotated_by,
            rotated_at=record.rotated_at,
            evidence_ref=record.evidence_ref,
            status=record.status,
            notes=record.notes,
        )
        handle.status = "active"
        handle.last_rotated_at = record.rotated_at
        handle.next_rotation_due_at = record.rotated_at + timedelta(
            days=handle.rotation_interval_days
        )
        handle.updated_at = utc_now()
        self.session.add(rotation)
        self.session.flush()
        return rotation

    def list_connector_credential_rotations(
        self,
        tenant_id: str,
        handle_id: str,
        limit: int = 100,
    ) -> list[ConnectorCredentialRotation]:
        statement: Select[tuple[ConnectorCredentialRotation]] = (
            select(ConnectorCredentialRotation)
            .where(
                ConnectorCredentialRotation.tenant_id == tenant_id,
                ConnectorCredentialRotation.handle_id == handle_id,
            )
            .order_by(
                ConnectorCredentialRotation.rotated_at.desc(),
                ConnectorCredentialRotation.created_at.desc(),
            )
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def create_connector_run(
        self,
        record: ConnectorRunCreate,
    ) -> ConnectorRun:
        connector_run = ConnectorRun(
            tenant_id=record.tenant_id,
            connector_id=record.connector_id,
            run_id=record.run_id,
            status=record.status,
            execution_mode=record.execution_mode,
            runtime_boundary=record.runtime_boundary,
            requested_by=record.requested_by,
            credential_handle_ids=record.credential_handle_ids,
            input_summary=record.input_summary,
            result_summary=record.result_summary,
            audit_event_id=record.audit_event_id,
            audit_event_type=record.audit_event_type,
            notes=record.notes,
        )
        self.session.add(connector_run)
        self.session.flush()
        return connector_run

    def list_connector_runs(
        self,
        tenant_id: str,
        connector_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ConnectorRun]:
        statement: Select[tuple[ConnectorRun]] = select(ConnectorRun).where(
            ConnectorRun.tenant_id == tenant_id
        )
        if connector_id is not None:
            statement = statement.where(ConnectorRun.connector_id == connector_id)
        if status is not None:
            statement = statement.where(ConnectorRun.status == status)

        statement = statement.order_by(
            ConnectorRun.created_at.desc(),
            ConnectorRun.id.desc(),
        ).limit(limit)
        return list(self.session.scalars(statement))

    def create_connector_ontology_proposal(
        self,
        record: ConnectorOntologyProposalCreate,
    ) -> ConnectorOntologyProposal:
        proposal = ConnectorOntologyProposal(
            tenant_id=record.tenant_id,
            connector_id=record.connector_id,
            proposal_id=record.proposal_id,
            source_run_id=record.source_run_id,
            source_file_name=record.source_file_name,
            mapping_profile=record.mapping_profile,
            status=record.status,
            write_mode=record.write_mode,
            graph_mutation_status=record.graph_mutation_status,
            proposed_by=record.proposed_by,
            node_id=record.node_id,
            node_type=record.node_type,
            ontology_type=record.ontology_type,
            field_summary=record.field_summary,
            evidence_refs=record.evidence_refs,
            promotion_id=record.promotion_id,
            policy_id=record.policy_id,
            policy_set_id=record.policy_set_id,
            policy_ids=record.policy_ids,
            policy_decision=record.policy_decision,
            promoted_by=record.promoted_by,
            ontology_mutation=record.ontology_mutation,
            audit_event_id=record.audit_event_id,
            audit_event_type=record.audit_event_type,
            notes=record.notes,
        )
        self.session.add(proposal)
        self.session.flush()
        return proposal

    def get_connector_ontology_proposal(
        self,
        tenant_id: str,
        proposal_id: str,
    ) -> ConnectorOntologyProposal | None:
        statement = select(ConnectorOntologyProposal).where(
            ConnectorOntologyProposal.tenant_id == tenant_id,
            ConnectorOntologyProposal.proposal_id == proposal_id,
        )
        return self.session.scalars(statement).first()

    def list_connector_ontology_proposals(
        self,
        tenant_id: str,
        connector_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ConnectorOntologyProposal]:
        statement: Select[tuple[ConnectorOntologyProposal]] = select(
            ConnectorOntologyProposal
        ).where(ConnectorOntologyProposal.tenant_id == tenant_id)
        if connector_id is not None:
            statement = statement.where(ConnectorOntologyProposal.connector_id == connector_id)
        if status is not None:
            statement = statement.where(ConnectorOntologyProposal.status == status)

        statement = statement.order_by(
            ConnectorOntologyProposal.created_at.desc(),
            ConnectorOntologyProposal.id.desc(),
        ).limit(limit)
        return list(self.session.scalars(statement))

    def create_connector_ontology_promotion(
        self,
        record: ConnectorOntologyPromotionCreate,
    ) -> ConnectorOntologyPromotion:
        promotion = ConnectorOntologyPromotion(
            tenant_id=record.tenant_id,
            connector_id=record.connector_id,
            promotion_id=record.promotion_id,
            idempotency_key=record.idempotency_key,
            proposal_id=record.proposal_id,
            manual_import_id=record.manual_import_id,
            status=record.status,
            promotion_mode=record.promotion_mode,
            requested_by=record.requested_by,
            graph_mutation_status=record.graph_mutation_status,
            ontology_mutation=record.ontology_mutation,
            permission_decision=record.permission_decision,
            policy_id=record.policy_id,
            policy_set_id=record.policy_set_id,
            policy_ids=record.policy_ids,
            policy_decision=record.policy_decision,
            audit_event_id=record.audit_event_id,
            audit_event_type=record.audit_event_type,
            notes=record.notes,
        )
        self.session.add(promotion)
        self.session.flush()
        return promotion

    def get_connector_ontology_promotion_by_idempotency_key(
        self,
        tenant_id: str,
        idempotency_key: str,
    ) -> ConnectorOntologyPromotion | None:
        statement = select(ConnectorOntologyPromotion).where(
            ConnectorOntologyPromotion.tenant_id == tenant_id,
            ConnectorOntologyPromotion.idempotency_key == idempotency_key,
        )
        return self.session.scalars(statement).first()

    def list_connector_ontology_promotions(
        self,
        tenant_id: str,
        proposal_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ConnectorOntologyPromotion]:
        statement: Select[tuple[ConnectorOntologyPromotion]] = select(
            ConnectorOntologyPromotion
        ).where(ConnectorOntologyPromotion.tenant_id == tenant_id)
        if proposal_id is not None:
            statement = statement.where(ConnectorOntologyPromotion.proposal_id == proposal_id)
        if status is not None:
            statement = statement.where(ConnectorOntologyPromotion.status == status)

        statement = statement.order_by(
            ConnectorOntologyPromotion.created_at.desc(),
            ConnectorOntologyPromotion.id.desc(),
        ).limit(limit)
        return list(self.session.scalars(statement))

    def record_connector_ontology_proposal_promotion(
        self,
        record: ConnectorOntologyPromotionResultRecord,
    ) -> ConnectorOntologyProposal:
        proposal = self.get_connector_ontology_proposal(record.tenant_id, record.proposal_id)
        if proposal is None:
            raise PersistenceRecordNotFound("Connector ontology proposal not found")

        proposal.status = record.status
        proposal.graph_mutation_status = record.graph_mutation_status
        proposal.promotion_id = record.promotion_id
        proposal.policy_id = record.policy_id
        proposal.policy_set_id = record.policy_set_id
        proposal.policy_ids = record.policy_ids
        proposal.policy_decision = record.policy_decision
        proposal.promoted_by = record.promoted_by
        proposal.promoted_at = utc_now()
        proposal.ontology_mutation = record.ontology_mutation
        if record.audit_event_id is not None:
            proposal.audit_event_id = record.audit_event_id
        if record.audit_event_type is not None:
            proposal.audit_event_type = record.audit_event_type
        proposal.updated_at = utc_now()
        self.session.flush()
        return proposal

    def create_connector_promotion_policy(
        self,
        record: ConnectorPromotionPolicyCreate,
    ) -> ConnectorPromotionPolicy:
        policy = ConnectorPromotionPolicy(
            tenant_id=record.tenant_id,
            connector_id=record.connector_id,
            policy_id=record.policy_id,
            policy_version=record.policy_version,
            status=record.status,
            enforcement_mode=record.enforcement_mode,
            created_by=record.created_by,
            required_authoring_scope=record.required_authoring_scope,
            required_scopes=record.required_scopes,
            required_manual_import_status=record.required_manual_import_status,
            required_workflow_signal_status=record.required_workflow_signal_status,
            allowed_risk_levels=record.allowed_risk_levels,
            allowed_ontology_types=record.allowed_ontology_types,
            review_window_hours=record.review_window_hours,
            permission_decision=record.permission_decision,
            audit_event_id=record.audit_event_id,
            audit_event_type=record.audit_event_type,
            revises_policy_id=record.revises_policy_id,
            replaced_by_policy_id=record.replaced_by_policy_id,
            revision_idempotency_key=record.revision_idempotency_key,
            revision_approval_id=record.revision_approval_id,
            revision_decision=record.revision_decision,
            revision_workflow_signal_status=record.revision_workflow_signal_status,
            notes=record.notes,
        )
        self.session.add(policy)
        self.session.flush()
        return policy

    def get_connector_promotion_policy(
        self,
        tenant_id: str,
        policy_id: str,
    ) -> ConnectorPromotionPolicy | None:
        statement = select(ConnectorPromotionPolicy).where(
            ConnectorPromotionPolicy.tenant_id == tenant_id,
            ConnectorPromotionPolicy.policy_id == policy_id,
        )
        return self.session.scalars(statement).first()

    def get_connector_promotion_policy_by_revision_idempotency_key(
        self,
        tenant_id: str,
        idempotency_key: str,
    ) -> ConnectorPromotionPolicy | None:
        statement = select(ConnectorPromotionPolicy).where(
            ConnectorPromotionPolicy.tenant_id == tenant_id,
            ConnectorPromotionPolicy.revision_idempotency_key == idempotency_key,
        )
        return self.session.scalars(statement).first()

    def revise_connector_promotion_policy(
        self,
        policy: ConnectorPromotionPolicy,
        record: ConnectorPromotionPolicyCreate,
    ) -> ConnectorPromotionPolicy:
        policy.status = "superseded"
        policy.replaced_by_policy_id = record.policy_id
        policy.updated_at = utc_now()
        revised_policy = self.create_connector_promotion_policy(record)
        self.session.flush()
        return revised_policy

    def enable_connector_promotion_policy(
        self,
        record: ConnectorPromotionPolicyEnableRecord,
    ) -> ConnectorPromotionPolicy:
        policy = self.get_connector_promotion_policy(record.tenant_id, record.policy_id)
        if policy is None:
            raise PersistenceRecordNotFound("Connector promotion policy not found")

        policy.status = record.status
        policy.enforcement_mode = record.enforcement_mode
        policy.permission_decision = record.permission_decision
        policy.audit_event_id = record.audit_event_id
        policy.audit_event_type = record.audit_event_type
        if record.note:
            policy.notes = [*policy.notes, record.note]
        policy.updated_at = utc_now()
        self.session.flush()
        return policy

    def adopt_connector_promotion_policy_revision(
        self,
        current_policy: ConnectorPromotionPolicy,
        revised_policy: ConnectorPromotionPolicy,
        *,
        audit_event_id: UUID,
        audit_event_type: str,
        note: str,
    ) -> ConnectorPromotionPolicy:
        current_policy.status = "superseded"
        current_policy.replaced_by_policy_id = revised_policy.policy_id
        current_policy.updated_at = utc_now()

        revised_policy.status = "enabled"
        revised_policy.enforcement_mode = "required"
        revised_policy.audit_event_id = audit_event_id
        revised_policy.audit_event_type = audit_event_type
        revised_policy.notes = [*revised_policy.notes, note]
        revised_policy.updated_at = utc_now()
        self.session.flush()
        return revised_policy

    def list_connector_promotion_policies(
        self,
        tenant_id: str,
        connector_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ConnectorPromotionPolicy]:
        statement: Select[tuple[ConnectorPromotionPolicy]] = select(
            ConnectorPromotionPolicy
        ).where(ConnectorPromotionPolicy.tenant_id == tenant_id)
        if connector_id is not None:
            statement = statement.where(ConnectorPromotionPolicy.connector_id == connector_id)
        if status is not None:
            statement = statement.where(ConnectorPromotionPolicy.status == status)

        statement = statement.order_by(
            ConnectorPromotionPolicy.created_at.desc(),
            ConnectorPromotionPolicy.id.desc(),
        ).limit(limit)
        return list(self.session.scalars(statement))

    def create_connector_promotion_policy_set(
        self,
        record: ConnectorPromotionPolicySetCreate,
    ) -> ConnectorPromotionPolicySet:
        policy_set = ConnectorPromotionPolicySet(
            tenant_id=record.tenant_id,
            connector_id=record.connector_id,
            policy_set_id=record.policy_set_id,
            policy_set_version=record.policy_set_version,
            status=record.status,
            activated_by=record.activated_by,
            activation_scope=record.activation_scope,
            policy_ids=record.policy_ids,
            permission_decision=record.permission_decision,
            audit_event_id=record.audit_event_id,
            audit_event_type=record.audit_event_type,
            activation_reason=record.activation_reason,
            replaces_policy_set_id=record.replaces_policy_set_id,
            replaced_by_policy_set_id=record.replaced_by_policy_set_id,
            replacement_approval_id=record.replacement_approval_id,
            replacement_decision=record.replacement_decision,
            replacement_workflow_signal_status=record.replacement_workflow_signal_status,
            replaced_at=record.replaced_at,
            rollback_to_policy_set_id=record.rollback_to_policy_set_id,
            rollback_approval_id=record.rollback_approval_id,
            rollback_decision=record.rollback_decision,
            rollback_workflow_signal_status=record.rollback_workflow_signal_status,
            policy_revision_adoptions=record.policy_revision_adoptions,
            notes=record.notes,
        )
        self.session.add(policy_set)
        self.session.flush()
        return policy_set

    def replace_connector_promotion_policy_set(
        self,
        active_policy_set: ConnectorPromotionPolicySet,
        record: ConnectorPromotionPolicySetCreate,
    ) -> ConnectorPromotionPolicySet:
        replaced_at = utc_now()
        active_policy_set.status = "superseded"
        active_policy_set.replaced_by_policy_set_id = record.policy_set_id
        active_policy_set.replacement_approval_id = (
            record.replacement_approval_id or record.rollback_approval_id
        )
        active_policy_set.replacement_decision = (
            record.replacement_decision or record.rollback_decision
        )
        active_policy_set.replacement_workflow_signal_status = (
            record.replacement_workflow_signal_status or record.rollback_workflow_signal_status
        )
        active_policy_set.replaced_at = replaced_at
        policy_set = self.create_connector_promotion_policy_set(
            record.model_copy(
                update={
                    "replaces_policy_set_id": active_policy_set.policy_set_id,
                    "replaced_at": None,
                }
            )
        )
        self.session.flush()
        return policy_set

    def get_connector_promotion_policy_set(
        self,
        tenant_id: str,
        policy_set_id: str,
    ) -> ConnectorPromotionPolicySet | None:
        statement = select(ConnectorPromotionPolicySet).where(
            ConnectorPromotionPolicySet.tenant_id == tenant_id,
            ConnectorPromotionPolicySet.policy_set_id == policy_set_id,
        )
        return self.session.scalars(statement).first()

    def list_connector_promotion_policy_sets(
        self,
        tenant_id: str,
        connector_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ConnectorPromotionPolicySet]:
        statement: Select[tuple[ConnectorPromotionPolicySet]] = select(
            ConnectorPromotionPolicySet
        ).where(ConnectorPromotionPolicySet.tenant_id == tenant_id)
        if connector_id is not None:
            statement = statement.where(ConnectorPromotionPolicySet.connector_id == connector_id)
        if status is not None:
            statement = statement.where(ConnectorPromotionPolicySet.status == status)

        statement = statement.order_by(
            ConnectorPromotionPolicySet.created_at.desc(),
            ConnectorPromotionPolicySet.id.desc(),
        ).limit(limit)
        return list(self.session.scalars(statement))

    def list_active_connector_promotion_policy_sets(
        self,
        tenant_id: str,
        connector_id: str,
    ) -> list[ConnectorPromotionPolicySet]:
        return self.list_connector_promotion_policy_sets(
            tenant_id=tenant_id,
            connector_id=connector_id,
            status="active",
            limit=20,
        )

    def create_connector_manual_import_request(
        self,
        record: ConnectorManualImportRequestCreate,
    ) -> ConnectorManualImportRequest:
        manual_import = ConnectorManualImportRequest(
            tenant_id=record.tenant_id,
            connector_id=record.connector_id,
            import_id=record.import_id,
            idempotency_key=record.idempotency_key,
            status=record.status,
            import_mode=record.import_mode,
            requested_by=record.requested_by,
            owner_role=record.owner_role,
            risk_level=record.risk_level,
            approval_id=record.approval_id,
            workflow_id=record.workflow_id,
            proposal_ids=record.proposal_ids,
            import_summary=record.import_summary,
            controls=record.controls,
            graph_mutation_status=record.graph_mutation_status,
            workflow_signal_status=record.workflow_signal_status,
            decision=record.decision,
            decision_actor_id=record.decision_actor_id,
            decision_note=record.decision_note,
            workflow_signal=record.workflow_signal,
            audit_event_id=record.audit_event_id,
            audit_event_type=record.audit_event_type,
            notes=record.notes,
        )
        self.session.add(manual_import)
        self.session.flush()
        return manual_import

    def get_connector_manual_import_request(
        self,
        tenant_id: str,
        import_id: str,
    ) -> ConnectorManualImportRequest | None:
        statement = select(ConnectorManualImportRequest).where(
            ConnectorManualImportRequest.tenant_id == tenant_id,
            ConnectorManualImportRequest.import_id == import_id,
        )
        return self.session.scalars(statement).first()

    def get_connector_manual_import_request_by_idempotency_key(
        self,
        tenant_id: str,
        idempotency_key: str,
    ) -> ConnectorManualImportRequest | None:
        statement = select(ConnectorManualImportRequest).where(
            ConnectorManualImportRequest.tenant_id == tenant_id,
            ConnectorManualImportRequest.idempotency_key == idempotency_key,
        )
        return self.session.scalars(statement).first()

    def list_connector_manual_import_requests(
        self,
        tenant_id: str,
        connector_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ConnectorManualImportRequest]:
        statement: Select[tuple[ConnectorManualImportRequest]] = select(
            ConnectorManualImportRequest
        ).where(ConnectorManualImportRequest.tenant_id == tenant_id)
        if connector_id is not None:
            statement = statement.where(ConnectorManualImportRequest.connector_id == connector_id)
        if status is not None:
            statement = statement.where(ConnectorManualImportRequest.status == status)

        statement = statement.order_by(
            ConnectorManualImportRequest.created_at.desc(),
            ConnectorManualImportRequest.id.desc(),
        ).limit(limit)
        return list(self.session.scalars(statement))

    def record_connector_manual_import_decision(
        self,
        record: ConnectorManualImportDecisionRecord,
    ) -> ConnectorManualImportRequest:
        manual_import = self.get_connector_manual_import_request(
            record.tenant_id,
            record.import_id,
        )
        if manual_import is None:
            raise PersistenceRecordNotFound("Connector manual import request not found")

        manual_import.status = record.status
        manual_import.decision = record.decision
        manual_import.decision_actor_id = record.decision_actor_id
        manual_import.decision_note = record.decision_note
        manual_import.decided_at = utc_now()
        manual_import.workflow_signal_status = record.workflow_signal_status
        manual_import.workflow_signal = record.workflow_signal
        if record.audit_event_id is not None:
            manual_import.audit_event_id = record.audit_event_id
        if record.audit_event_type is not None:
            manual_import.audit_event_type = record.audit_event_type
        manual_import.updated_at = utc_now()
        self.session.flush()
        return manual_import
