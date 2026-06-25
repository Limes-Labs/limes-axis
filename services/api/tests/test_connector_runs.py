from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from runpy import run_path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.audit import AuditEventCreate
from axis_api.config import Settings
from axis_api.connector_execution import ConnectorExecutionRequest, ConnectorExecutionResult
from axis_api.connector_manifests import (
    ConnectorManifestCreateRequest,
    ConnectorManifestLifecycleRequest,
    record_demo_connector_manifest,
    transition_demo_connector_manifest_lifecycle,
)
from axis_api.connector_reference import ConnectorReferenceRecordNotFound
from axis_api.connector_runs import (
    ConnectorRunCreateRequest,
    ConnectorRunQuery,
    ConnectorRunValidationError,
    ConnectorSyncCheckpointQuery,
    build_connector_run_registry,
    build_connector_sync_checkpoint_registry,
    record_demo_connector_run,
)
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.models import Base, utc_now
from axis_api.persistence import (
    AxisPersistenceRepository,
    ConnectorCredentialHandleCreate,
    ConnectorCredentialLeaseCreate,
    ConnectorEgressPolicyCreate,
    ConnectorRunCreate,
    ConnectorSyncCheckpointClaimCreate,
    ConnectorSyncCheckpointCreate,
    DemoReferenceRecordCreate,
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
    seed_connector_registry_reference(factory)
    yield factory
    engine.dispose()


@pytest.fixture
def empty_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


def connector_registry_payload() -> dict:
    migration = run_path("migrations/versions/0023_connector_registry_reference.py")
    return deepcopy(migration["CONNECTOR_REGISTRY_PAYLOAD"])


def seed_connector_registry_reference(
    factory: sessionmaker[Session],
    payload: dict | None = None,
) -> None:
    registry_payload = deepcopy(payload or connector_registry_payload())
    with session_scope(factory) as session:
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id="tenant_demo_manufacturing",
                surface="connectors",
                reference_id="manufacturing-connector-registry",
                status="active",
                source="bootstrap",
                version="2026-06-22",
                payload=registry_payload,
            )
        )


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


def seed_connector_sync_checkpoint(
    repository: AxisPersistenceRepository,
    *,
    checkpoint_id: str,
    run_id: str,
    sequence: int,
    created_at: datetime,
) -> None:
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="axis-sync-worker-role",
            event_type="connector.run.sync_execution_preflight_passed",
            payload={
                "connector_id": "external_db_operational_mirror",
                "run_id": run_id,
                "checkpoint_id": checkpoint_id,
            },
        )
    )
    checkpoint = repository.create_connector_sync_checkpoint(
        ConnectorSyncCheckpointCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="external_db_operational_mirror",
            run_id=run_id,
            checkpoint_id=checkpoint_id,
            checkpoint_type="sync_execution",
            status="sync_execution_preflight_passed",
            sequence=sequence,
            runtime_boundary="axis-connector-sandbox",
            adapter="axis-postgres-external-db-sync-executor",
            cursor={
                "high_watermark_kind": "timestamp",
                "high_watermark_value": created_at.isoformat(),
            },
            result_summary={
                "external_query_started": "false",
                "credential_material_returned": "false",
            },
            evidence_refs=[str(audit_event.id)],
            audit_event_id=audit_event.id,
            audit_event_type=audit_event.event_type,
            notes=["Checkpoint seeded for pagination behavior test."],
        )
    )
    checkpoint.created_at = created_at
    checkpoint.updated_at = created_at


def connector_run_request() -> ConnectorRunCreateRequest:
    return ConnectorRunCreateRequest(
        tenant_id="tenant_demo_manufacturing",
        connector_id="file_csv_manufacturing_assets",
        run_id="run_file_csv_assets_preview_20260622",
        execution_mode="preview",
        requested_by="plant-operations-owner-role",
        credential_handle_ids=["cred_file_csv_readonly"],
        input_summary={"file_name": "manufacturing-assets-demo.csv", "record_count": "2"},
        result_summary={"accepted_record_count": "2", "rejected_record_count": "0"},
        notes=["Run record only; no connector execution occurred."],
    )


def connector_manifest_request(
    connector_id: str,
    payload: dict | None = None,
) -> ConnectorManifestCreateRequest:
    registry_payload = deepcopy(payload or connector_registry_payload())
    connector = next(
        item
        for item in registry_payload["connectors"]
        if item["manifest"]["connector_id"] == connector_id
    )
    return ConnectorManifestCreateRequest(
        tenant_id="tenant_demo_manufacturing",
        registered_by="platform-connector-owner-role",
        manifest=connector["manifest"],
        runtime_policy=connector["runtime_policy"],
        preview_sample=connector["preview_sample"],
        notes=["Manifest is registered without enabling live sync."],
    )


def seed_registered_connector_manifest(
    repository: AxisPersistenceRepository,
    connector_id: str = "file_csv_manufacturing_assets",
    payload: dict | None = None,
) -> None:
    record_demo_connector_manifest(repository, connector_manifest_request(connector_id, payload))


def seed_active_connector_manifest(
    repository: AxisPersistenceRepository,
    connector_id: str = "file_csv_manufacturing_assets",
    payload: dict | None = None,
) -> None:
    seed_registered_connector_manifest(repository, connector_id, payload)
    transition_demo_connector_manifest_lifecycle(
        repository,
        connector_id,
        ConnectorManifestLifecycleRequest(
            tenant_id="tenant_demo_manufacturing",
            transitioned_by="platform-connector-owner-role",
            target_status="active_preview",
            actor_scopes=["connectors:manifest:lifecycle"],
            transition_reason="Validated for tenant connector run tests.",
            evidence_refs=["test://connector-run-active-manifest"],
        ),
    )


def test_connector_run_path_does_not_load_demo_connector_registry_seed() -> None:
    source = Path("src/axis_api/connector_runs.py").read_text()

    assert "get_manufacturing_connector_registry" not in source


def test_record_demo_connector_run_requires_persisted_connector_registry(
    empty_session_factory: sessionmaker[Session],
) -> None:
    with session_scope(empty_session_factory) as session:
        repository = AxisPersistenceRepository(session)
        with pytest.raises(ConnectorReferenceRecordNotFound):
            record_demo_connector_run(repository, connector_run_request())


