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
    DailyPlantBriefIdempotencyConflict,
    DailyPlantBriefPermissionDenied,
    DailyPlantBriefRequest,
    DailyPlantBriefValidationError,
    generate_daily_plant_brief,
)
from axis_api.models import AuditEvent, Base, ManufacturingDailyBrief
from axis_api.persistence import (
    AxisPersistenceRepository,
    ManufacturingOperationRecordCreate,
)


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


def seed_daily_brief_operations(repository: AxisPersistenceRepository) -> None:
    records = [
        ManufacturingOperationRecordCreate(
            tenant_id="tenant_demo_manufacturing",
            record_id="order_rush_4812",
            domain="Production",
            record_type="production_order",
            source_system="ERP",
            status="action_required",
            owner_role="plant-operations-owner",
            related_asset="asset_line_2_packaging",
            workflow_id="wf_supplier_delay_review",
            risk_level="high",
            occurred_at=datetime(2026, 6, 21, 13, 45, tzinfo=UTC),
            payload={"order_number": "PO-4812", "blocked_by": ["material_lot_motors_7741"]},
            evidence_refs=["erp:orders:PO-4812", "mes:line_schedule:line-2-packaging"],
        ),
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
            payload={"supplier": "Adriatic Motors", "delay_hours": 18},
            evidence_refs=["supplier_portal:shipment:AM-7741"],
        ),
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
            payload={"batch": "Q-1842", "inspection_variance_ppm": 37},
            evidence_refs=["qms:inspection:Q-1842"],
        ),
        ManufacturingOperationRecordCreate(
            tenant_id="tenant_other",
            record_id="other_order",
            domain="Production",
            record_type="production_order",
            source_system="ERP",
            status="ready",
            owner_role="other-owner",
            occurred_at=datetime(2026, 6, 21, 12, 0, tzinfo=UTC),
            payload={"order_number": "OTHER"},
            evidence_refs=["erp:orders:OTHER"],
        ),
    ]
    for record in records:
        repository.create_manufacturing_operation_record(record)


def daily_brief_request(**overrides) -> DailyPlantBriefRequest:
    payload = {
        "tenant_id": "tenant_demo_manufacturing",
        "brief_date": "2026-06-21",
        "requested_by": "agent_daily_brief",
        "actor_scopes": ["briefs:generate", "audit:read", "workflows:read"],
    }
    payload.update(overrides)
    return DailyPlantBriefRequest(**payload)


def test_generate_daily_plant_brief_persists_audit_backed_summary(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_daily_brief_operations(repository)
        brief = generate_daily_plant_brief(repository, daily_brief_request())

    assert brief.status == "generated"
    assert brief.requested_by == "agent_daily_brief"
    assert brief.permission_decision.allowed is True
    assert brief.audit_event_type == "manufacturing.daily_brief.generated"
    assert brief.audit_event_id is not None
    assert brief.summary_payload["summary"]["action_required_count"] == 2
    assert brief.summary_payload["summary"]["watch_count"] == 1
    assert brief.summary_payload["generation_boundary"] == "deterministic_persisted_records"
    assert "tenant_other" not in brief.model_dump_json()
    assert "password" not in brief.model_dump_json().lower()
    assert "secret" not in brief.model_dump_json().lower()

    with session_factory() as session:
        assert len(list(session.scalars(select(ManufacturingDailyBrief)))) == 1
        audit_event = session.scalars(select(AuditEvent)).one()
        assert audit_event.event_type == "manufacturing.daily_brief.generated"
        assert audit_event.actor_id == "agent_daily_brief"
        assert audit_event.payload["brief_id"] == brief.brief_id


def test_generate_daily_plant_brief_is_idempotent_for_same_request(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_daily_brief_operations(repository)
        first = generate_daily_plant_brief(repository, daily_brief_request())
        second = generate_daily_plant_brief(repository, daily_brief_request())
        with pytest.raises(DailyPlantBriefPermissionDenied):
            generate_daily_plant_brief(
                repository,
                daily_brief_request(actor_scopes=["briefs:generate", "audit:read"]),
            )

    assert second.idempotent_replay is True
    assert second.brief_id == first.brief_id
    with session_factory() as session:
        assert len(list(session.scalars(select(ManufacturingDailyBrief)))) == 1
        assert len(list(session.scalars(select(AuditEvent)))) == 1


def test_generate_daily_plant_brief_rejects_missing_permissions(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_daily_brief_operations(repository)
        with pytest.raises(DailyPlantBriefPermissionDenied) as exc_info:
            generate_daily_plant_brief(
                repository,
                daily_brief_request(actor_scopes=["briefs:generate", "audit:read"]),
            )

    assert exc_info.value.decision.reason == "missing_scope:workflows:read"
    with session_factory() as session:
        assert list(session.scalars(select(ManufacturingDailyBrief))) == []
        assert list(session.scalars(select(AuditEvent))) == []


def test_generate_daily_plant_brief_rejects_missing_source_records(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_daily_brief_operations(repository)
        with pytest.raises(DailyPlantBriefValidationError) as exc_info:
            generate_daily_plant_brief(
                repository,
                daily_brief_request(source_record_ids=["missing_record"]),
            )

    assert exc_info.value.reason == "missing_source_records:missing_record"


def test_generate_daily_plant_brief_detects_idempotency_conflict(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_daily_brief_operations(repository)
        generate_daily_plant_brief(
            repository,
            daily_brief_request(
                idempotency_key="brief-key",
                source_record_ids=["order_rush_4812"],
            ),
        )
        with pytest.raises(DailyPlantBriefIdempotencyConflict):
            generate_daily_plant_brief(
                repository,
                daily_brief_request(
                    idempotency_key="brief-key",
                    source_record_ids=["batch_q_1842_quality"],
                ),
            )


def test_daily_plant_brief_endpoint_returns_created_then_idempotent_replay(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        seed_daily_brief_operations(AxisPersistenceRepository(session))

    client = TestClient(app)
    payload = daily_brief_request(idempotency_key="daily-brief-endpoint").model_dump()
    first = client.post("/demo/manufacturing/operations/daily-brief", json=payload)
    second = client.post("/demo/manufacturing/operations/daily-brief", json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["brief_id"] == second.json()["brief_id"]
    assert first.json()["summary_payload"]["summary"]["record_count"] == 3
    assert second.json()["idempotent_replay"] is True
