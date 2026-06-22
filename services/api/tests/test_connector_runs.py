import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.audit import AuditEventCreate
from axis_api.config import Settings
from axis_api.connector_runs import ConnectorRunQuery, build_connector_run_registry
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.models import Base
from axis_api.persistence import AxisPersistenceRepository, ConnectorRunCreate


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


def seed_connector_runs(repository: AxisPersistenceRepository) -> None:
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="connector-runtime-adapter",
            event_type="connector.run.recorded",
            payload={
                "connector_id": "file_csv_manufacturing_assets",
                "run_id": "run_file_csv_assets_preview_20260622",
                "execution_mode": "preview",
            },
        )
    )
    repository.create_connector_run(
        ConnectorRunCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="file_csv_manufacturing_assets",
            run_id="run_file_csv_assets_preview_20260622",
            status="recorded_preview_only",
            execution_mode="preview",
            runtime_boundary="axis-connector-sandbox",
            requested_by="plant-operations-owner-role",
            credential_handle_ids=["cred_file_csv_readonly"],
            input_summary={"file_name": "manufacturing-assets-demo.csv", "record_count": "2"},
            result_summary={"accepted_record_count": "2", "rejected_record_count": "0"},
            audit_event_id=audit_event.id,
            notes=["Run record only; no connector execution occurred."],
        )
    )
    repository.create_connector_run(
        ConnectorRunCreate(
            tenant_id="tenant_other",
            connector_id="file_csv_manufacturing_assets",
            run_id="run_other",
            status="recorded_preview_only",
            execution_mode="preview",
            runtime_boundary="axis-connector-sandbox",
            requested_by="other-owner-role",
            input_summary={"file_name": "other.csv"},
            result_summary={},
            audit_event_id=audit_event.id,
        )
    )


def test_build_connector_run_registry_maps_persisted_runs(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_runs(repository)
        registry = build_connector_run_registry(
            repository,
            ConnectorRunQuery(tenant_id="tenant_demo_manufacturing"),
        )

    assert registry.tenant_id == "tenant_demo_manufacturing"
    assert registry.metrics[0].label == "Connector Runs"
    assert registry.metrics[0].value == "1"
    assert registry.metrics[1].label == "Audit Writes"
    assert registry.metrics[1].value == "1"
    assert registry.runs[0].run_id == "run_file_csv_assets_preview_20260622"
    assert registry.runs[0].status == "recorded_preview_only"
    assert registry.runs[0].audit_event_type == "connector.run.recorded"
    assert "tenant_other" not in registry.model_dump_json()
    assert "csv_content" not in registry.model_dump_json().lower()
    assert "password" not in registry.model_dump_json().lower()
    assert "credential_value" not in registry.model_dump_json().lower()


def test_connector_runs_endpoint_returns_tenant_scoped_records(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        seed_connector_runs(AxisPersistenceRepository(session))
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/connectors/runs",
        params={"tenant_id": "tenant_demo_manufacturing"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["metrics"][0]["value"] == "1"
    assert body["runs"][0]["run_id"] == "run_file_csv_assets_preview_20260622"
    assert body["runs"][0]["audit_event_type"] == "connector.run.recorded"
    assert "tenant_other" not in str(body)
    assert "csv_content" not in str(body).lower()
    assert "password" not in str(body).lower()
    assert "credential_value" not in str(body).lower()


def test_create_connector_run_rejects_raw_payload_fields(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/runs",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "file_csv_manufacturing_assets",
            "run_id": "run_file_csv_assets_preview_20260622",
            "execution_mode": "preview",
            "requested_by": "plant-operations-owner-role",
            "credential_handle_ids": ["cred_file_csv_readonly"],
            "input_summary": {
                "file_name": "manufacturing-assets-demo.csv",
                "csv_content": "asset_id,asset_name",
            },
            "result_summary": {"accepted_record_count": "2"},
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "raw_payload_field"


def test_create_connector_run_records_audit_event(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/runs",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "file_csv_manufacturing_assets",
            "run_id": "run_file_csv_assets_preview_20260622",
            "execution_mode": "preview",
            "requested_by": "plant-operations-owner-role",
            "credential_handle_ids": ["cred_file_csv_readonly"],
            "input_summary": {"file_name": "manufacturing-assets-demo.csv", "record_count": "2"},
            "result_summary": {"accepted_record_count": "2", "rejected_record_count": "0"},
            "notes": ["Run record only; no connector execution occurred."],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["run_id"] == "run_file_csv_assets_preview_20260622"
    assert body["status"] == "recorded_preview_only"
    assert body["audit_event_type"] == "connector.run.recorded"
    assert body["audit_event_id"]
    assert "csv_content" not in str(body).lower()
    assert "password" not in str(body).lower()
    assert "credential_value" not in str(body).lower()

    with session_scope(session_factory) as session:
        events = AxisPersistenceRepository(session).list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.recorded",
        )

    assert len(events) == 1
    assert events[0].payload["run_id"] == "run_file_csv_assets_preview_20260622"
    assert "csv_content" not in str(events[0].payload).lower()


def test_create_connector_run_rejects_live_sync_mode(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/runs",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "file_csv_manufacturing_assets",
            "run_id": "run_live_sync_blocked",
            "execution_mode": "live_sync",
            "requested_by": "plant-operations-owner-role",
            "input_summary": {"file_name": "manufacturing-assets-demo.csv"},
            "result_summary": {},
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "unsupported_execution_mode"


def test_openapi_exposes_connector_run_endpoints() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/demo/manufacturing/connectors/runs" in paths
