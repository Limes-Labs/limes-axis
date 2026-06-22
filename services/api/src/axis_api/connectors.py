import csv
from io import StringIO

from pydantic import BaseModel, Field

from axis_api.demo import OverviewMetric, OverviewStatus


class ConnectorCredentialRequirements(BaseModel):
    storage: str = Field(min_length=1)
    required_secret_refs: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ConnectorSchemaField(BaseModel):
    source_column: str = Field(min_length=1)
    target_field: str = Field(min_length=1)
    ontology_target: str = Field(min_length=1)
    data_type: str = Field(min_length=1)
    required: bool
    description: str = Field(min_length=1)


class ConnectorManifest(BaseModel):
    connector_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    connector_type: str = Field(min_length=1)
    version: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    sync_modes: list[str] = Field(default_factory=list)
    runtime_boundary: str = Field(min_length=1)
    required_permissions: list[str] = Field(default_factory=list)
    credential_requirements: ConnectorCredentialRequirements
    schema_fields: list[ConnectorSchemaField] = Field(default_factory=list)
    mapping_notes: list[str] = Field(default_factory=list)


class ConnectorRuntimePolicy(BaseModel):
    allowed_operations: list[str] = Field(default_factory=list)
    blocked_operations: list[str] = Field(default_factory=list)
    egress_policy: str = Field(min_length=1)
    max_file_size_mb: int = Field(ge=1)
    row_limit: int = Field(ge=1)
    payload_policy: str = Field(min_length=1)


class ConnectorPreviewSample(BaseModel):
    file_name: str = Field(min_length=1)
    record_count: int = Field(ge=0)
    headers: list[str] = Field(default_factory=list)
    sample_rows: list[dict[str, str]] = Field(default_factory=list)


class ConnectorRegistryItem(BaseModel):
    manifest: ConnectorManifest
    runtime_policy: ConnectorRuntimePolicy
    preview_sample: ConnectorPreviewSample
    connector_status: OverviewStatus


class ManufacturingConnectorRegistry(BaseModel):
    tenant_id: str = Field(min_length=1)
    plant_name: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    registry_status: OverviewStatus
    metrics: list[OverviewMetric] = Field(default_factory=list)
    connectors: list[ConnectorRegistryItem] = Field(default_factory=list)
    connector_notes: list[str] = Field(default_factory=list)


class ConnectorCsvPreviewRequest(BaseModel):
    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    connector_id: str = Field(default="file_csv_manufacturing_assets", min_length=1)
    file_name: str = Field(min_length=1, max_length=240)
    csv_content: str = Field(min_length=1)


class ProposedOntologyEntity(BaseModel):
    node_id: str = Field(min_length=1)
    node_type: str = Field(min_length=1)
    ontology_type: str = Field(min_length=1)
    field_summary: dict[str, str] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)


class ConnectorAuditEventPreview(BaseModel):
    event_type: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    result: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    payload_preview: dict[str, str] = Field(default_factory=dict)


