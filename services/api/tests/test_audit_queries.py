import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.audit import AuditEventCreate
from axis_api.audit_queries import AuditEventQuery, query_persisted_audit_events
from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.models import Base
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


def seed_audit_events(repository: AxisPersistenceRepository) -> None:
    repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="agent_supply_risk",
            event_type="action.proposal.created",
            payload={
                "action_id": "request_supplier_expedite",
                "action_run_id": "act_run_supply_1",
                "workflow_id": "wf_supplier_delay_review",
                "approval_id": "appr_expedite_supplier_batch",
                "status": "approval_required",
                "execution_mode": "approval_gated_dry_run",
                "risk_level": "high",
                "approval_required": True,
                "permission_decision": {"allowed": True, "reason": "allowed"},
                "payload_field_names": ["supplier_batch_id", "target_arrival"],
            },
        )
    )
    repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="plant-operations-owner-role",
            event_type="approval.decision.recorded",
            payload={
                "approval_id": "appr_expedite_supplier_batch",
                "workflow_id": "wf_supplier_delay_review",
                "action_id": "request_supplier_expedite",
                "decision": "approve",
                "required_permission": "approvals:supply:decide",
                "permission_decision": {"allowed": True, "reason": "allowed"},
                "workflow_signal": {
                    "status": "approval_signaled",
                    "adapter": "axis-temporal-adapter",
                },
            },
        )
    )
    repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_other",
            actor_id="other-actor",
            event_type="approval.decision.recorded",
            payload={"approval_id": "appr_other", "decision": "approve"},
        )
    )


def test_query_persisted_audit_events_maps_records_to_public_explorer(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_audit_events(repository)
        explorer = query_persisted_audit_events(
            repository,
            AuditEventQuery(tenant_id="tenant_demo_manufacturing"),
        )

    assert explorer.tenant_id == "tenant_demo_manufacturing"
    assert explorer.ledger_status == "ready"
    assert explorer.metrics[0].label == "Persisted Events"
    assert explorer.metrics[0].value == "2"
    assert len(explorer.events) == 2
    assert {event.tenant_id for event in explorer.events} == {"tenant_demo_manufacturing"}
    assert "approval.decision.recorded" in explorer.filter_options.event_types
    assert "agent_supply_risk" in explorer.filter_options.actors
    assert "wf_supplier_delay_review" in explorer.filter_options.scopes
    first = explorer.events[0]
    assert first.audit_event_id
    assert first.data_classification == "public-demo"
    assert first.payload_preview
    assert "password" not in explorer.model_dump_json().lower()
    assert "secret" not in explorer.model_dump_json().lower()


def test_query_persisted_audit_events_filters_by_event_actor_and_scope(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_audit_events(repository)
        by_event = query_persisted_audit_events(
            repository,
            AuditEventQuery(
                tenant_id="tenant_demo_manufacturing",
                event_type="action.proposal.created",
            ),
        )
        by_actor = query_persisted_audit_events(
            repository,
            AuditEventQuery(
                tenant_id="tenant_demo_manufacturing",
                actor_id="plant-operations-owner-role",
            ),
        )
        by_scope = query_persisted_audit_events(
            repository,
            AuditEventQuery(
                tenant_id="tenant_demo_manufacturing",
                scope="wf_supplier_delay_review",
            ),
        )
        empty = query_persisted_audit_events(
            repository,
            AuditEventQuery(
                tenant_id="tenant_demo_manufacturing",
                scope="missing-scope",
            ),
        )

    assert [event.event_type for event in by_event.events] == ["action.proposal.created"]
    assert [event.actor_id for event in by_actor.events] == ["plant-operations-owner-role"]
    assert len(by_scope.events) == 2
    assert empty.events == []
    assert empty.filter_options.tenants == ["tenant_demo_manufacturing"]


def test_persisted_audit_events_endpoint_returns_tenant_scoped_query(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        seed_audit_events(AxisPersistenceRepository(session))
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/audit/events",
        params={
            "tenant_id": "tenant_demo_manufacturing",
            "event_type": "approval.decision.recorded",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["metrics"][0]["value"] == "1"
    assert body["events"][0]["event_type"] == "approval.decision.recorded"
    assert body["events"][0]["related_approval_id"] == "appr_expedite_supplier_batch"
    assert "tenant_other" not in str(body)


def test_persisted_audit_events_endpoint_returns_empty_result_for_empty_query(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    response = client.get("/demo/manufacturing/audit/events")

    assert response.status_code == 200
    body = response.json()
    assert body["events"] == []
    assert body["filter_options"]["tenants"] == ["tenant_demo_manufacturing"]
    assert body["ledger_status"] == "watch"


def test_openapi_exposes_persisted_audit_events_endpoint() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/demo/manufacturing/audit/events" in response.json()["paths"]