def test_record_demo_connector_run_uses_persisted_connector_manifest(
    session_factory: sessionmaker[Session],
) -> None:
    payload = connector_registry_payload()
    payload["connectors"][0]["manifest"]["runtime_boundary"] = (
        "persisted-run-runtime-boundary"
    )
    seed_connector_registry_reference(session_factory, payload)

    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_active_connector_manifest(repository, payload=payload)
        run = record_demo_connector_run(repository, connector_run_request())
        events = repository.list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.recorded",
        )

    assert run.runtime_boundary == "persisted-run-runtime-boundary"
    assert events[0].payload["runtime_boundary"] == "persisted-run-runtime-boundary"


def test_record_demo_connector_run_requires_active_preview_manifest(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_registered_connector_manifest(repository)

        with pytest.raises(ConnectorRunValidationError) as exc_info:
            record_demo_connector_run(repository, connector_run_request())

    assert exc_info.value.reason == "connector_manifest_not_active_preview"


def seed_connector_credential_handle(repository: AxisPersistenceRepository) -> None:
    seed_active_connector_manifest(repository)
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
    seed_active_connector_manifest(repository, "external_db_operational_mirror")
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


def seed_external_db_credential_lease(
    repository: AxisPersistenceRepository,
    *,
    secret_material_returned: bool = False,
    provider_lease_ref: str | None = (
        "self-hosted-vault-kms://tenant_demo_manufacturing/"
        "lease_external_db_readonly_20260622"
    ),
) -> None:
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
                "provider_lease_ref": provider_lease_ref or "",
                "secret_material_returned": secret_material_returned,
            },
            granted_at=now,
            expires_at=now.replace(year=now.year + 1),
            renewal_due_at=now,
            notes=["Active lease for external DB sync tests."],
        )
    )


