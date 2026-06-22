from pathlib import Path
from runpy import run_path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.config import Settings
from axis_api.connectors import (
    ConnectorCsvPreviewRequest,
    ConnectorExternalDbPreviewRequest,
    ManufacturingConnectorRegistry,
    preview_external_db_connector,
    preview_file_csv_connector,
)
from axis_api.db import session_scope
from axis_api.main import create_app
from axis_api.models import Base
from axis_api.persistence import AxisPersistenceRepository, DemoReferenceRecordCreate


def persisted_connector_registry_payload() -> dict:
    return {
        "tenant_id": "tenant_demo_manufacturing",
        "plant_name": "Persisted Ravenna Works",
        "scenario": "Persisted Connector Cockpit",
        "registry_status": "ready",
        "metrics": [
            {
                "label": "Persisted Connector Registry",
                "value": "1",
                "detail": "Loaded from demo_reference_records.",
                "status": "ready",
            }
        ],
        "connectors": [
            {
                "connector_status": "ready",
                "manifest": {
                    "connector_id": "persisted_file_csv_assets",
                    "display_name": "Persisted manufacturing assets CSV",
                    "connector_type": "file_csv",
                    "version": "2026-06-22",
                    "source_type": "file",
                    "sync_modes": ["preview"],
                    "runtime_boundary": "axis-connector-sandbox",
                    "required_permissions": ["connectors:read"],
                    "credential_requirements": {
                        "storage": "none",
                        "required_secret_refs": [],
                        "notes": ["No credential material required."],
                    },
                    "schema_fields": [
                        {
                            "source_column": "asset_id",
                            "target_field": "node_id",
                            "ontology_target": "manufacturing_asset",
                            "data_type": "string",
                            "required": True,
                            "description": "Persisted asset identifier.",
                        }
                    ],
                    "mapping_notes": ["Persisted test fixture."],
                },
                "runtime_policy": {
                    "allowed_operations": ["schema_validate"],
                    "blocked_operations": ["live_sync"],
                    "egress_policy": "no-external-egress",
                    "max_file_size_mb": 5,
                    "row_limit": 500,
                    "payload_policy": "metadata-only",
                },
                "preview_sample": {
                    "file_name": "persisted-assets.csv",
                    "record_count": 0,
                    "headers": ["asset_id"],
                    "sample_rows": [],
                },
            }
        ],
        "connector_notes": ["Persisted connector registry reference."],
    }


def bootstrap_connector_registry() -> ManufacturingConnectorRegistry:
    migration = run_path("migrations/versions/0023_connector_registry_reference.py")
    return ManufacturingConnectorRegistry.model_validate(
        migration["CONNECTOR_REGISTRY_PAYLOAD"]
    )


@pytest.fixture
def connector_session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


def test_connector_runtime_module_does_not_define_registry_seed() -> None:
    source = Path("src/axis_api/connectors.py").read_text()

    assert "def get_manufacturing_connector_registry" not in source


def test_manufacturing_connector_registry_exposes_file_csv_manifest() -> None:
    registry = bootstrap_connector_registry()

    assert registry.tenant_id == "tenant_demo_manufacturing"
    assert registry.registry_status == "watch"
    assert registry.metrics[0].label == "Connector Manifests"
    assert registry.metrics[0].value == "2"
    assert len(registry.connectors) == 2

    connector = registry.connectors[0]
    assert connector.manifest.connector_id == "file_csv_manufacturing_assets"
    assert connector.manifest.connector_type == "file_csv"
    assert connector.manifest.sync_modes == ["preview", "manual_import"]
    assert connector.manifest.runtime_boundary == "axis-connector-sandbox"
    assert connector.manifest.required_permissions == [
        "connectors:read",
        "connectors:file_csv:preview",
    ]
    assert connector.manifest.credential_requirements.storage == "none"
    assert connector.manifest.credential_requirements.required_secret_refs == []
    assert [field.source_column for field in connector.manifest.schema_fields] == [
        "asset_id",
        "asset_name",
        "domain",
        "station",
        "risk_level",
    ]
    assert connector.preview_sample.record_count == 3
    assert "password" not in registry.model_dump_json().lower()
    assert "api_key" not in registry.model_dump_json().lower()
    assert "credential_value" not in registry.model_dump_json().lower()


