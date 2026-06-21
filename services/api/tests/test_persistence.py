import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from axis_api.audit import AuditEventCreate
from axis_api.models import ActionRun, ApprovalRecord, AuditEvent, Base
from axis_api.persistence import (
    ActionRunCreate,
    ActionRunResultRecord,
    ApprovalDecisionRecord,
    ApprovalRecordCreate,
    AxisPersistenceRepository,
    PersistenceRecordNotFound,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        yield session
    engine.dispose()


def test_persistence_metadata_exposes_foundation_tables() -> None:
    assert {"audit_events", "approval_records", "action_runs"}.issubset(
        Base.metadata.tables.keys()
    )
    assert ApprovalRecord.__table__.c.tenant_id.index is True
    assert ActionRun.__table__.c.idempotency_key.index is True
    assert AuditEvent.__table__.c.event_type.index is True


def test_repository_appends_audit_events_without_cross_tenant_leakage(session: Session) -> None:
    repository = AxisPersistenceRepository(session)
    first = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="axis-test",
            event_type="approval.created",
            payload={"approval_id": "appr_1"},
        )
    )
    repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_other",
            actor_id="axis-test",
            event_type="approval.created",
            payload={"approval_id": "appr_other"},
        )
    )

    events = repository.list_audit_events("tenant_demo_manufacturing")

    assert len(events) == 1
    assert events[0].id == first.id
    assert events[0].payload == {"approval_id": "appr_1"}


def test_repository_records_approval_decisions(session: Session) -> None:
    repository = AxisPersistenceRepository(session)
    approval = repository.create_approval_record(
        ApprovalRecordCreate(
            tenant_id="tenant_demo_manufacturing",
            approval_id="appr_expedite_supplier_batch",
            workflow_id="wf_supplier_delay_review",
            action_id="request_supplier_expedite",
            requested_by="agent_supply_risk",
            owner_role="plant-operations-owner",
            risk_level="high",
            payload={"required_permission": "approvals:supply:decide"},
        )
    )

    decided = repository.record_approval_decision(
        ApprovalDecisionRecord(
            tenant_id="tenant_demo_manufacturing",
            approval_id="appr_expedite_supplier_batch",
            decision="approved",
            decision_actor_id="plant-operations-owner-role",
            decision_note="Approved inside synthetic test scope.",
        )
    )

    assert decided.id == approval.id
    assert decided.status == "approved"
    assert decided.decision == "approved"
    assert decided.decision_actor_id == "plant-operations-owner-role"
    assert decided.decided_at is not None
    assert repository.list_approval_records("tenant_demo_manufacturing", status="approved") == [
        decided
    ]


def test_repository_raises_for_missing_approval_decision(session: Session) -> None:
    repository = AxisPersistenceRepository(session)

    with pytest.raises(PersistenceRecordNotFound, match="Approval record not found"):
        repository.record_approval_decision(
            ApprovalDecisionRecord(
                tenant_id="tenant_demo_manufacturing",
                approval_id="missing",
                decision="approved",
                decision_actor_id="plant-operations-owner-role",
            )
        )


def test_repository_records_action_runs_and_results(session: Session) -> None:
    repository = AxisPersistenceRepository(session)
    action_run = repository.create_action_run(
        ActionRunCreate(
            tenant_id="tenant_demo_manufacturing",
            action_id="request_supplier_expedite",
            idempotency_key="tenant_demo_manufacturing:request_supplier_expedite:appr_1",
            execution_mode="approval_gated_dry_run",
            requested_by="agent_supply_risk",
            approval_id="appr_expedite_supplier_batch",
            workflow_id="wf_supplier_delay_review",
            payload={"supplier_batch_id": "batch_motors_773"},
        )
    )

    found = repository.get_action_run_by_idempotency_key(
        "tenant_demo_manufacturing",
        "request_supplier_expedite",
        "tenant_demo_manufacturing:request_supplier_expedite:appr_1",
    )
    completed = repository.record_action_run_result(
        ActionRunResultRecord(
            tenant_id="tenant_demo_manufacturing",
            action_run_id=action_run.id,
            status="completed",
            result_payload={"dry_run": "recorded"},
        )
    )

    assert found == action_run
    assert completed.status == "completed"
    assert completed.result_payload == {"dry_run": "recorded"}
    assert repository.list_action_runs("tenant_demo_manufacturing", status="completed") == [
        completed
    ]


def test_action_run_idempotency_is_unique_per_tenant_action(session: Session) -> None:
    repository = AxisPersistenceRepository(session)
    payload = ActionRunCreate(
        tenant_id="tenant_demo_manufacturing",
        action_id="request_supplier_expedite",
        idempotency_key="duplicate-key",
        execution_mode="approval_gated_dry_run",
        requested_by="agent_supply_risk",
    )

    repository.create_action_run(payload)

    with pytest.raises(IntegrityError):
        repository.create_action_run(payload)
