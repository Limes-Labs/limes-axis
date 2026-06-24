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
    QualityRiskScenarioIdempotencyConflict,
    QualityRiskScenarioPermissionDenied,
    QualityRiskScenarioRequest,
    QualityRiskScenarioValidationError,
    generate_quality_risk_scenario,
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


def seed_quality_operations(repository: AxisPersistenceRepository) -> None:
    repository.create_manufacturing_operation_record(
        ManufacturingOperationRecordCreate(
            tenant_id="tenant_demo_manufacturing",
            record_id="batch_q_1842_quality",
            domain="Quality",
            record_type="quality_batch",
            source_system="QMS",
            status="watch",
            owner_role="quality-owner",
            related_asset="asset_batch_q_1842",
            workflow_id="wf_quality_hold_review",
            risk_level="high",
            occurred_at=datetime(2026, 6, 21, 13, 35, tzinfo=UTC),
            payload={
                "batch": "Q-1842",
                "inspection_variance_ppm": 37,
                "deviation_waiver": "not_released",
            },
            evidence_refs=["qms:inspection:Q-1842", "mes:batch_genealogy:Q-1842"],
        )
    )
    repository.create_manufacturing_operation_record(
        ManufacturingOperationRecordCreate(
            tenant_id="tenant_demo_manufacturing",
            record_id="order_rush_4812",
            domain="Production",
            record_type="production_order",
            source_system="ERP",
            status="action_required",
            owner_role="plant-operations-owner",
            occurred_at=datetime(2026, 6, 21, 13, 45, tzinfo=UTC),
            payload={"order_number": "PO-4812"},
            evidence_refs=["erp:orders:PO-4812"],
        )
    )
    repository.create_manufacturing_operation_record(
        ManufacturingOperationRecordCreate(
            tenant_id="tenant_other",
            record_id="other_quality",
            domain="Quality",
            record_type="quality_batch",
            source_system="QMS",
            status="action_required",
            owner_role="other-quality-owner",
            occurred_at=datetime(2026, 6, 21, 12, 0, tzinfo=UTC),
            payload={"batch": "OTHER"},
            evidence_refs=["qms:inspection:OTHER"],
        )
    )


def quality_request(**overrides) -> QualityRiskScenarioRequest:
    payload = {
        "tenant_id": "tenant_demo_manufacturing",
        "requested_by": "agent_quality_risk",
        "actor_scopes": ["quality:read", "workflows:read", "audit:read"],
    }
    payload.update(overrides)
    return QualityRiskScenarioRequest(**payload)


def test_generate_quality_risk_scenario_persists_audit_backed_artifact(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_quality_operations(repository)
        scenario = generate_quality_risk_scenario(repository, quality_request())

    assert scenario.domain == "Quality"
    assert scenario.risk_level == "high"
    assert scenario.owner_role == "quality-owner"
    assert scenario.workflow_ids == ["wf_quality_hold_review"]
    assert scenario.source_record_ids == ["batch_q_1842_quality"]
    assert scenario.permission_decision.allowed is True
    assert scenario.audit_event_type == "manufacturing.risk_scenario.generated"
    assert scenario.scenario_payload["generation_boundary"] == (
        "deterministic_persisted_quality_records"
    )
    assert scenario.scenario_payload["cited_evidence"] == [
        "mes:batch_genealogy:Q-1842",
        "qms:inspection:Q-1842",
    ]
    assert "tenant_other" not in scenario.model_dump_json()
    assert "password" not in scenario.model_dump_json().lower()
    assert "secret" not in scenario.model_dump_json().lower()

    with session_factory() as session:
        assert len(list(session.scalars(select(ManufacturingRiskScenario)))) == 1
        audit_event = session.scalars(select(AuditEvent)).one()
        assert audit_event.event_type == "manufacturing.risk_scenario.generated"
        assert audit_event.payload["domain"] == "Quality"
        assert audit_event.payload["risk_level"] == "high"


def test_generate_quality_risk_scenario_is_idempotent_but_rechecks_permissions(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_quality_operations(repository)
        first = generate_quality_risk_scenario(repository, quality_request())
        second = generate_quality_risk_scenario(repository, quality_request())
        with pytest.raises(QualityRiskScenarioPermissionDenied):
            generate_quality_risk_scenario(
                repository,
                quality_request(actor_scopes=["quality:read", "audit:read"]),
            )

    assert second.idempotent_replay is True
    assert second.scenario_id == first.scenario_id
    with session_factory() as session:
        assert len(list(session.scalars(select(ManufacturingRiskScenario)))) == 1
        assert len(list(session.scalars(select(AuditEvent)))) == 1


def test_generate_quality_risk_scenario_rejects_missing_source_records(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_quality_operations(repository)
        with pytest.raises(QualityRiskScenarioValidationError) as exc_info:
            generate_quality_risk_scenario(
                repository,
                quality_request(source_record_ids=["missing_quality_record"]),
            )

    assert exc_info.value.reason == "missing_source_records:missing_quality_record"


def test_generate_quality_risk_scenario_detects_idempotency_conflict(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_quality_operations(repository)
        generate_quality_risk_scenario(
            repository,
            quality_request(
                idempotency_key="quality-risk-key",
                source_record_ids=["batch_q_1842_quality"],
            ),
        )
        with pytest.raises(QualityRiskScenarioIdempotencyConflict):
            generate_quality_risk_scenario(
                repository,
                quality_request(
                    idempotency_key="quality-risk-key",
                    source_record_ids=[],
                ),
            )


def test_quality_risk_scenario_endpoint_returns_created_then_idempotent_replay(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        seed_quality_operations(AxisPersistenceRepository(session))

    client = TestClient(app)
    payload = quality_request(idempotency_key="quality-risk-endpoint").model_dump()
    first = client.post("/demo/manufacturing/operations/risk-scenarios/quality", json=payload)
    second = client.post("/demo/manufacturing/operations/risk-scenarios/quality", json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["scenario_id"] == second.json()["scenario_id"]
    assert first.json()["scenario_payload"]["domain"] == "Quality"
    assert second.json()["idempotent_replay"] is True
