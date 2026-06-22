from fastapi.testclient import TestClient

from axis_api.config import Settings
from axis_api.connectors import (
    ConnectorCsvPreviewRequest,
    get_manufacturing_connector_registry,
    preview_file_csv_connector,
)
from axis_api.main import create_app


def test_manufacturing_connector_registry_exposes_file_csv_manifest() -> None:
    registry = get_manufacturing_connector_registry()

    assert registry.tenant_id == "tenant_demo_manufacturing"
    assert registry.registry_status == "watch"
    assert registry.metrics[0].label == "Connector Manifests"
    assert registry.metrics[0].value == "1"
    assert len(registry.connectors) == 1

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


def test_openapi_exposes_connector_endpoints() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/demo/manufacturing/connectors" in paths
    assert "/demo/manufacturing/connectors/file-csv/preview" in paths