def seed_external_db_egress_policy(
    repository: AxisPersistenceRepository,
    *,
    policy_id: str = "egress_policy_private_endpoint_ops",
    status: str = "active",
    private_endpoint_ref: str = (
        "private-endpoint://tenant_demo_manufacturing/"
        "persisted-operations-postgres-readonly"
    ),
) -> None:
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id="tenant_demo_manufacturing",
            actor_id="network-policy-owner-role",
            event_type="connector.egress_policy.registered",
            payload={
                "connector_id": "external_db_operational_mirror",
                "policy_id": policy_id,
                "connection_profile_id": "profile_postgres_ops_readonly",
                "egress_boundary": "approved_private_endpoint",
                "private_endpoint_ref": private_endpoint_ref,
            },
        )
    )
    repository.create_connector_egress_policy(
        ConnectorEgressPolicyCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="external_db_operational_mirror",
            policy_id=policy_id,
            display_name="Operations Postgres private endpoint policy",
            status=status,
            connection_profile_id="profile_postgres_ops_readonly",
            egress_boundary="approved_private_endpoint",
            policy_mode="approved_private_endpoint",
            runtime_boundary="axis-egress-policy-enforcer",
            private_endpoint_ref=private_endpoint_ref,
            created_by="network-policy-owner-role",
            policy_document={
                "allowed_destination": "operations-postgres-readonly.internal",
                "transport": "private_endpoint",
                "live_query_mode": "read_only_snapshot",
            },
            evidence_refs=[str(audit_event.id)],
            audit_event_id=audit_event.id,
            notes=["Persisted egress policy for external DB preflight tests."],
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
    with session_scope(session_factory) as session:
        seed_active_connector_manifest(AxisPersistenceRepository(session))
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


def test_create_connector_run_endpoint_requires_active_preview_manifest(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        seed_registered_connector_manifest(AxisPersistenceRepository(session))
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/runs",
        json=connector_run_request().model_dump(),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "connector_manifest_not_active_preview"


def test_create_connector_run_endpoint_reports_missing_connector_registry(
    empty_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = empty_session_factory
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/runs",
        json=connector_run_request().model_dump(),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "code": "NOT_FOUND",
        "message": "Manufacturing connector registry reference record not found.",
        "surface": "connectors",
    }


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


def test_dispatch_scheduled_connector_sync_requires_current_active_manifest(
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
            "run_id": "run_file_csv_assets_dispatch_deprecated_manifest",
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

    with session_scope(session_factory) as session:
        transition_demo_connector_manifest_lifecycle(
            AxisPersistenceRepository(session),
            "file_csv_manufacturing_assets",
            ConnectorManifestLifecycleRequest(
                tenant_id="tenant_demo_manufacturing",
                transitioned_by="platform-connector-owner-role",
                target_status="deprecated",
                actor_scopes=["connectors:manifest:lifecycle"],
                transition_reason="Retired before scheduled sync dispatch.",
                evidence_refs=["test://connector-run-dispatch-deprecated-manifest"],
            ),
        )

    response = client.post(
        "/demo/manufacturing/connectors/runs/"
        "run_file_csv_assets_dispatch_deprecated_manifest/dispatch",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "dispatch_id": "dispatch_file_csv_assets_deprecated_manifest",
            "dispatched_by": "axis-scheduler-role",
            "actor_scopes": ["connectors:sync:dispatch"],
            "credential_lease_id": "lease_file_csv_readonly_20260622",
            "idempotency_key": "idem_dispatch_file_csv_assets_deprecated_manifest",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "connector_manifest_not_active_preview"

    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        run = repository.get_connector_run(
            "tenant_demo_manufacturing",
            "run_file_csv_assets_dispatch_deprecated_manifest",
        )
        events = repository.list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.sync_dispatch_deferred",
        )

    assert run is not None
    assert run.status == "sync_schedule_deferred"
    assert run.result_summary.get("sync_dispatch_result") is None
    assert events == []


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


def test_execute_scheduled_connector_sync_requires_current_active_manifest(
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
        run_id="run_file_csv_assets_scheduled_execute_deprecated_manifest",
        dispatch_id="dispatch_file_csv_assets_deprecated_manifest",
        dispatch_idempotency_key="idem_dispatch_file_csv_assets_deprecated_manifest",
    )

    with session_scope(session_factory) as session:
        transition_demo_connector_manifest_lifecycle(
            AxisPersistenceRepository(session),
            "file_csv_manufacturing_assets",
            ConnectorManifestLifecycleRequest(
                tenant_id="tenant_demo_manufacturing",
                transitioned_by="platform-connector-owner-role",
                target_status="deprecated",
                actor_scopes=["connectors:manifest:lifecycle"],
                transition_reason="Retired before scheduled sync execution.",
                evidence_refs=["test://connector-run-deprecated-manifest"],
            ),
        )

    response = client.post(
        "/demo/manufacturing/connectors/runs/"
        "run_file_csv_assets_scheduled_execute_deprecated_manifest/execute-sync",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "execution_id": "sync_exec_file_csv_assets_deprecated_manifest",
            "executed_by": "axis-sync-worker-role",
            "actor_scopes": ["connectors:sync:execute"],
            "credential_lease_id": "lease_file_csv_readonly_20260622",
            "idempotency_key": "idem_sync_exec_file_csv_assets_deprecated_manifest",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "connector_manifest_not_active_preview"

    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        run = repository.get_connector_run(
            "tenant_demo_manufacturing",
            "run_file_csv_assets_scheduled_execute_deprecated_manifest",
        )
        events = repository.list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.sync_execution_deferred",
        )

    assert run is not None
    assert run.status == "sync_dispatch_deferred"
    assert run.result_summary.get("sync_execution_result") is None
    assert events == []


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
        seed_external_db_egress_policy(repository)
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
        "egress_policy_evidence_status": "validated",
        "egress_policy_runtime_boundary": "axis-egress-policy-enforcer",
        "egress_policy_result_status": "egress_policy_approved",
        "egress_policy_ref": (
            "self-hosted-egress-policy://tenant_demo_manufacturing/"
            "egress_policy_private_endpoint_ops"
        ),
        "egress_policy_scope": (
            "external_db_operational_mirror:profile_postgres_ops_readonly"
        ),
        "egress_policy_mode": "approved_private_endpoint",
        "egress_policy_private_endpoint_ref": (
            "private-endpoint://tenant_demo_manufacturing/"
            "persisted-operations-postgres-readonly"
        ),
        "credential_lease_evidence_status": "validated",
        "credential_lease_id": "lease_external_db_readonly_20260622",
        "credential_lease_mode": "self_hosted_vault_kms_lease",
        "credential_lease_runtime_boundary": "axis-credential-lease-broker",
        "credential_lease_result_status": "lease_executed",
        "credential_lease_ref": (
            "self-hosted-vault-kms://tenant_demo_manufacturing/"
            "lease_external_db_readonly_20260622"
        ),
        "credential_lease_secret_material_returned": "false",
        "secret_reference_evidence_status": "validated",
        "secret_reference_runtime_boundary": "axis-secret-reference-resolver",
        "secret_reference_result_status": "secret_reference_validated",
        "secret_reference_scope": (
            "external_db_operational_mirror:profile_postgres_ops_readonly"
        ),
        "secret_reference_access_mode": "lease_scoped_secret_ref",
        "secret_reference_lease_ref": (
            "self-hosted-vault-kms://tenant_demo_manufacturing/"
            "lease_external_db_readonly_20260622"
        ),
        "secret_reference_material_returned": "false",
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
        repository = AxisPersistenceRepository(session)
        events = repository.list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.sync_execution_preflight_passed",
        )
        checkpoints = repository.list_connector_sync_checkpoints(
            "tenant_demo_manufacturing",
            run_id="run_external_db_orders_live_preflight_passed_20260622",
        )

    assert len(events) == 1
    assert events[0].payload["sync_execution_result"]["result_summary"][
        "egress_policy_decision"
    ] == "approved_private_endpoint"
    assert "vault://" not in str(events[0].payload).lower()
    assert "credential_value" not in str(events[0].payload).lower()
    assert "dsn" not in str(events[0].payload).lower()
    assert len(checkpoints) == 1
    assert checkpoints[0].checkpoint_id == (
        "chk_sync_exec_external_db_orders_live_preflight_passed_20260622_1400"
    )
    assert checkpoints[0].checkpoint_type == "sync_execution"
    assert checkpoints[0].status == "sync_execution_preflight_passed"
    assert checkpoints[0].sequence == 1
    assert checkpoints[0].adapter == "axis-postgres-external-db-sync-executor"
    assert checkpoints[0].result_summary["live_query_preflight_status"] == "passed"
    assert checkpoints[0].result_summary["external_query_started"] == "false"
    assert checkpoints[0].result_summary["credential_material_returned"] == "false"
    assert checkpoints[0].evidence_refs == [str(events[0].id)]
    assert "vault://" not in str(checkpoints[0].cursor).lower()
    assert "credential_value" not in str(checkpoints[0].cursor).lower()
    assert "dsn" not in str(checkpoints[0].cursor).lower()


def test_connector_sync_checkpoints_endpoint_returns_public_safe_records(
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
        seed_external_db_egress_policy(repository)
    client = TestClient(app)
    create_dispatched_scheduled_sync(
        client,
        run_id="run_external_db_orders_checkpoint_api_20260625",
        dispatch_id="dispatch_external_db_orders_checkpoint_api_20260625_1400",
        dispatch_idempotency_key="idem_dispatch_external_db_orders_checkpoint_api_20260625",
        connector_id="external_db_operational_mirror",
        credential_handle_id="cred_external_db_readonly",
        credential_lease_id="lease_external_db_readonly_20260622",
        input_summary={
            "connection_profile_id": "profile_postgres_ops_readonly",
            "schema_name": "operations",
            "table_name": "production_orders",
            "record_count": "2",
            "live_query_requested": "true",
            "query_mode": "read_only_snapshot",
            "egress_policy_id": "egress_policy_private_endpoint_ops",
            "egress_boundary": "approved_private_endpoint",
            "credential_access_mode": "lease_scoped_secret_ref",
        },
    )
    execute_response = client.post(
        "/demo/manufacturing/connectors/runs/"
        "run_external_db_orders_checkpoint_api_20260625/execute-sync",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "execution_id": "sync_exec_external_db_orders_checkpoint_api_20260625_1400",
            "executed_by": "axis-sync-worker-role",
            "actor_scopes": ["connectors:sync:execute"],
            "credential_lease_id": "lease_external_db_readonly_20260622",
            "idempotency_key": "idem_sync_exec_external_db_orders_checkpoint_api_20260625",
        },
    )
    assert execute_response.status_code == 200

    response = client.get(
        "/demo/manufacturing/connectors/runs/checkpoints",
        params={
            "tenant_id": "tenant_demo_manufacturing",
            "run_id": "run_external_db_orders_checkpoint_api_20260625",
            "actor_scopes": ["connectors:sync:checkpoint:read"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["registry_status"] == "ready"
    assert body["metrics"][0]["label"] == "Sync Checkpoints"
    assert body["metrics"][0]["value"] == "1"
    assert body["checkpoint_notes"] == [
        "Sync checkpoints are tenant-scoped runtime evidence for retry/resume.",
        "Checkpoint cursors are public-safe and exclude raw credentials.",
    ]
    assert len(body["checkpoints"]) == 1
    checkpoint = body["checkpoints"][0]
    assert checkpoint["connector_id"] == "external_db_operational_mirror"
    assert checkpoint["run_id"] == "run_external_db_orders_checkpoint_api_20260625"
    assert checkpoint["checkpoint_id"] == (
        "chk_sync_exec_external_db_orders_checkpoint_api_20260625_1400"
    )
    assert checkpoint["status"] == "sync_execution_preflight_passed"
    assert checkpoint["sequence"] == 1
    assert checkpoint["cursor"]["live_query_preflight_status"] == "passed"
    assert checkpoint["result_summary"]["credential_material_returned"] == "false"
    assert checkpoint["evidence_refs"]
    assert "vault://" not in str(body).lower()
    assert "credential_value" not in str(body).lower()
    assert "dsn" not in str(body).lower()


def test_connector_sync_checkpoints_endpoint_writes_read_audit_event(
    session_factory: sessionmaker[Session],
) -> None:
    created_at = datetime(2026, 6, 25, 10, 0, tzinfo=UTC)
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_sync_checkpoint(
            repository,
            checkpoint_id="chk_checkpoint_read_audit",
            run_id="run_checkpoint_read_audit",
            sequence=1,
            created_at=created_at,
        )
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/connectors/runs/checkpoints",
        params={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "external_db_operational_mirror",
            "run_id": "run_checkpoint_read_audit",
            "status": "sync_execution_preflight_passed",
            "actor_scopes": ["connectors:sync:checkpoint:read"],
            "limit": 25,
        },
    )

    assert response.status_code == 200
    with session_scope(session_factory) as session:
        events = AxisPersistenceRepository(session).list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.sync_checkpoints_read",
        )

    assert len(events) == 1
    event = events[0]
    assert event.actor_id == "connector-sync-checkpoint-reader"
    assert event.payload == {
        "connector_id": "external_db_operational_mirror",
        "run_id": "run_checkpoint_read_audit",
        "status": "sync_execution_preflight_passed",
        "created_after": None,
        "created_before": None,
        "limit": 25,
        "returned_checkpoint_count": 1,
        "checkpoint_ids": ["chk_checkpoint_read_audit"],
        "required_permission": "connectors:sync:checkpoint:read",
        "read_scope_source": "demo_actor_scopes",
    }
    assert "vault://" not in str(event.payload).lower()
    assert "credential_value" not in str(event.payload).lower()
    assert "dsn" not in str(event.payload).lower()


def test_connector_sync_checkpoint_claim_records_worker_lease_without_live_sync(
    session_factory: sessionmaker[Session],
) -> None:
    created_at = datetime(2026, 6, 25, 10, 0, tzinfo=UTC)
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_sync_checkpoint(
            repository,
            checkpoint_id="chk_checkpoint_worker_claim",
            run_id="run_checkpoint_worker_claim",
            sequence=1,
            created_at=created_at,
        )
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/runs/checkpoints/"
        "chk_checkpoint_worker_claim/claims",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "claim_id": "claim_checkpoint_worker_20260625_1000",
            "claimed_by": "axis-sync-worker-role",
            "actor_scopes": ["connectors:sync:checkpoint:claim"],
            "idempotency_key": "idem_claim_checkpoint_worker_20260625_1000",
            "lease_duration_seconds": 900,
            "notes": ["Claim checkpoint for retry planning only."],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["connector_id"] == "external_db_operational_mirror"
    assert body["run_id"] == "run_checkpoint_worker_claim"
    assert body["checkpoint_id"] == "chk_checkpoint_worker_claim"
    assert body["claim_id"] == "claim_checkpoint_worker_20260625_1000"
    assert body["status"] == "claimed"
    assert body["claimed_by"] == "axis-sync-worker-role"
    assert body["lease_duration_seconds"] == 900
    assert body["claim_result"] == {
        "external_sync_started": False,
        "secret_material_returned": False,
        "worker_claim_only": True,
    }
    assert body["audit_event_type"] == "connector.run.sync_checkpoint_claimed"
    assert "vault://" not in str(body).lower()
    assert "credential_value" not in str(body).lower()
    assert "dsn" not in str(body).lower()

    with session_scope(session_factory) as session:
        events = AxisPersistenceRepository(session).list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.sync_checkpoint_claimed",
        )

    assert len(events) == 1
    assert events[0].actor_id == "axis-sync-worker-role"
    assert events[0].payload["checkpoint_id"] == "chk_checkpoint_worker_claim"
    assert events[0].payload["claim_id"] == "claim_checkpoint_worker_20260625_1000"
    assert events[0].payload["external_sync_started"] is False
    assert events[0].payload["secret_material_returned"] is False


def test_connector_sync_checkpoint_claim_replays_same_idempotency_key(
    session_factory: sessionmaker[Session],
) -> None:
    created_at = datetime(2026, 6, 25, 10, 0, tzinfo=UTC)
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_sync_checkpoint(
            repository,
            checkpoint_id="chk_checkpoint_worker_replay",
            run_id="run_checkpoint_worker_replay",
            sequence=1,
            created_at=created_at,
        )
    client = TestClient(app)
    payload = {
        "tenant_id": "tenant_demo_manufacturing",
        "claim_id": "claim_checkpoint_replay_20260625_1000",
        "claimed_by": "axis-sync-worker-role",
        "actor_scopes": ["connectors:sync:checkpoint:claim"],
        "idempotency_key": "idem_claim_checkpoint_replay_20260625_1000",
        "lease_duration_seconds": 900,
    }

    first_response = client.post(
        "/demo/manufacturing/connectors/runs/checkpoints/"
        "chk_checkpoint_worker_replay/claims",
        json=payload,
    )
    second_response = client.post(
        "/demo/manufacturing/connectors/runs/checkpoints/"
        "chk_checkpoint_worker_replay/claims",
        json=payload,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 200
    assert second_response.json() == first_response.json()
    with session_scope(session_factory) as session:
        events = AxisPersistenceRepository(session).list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.sync_checkpoint_claimed",
        )

    assert len(events) == 1


def test_connector_sync_checkpoint_claim_rejects_second_active_worker_claim(
    session_factory: sessionmaker[Session],
) -> None:
    created_at = datetime(2026, 6, 25, 10, 0, tzinfo=UTC)
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_sync_checkpoint(
            repository,
            checkpoint_id="chk_checkpoint_worker_conflict",
            run_id="run_checkpoint_worker_conflict",
            sequence=1,
            created_at=created_at,
        )
    client = TestClient(app)
    first_response = client.post(
        "/demo/manufacturing/connectors/runs/checkpoints/"
        "chk_checkpoint_worker_conflict/claims",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "claim_id": "claim_checkpoint_conflict_20260625_1000",
            "claimed_by": "axis-sync-worker-role-a",
            "actor_scopes": ["connectors:sync:checkpoint:claim"],
            "idempotency_key": "idem_claim_checkpoint_conflict_20260625_1000",
            "lease_duration_seconds": 900,
        },
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/demo/manufacturing/connectors/runs/checkpoints/"
        "chk_checkpoint_worker_conflict/claims",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "claim_id": "claim_checkpoint_conflict_20260625_1005",
            "claimed_by": "axis-sync-worker-role-b",
            "actor_scopes": ["connectors:sync:checkpoint:claim"],
            "idempotency_key": "idem_claim_checkpoint_conflict_20260625_1005",
            "lease_duration_seconds": 900,
        },
    )

    assert second_response.status_code == 409
    assert second_response.json()["detail"] == {
        "code": "CONFLICT",
        "message": "The connector sync checkpoint claim conflicts with existing evidence.",
        "reason": "active_checkpoint_claim_exists",
        "active_claim_id": "claim_checkpoint_conflict_20260625_1000",
    }
    with session_scope(session_factory) as session:
        events = AxisPersistenceRepository(session).list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.sync_checkpoint_claimed",
        )

    assert len(events) == 1
    assert events[0].actor_id == "axis-sync-worker-role-a"


