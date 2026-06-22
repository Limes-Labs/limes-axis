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


def seed_external_db_credential_handle(repository: AxisPersistenceRepository) -> None:
    now = utc_now()
    repository.create_connector_credential_handle(
        ConnectorCredentialHandleCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="external_db_operational_mirror",
            handle_id="cred_external_db_readonly",
            display_name="Read-only external DB mirror handle",
            status="active",
            secret_provider="vault-dev",
            secret_ref="vault://axis/demo/external-db-readonly",
            purpose="read_only_external_db_sync",
            rotation_interval_days=30,
            last_rotated_at=now,
            next_rotation_due_at=now,
            created_by="security-owner-role",
            labels={"environment": "demo"},
            notes=["Metadata-only external DB credential handle."],
        )
    )


def seed_external_db_credential_lease(repository: AxisPersistenceRepository) -> None:
    now = utc_now()
    repository.create_connector_credential_lease(
        ConnectorCredentialLeaseCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="external_db_operational_mirror",
            handle_id="cred_external_db_readonly",
            lease_id="lease_external_db_readonly_20260622",
            status="active",
            lease_mode="self_hosted_vault_kms_lease",
            runtime_boundary="axis-credential-lease-broker",
            requested_by="axis-connector-runtime-role",
            lease_purpose="scheduled_external_db_sync",
            secret_provider="vault-dev",
            secret_ref="vault://axis/demo/external-db-readonly",
            vault_kms_policy={"ttl_seconds": "900", "max_ttl_seconds": "1800"},
            permission_decision={"allowed": "true", "scope": "connectors:credential_lease:request"},
            lease_result={
                "adapter": "axis-self-hosted-vault-kms-lease-adapter",
                "status": "lease_executed",
                "provider_lease_ref": (
                    "self-hosted-vault-kms://tenant_demo_manufacturing/"
                    "lease_external_db_readonly_20260622"
                ),
                "secret_material_returned": False,
            },
            granted_at=now,
            expires_at=now.replace(year=now.year + 1),
            renewal_due_at=now,
            notes=["Active lease for external DB sync tests."],
        )
    )


def create_dispatched_scheduled_sync(
    client: TestClient,
    *,
    run_id: str,
    dispatch_id: str,
    dispatch_idempotency_key: str,
    connector_id: str = "file_csv_manufacturing_assets",
    credential_handle_id: str = "cred_file_csv_readonly",
    credential_lease_id: str = "lease_file_csv_readonly_20260622",
    input_summary: dict[str, str] | None = None,
) -> None:
    create_response = client.post(
        "/demo/manufacturing/connectors/runs",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": connector_id,
            "run_id": run_id,
            "execution_mode": "scheduled_sync_plan",
            "requested_by": "plant-operations-owner-role",
            "credential_handle_ids": [credential_handle_id],
            "credential_lease_id": credential_lease_id,
            "schedule_id": "schedule_file_csv_assets_hourly",
            "schedule_cadence": "hourly",
            "schedule_timezone": "Europe/Rome",
            "next_run_at": "2026-06-22T14:00:00Z",
            "input_summary": input_summary
            or {"source": "manufacturing-assets-demo.csv", "record_count": "2"},
            "result_summary": {},
        },
    )
    assert create_response.status_code == 201

    dispatch_response = client.post(
        f"/demo/manufacturing/connectors/runs/{run_id}/dispatch",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "dispatch_id": dispatch_id,
            "dispatched_by": "axis-scheduler-role",
            "actor_scopes": ["connectors:sync:dispatch"],
            "credential_lease_id": credential_lease_id,
            "idempotency_key": dispatch_idempotency_key,
        },
    )
    assert dispatch_response.status_code == 200


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


