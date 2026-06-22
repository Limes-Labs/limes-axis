from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.config import Settings
from axis_api.connector_credential_handles import (
    ConnectorCredentialHandleQuery,
    build_connector_credential_handle_registry,
)
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.models import Base
from axis_api.persistence import (
    AxisPersistenceRepository,
    ConnectorCredentialHandleCreate,
    ConnectorCredentialRotationCreate,
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


def seed_connector_credential_handles(repository: AxisPersistenceRepository) -> None:
    repository.create_connector_credential_handle(
        ConnectorCredentialHandleCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="file_csv_manufacturing_assets",
            handle_id="cred_file_csv_readonly",
            display_name="File CSV readonly vault reference",
            status="active",
            secret_provider="external_vault",
            secret_ref="vault://axis/demo/connectors/file-csv-readonly",
            purpose="preview_import_readonly",
            rotation_interval_days=30,
            last_rotated_at=datetime(2026, 6, 1, tzinfo=UTC),
            next_rotation_due_at=datetime(2026, 7, 1, tzinfo=UTC),
            created_by="plant-operations-owner-role",
            labels={"environment": "demo"},
            notes=["Metadata-only handle; no raw credential value is stored."],
        )
    )
    repository.record_connector_credential_rotation(
        ConnectorCredentialRotationCreate(
            tenant_id="tenant_demo_manufacturing",
            handle_id="cred_file_csv_readonly",
            rotated_by="security-operations-role",
            rotated_at=datetime(2026, 6, 22, tzinfo=UTC),
            evidence_ref="change-window-2026-06-22",
            status="rotated",
            notes=["Reference rotated in external vault; Axis stored metadata only."],
        )
    )
    repository.create_connector_credential_handle(
        ConnectorCredentialHandleCreate(
            tenant_id="tenant_other",
            connector_id="file_csv_manufacturing_assets",
            handle_id="cred_other",
            display_name="Other tenant handle",
            status="active",
            secret_provider="external_vault",
            secret_ref="vault://axis/demo/connectors/other",
            purpose="preview_import_readonly",
            rotation_interval_days=30,
            last_rotated_at=datetime(2026, 6, 1, tzinfo=UTC),
            next_rotation_due_at=datetime(2026, 7, 1, tzinfo=UTC),
            created_by="other-owner-role",
        )
    )


def test_build_connector_credential_handle_registry_maps_persisted_handles(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_credential_handles(repository)
        registry = build_connector_credential_handle_registry(
            repository,
            ConnectorCredentialHandleQuery(tenant_id="tenant_demo_manufacturing"),
        )

    assert registry.tenant_id == "tenant_demo_manufacturing"
    assert registry.metrics[0].label == "Credential Handles"
    assert registry.metrics[0].value == "1"
    assert registry.handles[0].handle_id == "cred_file_csv_readonly"
    assert registry.handles[0].secret_provider == "external_vault"
    assert registry.handles[0].secret_ref == "vault://axis/demo/connectors/file-csv-readonly"
    assert registry.handles[0].rotation_status == "healthy"
    assert registry.handles[0].rotation_count == 1
    assert "tenant_other" not in registry.model_dump_json()
    assert "password" not in registry.model_dump_json().lower()
    assert "api_key" not in registry.model_dump_json().lower()
    assert "credential_value" not in registry.model_dump_json().lower()


def test_connector_credential_handles_endpoint_returns_tenant_scoped_records(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        seed_connector_credential_handles(AxisPersistenceRepository(session))
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/connectors/credential-handles",
        params={"tenant_id": "tenant_demo_manufacturing"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["metrics"][0]["value"] == "1"
    assert body["handles"][0]["handle_id"] == "cred_file_csv_readonly"
    assert body["handles"][0]["rotation_status"] == "healthy"
    assert body["handles"][0]["rotation_count"] == 1
    assert "tenant_other" not in str(body)
    assert "password" not in str(body).lower()
    assert "api_key" not in str(body).lower()
    assert "credential_value" not in str(body).lower()


def test_create_connector_credential_handle_rejects_inline_secret_values(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/credential-handles",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "file_csv_manufacturing_assets",
            "handle_id": "cred_file_csv_readonly",
            "display_name": "File CSV readonly vault reference",
            "secret_provider": "external_vault",
            "secret_ref": "literal-password-value",
            "purpose": "preview_import_readonly",
            "rotation_interval_days": 30,
            "created_by": "plant-operations-owner-role",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "invalid_secret_ref"


def test_create_connector_credential_handle_persists_external_reference_only(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/credential-handles",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "file_csv_manufacturing_assets",
            "handle_id": "cred_file_csv_readonly",
            "display_name": "File CSV readonly vault reference",
            "secret_provider": "external_vault",
            "secret_ref": "vault://axis/demo/connectors/file-csv-readonly",
            "purpose": "preview_import_readonly",
            "rotation_interval_days": 30,
            "created_by": "plant-operations-owner-role",
            "labels": {"environment": "demo"},
            "notes": ["Metadata-only handle."],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["handle_id"] == "cred_file_csv_readonly"
    assert body["secret_ref"] == "vault://axis/demo/connectors/file-csv-readonly"
    assert body["rotation_status"] == "healthy"
    assert body["rotation_count"] == 0
    assert "password" not in str(body).lower()
    assert "api_key" not in str(body).lower()
    assert "credential_value" not in str(body).lower()


def test_rotate_connector_credential_handle_records_rotation_history(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        repository.create_connector_credential_handle(
            ConnectorCredentialHandleCreate(
                tenant_id="tenant_demo_manufacturing",
                connector_id="file_csv_manufacturing_assets",
                handle_id="cred_file_csv_readonly",
                display_name="File CSV readonly vault reference",
                status="active",
                secret_provider="external_vault",
                secret_ref="vault://axis/demo/connectors/file-csv-readonly",
                purpose="preview_import_readonly",
                rotation_interval_days=30,
                last_rotated_at=datetime(2026, 6, 1, tzinfo=UTC),
                next_rotation_due_at=datetime(2026, 7, 1, tzinfo=UTC),
                created_by="plant-operations-owner-role",
            )
        )
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/credential-handles/cred_file_csv_readonly/rotations",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "rotated_by": "security-operations-role",
            "rotated_at": "2026-06-22T00:00:00Z",
            "evidence_ref": "change-window-2026-06-22",
            "notes": ["Reference rotated in external vault."],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["handle_id"] == "cred_file_csv_readonly"
    assert body["rotation_count"] == 1
    assert body["last_rotation"]["evidence_ref"] == "change-window-2026-06-22"
    assert body["last_rotated_at"] == "2026-06-22T00:00:00Z"
    assert body["next_rotation_due_at"] == "2026-07-22T00:00:00Z"


def test_openapi_exposes_connector_credential_handle_endpoints() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/demo/manufacturing/connectors/credential-handles" in paths
    assert "/demo/manufacturing/connectors/credential-handles/{handle_id}/rotations" in paths
