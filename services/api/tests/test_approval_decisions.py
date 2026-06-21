import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.approval_decisions import ApprovalDecisionRequest, record_demo_approval_decision
from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.demo import ApprovalDecision
from axis_api.main import create_app
from axis_api.models import ApprovalRecord, AuditEvent, Base
from axis_api.persistence import AxisPersistenceRepository


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


def test_record_demo_approval_decision_persists_approval_and_audit_event(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        result = record_demo_approval_decision(
            repository,
            "appr_expedite_supplier_batch",
            ApprovalDecisionRequest(
                decision=ApprovalDecision.APPROVE,
                actor_id="plant-operations-owner-role",
                note="Approved in synthetic test scope.",
            ),
        )

    with session_factory() as session:
        approval = session.scalars(select(ApprovalRecord)).one()
        audit_event = session.scalars(select(AuditEvent)).one()

    assert result.persisted is True
    assert result.workflow_signal_status == "pending_runtime_signal"
    assert result.action_id == "request_supplier_expedite"
    assert result.audit_event_id == audit_event.id
    assert approval.status == "approve"
    assert approval.decision_actor_id == "plant-operations-owner-role"
    assert approval.decided_at is not None
    assert audit_event.event_type == "approval.decision.recorded"
    assert audit_event.payload["approval_id"] == "appr_expedite_supplier_batch"
    assert audit_event.payload["decision"] == "approve"
    assert audit_event.payload["decision_note_recorded"] == "true"


def test_record_demo_approval_decision_reuses_existing_approval_record(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        record_demo_approval_decision(
            repository,
            "appr_quality_hold_batch",
            ApprovalDecisionRequest(
                decision=ApprovalDecision.REQUEST_CHANGES,
                actor_id="quality-owner-role",
            ),
        )
        record_demo_approval_decision(
            repository,
            "appr_quality_hold_batch",
            ApprovalDecisionRequest(
                decision=ApprovalDecision.REJECT,
                actor_id="quality-owner-role",
            ),
        )

    with session_factory() as session:
        approvals = list(session.scalars(select(ApprovalRecord)))
        audit_events = list(session.scalars(select(AuditEvent)))

    assert len(approvals) == 1
    assert approvals[0].status == "reject"
    assert len(audit_events) == 2


def test_approval_decision_endpoint_persists_result(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/approvals/appr_shift_maintenance_window/decision",
        json={
            "decision": "approve",
            "actor_id": "maintenance-owner-role",
            "note": "Approved in synthetic endpoint test.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["approval_id"] == "appr_shift_maintenance_window"
    assert body["action_id"] == "shift_maintenance_window"
    assert body["audit_event_type"] == "approval.decision.recorded"
    assert body["workflow_signal_status"] == "pending_runtime_signal"

    with session_factory() as session:
        approval = session.scalars(select(ApprovalRecord)).one()
        audit_event = session.scalars(select(AuditEvent)).one()

    assert approval.status == "approve"
    assert approval.decision_actor_id == "maintenance-owner-role"
    assert audit_event.actor_id == "maintenance-owner-role"


def test_approval_decision_endpoint_handles_missing_approval(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/approvals/missing/decision",
        json={"decision": "approve", "actor_id": "plant-operations-owner-role"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Approval not found"


def test_openapi_exposes_approval_decision_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/demo/manufacturing/approvals/{approval_id}/decision" in response.json()["paths"]