def test_dispatch_scheduled_connector_sync_claims_run_without_external_sync(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_credential_handle(repository)
        seed_connector_credential_lease(repository)
    client = TestClient(app)

    create_response = client.post(
        "/demo/manufacturing/connectors/runs",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "file_csv_manufacturing_assets",
            "run_id": "run_file_csv_assets_scheduled_dispatch_20260622",
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
        },
    )
    assert create_response.status_code == 201

    response = client.post(
        "/demo/manufacturing/connectors/runs/run_file_csv_assets_scheduled_dispatch_20260622/dispatch",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "dispatch_id": "dispatch_file_csv_assets_hourly_20260622_1400",
            "dispatched_by": "axis-scheduler-role",
            "actor_scopes": ["connectors:sync:dispatch"],
            "credential_lease_id": "lease_file_csv_readonly_20260622",
            "idempotency_key": "idem_dispatch_file_csv_assets_hourly_20260622_1400",
            "notes": ["Dispatch claim only; live sync remains disabled."],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "sync_dispatch_deferred"
    assert body["audit_event_type"] == "connector.run.sync_dispatch_deferred"
    assert body["schedule_result"]["external_sync_started"] is False
    assert body["dispatch_result"] == {
        "adapter": "axis-deferred-connector-sync-dispatcher",
        "status": "sync_dispatch_deferred",
        "dispatch_ref": (
            "deferred-sync-dispatch://tenant_demo_manufacturing/"
            "run_file_csv_assets_scheduled_dispatch_20260622/"
            "dispatch_file_csv_assets_hourly_20260622_1400"
        ),
        "external_sync_started": False,
        "idempotency_key": "idem_dispatch_file_csv_assets_hourly_20260622_1400",
        "result_summary": {
            "runtime_status": "dispatch_deferred",
            "external_sync_started": "false",
            "connector_id": "file_csv_manufacturing_assets",
            "schedule_id": "schedule_file_csv_assets_hourly",
            "dispatch_id": "dispatch_file_csv_assets_hourly_20260622_1400",
        },
        "notes": [
            "Connector sync dispatch is deferred by the Axis runtime adapter.",
            "No external sync, credential retrieval or graph mutation was started.",
        ],
    }
    assert body["result_summary"]["sync_dispatch_result"]["external_sync_started"] is False
    assert "vault://" not in str(body).lower()
    assert "credential_value" not in str(body).lower()

    with session_scope(session_factory) as session:
        events = AxisPersistenceRepository(session).list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.sync_dispatch_deferred",
        )

    assert len(events) == 1
    assert events[0].payload["dispatch_result"]["external_sync_started"] is False
    assert events[0].payload["credential_lease_id"] == "lease_file_csv_readonly_20260622"
    assert "vault://" not in str(events[0].payload).lower()
    assert "credential_value" not in str(events[0].payload).lower()


def test_dispatch_scheduled_connector_sync_replays_same_idempotency_key(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_credential_handle(repository)
        seed_connector_credential_lease(repository)
    client = TestClient(app)

    create_response = client.post(
        "/demo/manufacturing/connectors/runs",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "file_csv_manufacturing_assets",
            "run_id": "run_file_csv_assets_scheduled_replay_20260622",
            "execution_mode": "scheduled_sync_plan",
            "requested_by": "plant-operations-owner-role",
            "credential_handle_ids": ["cred_file_csv_readonly"],
            "credential_lease_id": "lease_file_csv_readonly_20260622",
            "schedule_id": "schedule_file_csv_assets_hourly",
            "schedule_cadence": "hourly",
            "schedule_timezone": "Europe/Rome",
            "next_run_at": "2026-06-22T14:00:00Z",
            "input_summary": {"source": "manufacturing-assets-demo.csv"},
            "result_summary": {},
        },
    )
    assert create_response.status_code == 201

    payload = {
        "tenant_id": "tenant_demo_manufacturing",
        "dispatch_id": "dispatch_file_csv_assets_replay_20260622_1400",
        "dispatched_by": "axis-scheduler-role",
        "actor_scopes": ["connectors:sync:dispatch"],
        "credential_lease_id": "lease_file_csv_readonly_20260622",
        "idempotency_key": "idem_dispatch_file_csv_assets_replay_20260622_1400",
    }

    first = client.post(
        "/demo/manufacturing/connectors/runs/run_file_csv_assets_scheduled_replay_20260622/dispatch",
        json=payload,
    )
    second = client.post(
        "/demo/manufacturing/connectors/runs/run_file_csv_assets_scheduled_replay_20260622/dispatch",
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["audit_event_id"] == first.json()["audit_event_id"]
    assert second.json()["dispatch_result"]["idempotency_key"] == payload["idempotency_key"]

    with session_scope(session_factory) as session:
        events = AxisPersistenceRepository(session).list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.sync_dispatch_deferred",
        )

    assert len(events) == 1


