from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.db import session_scope
from axis_api.models import ApprovalDecisionOutbox, Base
from axis_api.persistence import ApprovalDecisionOutboxCreate, AxisPersistenceRepository
from axis_api.workflow_runtime import (
    APPROVAL_DECISION_SCHEMA_VERSION,
    APPROVAL_DECISION_SIGNAL_NAME,
    WorkflowSignalRequest,
)

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


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


def _create(
    repository: AxisPersistenceRepository,
    *,
    approval_id: str,
    available_at: datetime,
    event_id: UUID | None = None,
) -> ApprovalDecisionOutbox:
    resolved_event_id = event_id or uuid4()
    request = WorkflowSignalRequest(
        tenant_id="tenant_outbox",
        workflow_id=f"workflow_{approval_id}",
        approval_id=approval_id,
        decision="approve",
        decision_event_id=resolved_event_id,
        actor_id="owner-role",
    )
    return repository.create_approval_decision_outbox(
        ApprovalDecisionOutboxCreate(
            id=resolved_event_id,
            tenant_id=request.tenant_id,
            approval_id=request.approval_id,
            workflow_id=request.workflow_id,
            signal_name=APPROVAL_DECISION_SIGNAL_NAME,
            schema_version=APPROVAL_DECISION_SCHEMA_VERSION,
            decision=request.decision.value,
            decision_actor_id=request.actor_id or "",
            payload=request.runtime_payload,
            available_at=available_at,
        )
    )


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def test_claim_selects_due_and_expired_leases_but_not_future_rows(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        _create(repository, approval_id="due", available_at=NOW)
        future = _create(repository, approval_id="future", available_at=NOW + timedelta(minutes=1))
        stale = _create(repository, approval_id="stale", available_at=NOW - timedelta(minutes=5))
        stale.status = "dispatching"
        stale.attempt_count = 3
        stale.claim_token = uuid4()
        stale.claimed_at = NOW - timedelta(minutes=2)
        stale.lease_expires_at = NOW - timedelta(seconds=1)
        session.flush()

    with session_scope(session_factory) as session:
        claimed = AxisPersistenceRepository(session).claim_approval_decision_outbox(
            now=NOW,
            lease_expires_at=NOW + timedelta(seconds=30),
            limit=10,
        )
        by_approval = {row.approval_id: row for row in claimed}
        assert set(by_approval) == {"due", "stale"}
        assert by_approval["due"].attempt_count == 1
        assert by_approval["stale"].attempt_count == 4
        assert all(row.status == "dispatching" for row in claimed)
        assert all(row.claim_token is not None for row in claimed)
        assert all(_as_utc(row.last_attempt_at) == NOW for row in claimed)
        assert all(_as_utc(row.lease_expires_at) == NOW + timedelta(seconds=30) for row in claimed)

    with session_factory() as session:
        persisted_future = session.scalar(
            select(ApprovalDecisionOutbox).where(ApprovalDecisionOutbox.id == future.id)
        )
        assert persisted_future is not None
        assert persisted_future.status == "pending"
        assert persisted_future.attempt_count == 0


def test_completion_and_retry_are_fenced_by_the_current_claim_token(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        row = _create(AxisPersistenceRepository(session), approval_id="fenced", available_at=NOW)
        row_id = row.id
    with session_scope(session_factory) as session:
        claimed = AxisPersistenceRepository(session).claim_approval_decision_outbox(
            now=NOW,
            lease_expires_at=NOW + timedelta(seconds=30),
            limit=1,
        )[0]
        claim_token = claimed.claim_token
        assert claim_token is not None

    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        assert repository.complete_approval_decision_outbox(
            row_id, uuid4(), delivered_at=NOW + timedelta(seconds=1)
        ) is False
        assert repository.retry_approval_decision_outbox(
            row_id,
            uuid4(),
            available_at=NOW + timedelta(seconds=10),
            updated_at=NOW + timedelta(seconds=1),
            error="wrong lease",
            dead_letter=False,
        ) is False

    with session_scope(session_factory) as session:
        assert AxisPersistenceRepository(session).complete_approval_decision_outbox(
            row_id, claim_token, delivered_at=NOW + timedelta(seconds=2)
        ) is True

    with session_factory() as session:
        delivered = session.get(ApprovalDecisionOutbox, row_id)
        assert delivered is not None
        assert delivered.status == "delivered"
        assert delivered.claim_token is None
        assert delivered.claimed_at is None
        assert delivered.lease_expires_at is None
        assert _as_utc(delivered.delivered_at) == NOW + timedelta(seconds=2)


@pytest.mark.parametrize(
    ("dead_letter", "expected_status"),
    [(False, "pending"), (True, "dead_letter")],
)
def test_retry_records_timestamp_error_and_dead_letter_state(
    session_factory: sessionmaker[Session], dead_letter: bool, expected_status: str
) -> None:
    approval_id = f"retry-{dead_letter}"
    with session_scope(session_factory) as session:
        row = _create(
            AxisPersistenceRepository(session), approval_id=approval_id, available_at=NOW
        )
        row_id = row.id
    with session_scope(session_factory) as session:
        claimed = AxisPersistenceRepository(session).claim_approval_decision_outbox(
            now=NOW,
            lease_expires_at=NOW + timedelta(seconds=30),
            limit=1,
        )[0]
        token = claimed.claim_token
        assert token is not None
    retry_at = NOW + timedelta(seconds=17)
    updated_at = NOW + timedelta(seconds=2)
    with session_scope(session_factory) as session:
        changed = AxisPersistenceRepository(session).retry_approval_decision_outbox(
            row_id,
            token,
            available_at=retry_at,
            updated_at=updated_at,
            error="x" * 300,
            dead_letter=dead_letter,
        )
        assert changed is True

    with session_factory() as session:
        row = session.get(ApprovalDecisionOutbox, row_id)
        assert row is not None
        assert row.status == expected_status
        assert row.claim_token is None
        assert _as_utc(row.available_at) == retry_at
        assert _as_utc(row.last_attempt_at) == NOW
        assert len(row.last_error or "") == 200
        expected_dead_lettered_at = updated_at if dead_letter else None
        assert _as_utc(row.dead_lettered_at) == expected_dead_lettered_at


def test_database_constraints_reject_duplicate_approval_and_invalid_status(
    session_factory: sessionmaker[Session],
) -> None:
    with pytest.raises(IntegrityError), session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        _create(repository, approval_id="duplicate", available_at=NOW)
        _create(repository, approval_id="duplicate", available_at=NOW)

    with pytest.raises(IntegrityError), session_scope(session_factory) as session:
        row = _create(
            AxisPersistenceRepository(session),
            approval_id="bad",
            available_at=NOW,
        )
        row.status = "invented"