def test_manufacturing_connector_registry_exposes_external_db_manifest() -> None:
    registry = bootstrap_connector_registry()

    connector = registry.connectors[1]
    assert connector.manifest.connector_id == "external_db_operational_mirror"
    assert connector.manifest.connector_type == "external_db"
    assert connector.manifest.source_type == "database"
    assert connector.manifest.sync_modes == ["schema_preview", "manual_import"]
    assert connector.manifest.runtime_boundary == "axis-connector-sandbox"
    assert connector.manifest.required_permissions == [
        "connectors:read",
        "connectors:external_db:preview",
    ]
    assert connector.manifest.credential_requirements.storage == "external_reference"
    assert connector.manifest.credential_requirements.required_secret_refs == [
        "cred_external_db_readonly"
    ]
    assert connector.runtime_policy.allowed_operations == [
        "schema_validate",
        "metadata_preview",
        "dry_run_diff",
    ]
    assert "live_query" in connector.runtime_policy.blocked_operations
    assert [field.source_column for field in connector.manifest.schema_fields] == [
        "order_id",
        "asset_id",
        "work_center",
        "status",
        "risk_level",
    ]
    serialized = registry.model_dump_json().lower()
    assert "connection_string" not in serialized
    assert "postgres://" not in serialized
    assert "password" not in serialized


def test_connector_registry_reference_contract_is_valid_and_actionable() -> None:
    registry = ManufacturingConnectorRegistry.model_validate(persisted_connector_registry_payload())

    assert registry.tenant_id == "tenant_demo_manufacturing"
    assert registry.scenario == "Persisted Connector Cockpit"
    assert registry.metrics[0].label == "Persisted Connector Registry"
    assert registry.connectors[0].manifest.connector_id == "persisted_file_csv_assets"


def test_connector_registry_bootstrap_payload_matches_contract() -> None:
    registry = bootstrap_connector_registry()

    assert registry.tenant_id == "tenant_demo_manufacturing"
    assert registry.scenario == "Plant Operations Cockpit"
    assert len(registry.connectors) == 2
    assert registry.connectors[0].manifest.connector_id == "file_csv_manufacturing_assets"
    assert registry.connectors[1].manifest.connector_id == "external_db_operational_mirror"
    serialized = registry.model_dump_json().lower()
    assert "password" not in serialized
    assert "api_key" not in serialized
    assert "credential_value" not in serialized


def test_connector_registry_endpoint_is_not_defined_as_runtime_seed() -> None:
    source = Path("src/axis_api/main.py").read_text()

    assert "return get_manufacturing_connector_registry()" not in source


def test_connector_registry_endpoint_returns_persisted_reference_data(
    connector_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = connector_session_factory
    with session_scope(connector_session_factory) as session:
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id="tenant_demo_manufacturing",
                surface="connectors",
                reference_id="manufacturing-connector-registry",
                status="active",
                source="bootstrap",
                version="2026-06-22",
                payload=persisted_connector_registry_payload(),
            )
        )
    client = TestClient(app)
    response = client.get("/demo/manufacturing/connectors")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["scenario"] == "Persisted Connector Cockpit"
    assert body["connectors"][0]["manifest"]["connector_id"] == "persisted_file_csv_assets"
    assert "password" not in str(body).lower()


def test_connector_registry_endpoint_reports_missing_reference_record(
    connector_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = connector_session_factory
    client = TestClient(app)
    response = client.get("/demo/manufacturing/connectors")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND"


def test_connector_registry_endpoint_rejects_invalid_reference_payload(
    connector_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = connector_session_factory
    with session_scope(connector_session_factory) as session:
        payload = persisted_connector_registry_payload()
        payload["tenant_id"] = "tenant_wrong"
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id="tenant_demo_manufacturing",
                surface="connectors",
                reference_id="manufacturing-connector-registry",
                status="active",
                source="bootstrap",
                version="2026-06-22",
                payload=payload,
            )
        )
    client = TestClient(app)
    response = client.get("/demo/manufacturing/connectors")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_FAILED"