def test_connector_sync_checkpoint_claim_expires_old_claim_before_takeover(
    session_factory: sessionmaker[Session],
) -> None:
    created_at = datetime(2026, 6, 25, 10, 0, tzinfo=UTC)
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_sync_checkpoint(
            repository,
            checkpoint_id="chk_checkpoint_worker_takeover",
            run_id="run_checkpoint_worker_takeover",
            sequence=1,
            created_at=created_at,
        )
        repository.create_connector_sync_checkpoint_claim(
            ConnectorSyncCheckpointClaimCreate(
                tenant_id="tenant_demo_manufacturing",
                connector_id="external_db_operational_mirror",
                run_id="run_checkpoint_worker_takeover",
                checkpoint_id="chk_checkpoint_worker_takeover",
                claim_id="claim_checkpoint_takeover_expired_20260625_0900",
                status="claimed",
                claimed_by="axis-sync-worker-role-old",
                idempotency_key="idem_claim_checkpoint_takeover_expired_20260625_0900",
                lease_duration_seconds=60,
                lease_expires_at=datetime(2026, 1, 1, 9, 1, tzinfo=UTC),
                claim_result={
                    "external_sync_started": False,
                    "secret_material_returned": False,
                    "worker_claim_only": True,
                },
                audit_event_type="connector.run.sync_checkpoint_claimed",
            )
        )
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/runs/checkpoints/"
        "chk_checkpoint_worker_takeover/claims",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "claim_id": "claim_checkpoint_takeover_20260625_1000",
            "claimed_by": "axis-sync-worker-role-new",
            "actor_scopes": ["connectors:sync:checkpoint:claim"],
            "idempotency_key": "idem_claim_checkpoint_takeover_20260625_1000",
            "lease_duration_seconds": 900,
        },
    )

    assert response.status_code == 201
    assert response.json()["claim_id"] == "claim_checkpoint_takeover_20260625_1000"
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        claims = repository.list_connector_sync_checkpoint_claims(
            "tenant_demo_manufacturing",
            checkpoint_id="chk_checkpoint_worker_takeover",
        )
        events = repository.list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.sync_checkpoint_claim_expired",
        )

    claims_by_id = {claim.claim_id: claim for claim in claims}
    assert claims_by_id[
        "claim_checkpoint_takeover_expired_20260625_0900"
    ].status == "expired"
    assert claims_by_id["claim_checkpoint_takeover_20260625_1000"].status == "claimed"
    assert len(events) == 1
    assert events[0].actor_id == "axis-sync-worker-role-new"
    assert events[0].payload["checkpoint_id"] == "chk_checkpoint_worker_takeover"
    assert (
        events[0].payload["expired_claim_id"]
        == "claim_checkpoint_takeover_expired_20260625_0900"
    )
    assert events[0].payload["replacement_claim_id"] == "claim_checkpoint_takeover_20260625_1000"
    assert events[0].payload["external_sync_started"] is False
    assert events[0].payload["secret_material_returned"] is False


