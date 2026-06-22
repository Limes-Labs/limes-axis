from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from axis_api.audit import AuditEventCreate
from axis_api.connectors import get_manufacturing_connector_registry
from axis_api.demo import OverviewMetric, OverviewStatus
from axis_api.persistence import AxisPersistenceRepository, ConnectorManualImportRequestCreate


class ConnectorManualImportValidationError(ValueError):
    def __init__(self, message: str, reason: str) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason


class ConnectorManualImportIdempotencyConflict(ValueError):
    def __init__(self, import_id: str) -> None:
        super().__init__("Idempotency key already exists with a different payload")
        self.import_id = import_id


class ConnectorManualImportQuery(BaseModel):
    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    connector_id: str | None = Field(default=None, min_length=1)
    status: str | None = Field(default=None, min_length=1)
    limit: int = Field(default=100, ge=1, le=200)


def _default_controls() -> list[str]:
    return [
        "approval_required",
        "workflow_signal_required",
        "idempotency_enforced",
    ]


class ConnectorManualImportCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    connector_id: str = Field(default="file_csv_manufacturing_assets", min_length=1)
    import_id: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    idempotency_key: str = Field(min_length=1, max_length=200)
    import_mode: str = Field(default="manual_import_request", min_length=1, max_length=80)
    requested_by: str = Field(min_length=1, max_length=160)
    owner_role: str = Field(min_length=1, max_length=160)
    risk_level: str = Field(min_length=1, max_length=40)
    approval_id: str = Field(min_length=1, max_length=160)
    workflow_id: str = Field(min_length=1, max_length=160)
    proposal_ids: list[str] = Field(min_length=1)
    import_summary: dict[str, str] = Field(default_factory=dict)
    controls: list[str] = Field(default_factory=_default_controls)
    notes: list[str] = Field(default_factory=list)


class ConnectorManualImportRecord(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    import_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    status: str = Field(min_length=1)
    import_mode: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    owner_role: str = Field(min_length=1)
    risk_level: str = Field(min_length=1)
    approval_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    proposal_ids: list[str] = Field(default_factory=list)
    import_summary: dict[str, str] = Field(default_factory=dict)
    controls: list[str] = Field(default_factory=list)
    graph_mutation_status: str = Field(min_length=1)
    workflow_signal_status: str = Field(min_length=1)
    audit_event_id: UUID | None = None
    audit_event_type: str = Field(min_length=1)
    notes: list[str] = Field(default_factory=list)
    created_at: datetime
    idempotent_replay: bool = False


class ManufacturingConnectorManualImportRegistry(BaseModel):
    tenant_id: str = Field(min_length=1)
    plant_name: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    registry_status: OverviewStatus
    metrics: list[OverviewMetric] = Field(default_factory=list)
    imports: list[ConnectorManualImportRecord] = Field(default_factory=list)
    import_notes: list[str] = Field(default_factory=list)


AUDIT_EVENT_TYPE = "connector.manual_import.requested"
ALLOWED_IMPORT_MODES = {"manual_import_request"}
REQUEST_STATUS = "approval_required"
GRAPH_MUTATION_STATUS = "not_applied"
WORKFLOW_SIGNAL_STATUS = "pending_approval_decision"
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


def build_connector_manual_import_registry(
    repository: AxisPersistenceRepository,
    query: ConnectorManualImportQuery,
) -> ManufacturingConnectorManualImportRegistry:
    records = repository.list_connector_manual_import_requests(
        tenant_id=query.tenant_id,
        connector_id=query.connector_id,
        status=query.status,
        limit=query.limit,
    )
    imports = [_manual_import_from_record(record) for record in records]
    approval_required = sum(1 for item in imports if item.status == REQUEST_STATUS)
    graph_mutations = sum(
        1 for item in imports if item.graph_mutation_status != GRAPH_MUTATION_STATUS
    )
    return ManufacturingConnectorManualImportRegistry(
        tenant_id=query.tenant_id,
        plant_name="Ravenna Works",
        scenario="Plant Operations Cockpit",
        registry_status=OverviewStatus.READY if imports else OverviewStatus.WATCH,
        metrics=[
            OverviewMetric(
                label="Manual Imports",
                value=str(len(imports)),
                detail="Approval-gated connector import requests",
                status=OverviewStatus.READY if imports else OverviewStatus.WATCH,
            ),
            OverviewMetric(
                label="Approval Required",
                value=str(approval_required),
                detail="Manual imports waiting for human decision",
                status=OverviewStatus.WATCH if approval_required else OverviewStatus.READY,
            ),
            OverviewMetric(
                label="Graph Mutations",
                value=str(graph_mutations),
                detail="Manual import requests do not mutate the ontology graph",
                status=OverviewStatus.READY
                if graph_mutations == 0
                else OverviewStatus.ACTION_REQUIRED,
            ),
        ],
        imports=imports,
        import_notes=[
            "Manual import requests are approval-gated metadata records.",
            "Workflow ids and signal status are recorded before any connector import can run.",
            "Idempotency keys prevent duplicate import requests and duplicate audit events.",
            "Graph mutation is not applied by this connector foundation slice.",
        ],
    )


def record_demo_connector_manual_import(
    repository: AxisPersistenceRepository,
    request: ConnectorManualImportCreateRequest,
) -> ConnectorManualImportRecord:
    manifest = _manifest_for_connector(request.connector_id)
    _validate_import_mode(request.import_mode)
    _validate_redacted_summary(request.import_summary)

    existing = repository.get_connector_manual_import_request_by_idempotency_key(
        request.tenant_id,
        request.idempotency_key,
    )
    if existing is not None:
        if _fingerprint_from_record(existing) != _fingerprint_from_request(request):
            raise ConnectorManualImportIdempotencyConflict(existing.import_id)
        return _manual_import_from_record(existing, idempotent_replay=True)

    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=request.tenant_id,
            actor_id=request.requested_by,
            event_type=AUDIT_EVENT_TYPE,
            payload={
                "connector_id": request.connector_id,
                "import_id": request.import_id,
                "idempotency_key": request.idempotency_key,
                "status": REQUEST_STATUS,
                "import_mode": request.import_mode,
                "requested_by": request.requested_by,
                "owner_role": request.owner_role,
                "risk_level": request.risk_level,
                "approval_id": request.approval_id,
                "workflow_id": request.workflow_id,
                "proposal_ids": request.proposal_ids,
                "proposal_count": len(request.proposal_ids),
                "import_summary": request.import_summary,
                "controls": request.controls,
                "graph_mutation_status": GRAPH_MUTATION_STATUS,
                "workflow_signal_status": WORKFLOW_SIGNAL_STATUS,
                "runtime_boundary": manifest.runtime_boundary,
            },
        )
    )
    record = repository.create_connector_manual_import_request(
        ConnectorManualImportRequestCreate(
            tenant_id=request.tenant_id,
            connector_id=request.connector_id,
            import_id=request.import_id,
            idempotency_key=request.idempotency_key,
            status=REQUEST_STATUS,
            import_mode=request.import_mode,
            requested_by=request.requested_by,
            owner_role=request.owner_role,
            risk_level=request.risk_level,
            approval_id=request.approval_id,
            workflow_id=request.workflow_id,
            proposal_ids=request.proposal_ids,
            import_summary=request.import_summary,
            controls=request.controls,
            graph_mutation_status=GRAPH_MUTATION_STATUS,
            workflow_signal_status=WORKFLOW_SIGNAL_STATUS,
            audit_event_id=audit_event.id,
            audit_event_type=AUDIT_EVENT_TYPE,
            notes=request.notes,
        )
    )
    return _manual_import_from_record(record)