def test_file_csv_connector_preview_maps_rows_to_ontology_entities() -> None:
    preview = preview_file_csv_connector(
        ConnectorCsvPreviewRequest(
            tenant_id="tenant_demo_manufacturing",
            connector_id="file_csv_manufacturing_assets",
            file_name="assets.csv",
            csv_content=(
                "asset_id,asset_name,domain,station,risk_level\n"
                "asset_line_2_packaging,Line 2 Packaging,Operations,Line 2,high\n"
                "asset_press_4,Press 4,Maintenance,Press 4,medium\n"
            ),
        )
    )

    assert preview.connector_id == "file_csv_manufacturing_assets"
    assert preview.preview_status == "ready"
    assert preview.sync_mode == "preview_only"
    assert preview.record_count == 2
    assert preview.accepted_record_count == 2
    assert preview.rejected_record_count == 0
    assert preview.validation_issues == []
    assert [entity.node_id for entity in preview.proposed_entities] == [
        "asset_line_2_packaging",
        "asset_press_4",
    ]
    assert preview.proposed_entities[0].node_type == "asset"
    assert preview.proposed_entities[0].ontology_type == "manufacturing_asset"
    assert preview.proposed_entities[0].field_summary == {
        "asset_name": "Line 2 Packaging",
        "domain": "Operations",
        "station": "Line 2",
        "risk_level": "high",
    }
    assert preview.audit_event_preview.event_type == "connector.preview.generated"
    assert preview.audit_event_preview.scope == "file_csv_manufacturing_assets"
    assert "assets.csv" in preview.audit_event_preview.evidence_refs
    assert "csv_content" not in preview.model_dump_json()


def test_file_csv_connector_preview_blocks_missing_required_columns() -> None:
    preview = preview_file_csv_connector(
        ConnectorCsvPreviewRequest(
            tenant_id="tenant_demo_manufacturing",
            connector_id="file_csv_manufacturing_assets",
            file_name="assets.csv",
            csv_content=(
                "asset_id,asset_name,domain,risk_level\n"
                "asset_line_2_packaging,Line 2 Packaging,Operations,high\n"
            ),
        )
    )

    assert preview.preview_status == "blocked"
    assert preview.record_count == 1
    assert preview.accepted_record_count == 0
    assert preview.rejected_record_count == 1
    assert preview.proposed_entities == []
    assert preview.validation_issues == [
        "Missing required column: station",
    ]


def test_file_csv_connector_preview_blocks_unsupported_connector_ids() -> None:
    preview = preview_file_csv_connector(
        ConnectorCsvPreviewRequest(
            tenant_id="tenant_demo_manufacturing",
            connector_id="unknown_connector",
            file_name="assets.csv",
            csv_content=(
                "asset_id,asset_name,domain,station,risk_level\n"
                "asset_line_2_packaging,Line 2 Packaging,Operations,Line 2,high\n"
            ),
        )
    )

    assert preview.preview_status == "blocked"
    assert preview.accepted_record_count == 0
    assert preview.rejected_record_count == 1
    assert preview.proposed_entities == []
    assert preview.validation_issues == [
        "Unsupported connector_id: unknown_connector",
    ]


def test_external_db_connector_preview_returns_metadata_only_mapping() -> None:
    preview = preview_external_db_connector(
        ConnectorExternalDbPreviewRequest(
            tenant_id="tenant_demo_manufacturing",
            connector_id="external_db_operational_mirror",
            connection_profile_id="profile_postgres_ops_readonly",
            schema_name="operations",
            table_name="production_orders",
            selected_columns=[
                "order_id",
                "asset_id",
                "work_center",
                "status",
                "risk_level",
            ],
            sample_limit=2,
            credential_handle_id="cred_external_db_readonly",
        )
    )

    assert preview.connector_id == "external_db_operational_mirror"
    assert preview.preview_status == "ready"
    assert preview.sync_mode == "schema_preview_only"
    assert preview.live_query_executed is False
    assert preview.inspected_table.schema_name == "operations"
    assert preview.inspected_table.table_name == "production_orders"
    assert preview.inspected_table.sample_limit == 2
    assert [column.source_column for column in preview.inspected_table.columns] == [
        "order_id",
        "asset_id",
        "work_center",
        "status",
        "risk_level",
    ]
    assert preview.proposed_entities[0].ontology_type == "production_order"
    assert preview.audit_event_preview.event_type == "connector.external_db.previewed"
    assert preview.audit_event_preview.scope == "external_db_operational_mirror"
    assert preview.audit_event_preview.payload_preview == {
        "connection_profile_id": "profile_postgres_ops_readonly",
        "table_ref": "operations.production_orders",
        "live_query_executed": "false",
        "credential_handle_id": "cred_external_db_readonly",
    }
    serialized = preview.model_dump_json().lower()
    assert "connection_string" not in serialized
    assert "postgres://" not in serialized
    assert "password" not in serialized
    assert "raw_sql" not in serialized


