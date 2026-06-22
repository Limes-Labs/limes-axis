import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.config import Settings
from axis_api.connector_configurations import (
    ConnectorConfigurationQuery,
    build_connector_configuration_registry,
)
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.models import Base
from axis_api.persistence import AxisPersistenceRepository, ConnectorConfigurationCreate


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


def seed_connector_configurations(repository: AxisPersistenceRepository) -> None:
    repository.create_connector_configuration(
        ConnectorConfigurationCreate(
            tenant_id="tenant_demo_manufacturing",
            connector_id="file_csv_manufacturing_assets",
            display_name="Manufacturing assets CSV intake",
            status="configured_preview_only",
            sync_mode="preview",
            runtime_boundary="axis-connector-sandbox",
            created_by="plant-operations-owner-role",
            configuration_payload={
                "file_name_pattern": "*.csv",
                "mapping_profile": "manufacturing_asset_v1",
                "row_limit": "500",
            },
            credential_ref_ids=[],
            notes=[
                "Preview-only tenant configuration.",
                "No raw credential values are stored.",
            ],
        )
    )
    repository.create_connector_configuration(
        ConnectorConfigurationCreate(
            tenant_id="tenant_other",
            connector_id="file_csv_manufacturing_assets",
            display_name="Other tenant CSV intake",
            status="configured_preview_only",
            sync_mode="preview",
            runtime_boundary="axis-connector-sandbox",
            created_by="other-owner-role",
            configuration_payload={"file_name_pattern": "*.csv"},
            credential_ref_ids=[],
            notes=[],
        )
    )


def test_build_connector_configuration_registry_maps_persisted_records(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_connector_configurations(repository)
        registry = build_connector_configuration_registry(
            repository,
            ConnectorConfigurationQuery(tenant_id="tenant_demo_manufacturing"),
        )

    assert registry.tenant_id == "tenant_demo_manufacturing"
    assert registry.registry_status == "watch"
    assert registry.metrics[0].label == "Configured Connectors"
    assert registry.metrics[0].value == "1"
    assert len(registry.configurations) == 1
    configuration = registry.configurations[0]
    assert configuration.connector_id == "file_csv_manufacturing_assets"
    assert configuration.status == "configured_preview_only"
    assert configuration.sync_mode == "preview"
    assert configuration.runtime_boundary == "axis-connector-sandbox"
    assert configuration.credential_ref_ids == []
    assert configuration.configuration_payload == {
        "file_name_pattern": "*.csv",
        "mapping_profile": "manufacturing_asset_v1",
        "row_limit": "500",
    }
    assert "tenant_other" not in registry.model_dump_json()
    assert "password" not in registry.model_dump_json().lower()
    assert "api_key" not in registry.model_dump_json().lower()
    assert "credential_value" not in registry.model_dump_json().lower()


def test_connector_configurations_endpoint_returns_tenant_scoped_records(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    with session_scope(session_factory) as session:
        seed_connector_configurations(AxisPersistenceRepository(session))
    client = TestClient(app)

    response = client.get(
        "/demo/manufacturing/connectors/configurations",
        params={"tenant_id": "tenant_demo_manufacturing"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["metrics"][0]["value"] == "1"
    assert body["configurations"][0]["connector_id"] == "file_csv_manufacturing_assets"
    assert body["configurations"][0]["status"] == "configured_preview_only"
    assert body["configurations"][0]["credential_ref_ids"] == []
    assert "tenant_other" not in str(body)
    assert "password" not in str(body).lower()
    assert "api_key" not in str(body).lower()
    assert "credential_value" not in str(body).lower()


def test_create_connector_configuration_endpoint_rejects_raw_secret_payloads(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/configurations",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "file_csv_manufacturing_assets",
            "display_name": "Manufacturing assets CSV intake",
            "sync_mode": "preview",
            "created_by": "plant-operations-owner-role",
            "configuration_payload": {
                "file_name_pattern": "*.csv",
                "password": "do-not-store",
            },
            "credential_ref_ids": [],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "raw_secret_field"


def test_create_connector_configuration_endpoint_persists_preview_only_config(
    session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = session_factory
    client = TestClient(app)

    response = client.post(
        "/demo/manufacturing/connectors/configurations",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "file_csv_manufacturing_assets",
            "display_name": "Manufacturing assets CSV intake",
            "sync_mode": "preview",
            "created_by": "plant-operations-owner-role",
            "configuration_payload": {
                "file_name_pattern": "*.csv",
                "mapping_profile": "manufacturing_asset_v1",
            },
            "credential_ref_ids": [],
            "notes": ["Preview-only tenant configuration."],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["connector_id"] == "file_csv_manufacturing_assets"
    assert body["status"] == "configured_preview_only"
    assert body["sync_mode"] == "preview"
    assert body["runtime_boundary"] == "axis-connector-sandbox"
    assert body["credential_ref_ids"] == []
    assert body["configuration_payload"]["mapping_profile"] == "manufacturing_asset_v1"
    assert "password" not in str(body).lower()
    assert "api_key" not in str(body).lower()
    assert "credential_value" not in str(body).lower()


def test_openapi_exposes_connector_configuration_endpoints() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/demo/manufacturing/connectors/configurations" in paths
