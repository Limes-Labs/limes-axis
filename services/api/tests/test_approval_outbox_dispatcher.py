from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.approval_outbox import (
    OUTBOX_DEAD_LETTER_EVENT,
    OUTBOX_DELIVERED_EVENT,
    ApprovalDecisionOutboxDispatcher,
)
from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.models import ApprovalDecisionOutbox, AuditEvent, Base
from axis_api.persistence import ApprovalDecisionOutboxCreate, AxisPersistenceRepository
from axis_api.workflow_runtime import (
    APPROVAL_DECISION_SCHEMA_VERSION,
    APPROVAL_DECISION_SIGNAL_NAME,
    WorkflowSignalError,
    WorkflowSignalRequest,
    WorkflowSignalResult,
)

NOW = datetime(2026, 7, 18, 14, 0, tzinfo=UTC)


class RecordingRuntime:
    def __init__(self) -> None:
        self.requests: list[WorkflowSignalRequest] = []

    async def signal_approval_decision(
        self, request: WorkflowSignalRequest
    ) -> WorkflowSignalResult:
        self.requests.append(request)
        return WorkflowSignalResult(
            workflow_id=request.workflow_id,
            status="approval_signaled",
            adapter="test-runtime",
            signal_name=request.signal_name,
            payload=request.runtime_payload,
        )


class FailingRuntime:
    def __init__(self, *, may_be_closed: bool = False, result: dict | None = None) -> None:
        self.may_be_closed = may_be_closed
        self.result = result
        self.signal_calls = 0
        self.read_calls = 0

    async def signal_approval_decision(self, request: WorkflowSignalRequest) -> None:
        self.signal_calls += 1
        raise WorkflowSignalError("temporal_unavailable", may_be_closed=self.may_be_closed)

    async def get_approval_decision_result(self, workflow_id: str) -> dict | None:
        self.read_calls += 1
        return self.result


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


def _settings(*, max_attempts: int = 3) -> Settings:
    return Settings(
        postgres_dsn="sqlite+pysqlite://",
        approval_decision_outbox_dispatch_enabled=True,
        approval_decision_outbox_batch_size=10,
        approval_decision_outbox_claim_timeout_seconds=30,
        approval_decision_outbox_max_attempts=max_attempts,
        approval_decision_outbox_retry_base_seconds=4,
        approval_decision_outbox_retry_max_seconds=60,
    )


def _enqueue(
    factory: sessionmaker[Session],
    *,
    event_id: UUID | None = None,
    approval_id: str = "approval-dispatch",
    payload_overrides: dict | None = None,
    attempt_count: int = 0,
) -> UUID:
    resolved_event_id = event_id or uuid4()
    request = WorkflowSignalRequest(
        tenant_id="tenant-dispatch",
        workflow_id=f"workflow-{approval_id}",
        approval_id=approval_id,
        decision="request_changes",
        decision_event_id=resolved_event_id,
        actor_id="quality-owner",
        note="Please attach the missing evidence.",
    )
    payload = {**request.runtime_payload, **(payload_overrides or {})}
    with session_scope(factory) as session:
        row = AxisPersistenceRepository(session).create_approval_decision_outbox(
            ApprovalDecisionOutboxCreate(
                id=resolved_event_id,
                tenant_id=request.tenant_id,
                approval_id=request.approval_id,
                workflow_id=request.workflow_id,
                signal_name=APPROVAL_DECISION_SIGNAL_NAME,
                schema_version=APPROVAL_DECISION_SCHEMA_VERSION,
                decision=request.decision.value,
                decision_actor_id=request.actor_id or "",
                payload=payload,
                available_at=NOW,
            )
        )
        row.attempt_count = attempt_count
    return resolved_event_id


def _row(factory: sessionmaker[Session], event_id: UUID) -> ApprovalDecisionOutbox:
    with factory() as session:
        row = session.get(ApprovalDecisionOutbox, event_id)
        assert row is not None
        session.expunge(row)
        return row


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


async def test_dispatcher_delivers_valid_payload_and_writes_one_audit_event(
    session_factory: sessionmaker[Session],
) -> None:
    event_id = _enqueue(session_factory)
    runtime = RecordingRuntime()
    dispatcher = ApprovalDecisionOutboxDispatcher(
        settings=_settings(),
        session_factory=session_factory,
        workflow_runtime=runtime,
        clock=lambda: NOW,
    )

    result = await dispatcher.run_once()
    second = await dispatcher.run_once()

    assert result.model_dump() == {
        "claimed": 1,
        "delivered": 1,
        "retried": 0,
        "dead_lettered": 0,
        "fenced": 0,
    }
    assert second.claimed == 0
    assert len(runtime.requests) == 1
    assert runtime.requests[0].decision_event_id == event_id
    assert runtime.requests[0].decision.value == "request_changes"
    persisted = _row(session_factory, event_id)
    assert persisted.status == "delivered"
    assert persisted.attempt_count == 1
    assert _as_utc(persisted.delivered_at) == NOW
    with session_factory() as session:
        audits = list(session.scalars(select(AuditEvent)))
    assert len(audits) == 1
    assert audits[0].event_type == OUTBOX_DELIVERED_EVENT
    assert audits[0].payload["decision_event_id"] == str(event_id)