def test_connector_sync_checkpoint_claim_renew_extends_worker_lease_without_live_sync(
    session_factory: sessionmaker[Session],
) -> None:
    created_at = datetime(2026, 6, 25, 10, 0, tzinfo=UTC)
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_sync_checkpoint(
            repository,
            checkpoint_id="chk_checkpoint_worker_renew",
            run_id="run_checkpoint_worker_renew",
            sequence=1,
            created_at=created_at,
        )
    client = TestClient(app)
    claim_response = client.post(
        "/demo/manufacturing/connectors/runs/checkpoints/"
        "chk_checkpoint_worker_renew/claims",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "claim_id": "claim_checkpoint_renew_20260625_1000",
            "claimed_by": "axis-sync-worker-role",
            "actor_scopes": ["connectors:sync:checkpoint:claim"],
            "idempotency_key": "idem_claim_checkpoint_renew_20260625_1000",
            "lease_duration_seconds": 900,
        },
    )
    assert claim_response.status_code == 201

    response = client.post(
        "/demo/manufacturing/connectors/runs/checkpoints/"
        "chk_checkpoint_worker_renew/claims/"
        "claim_checkpoint_renew_20260625_1000/renew",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "renewed_by": "axis-sync-worker-role",
            "actor_scopes": ["connectors:sync:checkpoint:claim:renew"],
            "renewed_at": "2026-06-25T10:08:00Z",
            "lease_duration_seconds": 1200,
            "renewal_reason": "worker still preparing retry window",
            "notes": ["Renewed before provider-specific live sync exists."],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "claimed"
    assert body["claim_id"] == "claim_checkpoint_renew_20260625_1000"
    assert body["renewal_count"] == 1
    assert body["renewed_by"] == "axis-sync-worker-role"
    assert body["renewed_at"] == "2026-06-25T10:08:00Z"
    assert body["lease_duration_seconds"] == 1200
    assert body["lease_expires_at"] == "2026-06-25T10:28:00Z"
    assert body["claim_result"] == {
        "external_sync_started": False,
        "secret_material_returned": False,
        "worker_claim_only": True,
    }
    assert body["audit_event_type"] == "connector.run.sync_checkpoint_claim_renewed"
    assert "vault://" not in str(body).lower()
    assert "credential_value" not in str(body).lower()
    assert "dsn" not in str(body).lower()

    with session_scope(session_factory) as session:
        events = AxisPersistenceRepository(session).list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.sync_checkpoint_claim_renewed",
        )

    assert len(events) == 1
    assert events[0].actor_id == "axis-sync-worker-role"
    assert events[0].payload["checkpoint_id"] == "chk_checkpoint_worker_renew"
    assert events[0].payload["claim_id"] == "claim_checkpoint_renew_20260625_1000"
    assert events[0].payload["external_sync_started"] is False
    assert events[0].payload["secret_material_returned"] is False


