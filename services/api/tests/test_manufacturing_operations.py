from datetime import UTC, datetime
from runpy import run_path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.manufacturing_operations import (
    ManufacturingOperationQuery,
    query_manufacturing_operations_dataset,
)
from axis_api.models import Base
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


def seed_operation_records(repository: AxisPersistenceRepository) -> None:
    repository.create_manufacturing_operation_record(
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
            payload={
                "order_number": "PO-4812",
                "planned_line": "Line 2 Packaging",
                "blocked_by": ["material_lot_motors_7741"],
            },
            evidence_refs=["erp:orders:PO-4812"],
        )
    )
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
            evidence_refs=["qms:inspection:Q-1842"],
        )
    )
    repository.create_manufacturing_operation_record(
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
        )
    )


def test_repository_lists_manufacturing_operations_tenant_scoped(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_operation_records(repository)
        records = repository.list_manufacturing_operation_records(
            tenant_id="tenant_demo_manufacturing"
        )

    assert [record.record_id for record in records] == [
        "order_rush_4812",
        "batch_q_1842_quality",
    ]
    assert all(record.tenant_id == "tenant_demo_manufacturing" for record in records)


def test_query_manufacturing_operations_dataset_filters_by_domain(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_operation_records(repository)
        dataset = query_manufacturing_operations_dataset(
            repository,
            ManufacturingOperationQuery(
                tenant_id="tenant_demo_manufacturing",
                domain="Quality",
            ),
        )

    assert dataset.tenant_id == "tenant_demo_manufacturing"
    assert dataset.domains == ["Quality"]
    assert dataset.source_systems == ["QMS"]
    assert dataset.metrics[0].label == "Operational Records"
    assert dataset.metrics[0].value == "1"
    assert dataset.records[0].record_id == "batch_q_1842_quality"
    assert dataset.records[0].payload["deviation_waiver"] == "not_released"
    assert "tenant_other" not in dataset.model_dump_json()
    assert "password" not in dataset.model_dump_json().lower()
    assert "secret" not in dataset.model_dump_json().lower()


def test_manufacturing_operations_endpoint_returns_persisted_records(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_operation_records(repository)

    client = TestClient(app)
    response = client.get("/demo/manufacturing/operations?status=action_required")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["metrics"][1]["label"] == "Action Required"
    assert body["metrics"][1]["value"] == "1"
    assert [record["record_id"] for record in body["records"]] == ["order_rush_4812"]
    assert body["records"][0]["source_system"] == "ERP"


def test_manufacturing_operation_bootstrap_records_cover_operational_domains() -> None:
    migration = run_path("migrations/versions/0031_manufacturing_operation_records.py")
    records = migration["MANUFACTURING_OPERATION_RECORDS"]

    assert {record["domain"] for record in records} == {
        "Maintenance",
        "Production",
        "Quality",
        "Supply",
    }
    assert {record["record_type"] for record in records} >= {
        "machine_status",
        "maintenance_window",
        "material_lot",
        "production_order",
        "quality_batch",
        "supplier_status",
    }
    assert all(record["evidence_refs"] for record in records)
    assert "password" not in str(records).lower()
    assert "secret" not in str(records).lower()
