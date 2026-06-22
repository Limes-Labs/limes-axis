import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.audit import AuditEventCreate
from axis_api.config import Settings
from axis_api.connector_execution import ConnectorExecutionRequest, ConnectorExecutionResult
from axis_api.connector_runs import ConnectorRunQuery, build_connector_run_registry
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.models import Base, utc_now
from axis_api.persistence import (
    AxisPersistenceRepository,
    ConnectorCredentialHandleCreate,
    ConnectorCredentialLeaseCreate,
    ConnectorRunCreate,
)


class RecordingConnectorExecutionRuntime:
    adapter_name = "axis-recording-connector-execution-adapter"

    def __init__(self) -> None:
        self.requests: list[ConnectorExecutionRequest] = []

    def execute(self, request: ConnectorExecutionRequest) -> ConnectorExecutionResult:
        self.requests.append(request)
        return ConnectorExecutionResult(
            adapter=self.adapter_name,
            status="execution_deferred",
            external_sync_started=False,
            idempotency_key=f"{request.tenant_id}:{request.run_id}:execution",
            result_summary={
                "runtime_status": "deferred",
                "external_sync_started": "false",
            },
            notes=["Recording runtime used by API test."],
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


def seed_connector_credential_handle(repository: AxisPersistenceRepository) -> None:
    now = utc_now()
    repository.create_connector_credential_handle(
        ConnectorCredentialHandleCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="file_csv_manufacturing_assets",
            handle_id="cred_file_csv_readonly",
            display_name="Read-only CSV intake handle",
            status="active",
            secret_provider="vault-dev",
            secret_ref="vault://axis/demo/file-csv-readonly",
            purpose="read_only_connector_execution",
            rotation_interval_days=30,
            last_rotated_at=now,
            next_rotation_due_at=now,
            created_by="security-owner-role",
            labels={"environment": "demo"},
            notes=["Metadata-only credential handle."],
        )
    )