def test_connector_sync_checkpoint_claim_release_closes_worker_lease_without_live_sync(
    session_factory: sessionmaker[Session],
) -> None:
    created_at = datetime(2026, 6, 25, 10, 0, tzinfo=UTC)
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_sync_checkpoint(
            repository,
            checkpoint_id="chk_checkpoint_worker_release",
            run_id="run_checkpoint_worker_release",
            sequence=1,
            created_at=created_at,
        )
    client = TestClient(app)
    claim_response = client.post(
        "/demo/manufacturing/connectors/runs/checkpoints/"
        "chk_checkpoint_worker_release/claims",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "claim_id": "claim_checkpoint_release_20260625_1000",
            "claimed_by": "axis-sync-worker-role",
            "actor_scopes": ["connectors:sync:checkpoint:claim"],
            "idempotency_key": "idem_claim_checkpoint_release_20260625_1000",
            "lease_duration_seconds": 900,
        },
    )
    assert claim_response.status_code == 201

    response = client.post(
        "/demo/manufacturing/connectors/runs/checkpoints/"
        "chk_checkpoint_worker_release/claims/"
        "claim_checkpoint_release_20260625_1000/release",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "released_by": "axis-sync-worker-role",
            "actor_scopes": ["connectors:sync:checkpoint:claim:release"],
            "released_at": "2026-06-25T10:11:00Z",
            "release_reason": "retry window handed back to scheduler",
            "notes": ["Released without external connector execution."],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "released"
    assert body["claim_id"] == "claim_checkpoint_release_20260625_1000"
    assert body["released_by"] == "axis-sync-worker-role"
    assert body["released_at"] == "2026-06-25T10:11:00Z"
    assert body["release_reason"] == "retry window handed back to scheduler"
    assert body["claim_result"] == {
        "external_sync_started": False,
        "secret_material_returned": False,
        "worker_claim_only": True,
    }
    assert body["audit_event_type"] == "connector.run.sync_checkpoint_claim_released"
    assert "vault://" not in str(body).lower()
    assert "credential_value" not in str(body).lower()
    assert "dsn" not in str(body).lower()

    with session_scope(session_factory) as session:
        events = AxisPersistenceRepository(session).list_audit_events(
            "tenant_demo_manufacturing",
            event_type="connector.run.sync_checkpoint_claim_released",
        )

    assert len(events) == 1
    assert events[0].actor_id == "axis-sync-worker-role"
    assert events[0].payload["checkpoint_id"] == "chk_checkpoint_worker_release"
    assert events[0].payload["claim_id"] == "claim_checkpoint_release_20260625_1000"
    assert events[0].payload["external_sync_started"] is False
    assert events[0].payload["secret_material_returned"] is False


def test_connector_sync_checkpoint_repository_filters_created_before(
    session_factory: sessionmaker[Session],
) -> None:
    older = datetime(2026, 6, 25, 10, 0, tzinfo=UTC)
    newer = older + timedelta(hours=1)

    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_sync_checkpoint(
            repository,
            checkpoint_id="chk_checkpoint_page_older",
            run_id="run_checkpoint_page_older",
            sequence=1,
            created_at=older,
        )
        seed_connector_sync_checkpoint(
            repository,
            checkpoint_id="chk_checkpoint_page_newer",
            run_id="run_checkpoint_page_newer",
            sequence=2,
            created_at=newer,
        )

        checkpoints = repository.list_connector_sync_checkpoints(
            "tenant_demo_manufacturing",
            created_before=newer,
        )

    assert [checkpoint.checkpoint_id for checkpoint in checkpoints] == [
        "chk_checkpoint_page_older"
    ]


def test_connector_sync_checkpoint_repository_filters_created_after(
    session_factory: sessionmaker[Session],
) -> None:
    older = datetime(2026, 6, 25, 10, 0, tzinfo=UTC)
    newer = older + timedelta(hours=1)

    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_sync_checkpoint(
            repository,
            checkpoint_id="chk_checkpoint_after_older",
            run_id="run_checkpoint_after_older",
            sequence=1,
            created_at=older,
        )
        seed_connector_sync_checkpoint(
            repository,
            checkpoint_id="chk_checkpoint_after_newer",
            run_id="run_checkpoint_after_newer",
            sequence=2,
            created_at=newer,
        )

        checkpoints = repository.list_connector_sync_checkpoints(
            "tenant_demo_manufacturing",
            created_after=older,
        )

    assert [checkpoint.checkpoint_id for checkpoint in checkpoints] == [
        "chk_checkpoint_after_newer"
    ]


def test_connector_sync_checkpoint_registry_rejects_invalid_time_window(
    session_factory: sessionmaker[Session],
) -> None:
    boundary = datetime(2026, 6, 25, 10, 0, tzinfo=UTC)

    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        with pytest.raises(ConnectorRunValidationError) as exc_info:
            build_connector_sync_checkpoint_registry(
                repository,
                ConnectorSyncCheckpointQuery(
                    tenant_id="tenant_demo_manufacturing",
                    created_after=boundary,
                    created_before=boundary,
                ),
            )

    assert exc_info.value.reason == "invalid_checkpoint_time_window"


def test_connector_sync_checkpoints_endpoint_filters_created_before(
    session_factory: sessionmaker[Session],
) -> None:
    older = datetime(2026, 6, 25, 10, 0, tzinfo=UTC)
    newer = older + timedelta(hours=1)
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_sync_checkpoint(
            repository,
            checkpoint_id="chk_checkpoint_api_page_older",
            run_id="run_checkpoint_api_page_older",
            sequence=1,
            created_at=older,
        )
        seed_connector_sync_checkpoint(
            repository,
            checkpoint_id="chk_checkpoint_api_page_newer",
            run_id="run_checkpoint_api_page_newer",
            sequence=2,
            created_at=newer,
        )
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/connectors/runs/checkpoints",
        params={
            "tenant_id": "tenant_demo_manufacturing",
            "actor_scopes": ["connectors:sync:checkpoint:read"],
            "created_before": newer.isoformat().replace("+00:00", "Z"),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [checkpoint["checkpoint_id"] for checkpoint in body["checkpoints"]] == [
        "chk_checkpoint_api_page_older"
    ]


def test_connector_sync_checkpoints_endpoint_filters_created_after(
    session_factory: sessionmaker[Session],
) -> None:
    older = datetime(2026, 6, 25, 10, 0, tzinfo=UTC)
    newer = older + timedelta(hours=1)
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_sync_checkpoint(
            repository,
            checkpoint_id="chk_checkpoint_api_after_older",
            run_id="run_checkpoint_api_after_older",
            sequence=1,
            created_at=older,
        )
        seed_connector_sync_checkpoint(
            repository,
            checkpoint_id="chk_checkpoint_api_after_newer",
            run_id="run_checkpoint_api_after_newer",
            sequence=2,
            created_at=newer,
        )
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/connectors/runs/checkpoints",
        params={
            "tenant_id": "tenant_demo_manufacturing",
            "actor_scopes": ["connectors:sync:checkpoint:read"],
            "created_after": older.isoformat().replace("+00:00", "Z"),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [checkpoint["checkpoint_id"] for checkpoint in body["checkpoints"]] == [
        "chk_checkpoint_api_after_newer"
    ]


def test_connector_sync_checkpoints_endpoint_rejects_invalid_time_window(
    session_factory: sessionmaker[Session],
) -> None:
    boundary = datetime(2026, 6, 25, 10, 0, tzinfo=UTC)
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/connectors/runs/checkpoints",
        params={
            "tenant_id": "tenant_demo_manufacturing",
            "actor_scopes": ["connectors:sync:checkpoint:read"],
            "created_after": boundary.isoformat().replace("+00:00", "Z"),
            "created_before": boundary.isoformat().replace("+00:00", "Z"),
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_FAILED"
    assert response.json()["detail"]["reason"] == "invalid_checkpoint_time_window"


def test_connector_sync_checkpoints_endpoint_requires_read_scope() -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/connectors/runs/checkpoints",
        params={
            "tenant_id": "tenant_demo_manufacturing",
            "actor_scopes": ["connectors:sync:execute"],
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "missing_required_scope"
    assert response.json()["detail"]["required_permission"] == (
        "connectors:sync:checkpoint:read"
    )


def test_execute_external_db_live_query_preflight_blocks_secret_material_returned(
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
        seed_external_db_credential_lease(repository, secret_material_returned=True)
        seed_external_db_egress_policy(repository)
    client = TestClient(app)
    create_dispatched_scheduled_sync(
        client,
        run_id="run_external_db_orders_live_preflight_secret_blocked_20260622",
        dispatch_id="dispatch_external_db_orders_live_preflight_secret_blocked_20260622_1400",
        dispatch_idempotency_key=(
            "idem_dispatch_external_db_orders_live_preflight_secret_blocked_20260622_1400"
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
        "run_external_db_orders_live_preflight_secret_blocked_20260622/execute-sync",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "execution_id": (
                "sync_exec_external_db_orders_live_preflight_secret_blocked_20260622_1400"
            ),
            "executed_by": "axis-sync-worker-role",
            "actor_scopes": ["connectors:sync:execute"],
            "credential_lease_id": "lease_external_db_readonly_20260622",
            "idempotency_key": (
                "idem_sync_exec_external_db_orders_live_preflight_secret_blocked_20260622_1400"
            ),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "sync_execution_preflight_blocked"
    assert body["audit_event_type"] == "connector.run.sync_execution_preflight_blocked"
    result_summary = body["sync_execution_result"]["result_summary"]
    assert result_summary["credential_lease_evidence_status"] == "failed"
    assert result_summary["credential_lease_result_status"] == "lease_executed"
    assert result_summary["credential_lease_secret_material_returned"] == "true"
    assert result_summary["secret_retrieval_decision"] == "blocked_secret_material_returned"
    assert result_summary["external_query_started"] == "false"
    assert result_summary["credential_material_returned"] == "false"
    assert "vault://" not in str(body).lower()
    assert "credential_value" not in str(body).lower()
    assert "dsn" not in str(body).lower()


def test_execute_external_db_live_query_preflight_blocks_unknown_egress_policy(
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
        run_id="run_external_db_orders_live_preflight_unknown_policy_20260622",
        dispatch_id="dispatch_external_db_orders_live_preflight_unknown_policy_20260622_1400",
        dispatch_idempotency_key=(
            "idem_dispatch_external_db_orders_live_preflight_unknown_policy_20260622_1400"
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
            "egress_policy_id": "egress_policy_unregistered",
            "egress_boundary": "approved_private_endpoint",
            "credential_access_mode": "lease_scoped_secret_ref",
        },
    )

    response = client.post(
        "/demo/manufacturing/connectors/runs/"
        "run_external_db_orders_live_preflight_unknown_policy_20260622/execute-sync",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "execution_id": (
                "sync_exec_external_db_orders_live_preflight_unknown_policy_20260622_1400"
            ),
            "executed_by": "axis-sync-worker-role",
            "actor_scopes": ["connectors:sync:execute"],
            "credential_lease_id": "lease_external_db_readonly_20260622",
            "idempotency_key": (
                "idem_sync_exec_external_db_orders_live_preflight_unknown_policy_20260622_1400"
            ),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "sync_execution_preflight_blocked"
    assert body["audit_event_type"] == "connector.run.sync_execution_preflight_blocked"
    result_summary = body["sync_execution_result"]["result_summary"]
    assert result_summary["egress_policy_evidence_status"] == "missing"
    assert result_summary["egress_policy_result_status"] == "egress_policy_not_found"
    assert result_summary["egress_policy_decision"] == "blocked_policy_not_found"
    assert result_summary["secret_retrieval_decision"] == "not_started"
    assert result_summary["credential_lease_evidence_status"] == "validated"
    assert result_summary["external_query_started"] == "false"
    assert result_summary["credential_material_returned"] == "false"
    assert result_summary["graph_mutation_started"] == "false"
    assert "vault://" not in str(body).lower()
    assert "password" not in str(body).lower()
    assert "credential_value" not in str(body).lower()
    assert "dsn" not in str(body).lower()


def test_execute_external_db_live_query_preflight_blocks_missing_persisted_egress_policy(
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
        run_id="run_external_db_orders_live_preflight_missing_policy_20260622",
        dispatch_id="dispatch_external_db_orders_live_preflight_missing_policy_20260622_1400",
        dispatch_idempotency_key=(
            "idem_dispatch_external_db_orders_live_preflight_missing_policy_20260622_1400"
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
        "run_external_db_orders_live_preflight_missing_policy_20260622/execute-sync",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "execution_id": (
                "sync_exec_external_db_orders_live_preflight_missing_policy_20260622_1400"
            ),
            "executed_by": "axis-sync-worker-role",
            "actor_scopes": ["connectors:sync:execute"],
            "credential_lease_id": "lease_external_db_readonly_20260622",
            "idempotency_key": (
                "idem_sync_exec_external_db_orders_live_preflight_missing_policy_20260622_1400"
            ),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "sync_execution_preflight_blocked"
    assert body["audit_event_type"] == "connector.run.sync_execution_preflight_blocked"
    result_summary = body["sync_execution_result"]["result_summary"]
    assert result_summary["egress_policy_evidence_status"] == "missing"
    assert result_summary["egress_policy_result_status"] == "egress_policy_not_found"
    assert result_summary["egress_policy_decision"] == "blocked_policy_not_found"
    assert result_summary["secret_retrieval_decision"] == "not_started"
    assert result_summary["external_query_started"] == "false"
    assert result_summary["credential_material_returned"] == "false"
    assert result_summary["graph_mutation_started"] == "false"
    assert "vault://" not in str(body).lower()
    assert "password" not in str(body).lower()
    assert "credential_value" not in str(body).lower()
    assert "dsn" not in str(body).lower()


def test_execute_external_db_live_query_preflight_blocks_missing_secret_reference(
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
        seed_external_db_credential_lease(repository, provider_lease_ref=None)
        seed_external_db_egress_policy(repository)
    client = TestClient(app)
    create_dispatched_scheduled_sync(
        client,
        run_id="run_external_db_orders_live_preflight_missing_ref_20260622",
        dispatch_id="dispatch_external_db_orders_live_preflight_missing_ref_20260622_1400",
        dispatch_idempotency_key=(
            "idem_dispatch_external_db_orders_live_preflight_missing_ref_20260622_1400"
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
        "run_external_db_orders_live_preflight_missing_ref_20260622/execute-sync",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "execution_id": (
                "sync_exec_external_db_orders_live_preflight_missing_ref_20260622_1400"
            ),
            "executed_by": "axis-sync-worker-role",
            "actor_scopes": ["connectors:sync:execute"],
            "credential_lease_id": "lease_external_db_readonly_20260622",
            "idempotency_key": (
                "idem_sync_exec_external_db_orders_live_preflight_missing_ref_20260622_1400"
            ),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "sync_execution_preflight_blocked"
    assert body["audit_event_type"] == "connector.run.sync_execution_preflight_blocked"
    result_summary = body["sync_execution_result"]["result_summary"]
    assert result_summary["egress_policy_evidence_status"] == "validated"
    assert result_summary["credential_lease_evidence_status"] == "failed"
    assert result_summary["credential_lease_ref"] == ""
    assert result_summary["secret_reference_evidence_status"] == "failed"
    assert (
        result_summary["secret_reference_result_status"]
        == "secret_reference_missing_lease_ref"
    )
    assert result_summary["secret_reference_lease_ref"] == ""
    assert result_summary["secret_retrieval_decision"] == "blocked_secret_reference_evidence"
    assert result_summary["external_query_started"] == "false"
    assert result_summary["credential_material_returned"] == "false"
    assert result_summary["graph_mutation_started"] == "false"
    assert "vault://" not in str(body).lower()
    assert "password" not in str(body).lower()
    assert "credential_value" not in str(body).lower()
    assert "dsn" not in str(body).lower()


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
    with session_scope(session_factory) as session:
        seed_active_connector_manifest(AxisPersistenceRepository(session))
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
    assert "/demo/manufacturing/connectors/runs/checkpoints" in paths
    assert "/demo/manufacturing/connectors/runs/{run_id}/dispatch" in paths
    assert "/demo/manufacturing/connectors/runs/{run_id}/execute-sync" in paths
