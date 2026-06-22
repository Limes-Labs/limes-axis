from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from axis_api.audit import AuditEventCreate
from axis_api.connectors import get_manufacturing_connector_registry
from axis_api.demo import OverviewMetric, OverviewStatus
from axis_api.persistence import AxisPersistenceRepository, ConnectorRunCreate


class ConnectorRunValidationError(ValueError):
    def __init__(self, message: str, reason: str) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason


class ConnectorRunQuery(BaseModel):
    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    connector_id: str | None = Field(default=None, min_length=1)
    status: str | None = Field(default=None, min_length=1)
    limit: int = Field(default=100, ge=1, le=200)


class ConnectorRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    connector_id: str = Field(default="file_csv_manufacturing_assets", min_length=1)
    run_id: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    execution_mode: str = Field(default="preview", min_length=1, max_length=80)
    requested_by: str = Field(min_length=1, max_length=160)
    credential_handle_ids: list[str] = Field(default_factory=list)
    input_summary: dict[str, str] = Field(default_factory=dict)
    result_summary: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ConnectorRunRecord(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    execution_mode: str = Field(min_length=1)
    runtime_boundary: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    credential_handle_ids: list[str] = Field(default_factory=list)
    input_summary: dict[str, str] = Field(default_factory=dict)
    result_summary: dict[str, str] = Field(default_factory=dict)
    audit_event_id: UUID | None = None
    audit_event_type: str = Field(min_length=1)
    notes: list[str] = Field(default_factory=list)
    created_at: datetime


class ManufacturingConnectorRunRegistry(BaseModel):
    tenant_id: str = Field(min_length=1)
    plant_name: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    registry_status: OverviewStatus
    metrics: list[OverviewMetric] = Field(default_factory=list)
    runs: list[ConnectorRunRecord] = Field(default_factory=list)
    run_notes: list[str] = Field(default_factory=list)


AUDIT_EVENT_TYPE = "connector.run.recorded"
ALLOWED_EXECUTION_MODES = {"preview", "manual_import_record"}
RAW_PAYLOAD_FIELD_NAMES = {
    "api_key",
    "client_secret",
    "credential_value",
    "csv_content",
    "password",
    "raw_file_content",
    "raw_payload",
    "secret",
    "secret_ref",
    "token",
}


def build_connector_run_registry(
    repository: AxisPersistenceRepository,
    query: ConnectorRunQuery,
) -> ManufacturingConnectorRunRegistry:
    records = repository.list_connector_runs(
        tenant_id=query.tenant_id,
        connector_id=query.connector_id,
        status=query.status,
        limit=query.limit,
    )
    runs = [_run_from_record(record) for record in records]
    audit_writes = sum(1 for run in runs if run.audit_event_id is not None)
    return ManufacturingConnectorRunRegistry(
        tenant_id=query.tenant_id,
        plant_name="Ravenna Works",
        scenario="Plant Operations Cockpit",
        registry_status=OverviewStatus.READY if runs else OverviewStatus.WATCH,
        metrics=[
            OverviewMetric(
                label="Connector Runs",
                value=str(len(runs)),
                detail="Metadata-only connector run records",
                status=OverviewStatus.READY if runs else OverviewStatus.WATCH,
            ),
            OverviewMetric(
                label="Audit Writes",
                value=str(audit_writes),
                detail="Append-only audit events linked to run records",
                status=OverviewStatus.READY if audit_writes == len(runs) else OverviewStatus.WATCH,
            ),
            OverviewMetric(
                label="Live Sync",
                value="Disabled",
                detail="Run records do not execute connector sync",
                status=OverviewStatus.WATCH,
            ),
        ],
        runs=runs,
        run_notes=[
            "Connector run records are metadata-only evidence.",
            "Creating a run record writes an append-only audit event.",
            "Raw payloads, file content and credential material are never stored.",
            "Live sync and connector-backed production actions remain future work.",
        ],
    )


def record_demo_connector_run(
    repository: AxisPersistenceRepository,
    request: ConnectorRunCreateRequest,
) -> ConnectorRunRecord:
    manifest = _manifest_for_connector(request.connector_id)
    _validate_execution_mode(request.execution_mode)
    _validate_redacted_summary(request.input_summary)
    _validate_redacted_summary(request.result_summary)
    status = _status_for_execution_mode(request.execution_mode)
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=request.tenant_id,
            actor_id=request.requested_by,
            event_type=AUDIT_EVENT_TYPE,
            payload={
                "connector_id": request.connector_id,
                "run_id": request.run_id,
                "status": status,
                "execution_mode": request.execution_mode,
                "credential_handle_ids": request.credential_handle_ids,
                "input_summary": request.input_summary,
                "result_summary": request.result_summary,
                "runtime_boundary": manifest.runtime_boundary,
            },
        )
    )
    record = repository.create_connector_run(
        ConnectorRunCreate(
            tenant_id=request.tenant_id,
            connector_id=request.connector_id,
            run_id=request.run_id,
            status=status,
            execution_mode=request.execution_mode,
            runtime_boundary=manifest.runtime_boundary,
            requested_by=request.requested_by,
            credential_handle_ids=request.credential_handle_ids,
            input_summary=request.input_summary,
            result_summary=request.result_summary,
            audit_event_id=audit_event.id,
            audit_event_type=AUDIT_EVENT_TYPE,
            notes=request.notes,
        )
    )
    return _run_from_record(record)


def _run_from_record(record) -> ConnectorRunRecord:
    return ConnectorRunRecord(
        tenant_id=record.tenant_id,
        connector_id=record.connector_id,
        run_id=record.run_id,
        status=record.status,
        execution_mode=record.execution_mode,
        runtime_boundary=record.runtime_boundary,
        requested_by=record.requested_by,
        credential_handle_ids=record.credential_handle_ids,
        input_summary=record.input_summary,
        result_summary=record.result_summary,
        audit_event_id=record.audit_event_id,
        audit_event_type=record.audit_event_type,
        notes=record.notes,
        created_at=record.created_at,
    )


def _manifest_for_connector(connector_id: str):
    registry = get_manufacturing_connector_registry()
    for connector in registry.connectors:
        if connector.manifest.connector_id == connector_id:
            return connector.manifest
    raise ConnectorRunValidationError(
        f"Unsupported connector_id: {connector_id}",
        "unsupported_connector_id",
    )


def _validate_execution_mode(execution_mode: str) -> None:
    if execution_mode in ALLOWED_EXECUTION_MODES:
        return
    raise ConnectorRunValidationError(
        "Only preview and manual_import_record run records are supported.",
        "unsupported_execution_mode",
    )


def _validate_redacted_summary(summary: dict[str, str]) -> None:
    for key in summary:
        if key.lower() in RAW_PAYLOAD_FIELD_NAMES:
            raise ConnectorRunValidationError(
                "Connector run summaries cannot include raw payload or credential fields.",
                "raw_payload_field",
            )


def _status_for_execution_mode(execution_mode: str) -> str:
    if execution_mode == "manual_import_record":
        return "recorded_manual_import_only"
    return "recorded_preview_only"
