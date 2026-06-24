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
    SupplierDelayScenarioIdempotencyConflict,
    SupplierDelayScenarioPermissionDenied,
    SupplierDelayScenarioRequest,
    SupplierDelayScenarioValidationError,
    generate_supplier_delay_scenario,
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


def seed_supply_operations(repository: AxisPersistenceRepository) -> None:
    repository.create_manufacturing_operation_record(
        ManufacturingOperationRecordCreate(
            tenant_id="tenant_demo_manufacturing",
            record_id="material_lot_motors_7741",
            domain="Supply",
            record_type="material_lot",
            source_system="Supplier Portal",
            status="action_required",
            owner_role="supply-planning-owner",
            related_asset="asset_motors_batch",
            workflow_id="wf_supplier_delay_review",
            risk_level="high",
            occurred_at=datetime(2026, 6, 21, 14, 5, tzinfo=UTC),
            payload={
                "supplier": "Adriatic Motors",
                "material": "Servo motor assembly",
                "quantity": 420,
                "delay_hours": 18,
                "expedite_slot": "2026-06-21T20:30:00+02:00",
            },
            evidence_refs=[
                "supplier_portal:shipment:AM-7741",
                "axis:audit:agent_supply_risk:proposal",
            ],
        )
    )
    repository.create_manufacturing_operation_record(
        ManufacturingOperationRecordCreate(
            tenant_id="tenant_demo_manufacturing",
            record_id="supplier_adriatic_motors",
            domain="Supply",
            record_type="supplier_status",
            source_system="Supplier Portal",
            status="watch",
            owner_role="supply-planning-owner",
            related_asset="asset_motors_batch",
            workflow_id="wf_supplier_delay_review",
            risk_level="medium",
            occurred_at=datetime(2026, 6, 21, 12, 30, tzinfo=UTC),
            payload={
                "supplier": "Adriatic Motors",
                "service_level": "at_risk",
                "open_shipments": 2,
                "confirmed_expedite_capacity": True,
            },
            evidence_refs=[
                "supplier_portal:supplier:adriatic-motors",
                "erp:supplier_scorecard:adriatic-motors",
            ],
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
            record_id="other_supply",
            domain="Supply",
            record_type="material_lot",
            source_system="Supplier Portal",
            status="action_required",
            owner_role="other-supply-owner",
            occurred_at=datetime(2026, 6, 21, 12, 0, tzinfo=UTC),
            payload={"supplier": "Other Supplier", "delay_hours": 99},
            evidence_refs=["supplier_portal:shipment:OTHER"],
        )
    )


def supplier_request(**overrides) -> SupplierDelayScenarioRequest:
    payload = {
        "tenant_id": "tenant_demo_manufacturing",
        "requested_by": "agent_supplier_delay",
        "actor_scopes": ["supply:read", "workflows:read", "audit:read"],
    }
    payload.update(overrides)
    return SupplierDelayScenarioRequest(**payload)


def test_generate_supplier_delay_scenario_persists_audit_backed_artifact(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_supply_operations(repository)
        scenario = generate_supplier_delay_scenario(repository, supplier_request())

    assert scenario.domain == "Supply"
    assert scenario.risk_level == "high"
    assert scenario.owner_role == "supply-planning-owner"
    assert scenario.workflow_ids == ["wf_supplier_delay_review"]
    assert scenario.source_record_ids == [
        "material_lot_motors_7741",
        "supplier_adriatic_motors",
    ]
    assert scenario.permission_decision.allowed is True
    assert scenario.audit_event_type == "manufacturing.risk_scenario.generated"
    assert scenario.scenario_payload["generation_boundary"] == (
        "deterministic_persisted_supply_records"
    )
    assert scenario.scenario_payload["suppliers"] == ["Adriatic Motors"]
    assert scenario.scenario_payload["max_delay_hours"] == 18
    assert "tenant_other" not in scenario.model_dump_json()
    assert "password" not in scenario.model_dump_json().lower()
    assert "secret" not in scenario.model_dump_json().lower()

    with session_factory() as session:
        assert len(list(session.scalars(select(ManufacturingRiskScenario)))) == 1
        audit_event = session.scalars(select(AuditEvent)).one()
        assert audit_event.event_type == "manufacturing.risk_scenario.generated"
        assert audit_event.payload["domain"] == "Supply"
        assert audit_event.payload["risk_level"] == "high"


def test_generate_supplier_delay_scenario_is_idempotent_but_rechecks_permissions(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_supply_operations(repository)
        first = generate_supplier_delay_scenario(repository, supplier_request())
        second = generate_supplier_delay_scenario(repository, supplier_request())
        with pytest.raises(SupplierDelayScenarioPermissionDenied):
            generate_supplier_delay_scenario(
                repository,
                supplier_request(actor_scopes=["supply:read", "audit:read"]),
            )

    assert second.idempotent_replay is True
    assert second.scenario_id == first.scenario_id
    with session_factory() as session:
        assert len(list(session.scalars(select(ManufacturingRiskScenario)))) == 1
        assert len(list(session.scalars(select(AuditEvent)))) == 1


def test_generate_supplier_delay_scenario_rejects_missing_source_records(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_supply_operations(repository)
        with pytest.raises(SupplierDelayScenarioValidationError) as exc_info:
            generate_supplier_delay_scenario(
                repository,
                supplier_request(source_record_ids=["missing_supply_record"]),
            )

    assert exc_info.value.reason == "missing_source_records:missing_supply_record"


def test_generate_supplier_delay_scenario_detects_idempotency_conflict(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_supply_operations(repository)
        generate_supplier_delay_scenario(
            repository,
            supplier_request(
                idempotency_key="supplier-delay-key",
                source_record_ids=["material_lot_motors_7741"],
            ),
        )
        with pytest.raises(SupplierDelayScenarioIdempotencyConflict):
            generate_supplier_delay_scenario(
                repository,
                supplier_request(
                    idempotency_key="supplier-delay-key",
                    source_record_ids=[],
                ),
            )


def test_supplier_delay_scenario_endpoint_returns_created_then_idempotent_replay(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        seed_supply_operations(AxisPersistenceRepository(session))

    client = TestClient(app)
    payload = supplier_request(idempotency_key="supplier-delay-endpoint").model_dump()
    first = client.post(
        "/demo/manufacturing/operations/risk-scenarios/supplier-delay",
        json=payload,
    )
    second = client.post(
        "/demo/manufacturing/operations/risk-scenarios/supplier-delay",
        json=payload,
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["scenario_id"] == second.json()["scenario_id"]
    assert first.json()["scenario_payload"]["domain"] == "Supply"
    assert second.json()["idempotent_replay"] is True