async def test_transient_failure_is_retried_with_bounded_exponential_backoff(
    session_factory: sessionmaker[Session],
) -> None:
    event_id = _enqueue(session_factory)
    runtime = FailingRuntime()
    dispatcher = ApprovalDecisionOutboxDispatcher(
        settings=_settings(),
        session_factory=session_factory,
        workflow_runtime=runtime,
        clock=lambda: NOW,
        random_uniform=lambda _low, maximum: maximum,
    )

    result = await dispatcher.run_once()

    assert result.retried == 1
    assert result.dead_lettered == 0
    persisted = _row(session_factory, event_id)
    assert persisted.status == "pending"
    assert persisted.attempt_count == 1
    assert persisted.last_error == "workflow_signal_error"
    assert _as_utc(persisted.available_at) == NOW + timedelta(seconds=4)
    assert persisted.dead_lettered_at is None
    with session_factory() as session:
        assert list(session.scalars(select(AuditEvent))) == []


async def test_max_attempt_failure_dead_letters_without_another_retry(
    session_factory: sessionmaker[Session],
) -> None:
    event_id = _enqueue(session_factory, attempt_count=2)
    dispatcher = ApprovalDecisionOutboxDispatcher(
        settings=_settings(max_attempts=3),
        session_factory=session_factory,
        workflow_runtime=FailingRuntime(),
        clock=lambda: NOW,
        random_uniform=lambda _low, maximum: maximum,
    )

    result = await dispatcher.run_once()

    assert result.dead_lettered == 1
    persisted = _row(session_factory, event_id)
    assert persisted.status == "dead_letter"
    assert persisted.attempt_count == 3
    assert _as_utc(persisted.available_at) == NOW
    assert _as_utc(persisted.dead_lettered_at) == NOW
    with session_factory() as session:
        audit = session.scalars(select(AuditEvent)).one()
    assert audit.event_type == OUTBOX_DEAD_LETTER_EVENT
    assert audit.payload["attempt_count"] == 3
    assert audit.payload["error_code"] == "workflow_signal_error"


async def test_invalid_payload_is_dead_lettered_without_secret_material_or_runtime_call(
    session_factory: sessionmaker[Session],
) -> None:
    secret = "customer-secret-token-123"
    event_id = _enqueue(
        session_factory,
        payload_overrides={"decision_event_id": str(uuid4()), "note": secret},
    )
    runtime = RecordingRuntime()
    dispatcher = ApprovalDecisionOutboxDispatcher(
        settings=_settings(),
        session_factory=session_factory,
        workflow_runtime=runtime,
        clock=lambda: NOW,
    )

    result = await dispatcher.run_once()

    assert result.dead_lettered == 1
    assert runtime.requests == []
    persisted = _row(session_factory, event_id)
    assert persisted.status == "dead_letter"
    assert persisted.last_error == "payload_row_mismatch"
    assert secret not in (persisted.last_error or "")
    with session_factory() as session:
        audit = session.scalars(select(AuditEvent)).one()
    assert audit.payload["error_code"] == "payload_row_mismatch"
    assert secret not in str(audit.payload)


async def test_closed_workflow_with_matching_event_is_reconciled_as_delivered(
    session_factory: sessionmaker[Session],
) -> None:
    event_id = _enqueue(session_factory)
    runtime = FailingRuntime(
        may_be_closed=True,
        result={"decision": _row(session_factory, event_id).payload},
    )
    dispatcher = ApprovalDecisionOutboxDispatcher(
        settings=_settings(),
        session_factory=session_factory,
        workflow_runtime=runtime,
        clock=lambda: NOW,
    )

    result = await dispatcher.run_once()

    assert result.delivered == 1
    assert runtime.signal_calls == 1
    assert runtime.read_calls == 1
    assert _row(session_factory, event_id).status == "delivered"


async def test_closed_workflow_with_conflicting_event_is_permanently_dead_lettered(
    session_factory: sessionmaker[Session],
) -> None:
    event_id = _enqueue(session_factory)
    conflicting = {**_row(session_factory, event_id).payload, "note": "mutated evidence"}
    runtime = FailingRuntime(may_be_closed=True, result={"decision": conflicting})
    dispatcher = ApprovalDecisionOutboxDispatcher(
        settings=_settings(),
        session_factory=session_factory,
        workflow_runtime=runtime,
        clock=lambda: NOW,
    )

    result = await dispatcher.run_once()

    assert result.dead_lettered == 1
    persisted = _row(session_factory, event_id)
    assert persisted.status == "dead_letter"
    assert persisted.last_error == "completed_workflow_conflict"
    assert persisted.attempt_count == 1