def test_dispatch_scheduled_connector_sync_requires_dispatch_scope(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_credential_handle(repository)
        seed_connector_credential_lease(repository)
    client = TestClient(app)

    create_response = client.post(
        "/demo/manufacturing/connectors/runs",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "file_csv_manufacturing_assets",
            "run_id": "run_file_csv_assets_scheduled_missing_scope",
            "execution_mode": "scheduled_sync_plan",
            "requested_by": "plant-operations-owner-role",
            "credential_handle_ids": ["cred_file_csv_readonly"],
            "credential_lease_id": "lease_file_csv_readonly_20260622",
            "schedule_id": "schedule_file_csv_assets_hourly",
            "schedule_cadence": "hourly",
            "schedule_timezone": "Europe/Rome",
            "next_run_at": "2026-06-22T14:00:00Z",
            "input_summary": {"source": "manufacturing-assets-demo.csv"},
            "result_summary": {},
        },
    )
    assert create_response.status_code == 201

    response = client.post(
        "/demo/manufacturing/connectors/runs/run_file_csv_assets_scheduled_missing_scope/dispatch",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "dispatch_id": "dispatch_file_csv_assets_missing_scope",
            "dispatched_by": "axis-scheduler-role",
            "actor_scopes": [],
            "credential_lease_id": "lease_file_csv_readonly_20260622",
            "idempotency_key": "idem_dispatch_file_csv_assets_missing_scope",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "missing_required_scope"
    assert response.json()["detail"]["required_permission"] == "connectors:sync:dispatch"


def test_execute_scheduled_connector_sync_defaults_to_deferred_without_external_sync(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_credential_handle(repository)
        seed_connector_credential_lease(repository)
    client = TestClient(app)
    create_dispatched_scheduled_sync(
        client,
        run_id="run_file_csv_assets_scheduled_execute_20260622",
        dispatch_id="dispatch_file_csv_assets_execute_20260622_1400",
        dispatch_idempotency_key="idem_dispatch_file_csv_assets_execute_20260622_1400",
    )

    response = client.post(
        "/demo/manufacturing/connectors/runs/"
        "run_file_csv_assets_scheduled_execute_20260622/execute-sync",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "execution_id": "sync_exec_file_csv_assets_20260622_1400",
            "executed_by": "axis-sync-worker-role",
            "actor_scopes": ["connectors:sync:execute"],
            "credential_lease_id": "lease_file_csv_readonly_20260622",
            "idempotency_key": "idem_sync_exec_file_csv_assets_20260622_1400",
            "notes": ["Execution request remains deferred until the runtime flag is enabled."],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "sync_execution_deferred"
    assert body["audit_event_type"] == "connector.run.sync_execution_deferred"
    assert body["schedule_result"]["external_sync_started"] is False
    assert body["dispatch_result"]["external_sync_started"] is False
    assert body["sync_execution_result"] == {
        "adapter": "axis-deferred-connector-sync-executor",
        "status": "sync_execution_deferred",
        "sync_ref": (
            "deferred-sync-execution://tenant_demo_manufacturing/"
            "run_file_csv_assets_scheduled_execute_20260622/"
            "sync_exec_file_csv_assets_20260622_1400"
        ),
        "external_sync_started": False,
        "idempotency_key": "idem_sync_exec_file_csv_assets_20260622_1400",
        "result_summary": {
            "runtime_status": "sync_execution_deferred",
            "external_sync_started": "false",
            "connector_id": "file_csv_manufacturing_assets",
            "schedule_id": "schedule_file_csv_assets_hourly",
            "dispatch_id": "dispatch_file_csv_assets_execute_20260622_1400",
            "execution_id": "sync_exec_file_csv_assets_20260622_1400",
        },
        "notes": [
            "Connector sync execution is deferred by the Axis runtime adapter.",
            "No external sync, credential retrieval or graph mutation was started.",
        ],
    }
    assert body["result_summary"]["sync_execution_result"]["external_sync_started"] is False
    assert "vault://" not in str(body).lower()
    assert "credential_value" not in str(body).lower()

    with session_scope(session_factory) as session:
        events = AxisPersistenceRepository(session).list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.sync_execution_deferred",
        )

    assert len(events) == 1
    assert events[0].payload["sync_execution_result"]["external_sync_started"] is False
    assert events[0].payload["credential_lease_id"] == "lease_file_csv_readonly_20260622"
    assert "vault://" not in str(events[0].payload).lower()
    assert "credential_value" not in str(events[0].payload).lower()


def test_execute_scheduled_connector_sync_self_hosted_runtime_when_enabled(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(
        Settings(
            postgres_dsn="sqlite+pysqlite://",
            connector_sync_execution_enabled=True,
        )
    )
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_credential_handle(repository)
        seed_connector_credential_lease(repository)
    client = TestClient(app)
    create_dispatched_scheduled_sync(
        client,
        run_id="run_file_csv_assets_scheduled_live_20260622",
        dispatch_id="dispatch_file_csv_assets_live_20260622_1400",
        dispatch_idempotency_key="idem_dispatch_file_csv_assets_live_20260622_1400",
    )

    response = client.post(
        "/demo/manufacturing/connectors/runs/"
        "run_file_csv_assets_scheduled_live_20260622/execute-sync",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "execution_id": "sync_exec_file_csv_assets_live_20260622_1400",
            "executed_by": "axis-sync-worker-role",
            "actor_scopes": ["connectors:sync:execute"],
            "credential_lease_id": "lease_file_csv_readonly_20260622",
            "idempotency_key": "idem_sync_exec_file_csv_assets_live_20260622_1400",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "sync_execution_completed"
    assert body["audit_event_type"] == "connector.run.sync_execution_completed"
    assert body["sync_execution_result"] == {
        "adapter": "axis-self-hosted-connector-sync-executor",
        "status": "sync_execution_completed",
        "sync_ref": (
            "self-hosted-sync-execution://tenant_demo_manufacturing/"
            "run_file_csv_assets_scheduled_live_20260622/"
            "sync_exec_file_csv_assets_live_20260622_1400"
        ),
        "external_sync_started": False,
        "idempotency_key": "idem_sync_exec_file_csv_assets_live_20260622_1400",
        "result_summary": {
            "runtime_status": "sync_execution_completed",
            "external_sync_started": "false",
            "connector_id": "file_csv_manufacturing_assets",
            "schedule_id": "schedule_file_csv_assets_hourly",
            "dispatch_id": "dispatch_file_csv_assets_live_20260622_1400",
            "execution_id": "sync_exec_file_csv_assets_live_20260622_1400",
            "records_read": "2",
            "records_accepted": "2",
            "records_rejected": "0",
            "graph_mutation_started": "false",
            "source_mode": "self_hosted_demo",
        },
        "notes": [
            "Connector sync executed through the self-hosted demo runtime.",
            "No external egress, credential material or graph mutation was started.",
        ],
    }
    assert body["result_summary"]["graph_mutation_started"] == "false"
    assert "vault://" not in str(body).lower()
    assert "credential_value" not in str(body).lower()

    with session_scope(session_factory) as session:
        events = AxisPersistenceRepository(session).list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.sync_execution_completed",
        )

    assert len(events) == 1
    assert events[0].payload["sync_execution_result"]["external_sync_started"] is False
    assert events[0].payload["sync_execution_result"]["result_summary"]["records_read"] == "2"


def test_execute_external_db_sync_uses_generic_runtime_until_external_db_flag_enabled(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(
        Settings(
            postgres_dsn="sqlite+pysqlite://",
            connector_sync_execution_enabled=True,
        )
    )
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_external_db_credential_handle(repository)
        seed_external_db_credential_lease(repository)
    client = TestClient(app)
    create_dispatched_scheduled_sync(
        client,
        run_id="run_external_db_orders_scheduled_generic_20260622",
        dispatch_id="dispatch_external_db_orders_generic_20260622_1400",
        dispatch_idempotency_key="idem_dispatch_external_db_orders_generic_20260622_1400",
        connector_id="external_db_operational_mirror",
        credential_handle_id="cred_external_db_readonly",
        credential_lease_id="lease_external_db_readonly_20260622",
        input_summary={
            "connection_profile_id": "profile_postgres_ops_readonly",
            "schema_name": "operations",
            "table_name": "production_orders",
            "record_count": "2",
        },
    )

    response = client.post(
        "/demo/manufacturing/connectors/runs/"
        "run_external_db_orders_scheduled_generic_20260622/execute-sync",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "execution_id": "sync_exec_external_db_orders_generic_20260622_1400",
            "executed_by": "axis-sync-worker-role",
            "actor_scopes": ["connectors:sync:execute"],
            "credential_lease_id": "lease_external_db_readonly_20260622",
            "idempotency_key": "idem_sync_exec_external_db_orders_generic_20260622_1400",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sync_execution_result"]["adapter"] == "axis-self-hosted-connector-sync-executor"
    assert body["sync_execution_result"]["result_summary"]["source_mode"] == "self_hosted_demo"
    assert "postgres-external-db-sync" not in body["sync_execution_result"]["sync_ref"]
    assert "vault://" not in str(body).lower()
    assert "credential_value" not in str(body).lower()


def test_execute_external_db_sync_uses_postgres_profile_adapter_when_enabled(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(
        Settings(
            postgres_dsn="sqlite+pysqlite://",
            connector_sync_execution_enabled=True,
            external_db_sync_execution_enabled=True,
        )
    )
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_external_db_credential_handle(repository)
        seed_external_db_credential_lease(repository)
    client = TestClient(app)
    create_dispatched_scheduled_sync(
        client,
        run_id="run_external_db_orders_scheduled_20260622",
        dispatch_id="dispatch_external_db_orders_20260622_1400",
        dispatch_idempotency_key="idem_dispatch_external_db_orders_20260622_1400",
        connector_id="external_db_operational_mirror",
        credential_handle_id="cred_external_db_readonly",
        credential_lease_id="lease_external_db_readonly_20260622",
        input_summary={
            "connection_profile_id": "profile_postgres_ops_readonly",
            "schema_name": "operations",
            "table_name": "production_orders",
            "selected_columns": "order_id,asset_id,work_center,status,risk_level",
            "record_count": "2",
        },
    )

    response = client.post(
        "/demo/manufacturing/connectors/runs/"
        "run_external_db_orders_scheduled_20260622/execute-sync",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "execution_id": "sync_exec_external_db_orders_20260622_1400",
            "executed_by": "axis-sync-worker-role",
            "actor_scopes": ["connectors:sync:execute"],
            "credential_lease_id": "lease_external_db_readonly_20260622",
            "idempotency_key": "idem_sync_exec_external_db_orders_20260622_1400",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "sync_execution_completed"
    assert body["audit_event_type"] == "connector.run.sync_execution_completed"
    assert body["sync_execution_result"] == {
        "adapter": "axis-postgres-external-db-sync-executor",
        "status": "sync_execution_completed",
        "sync_ref": (
            "postgres-external-db-sync://tenant_demo_manufacturing/"
            "profile_postgres_ops_readonly/"
            "run_external_db_orders_scheduled_20260622/"
            "sync_exec_external_db_orders_20260622_1400"
        ),
        "external_sync_started": False,
        "idempotency_key": "idem_sync_exec_external_db_orders_20260622_1400",
        "result_summary": {
            "runtime_status": "sync_execution_completed",
            "external_sync_started": "false",
            "connector_id": "external_db_operational_mirror",
            "schedule_id": "schedule_file_csv_assets_hourly",
            "dispatch_id": "dispatch_external_db_orders_20260622_1400",
            "execution_id": "sync_exec_external_db_orders_20260622_1400",
            "provider": "postgres",
            "connection_profile_id": "profile_postgres_ops_readonly",
            "schema_name": "operations",
            "table_name": "production_orders",
            "records_read": "2",
            "records_accepted": "2",
            "records_rejected": "0",
            "external_query_started": "false",
            "credential_material_returned": "false",
            "graph_mutation_started": "false",
            "source_mode": "external_db_profile",
        },
        "notes": [
            "Postgres external DB sync executed through the profile adapter boundary.",
            (
                "No raw connection string, credential material, external query or "
                "graph mutation was started."
            ),
        ],
    }
    assert "vault://" not in str(body).lower()
    assert "password" not in str(body).lower()
    assert "credential_value" not in str(body).lower()
    assert "dsn" not in str(body).lower()

    with session_scope(session_factory) as session:
        events = AxisPersistenceRepository(session).list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.sync_execution_completed",
        )

    assert len(events) == 1
    assert events[0].payload["sync_execution_result"]["adapter"] == (
        "axis-postgres-external-db-sync-executor"
    )
    assert events[0].payload["sync_execution_result"]["external_sync_started"] is False
    assert "vault://" not in str(events[0].payload).lower()
    assert "credential_value" not in str(events[0].payload).lower()
    assert "dsn" not in str(events[0].payload).lower()


def test_execute_external_db_live_query_preflight_blocks_by_default(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(
        Settings(
            postgres_dsn="sqlite+pysqlite://",
            connector_sync_execution_enabled=True,
            external_db_sync_execution_enabled=True,
        )
    )
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_external_db_credential_handle(repository)
        seed_external_db_credential_lease(repository)
    client = TestClient(app)
    create_dispatched_scheduled_sync(
        client,
        run_id="run_external_db_orders_live_preflight_blocked_20260622",
        dispatch_id="dispatch_external_db_orders_live_preflight_blocked_20260622_1400",
        dispatch_idempotency_key=(
            "idem_dispatch_external_db_orders_live_preflight_blocked_20260622_1400"
        ),
        connector_id="external_db_operational_mirror",
        credential_handle_id="cred_external_db_readonly",
        credential_lease_id="lease_external_db_readonly_20260622",
        input_summary={
            "connection_profile_id": "profile_postgres_ops_readonly",
            "schema_name": "operations",
            "table_name": "production_orders",
            "selected_columns": "order_id,asset_id,work_center,status,risk_level",
            "record_count": "2",
            "live_query_requested": "true",
            "query_mode": "read_only_snapshot",
        },
    )

    response = client.post(
        "/demo/manufacturing/connectors/runs/"
        "run_external_db_orders_live_preflight_blocked_20260622/execute-sync",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "execution_id": "sync_exec_external_db_orders_live_preflight_blocked_20260622_1400",
            "executed_by": "axis-sync-worker-role",
            "actor_scopes": ["connectors:sync:execute"],
            "credential_lease_id": "lease_external_db_readonly_20260622",
            "idempotency_key": (
                "idem_sync_exec_external_db_orders_live_preflight_blocked_20260622_1400"
            ),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "sync_execution_preflight_blocked"
    assert body["audit_event_type"] == "connector.run.sync_execution_preflight_blocked"
    assert body["sync_execution_result"]["adapter"] == "axis-postgres-external-db-sync-executor"
    assert body["sync_execution_result"]["external_sync_started"] is False
    assert body["sync_execution_result"]["sync_ref"] == (
        "postgres-external-db-preflight-blocked://tenant_demo_manufacturing/"
        "profile_postgres_ops_readonly/"
        "run_external_db_orders_live_preflight_blocked_20260622/"
        "sync_exec_external_db_orders_live_preflight_blocked_20260622_1400"
    )
    assert body["sync_execution_result"]["result_summary"] == {
        "runtime_status": "sync_execution_preflight_blocked",
        "external_sync_started": "false",
        "connector_id": "external_db_operational_mirror",
        "schedule_id": "schedule_file_csv_assets_hourly",
        "dispatch_id": "dispatch_external_db_orders_live_preflight_blocked_20260622_1400",
        "execution_id": "sync_exec_external_db_orders_live_preflight_blocked_20260622_1400",
        "provider": "postgres",
        "connection_profile_id": "profile_postgres_ops_readonly",
        "schema_name": "operations",
        "table_name": "production_orders",
        "query_mode": "read_only_snapshot",
        "records_read": "0",
        "records_accepted": "0",
        "records_rejected": "0",
        "live_query_requested": "true",
        "live_query_preflight_status": "blocked",
        "egress_policy_decision": "blocked_by_default",
        "secret_retrieval_decision": "not_started",
        "external_query_started": "false",
        "credential_material_returned": "false",
        "graph_mutation_started": "false",
        "source_mode": "external_db_live_preflight",
    }
    assert "vault://" not in str(body).lower()
    assert "password" not in str(body).lower()
    assert "credential_value" not in str(body).lower()
    assert "dsn" not in str(body).lower()


def test_execute_external_db_live_query_preflight_passes_when_policy_enabled(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(
        Settings(
            postgres_dsn="sqlite+pysqlite://",
            connector_sync_execution_enabled=True,
            external_db_sync_execution_enabled=True,
            external_db_live_query_preflight_enabled=True,
        )
    )
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_external_db_credential_handle(repository)
        seed_external_db_credential_lease(repository)
    client = TestClient(app)
    create_dispatched_scheduled_sync(
        client,
        run_id="run_external_db_orders_live_preflight_passed_20260622",
        dispatch_id="dispatch_external_db_orders_live_preflight_passed_20260622_1400",
        dispatch_idempotency_key=(
            "idem_dispatch_external_db_orders_live_preflight_passed_20260622_1400"
        ),
        connector_id="external_db_operational_mirror",
        credential_handle_id="cred_external_db_readonly",
        credential_lease_id="lease_external_db_readonly_20260622",
        input_summary={
            "connection_profile_id": "profile_postgres_ops_readonly",
            "schema_name": "operations",
            "table_name": "production_orders",
            "selected_columns": "order_id,asset_id,work_center,status,risk_level",
            "record_count": "2",
            "live_query_requested": "true",
            "query_mode": "read_only_snapshot",
            "egress_policy_id": "egress_policy_private_endpoint_ops",
            "egress_boundary": "approved_private_endpoint",
            "credential_access_mode": "lease_scoped_secret_ref",
        },
    )

    response = client.post(
        "/demo/manufacturing/connectors/runs/"
        "run_external_db_orders_live_preflight_passed_20260622/execute-sync",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "execution_id": "sync_exec_external_db_orders_live_preflight_passed_20260622_1400",
            "executed_by": "axis-sync-worker-role",
            "actor_scopes": ["connectors:sync:execute"],
            "credential_lease_id": "lease_external_db_readonly_20260622",
            "idempotency_key": (
                "idem_sync_exec_external_db_orders_live_preflight_passed_20260622_1400"
            ),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "sync_execution_preflight_passed"
    assert body["audit_event_type"] == "connector.run.sync_execution_preflight_passed"
    assert body["sync_execution_result"]["adapter"] == "axis-postgres-external-db-sync-executor"
    assert body["sync_execution_result"]["external_sync_started"] is False
    assert body["sync_execution_result"]["sync_ref"] == (
        "postgres-external-db-preflight://tenant_demo_manufacturing/"
        "profile_postgres_ops_readonly/"
        "run_external_db_orders_live_preflight_passed_20260622/"
        "sync_exec_external_db_orders_live_preflight_passed_20260622_1400"
    )
    assert body["sync_execution_result"]["result_summary"] == {
        "runtime_status": "sync_execution_preflight_passed",
        "external_sync_started": "false",
        "connector_id": "external_db_operational_mirror",
        "schedule_id": "schedule_file_csv_assets_hourly",
        "dispatch_id": "dispatch_external_db_orders_live_preflight_passed_20260622_1400",
        "execution_id": "sync_exec_external_db_orders_live_preflight_passed_20260622_1400",
        "provider": "postgres",
        "connection_profile_id": "profile_postgres_ops_readonly",
        "schema_name": "operations",
        "table_name": "production_orders",
        "query_mode": "read_only_snapshot",
        "egress_policy_id": "egress_policy_private_endpoint_ops",
        "egress_boundary": "approved_private_endpoint",
        "credential_access_mode": "lease_scoped_secret_ref",
        "records_read": "0",
        "records_accepted": "0",
        "records_rejected": "0",
        "live_query_requested": "true",
        "live_query_preflight_status": "passed",
        "egress_policy_decision": "approved_private_endpoint",
        "secret_retrieval_decision": "lease_scoped_reference_only",
        "external_query_started": "false",
        "credential_material_returned": "false",
        "graph_mutation_started": "false",
        "source_mode": "external_db_live_preflight",
    }
    assert "vault://" not in str(body).lower()
    assert "password" not in str(body).lower()
    assert "credential_value" not in str(body).lower()
    assert "dsn" not in str(body).lower()

    with session_scope(session_factory) as session:
        events = AxisPersistenceRepository(session).list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.sync_execution_preflight_passed",
        )

    assert len(events) == 1
    assert events[0].payload["sync_execution_result"]["result_summary"][
        "egress_policy_decision"
    ] == "approved_private_endpoint"
    assert "vault://" not in str(events[0].payload).lower()
    assert "credential_value" not in str(events[0].payload).lower()
    assert "dsn" not in str(events[0].payload).lower()


def test_execute_scheduled_connector_sync_replays_same_idempotency_key(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_credential_handle(repository)
        seed_connector_credential_lease(repository)
    client = TestClient(app)
    create_dispatched_scheduled_sync(
        client,
        run_id="run_file_csv_assets_scheduled_execute_replay",
        dispatch_id="dispatch_file_csv_assets_execute_replay",
        dispatch_idempotency_key="idem_dispatch_file_csv_assets_execute_replay",
    )
    payload = {
        "tenant_id": "tenant_demo_manufacturing",
        "execution_id": "sync_exec_file_csv_assets_execute_replay",
        "executed_by": "axis-sync-worker-role",
        "actor_scopes": ["connectors:sync:execute"],
        "credential_lease_id": "lease_file_csv_readonly_20260622",
        "idempotency_key": "idem_sync_exec_file_csv_assets_execute_replay",
    }

    first = client.post(
        "/demo/manufacturing/connectors/runs/"
        "run_file_csv_assets_scheduled_execute_replay/execute-sync",
        json=payload,
    )
    second = client.post(
        "/demo/manufacturing/connectors/runs/"
        "run_file_csv_assets_scheduled_execute_replay/execute-sync",
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["audit_event_id"] == first.json()["audit_event_id"]
    assert second.json()["sync_execution_result"]["idempotency_key"] == payload["idempotency_key"]

    with session_scope(session_factory) as session:
        events = AxisPersistenceRepository(session).list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.sync_execution_deferred",
        )

    assert len(events) == 1


def test_execute_scheduled_connector_sync_requires_execute_scope(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_credential_handle(repository)
        seed_connector_credential_lease(repository)
    client = TestClient(app)
    create_dispatched_scheduled_sync(
        client,
        run_id="run_file_csv_assets_scheduled_execute_missing_scope",
        dispatch_id="dispatch_file_csv_assets_execute_missing_scope",
        dispatch_idempotency_key="idem_dispatch_file_csv_assets_execute_missing_scope",
    )

    response = client.post(
        "/demo/manufacturing/connectors/runs/"
        "run_file_csv_assets_scheduled_execute_missing_scope/execute-sync",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "execution_id": "sync_exec_file_csv_assets_missing_scope",
            "executed_by": "axis-sync-worker-role",
            "actor_scopes": [],
            "credential_lease_id": "lease_file_csv_readonly_20260622",
            "idempotency_key": "idem_sync_exec_file_csv_assets_missing_scope",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "missing_required_scope"
    assert response.json()["detail"]["required_permission"] == "connectors:sync:execute"


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
    assert "/demo/manufacturing/connectors/runs/{run_id}/dispatch" in paths
    assert "/demo/manufacturing/connectors/runs/{run_id}/execute-sync" in paths