class ConnectorCsvPreviewResult(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    preview_status: str = Field(min_length=1)
    sync_mode: str = Field(min_length=1)
    record_count: int = Field(ge=0)
    accepted_record_count: int = Field(ge=0)
    rejected_record_count: int = Field(ge=0)
    validation_issues: list[str] = Field(default_factory=list)
    proposed_entities: list[ProposedOntologyEntity] = Field(default_factory=list)
    audit_event_preview: ConnectorAuditEventPreview
    preview_notes: list[str] = Field(default_factory=list)


def _file_csv_manifest() -> ConnectorManifest:
    return ConnectorManifest(
        connector_id="file_csv_manufacturing_assets",
        display_name="Manufacturing assets CSV",
        connector_type="file_csv",
        version="2026-06-22",
        source_type="file",
        sync_modes=["preview", "manual_import"],
        runtime_boundary="axis-connector-sandbox",
        required_permissions=[
            "connectors:read",
            "connectors:file_csv:preview",
        ],
        credential_requirements=ConnectorCredentialRequirements(
            storage="none",
            required_secret_refs=[],
            notes=[
                "Local CSV preview does not require stored credentials.",
                "Future connector runs must reference credential handles, not raw values.",
            ],
        ),
        schema_fields=[
            ConnectorSchemaField(
                source_column="asset_id",
                target_field="node_id",
                ontology_target="manufacturing_asset",
                data_type="string",
                required=True,
                description="Stable asset identifier used as the ontology node id.",
            ),
            ConnectorSchemaField(
                source_column="asset_name",
                target_field="display_name",
                ontology_target="manufacturing_asset",
                data_type="string",
                required=True,
                description="Human-readable manufacturing asset name.",
            ),
            ConnectorSchemaField(
                source_column="domain",
                target_field="domain",
                ontology_target="manufacturing_asset",
                data_type="string",
                required=True,
                description="Operational domain such as Operations, Quality or Maintenance.",
            ),
            ConnectorSchemaField(
                source_column="station",
                target_field="source_system_ref",
                ontology_target="manufacturing_asset",
                data_type="string",
                required=True,
                description="Plant station, line or source-system reference.",
            ),
            ConnectorSchemaField(
                source_column="risk_level",
                target_field="risk_level",
                ontology_target="manufacturing_asset",
                data_type="string",
                required=True,
                description="Public-safe risk posture used for demo governance checks.",
            ),
        ],
        mapping_notes=[
            "CSV preview maps rows to ontology entity proposals only.",
            "Manual import remains approval-gated and workflow-signaled before execution.",
            "Raw file content is never returned in API responses.",
        ],
    )


def _runtime_policy() -> ConnectorRuntimePolicy:
    return ConnectorRuntimePolicy(
        allowed_operations=["schema_validate", "preview_mapping", "dry_run_diff"],
        blocked_operations=["live_write", "credential_capture", "external_egress"],
        egress_policy="no-external-egress",
        max_file_size_mb=5,
        row_limit=500,
        payload_policy="redacted-preview-only",
    )


def _sample_preview() -> ConnectorPreviewSample:
    return ConnectorPreviewSample(
        file_name="manufacturing-assets-demo.csv",
        record_count=3,
        headers=["asset_id", "asset_name", "domain", "station", "risk_level"],
        sample_rows=[
            {
                "asset_id": "asset_line_2_packaging",
                "asset_name": "Line 2 Packaging",
                "domain": "Operations",
                "station": "Line 2",
                "risk_level": "high",
            },
            {
                "asset_id": "asset_press_4",
                "asset_name": "Press 4",
                "domain": "Maintenance",
                "station": "Press 4",
                "risk_level": "medium",
            },
        ],
    )


def get_manufacturing_connector_registry() -> ManufacturingConnectorRegistry:
    connector = ConnectorRegistryItem(
        manifest=_file_csv_manifest(),
        runtime_policy=_runtime_policy(),
        preview_sample=_sample_preview(),
        connector_status=OverviewStatus.WATCH,
    )
    return ManufacturingConnectorRegistry(
        tenant_id="tenant_demo_manufacturing",
        plant_name="Ravenna Works",
        scenario="Plant Operations Cockpit",
        registry_status=OverviewStatus.WATCH,
        metrics=[
            OverviewMetric(
                label="Connector Manifests",
                value="1",
                detail="Public-safe connector manifest available for preview",
                status=OverviewStatus.READY,
            ),
            OverviewMetric(
                label="CSV Preview",
                value="Ready",
                detail="File connector can validate and map local CSV rows",
                status=OverviewStatus.READY,
            ),
            OverviewMetric(
                label="Live Sync",
                value="Blocked",
                detail="No live connector mutation is enabled in this foundation slice",
                status=OverviewStatus.WATCH,
            ),
        ],
        connectors=[connector],
        connector_notes=[
            "Connector manifests are public-safe and preview-only.",
            "The file/CSV connector maps rows to ontology proposals without writing data.",
            "Credential storage, scheduled sync and production connector runs remain future work.",
        ],
    )


def _csv_rows(csv_content: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(StringIO(csv_content.strip()))
    headers = list(reader.fieldnames or [])
    rows = [
        {key: (value or "").strip() for key, value in row.items() if key is not None}
        for row in reader
    ]
    return headers, rows


def _required_columns() -> list[str]:
    return [field.source_column for field in _file_csv_manifest().schema_fields if field.required]


def _validation_issues(headers: list[str], rows: list[dict[str, str]]) -> list[str]:
    issues = [
        f"Missing required column: {column}"
        for column in _required_columns()
        if column not in headers
    ]
    if not rows:
        issues.append("CSV file must contain at least one data row.")
    return issues


def _connector_issues(request: ConnectorCsvPreviewRequest) -> list[str]:
    supported_connector_id = _file_csv_manifest().connector_id
    if request.connector_id == supported_connector_id:
        return []
    return [f"Unsupported connector_id: {request.connector_id}"]


def _entity_from_row(row: dict[str, str], file_name: str) -> ProposedOntologyEntity:
    return ProposedOntologyEntity(
        node_id=row["asset_id"],
        node_type="asset",
        ontology_type="manufacturing_asset",
        field_summary={
            "asset_name": row["asset_name"],
            "domain": row["domain"],
            "station": row["station"],
            "risk_level": row["risk_level"],
        },
        evidence_refs=[file_name, row["asset_id"]],
    )


def preview_file_csv_connector(
    request: ConnectorCsvPreviewRequest,
) -> ConnectorCsvPreviewResult:
    headers, rows = _csv_rows(request.csv_content)
    issues = [*_connector_issues(request), *_validation_issues(headers, rows)]
    proposed_entities = [] if issues else [
        _entity_from_row(row, request.file_name) for row in rows[:500]
    ]
    accepted_count = len(proposed_entities)
    rejected_count = len(rows) if issues else max(len(rows) - accepted_count, 0)
    preview_status = "ready" if not issues else "blocked"

    return ConnectorCsvPreviewResult(
        tenant_id=request.tenant_id,
        connector_id=request.connector_id,
        file_name=request.file_name,
        preview_status=preview_status,
        sync_mode="preview_only",
        record_count=len(rows),
        accepted_record_count=accepted_count,
        rejected_record_count=rejected_count,
        validation_issues=issues,
        proposed_entities=proposed_entities,
        audit_event_preview=ConnectorAuditEventPreview(
            event_type="connector.preview.generated",
            scope=request.connector_id,
            actor_id="connector-preview-service",
            result="ready" if not issues else "blocked",
            evidence_refs=[request.file_name, request.connector_id],
            payload_preview={
                "file_name": request.file_name,
                "record_count": str(len(rows)),
                "accepted_record_count": str(accepted_count),
                "rejected_record_count": str(rejected_count),
            },
        ),
        preview_notes=[
            "CSV content is parsed only for preview and is not persisted.",
            "Mapped rows become ontology proposals, not live graph mutations.",
            "Connector execution and scheduled sync remain outside preview boundaries.",
        ],
    )