def seed_connector_credential_lease(repository: AxisPersistenceRepository) -> None:
    now = utc_now()
    repository.create_connector_credential_lease(
        ConnectorCredentialLeaseCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="file_csv_manufacturing_assets",
            handle_id="cred_file_csv_readonly",
            lease_id="lease_file_csv_readonly_20260622",
            status="active",
            lease_mode="self_hosted_vault_kms_lease",
            runtime_boundary="axis-credential-lease-broker",
            requested_by="axis-connector-runtime-role",
            lease_purpose="scheduled_connector_sync",
            secret_provider="vault-dev",
            secret_ref="vault://axis/demo/file-csv-readonly",
            vault_kms_policy={"ttl_seconds": "900", "max_ttl_seconds": "1800"},
            permission_decision={"allowed": "true", "scope": "connectors:credential_lease:request"},
            lease_result={
                "adapter": "axis-self-hosted-vault-kms-lease-adapter",
                "status": "lease_executed",
                "provider_lease_ref": (
                    "self-hosted-vault-kms://tenant_demo_manufacturing/"
                    "lease_file_csv_readonly_20260622"
                ),
                "secret_material_returned": False,
            },
            granted_at=now,
            expires_at=now.replace(year=now.year + 1),
            renewal_due_at=now,
            notes=["Active lease for scheduled sync tests."],
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


def test_create_connector_run_uses_deferred_execution_runtime(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    runtime = RecordingConnectorExecutionRuntime()
    app.state.connector_execution_runtime = runtime
    with session_scope(session_factory) as session:
        seed_connector_credential_handle(AxisPersistenceRepository(session))
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/runs",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "file_csv_manufacturing_assets",
            "run_id": "run_file_csv_assets_governed_20260622",
            "execution_mode": "governed_dry_run",
            "requested_by": "plant-operations-owner-role",
            "credential_handle_ids": ["cred_file_csv_readonly"],
            "input_summary": {"file_name": "manufacturing-assets-demo.csv", "record_count": "2"},
            "result_summary": {},
            "notes": ["Execution must remain deferred until connector runtime is enabled."],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "execution_deferred"
    assert body["audit_event_type"] == "connector.run.execution_deferred"
    assert body["execution_result"] == {
        "adapter": "axis-recording-connector-execution-adapter",
        "status": "execution_deferred",
        "external_sync_started": False,
        "idempotency_key": (
            "tenant_demo_manufacturing:run_file_csv_assets_governed_20260622:execution"
        ),
        "result_summary": {
            "runtime_status": "deferred",
            "external_sync_started": "false",
        },
        "notes": ["Recording runtime used by API test."],
    }
    assert runtime.requests[0].credential_handle_ids == ["cred_file_csv_readonly"]
    assert "secret_ref" not in str(runtime.requests[0]).lower()
    assert "vault://" not in str(body).lower()

    with session_scope(session_factory) as session:
        events = AxisPersistenceRepository(session).list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.execution_deferred",
        )

    assert len(events) == 1
    assert events[0].payload["execution_result"]["external_sync_started"] is False
    assert "vault://" not in str(events[0].payload).lower()
    assert "credential_value" not in str(events[0].payload).lower()


def test_create_connector_run_schedules_sync_without_starting_external_sync(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_credential_handle(repository)
        seed_connector_credential_lease(repository)
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/runs",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "file_csv_manufacturing_assets",
            "run_id": "run_file_csv_assets_scheduled_20260622",
            "execution_mode": "scheduled_sync_plan",
            "requested_by": "plant-operations-owner-role",
            "credential_handle_ids": ["cred_file_csv_readonly"],
            "credential_lease_id": "lease_file_csv_readonly_20260622",
            "schedule_id": "schedule_file_csv_assets_hourly",
            "schedule_cadence": "hourly",
            "schedule_timezone": "Europe/Rome",
            "next_run_at": "2026-06-22T14:00:00Z",
            "input_summary": {"source": "manufacturing-assets-demo.csv", "record_count": "2"},
            "result_summary": {},
            "notes": ["Schedule sync without enabling live connector execution."],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "sync_schedule_deferred"
    assert body["execution_mode"] == "scheduled_sync_plan"
    assert body["audit_event_type"] == "connector.run.sync_scheduled"
    assert body["schedule_result"] == {
        "adapter": "axis-deferred-connector-sync-scheduler",
        "status": "sync_schedule_deferred",
        "schedule_ref": (
            "deferred-sync://tenant_demo_manufacturing/"
            "schedule_file_csv_assets_hourly"
        ),
        "external_sync_started": False,
        "idempotency_key": (
            "tenant_demo_manufacturing:run_file_csv_assets_scheduled_20260622:"
            "schedule_file_csv_assets_hourly:sync-schedule"
        ),
        "result_summary": {
            "runtime_status": "schedule_deferred",
            "external_sync_started": "false",
            "connector_id": "file_csv_manufacturing_assets",
            "schedule_id": "schedule_file_csv_assets_hourly",
            "schedule_cadence": "hourly",
            "next_run_at": "2026-06-22T14:00:00Z",
        },
        "notes": [
            "Connector sync scheduling is deferred by the Axis runtime adapter.",
            "No external sync, credential retrieval or graph mutation was started.",
        ],
    }
    assert body["result_summary"]["sync_schedule_result"]["external_sync_started"] is False
    assert "vault://" not in str(body).lower()
    assert "credential_value" not in str(body).lower()

    with session_scope(session_factory) as session:
        events = AxisPersistenceRepository(session).list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.sync_scheduled",
        )

    assert len(events) == 1
    assert events[0].payload["schedule_result"]["external_sync_started"] is False
    assert events[0].payload["credential_lease_id"] == "lease_file_csv_readonly_20260622"
    assert "vault://" not in str(events[0].payload).lower()
    assert "credential_value" not in str(events[0].payload).lower()


def test_create_connector_run_scheduled_sync_requires_active_lease(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        seed_connector_credential_handle(AxisPersistenceRepository(session))
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/runs",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "file_csv_manufacturing_assets",
            "run_id": "run_file_csv_assets_scheduled_missing_lease",
            "execution_mode": "scheduled_sync_plan",
            "requested_by": "plant-operations-owner-role",
            "credential_handle_ids": ["cred_file_csv_readonly"],
            "credential_lease_id": "lease_missing",
            "schedule_id": "schedule_file_csv_assets_hourly",
            "schedule_cadence": "hourly",
            "schedule_timezone": "Europe/Rome",
            "next_run_at": "2026-06-22T14:00:00Z",
            "input_summary": {"source": "manufacturing-assets-demo.csv"},
            "result_summary": {},
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "credential_lease_not_found"


def test_create_connector_run_requires_credential_handle_for_governed_execution(
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
            "run_id": "run_file_csv_assets_governed_missing_credential",
            "execution_mode": "governed_dry_run",
            "requested_by": "plant-operations-owner-role",
            "credential_handle_ids": [],
            "input_summary": {"file_name": "manufacturing-assets-demo.csv"},
            "result_summary": {},
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "credential_handle_required"


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