def _manual_import_from_record(
    record,
    idempotent_replay: bool = False,
) -> ConnectorManualImportRecord:
    return ConnectorManualImportRecord(
        tenant_id=record.tenant_id,
        connector_id=record.connector_id,
        import_id=record.import_id,
        idempotency_key=record.idempotency_key,
        status=record.status,
        import_mode=record.import_mode,
        requested_by=record.requested_by,
        owner_role=record.owner_role,
        risk_level=record.risk_level,
        approval_id=record.approval_id,
        workflow_id=record.workflow_id,
        proposal_ids=record.proposal_ids,
        import_summary=record.import_summary,
        controls=record.controls,
        graph_mutation_status=record.graph_mutation_status,
        workflow_signal_status=record.workflow_signal_status,
        audit_event_id=record.audit_event_id,
        audit_event_type=record.audit_event_type,
        notes=record.notes,
        created_at=record.created_at,
        idempotent_replay=idempotent_replay,
    )


def _manifest_for_connector(connector_id: str):
    registry = get_manufacturing_connector_registry()
    for connector in registry.connectors:
        if connector.manifest.connector_id == connector_id:
            return connector.manifest
    raise ConnectorManualImportValidationError(
        f"Unsupported connector_id: {connector_id}",
        "unsupported_connector_id",
    )


def _validate_import_mode(import_mode: str) -> None:
    if import_mode in ALLOWED_IMPORT_MODES:
        return
    raise ConnectorManualImportValidationError(
        "Connector manual imports can only be recorded as manual_import_request.",
        "unsupported_import_mode",
    )


def _validate_redacted_summary(summary: dict[str, str]) -> None:
    for key in summary:
        if key.lower() in RAW_PAYLOAD_FIELD_NAMES:
            raise ConnectorManualImportValidationError(
                "Connector manual import summaries cannot include raw payload fields.",
                "raw_payload_field",
            )


def _fingerprint_from_request(request: ConnectorManualImportCreateRequest) -> dict:
    return {
        "connector_id": request.connector_id,
        "import_id": request.import_id,
        "import_mode": request.import_mode,
        "requested_by": request.requested_by,
        "owner_role": request.owner_role,
        "risk_level": request.risk_level,
        "approval_id": request.approval_id,
        "workflow_id": request.workflow_id,
        "proposal_ids": request.proposal_ids,
        "import_summary": request.import_summary,
        "controls": request.controls,
        "notes": request.notes,
    }


def _fingerprint_from_record(record) -> dict:
    return {
        "connector_id": record.connector_id,
        "import_id": record.import_id,
        "import_mode": record.import_mode,
        "requested_by": record.requested_by,
        "owner_role": record.owner_role,
        "risk_level": record.risk_level,
        "approval_id": record.approval_id,
        "workflow_id": record.workflow_id,
        "proposal_ids": record.proposal_ids,
        "import_summary": record.import_summary,
        "controls": record.controls,
        "notes": record.notes,
    }
