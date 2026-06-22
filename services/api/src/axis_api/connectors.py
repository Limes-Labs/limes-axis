import csv
from io import StringIO

from pydantic import BaseModel, ConfigDict, Field

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


class ConnectorExternalDbPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    connector_id: str = Field(default="external_db_operational_mirror", min_length=1)
    connection_profile_id: str = Field(
        default="profile_postgres_ops_readonly",
        min_length=1,
        max_length=120,
    )
    schema_name: str = Field(default="operations", min_length=1, max_length=120)
    table_name: str = Field(default="production_orders", min_length=1, max_length=120)
    selected_columns: list[str] = Field(
        default_factory=lambda: [
            "order_id",
            "asset_id",
            "work_center",
            "status",
            "risk_level",
        ],
    )
    sample_limit: int = Field(default=2, ge=1, le=100)
    credential_handle_id: str = Field(default="cred_external_db_readonly", min_length=1)
    metadata: dict[str, str] = Field(default_factory=dict)


class ConnectorExternalDbColumnPreview(BaseModel):
    source_column: str = Field(min_length=1)
    target_field: str = Field(min_length=1)
    ontology_target: str = Field(min_length=1)
    data_type: str = Field(min_length=1)
    nullable: bool


class ConnectorExternalDbTablePreview(BaseModel):
    schema_name: str = Field(min_length=1)
    table_name: str = Field(min_length=1)
    table_ref: str = Field(min_length=1)
    record_count_estimate: str = Field(min_length=1)
    sample_limit: int = Field(ge=1)
    columns: list[ConnectorExternalDbColumnPreview] = Field(default_factory=list)
    sample_rows: list[dict[str, str]] = Field(default_factory=list)


