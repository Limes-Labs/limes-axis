from fastapi.testclient import TestClient

from axis_api.config import Settings
from axis_api.connectors import (
    ConnectorCsvPreviewRequest,
    ConnectorExternalDbPreviewRequest,
    get_manufacturing_connector_registry,
    preview_external_db_connector,
    preview_file_csv_connector,
)
from axis_api.main import create_app


def test_manufacturing_connector_registry_exposes_file_csv_manifest() -> None:
    registry = get_manufacturing_connector_registry()

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
    registry = get_manufacturing_connector_registry()

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


def test_connector_registry_endpoint_returns_public_manifest() -> None:
    client = TestClient(create_app(Settings(postgres_dsn="sqlite+pysqlite://")))

    response = client.get("/demo/manufacturing/connectors")

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["connectors"][0]["manifest"]["connector_id"] == (
        "file_csv_manufacturing_assets"
    )
    assert body["connectors"][0]["manifest"]["credential_requirements"]["storage"] == "none"
    assert body["connectors"][1]["manifest"]["connector_id"] == (
        "external_db_operational_mirror"
    )
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
