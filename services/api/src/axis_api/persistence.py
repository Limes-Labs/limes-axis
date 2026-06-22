from datetime import datetime
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