class ConnectorExternalDbPreviewResult(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    connection_profile_id: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    preview_status: str = Field(min_length=1)
    sync_mode: str = Field(min_length=1)
    live_query_executed: bool
    validation_issues: list[str] = Field(default_factory=list)
    inspected_table: ConnectorExternalDbTablePreview
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


def _external_db_manifest() -> ConnectorManifest:
    return ConnectorManifest(
        connector_id="external_db_operational_mirror",
        display_name="Postgres operational mirror",
        connector_type="external_db",
        version="2026-06-22",
        source_type="database",
        sync_modes=["schema_preview", "manual_import"],
        runtime_boundary="axis-connector-sandbox",
        required_permissions=[
            "connectors:read",
            "connectors:external_db:preview",
        ],
        credential_requirements=ConnectorCredentialRequirements(
            storage="external_reference",
            required_secret_refs=["cred_external_db_readonly"],
            notes=[
                "Database preview uses credential handles and profile ids only.",
                "Raw DSNs, SQL text and credential values are rejected.",
            ],
        ),
        schema_fields=[
            ConnectorSchemaField(
                source_column="order_id",
                target_field="node_id",
                ontology_target="production_order",
                data_type="string",
                required=True,
                description="Stable production order identifier from the source table.",
            ),
            ConnectorSchemaField(
                source_column="asset_id",
                target_field="asset_ref",
                ontology_target="production_order",
                data_type="string",
                required=True,
                description="Manufacturing asset reference linked by policy-aware import.",
            ),
            ConnectorSchemaField(
                source_column="work_center",
                target_field="source_system_ref",
                ontology_target="production_order",
                data_type="string",
                required=True,
                description="Operational work center or line reference.",
            ),
            ConnectorSchemaField(
                source_column="status",
                target_field="operational_status",
                ontology_target="production_order",
                data_type="string",
                required=True,
                description="Public-safe order status used for preview mapping.",
            ),
            ConnectorSchemaField(
                source_column="risk_level",
                target_field="risk_level",
                ontology_target="production_order",
                data_type="string",
                required=True,
                description="Governance risk posture used for import controls.",
            ),
        ],
        mapping_notes=[
            "Database preview inspects declared metadata only; no live SQL is executed.",
            "Imports remain proposal-only until approval, workflow and policy gates pass.",
            "Connection details stay outside Axis as credential handles and profiles.",
        ],
    )


def _external_db_sample_preview() -> ConnectorPreviewSample:
    return ConnectorPreviewSample(
        file_name="profile_postgres_ops_readonly:operations.production_orders",
        record_count=2,
        headers=["order_id", "asset_id", "work_center", "status", "risk_level"],
        sample_rows=[
            {
                "order_id": "order_po_10045",
                "asset_id": "asset_line_2_packaging",
                "work_center": "Line 2",
                "status": "blocked",
                "risk_level": "high",
            },
            {
                "order_id": "order_po_10046",
                "asset_id": "asset_press_4",
                "work_center": "Press 4",
                "status": "scheduled",
                "risk_level": "medium",
            },
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


def _external_db_requested_keys(request: ConnectorExternalDbPreviewRequest) -> set[str]:
    return {key.lower() for key in request.metadata}


def _external_db_requested_values(request: ConnectorExternalDbPreviewRequest) -> list[str]:
    return [str(value).lower() for value in request.metadata.values()]


def _external_db_validation_issues(
    request: ConnectorExternalDbPreviewRequest,
) -> list[str]:
    issues: list[str] = []
    supported_connector_id = _external_db_manifest().connector_id
    if request.connector_id != supported_connector_id:
        issues.append(f"Unsupported connector_id: {request.connector_id}")

    keys = _external_db_requested_keys(request)
    values = _external_db_requested_values(request)
    connection_keys = {"connection_string", "dsn", "jdbc_url", "database_url", "host", "port"}
    connection_markers = ("postgres://", "postgresql://", "jdbc:", "user:password")
    has_raw_connection_value = any(
        marker in value for marker in connection_markers for value in values
    )
    if keys.intersection(connection_keys) or has_raw_connection_value:
        issues.append("Raw connection material is not accepted in external DB preview.")

    query_keys = {"raw_sql", "sql", "query", "statement", "where_clause"}
    query_markers = ("select ", "insert ", "update ", "delete ", "drop ")
    has_raw_query_value = any(
        marker in value for marker in query_markers for value in values
    )
    if keys.intersection(query_keys) or has_raw_query_value:
        issues.append("Raw SQL or query text is not accepted in external DB preview.")

    credential_keys = {"api_key", "token", "secret", "secret_ref", "credential_value"}
    if keys.intersection(credential_keys):
        issues.append("Raw credential material is not accepted in external DB preview.")

    supported_columns = {field.source_column for field in _external_db_manifest().schema_fields}
    unsupported_columns = [
        column for column in request.selected_columns if column not in supported_columns
    ]
    if unsupported_columns:
        issues.append(f"Unsupported metadata column(s): {', '.join(unsupported_columns)}")

    return issues


def _external_db_columns(
    request: ConnectorExternalDbPreviewRequest,
    issues: list[str],
) -> list[ConnectorExternalDbColumnPreview]:
    if issues:
        return []

    schema_by_column = {
        field.source_column: field for field in _external_db_manifest().schema_fields
    }
    selected_columns = request.selected_columns or list(schema_by_column)
    return [
        ConnectorExternalDbColumnPreview(
            source_column=column,
            target_field=schema_by_column[column].target_field,
            ontology_target=schema_by_column[column].ontology_target,
            data_type=schema_by_column[column].data_type,
            nullable=not schema_by_column[column].required,
        )
        for column in selected_columns
        if column in schema_by_column
    ]


def _external_db_sample_rows(
    request: ConnectorExternalDbPreviewRequest,
    issues: list[str],
) -> list[dict[str, str]]:
    if issues:
        return []
    return _external_db_sample_preview().sample_rows[: request.sample_limit]


def _external_db_proposed_entities(
    request: ConnectorExternalDbPreviewRequest,
    issues: list[str],
) -> list[ProposedOntologyEntity]:
    if issues:
        return []

    return [
        ProposedOntologyEntity(
            node_id=row["order_id"],
            node_type="work_order",
            ontology_type="production_order",
            field_summary={
                "asset_id": row["asset_id"],
                "work_center": row["work_center"],
                "status": row["status"],
                "risk_level": row["risk_level"],
            },
            evidence_refs=[
                request.connection_profile_id,
                f"{request.schema_name}.{request.table_name}",
                row["order_id"],
            ],
        )
        for row in _external_db_sample_rows(request, issues)
    ]


def preview_external_db_connector(
    request: ConnectorExternalDbPreviewRequest,
) -> ConnectorExternalDbPreviewResult:
    issues = _external_db_validation_issues(request)
    table_ref = f"{request.schema_name}.{request.table_name}"
    preview_status = "ready" if not issues else "blocked"

    return ConnectorExternalDbPreviewResult(
        tenant_id=request.tenant_id,
        connector_id=request.connector_id,
        connection_profile_id=request.connection_profile_id,
        source_type="database",
        preview_status=preview_status,
        sync_mode="schema_preview_only",
        live_query_executed=False,
        validation_issues=issues,
        inspected_table=ConnectorExternalDbTablePreview(
            schema_name=request.schema_name,
            table_name=request.table_name,
            table_ref=table_ref,
            record_count_estimate="not_queried",
            sample_limit=request.sample_limit,
            columns=_external_db_columns(request, issues),
            sample_rows=_external_db_sample_rows(request, issues),
        ),
        proposed_entities=_external_db_proposed_entities(request, issues),
        audit_event_preview=ConnectorAuditEventPreview(
            event_type="connector.external_db.previewed",
            scope=request.connector_id,
            actor_id="connector-preview-service",
            result=preview_status,
            evidence_refs=[
                request.connection_profile_id,
                table_ref,
                request.credential_handle_id,
            ],
            payload_preview={
                "connection_profile_id": request.connection_profile_id,
                "table_ref": table_ref,
                "live_query_executed": "false",
                "credential_handle_id": request.credential_handle_id,
            },
        ),
        preview_notes=[
            "External DB preview is metadata-only and does not execute SQL.",
            "Connection details remain outside Axis behind profile ids and credential handles.",
            "Mapped rows become ontology proposals, not live graph mutations.",
        ],
    )
