from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.manufacturing_operations import (
    MaintenanceRiskScenarioIdempotencyConflict,
    MaintenanceRiskScenarioPermissionDenied,
    MaintenanceRiskScenarioRequest,
    MaintenanceRiskScenarioValidationError,
    generate_maintenance_risk_scenario,
)
from axis_api.models import AuditEvent, Base, ManufacturingRiskScenario
from axis_api.persistence import AxisPersistenceRepository, ManufacturingOperationRecordCreate


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


def seed_maintenance_operations(repository: AxisPersistenceRepository) -> None:
    repository.create_manufacturing_operation_record(
        ManufacturingOperationRecordCreate(
            tenant_id="tenant_demo_manufacturing",
            record_id="press_4_vibration_watch",
            domain="Maintenance",
            record_type="asset_condition",
            source_system="CMMS",
            status="watch",
            owner_role="maintenance-planner",
            related_asset="asset_press_4",
            workflow_id="wf_press_4_maintenance_review",
            risk_level="medium",
            occurred_at=datetime(2026, 6, 21, 14, 5, tzinfo=UTC),
            payload={
                "asset": "Press 4",
                "vibration_mm_s": 7.4,
                "planned_window": "night_shift",
            },
            evidence_refs=["cmms:asset:press-4", "mes:line:press-cell"],
        )
    )
    repository.create_manufacturing_operation_record(
        ManufacturingOperationRecordCreate(
            tenant_id="tenant_demo_manufacturing",
            record_id="batch_q_1842_quality",
            domain="Quality",
            record_type="quality_batch",
            source_system="QMS",
            status="action_required",
            owner_role="quality-owner",
            occurred_at=datetime(2026, 6, 21, 13, 35, tzinfo=UTC),
            payload={"batch": "Q-1842"},
            evidence_refs=["qms:inspection:Q-1842"],
        )
    )
    repository.create_manufacturing_operation_record(
        ManufacturingOperationRecordCreate(
            tenant_id="tenant_other",
            record_id="other_maintenance",
            domain="Maintenance",
            record_type="asset_condition",
            source_system="CMMS",
            status="action_required",
            owner_role="other-maintenance-owner",
            occurred_at=datetime(2026, 6, 21, 12, 0, tzinfo=UTC),
            payload={"asset": "Other"},
            evidence_refs=["cmms:asset:other"],
        )
    )


def maintenance_request(**overrides) -> MaintenanceRiskScenarioRequest:
    payload = {
        "tenant_id": "tenant_demo_manufacturing",
        "requested_by": "agent_maintenance_risk",
        "actor_scopes": ["maintenance:read", "workflows:read", "audit:read"],
    }
    payload.update(overrides)
    return MaintenanceRiskScenarioRequest(**payload)


def test_generate_maintenance_risk_scenario_persists_audit_backed_artifact(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_maintenance_operations(repository)
        scenario = generate_maintenance_risk_scenario(repository, maintenance_request())

    assert scenario.domain == "Maintenance"
    assert scenario.risk_level == "medium"
    assert scenario.owner_role == "maintenance-planner"
    assert scenario.workflow_ids == ["wf_press_4_maintenance_review"]
    assert scenario.source_record_ids == ["press_4_vibration_watch"]
    assert scenario.permission_decision.allowed is True
    assert scenario.audit_event_type == "manufacturing.risk_scenario.generated"
    assert scenario.scenario_payload["generation_boundary"] == (
        "deterministic_persisted_maintenance_records"
    )
    assert scenario.scenario_payload["cited_evidence"] == [
        "cmms:asset:press-4",
        "mes:line:press-cell",
    ]
    assert "tenant_other" not in scenario.model_dump_json()
    assert "password" not in scenario.model_dump_json().lower()
    assert "secret" not in scenario.model_dump_json().lower()

    with session_factory() as session:
        assert len(list(session.scalars(select(ManufacturingRiskScenario)))) == 1
        audit_event = session.scalars(select(AuditEvent)).one()
        assert audit_event.event_type == "manufacturing.risk_scenario.generated"
        assert audit_event.payload["domain"] == "Maintenance"
        assert audit_event.payload["risk_level"] == "medium"


def test_generate_maintenance_risk_scenario_is_idempotent_but_rechecks_permissions(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_maintenance_operations(repository)
        first = generate_maintenance_risk_scenario(repository, maintenance_request())
        second = generate_maintenance_risk_scenario(repository, maintenance_request())
        with pytest.raises(MaintenanceRiskScenarioPermissionDenied):
            generate_maintenance_risk_scenario(
                repository,
                maintenance_request(actor_scopes=["maintenance:read", "audit:read"]),
            )

    assert second.idempotent_replay is True
    assert second.scenario_id == first.scenario_id
    with session_factory() as session:
        assert len(list(session.scalars(select(ManufacturingRiskScenario)))) == 1
        assert len(list(session.scalars(select(AuditEvent)))) == 1


def test_generate_maintenance_risk_scenario_rejects_missing_source_records(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_maintenance_operations(repository)
        with pytest.raises(MaintenanceRiskScenarioValidationError) as exc_info:
            generate_maintenance_risk_scenario(
                repository,
                maintenance_request(source_record_ids=["missing_maintenance_record"]),
            )

    assert exc_info.value.reason == "missing_source_records:missing_maintenance_record"


def test_generate_maintenance_risk_scenario_detects_idempotency_conflict(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_maintenance_operations(repository)
        generate_maintenance_risk_scenario(
            repository,
            maintenance_request(
                idempotency_key="maintenance-risk-key",
                source_record_ids=["press_4_vibration_watch"],
            ),
        )
        with pytest.raises(MaintenanceRiskScenarioIdempotencyConflict):
            generate_maintenance_risk_scenario(
                repository,
                maintenance_request(
                    idempotency_key="maintenance-risk-key",
                    source_record_ids=[],
                ),
            )


def test_maintenance_risk_scenario_endpoint_returns_created_then_idempotent_replay(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        seed_maintenance_operations(AxisPersistenceRepository(session))

    client = TestClient(app)
    payload = maintenance_request(idempotency_key="maintenance-risk-endpoint").model_dump()
    first = client.post(
        "/demo/manufacturing/operations/risk-scenarios/maintenance",
        json=payload,
    )
    second = client.post(
        "/demo/manufacturing/operations/risk-scenarios/maintenance",
        json=payload,
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["scenario_id"] == second.json()["scenario_id"]
    assert first.json()["scenario_payload"]["domain"] == "Maintenance"
    assert second.json()["idempotent_replay"] is True
