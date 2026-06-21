from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from axis_api.audit import AuditEventCreate
from axis_api.models import ActionRun, ApprovalRecord, AuditEvent, utc_now


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