def test_external_db_connector_preview_blocks_raw_connection_and_query_material() -> None:
    preview = preview_external_db_connector(
        ConnectorExternalDbPreviewRequest(
            tenant_id="tenant_demo_manufacturing",
            connector_id="external_db_operational_mirror",
            connection_profile_id="profile_postgres_ops_readonly",
            schema_name="operations",
            table_name="production_orders",
            selected_columns=["order_id"],
            sample_limit=1,
            credential_handle_id="cred_external_db_readonly",
            metadata={
                "connection_string": "postgres://user:password@example.local/db",
                "raw_sql": "select * from production_orders",
            },
        )
    )

    assert preview.preview_status == "blocked"
    assert preview.live_query_executed is False
    assert preview.proposed_entities == []
    assert preview.validation_issues == [
        "Raw connection material is not accepted in external DB preview.",
        "Raw SQL or query text is not accepted in external DB preview.",
    ]
    assert preview.audit_event_preview.result == "blocked"
    serialized = preview.model_dump_json().lower()
    assert "postgres://" not in serialized
    assert "select *" not in serialized
    assert "password" not in serialized


def test_connector_registry_endpoint_returns_bootstrap_public_manifest(
    connector_session_factory: sessionmaker[Session],
) -> None:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://"))
    app.state.session_factory = connector_session_factory
    migration = run_path("migrations/versions/0023_connector_registry_reference.py")
    with session_scope(connector_session_factory) as session:
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id="tenant_demo_manufacturing",
                surface="connectors",
                reference_id="manufacturing-connector-registry",
                status="active",
                source="bootstrap",
                version="2026-06-22",
                payload=migration["CONNECTOR_REGISTRY_PAYLOAD"],
            )
        )
    client = TestClient(app)

    response = client.get("/demo/manufacturing/connectors")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["connectors"][0]["manifest"]["connector_id"] == ("file_csv_manufacturing_assets")
    assert body["connectors"][0]["manifest"]["credential_requirements"]["storage"] == "none"
    assert body["connectors"][1]["manifest"]["connector_id"] == ("external_db_operational_mirror")
    assert "password" not in str(body).lower()
    assert "api_key" not in str(body).lower()
    assert "credential_value" not in str(body).lower()


def test_connector_file_csv_preview_endpoint_returns_redacted_mapping_preview() -> None:
    client = TestClient(create_app(Settings(postgres_dsn="sqlite+pysqlite://")))

    response = client.post(
        "/demo/manufacturing/connectors/file-csv/preview",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "file_csv_manufacturing_assets",
            "file_name": "assets.csv",
            "csv_content": (
                "asset_id,asset_name,domain,station,risk_level\n"
                "asset_line_2_packaging,Line 2 Packaging,Operations,Line 2,high\n"
            ),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["preview_status"] == "ready"
    assert body["record_count"] == 1
    assert body["proposed_entities"][0]["node_id"] == "asset_line_2_packaging"
    assert body["audit_event_preview"]["event_type"] == "connector.preview.generated"
    assert "csv_content" not in str(body)


def test_connector_external_db_preview_endpoint_returns_metadata_only_preview() -> None:
    client = TestClient(create_app(Settings(postgres_dsn="sqlite+pysqlite://")))

    response = client.post(
        "/demo/manufacturing/connectors/external-db/preview",
        json={
            "tenant_id": "tenant_demo_manufacturing",
            "connector_id": "external_db_operational_mirror",
            "connection_profile_id": "profile_postgres_ops_readonly",
            "schema_name": "operations",
            "table_name": "production_orders",
            "selected_columns": ["order_id", "asset_id", "status"],
            "sample_limit": 2,
            "credential_handle_id": "cred_external_db_readonly",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["preview_status"] == "ready"
    assert body["live_query_executed"] is False
    assert body["audit_event_preview"]["event_type"] == "connector.external_db.previewed"
    assert body["inspected_table"]["columns"][0]["source_column"] == "order_id"
    assert "connection_string" not in str(body).lower()
    assert "postgres://" not in str(body).lower()
    assert "password" not in str(body).lower()


def test_openapi_exposes_connector_endpoints() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/demo/manufacturing/connectors" in paths
    assert "/demo/manufacturing/connectors/file-csv/preview" in paths
    assert "/demo/manufacturing/connectors/external-db/preview" in paths
