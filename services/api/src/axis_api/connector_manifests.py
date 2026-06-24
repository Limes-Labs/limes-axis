from collections.abc import Iterator
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from axis_api.audit import AuditEventCreate
from axis_api.connectors import ConnectorManifest, ConnectorPreviewSample, ConnectorRuntimePolicy
from axis_api.demo import OverviewMetric, OverviewStatus
from axis_api.persistence import (
    AxisPersistenceRepository,
    ConnectorManifestCreate,
    ConnectorManifestLifecycleUpdate,
    PersistenceRecordNotFound,
)


class ConnectorManifestValidationError(ValueError):
    def __init__(self, message: str, reason: str) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason


class ConnectorManifestLifecycleValidationError(ValueError):
    def __init__(self, message: str, reason: str) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason


class ConnectorManifestConflict(ValueError):
    def __init__(self, connector_id: str) -> None:
        super().__init__("Connector manifest already exists")
        self.connector_id = connector_id


class ConnectorManifestQuery(BaseModel):
    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    connector_id: str | None = Field(default=None, min_length=1)
    status: str | None = Field(default=None, min_length=1)
    limit: int = Field(default=100, ge=1, le=200)


class ConnectorManifestCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    registered_by: str = Field(min_length=1, max_length=160)
    manifest: dict[str, Any] = Field(default_factory=dict)
    runtime_policy: dict[str, Any] = Field(default_factory=dict)
    preview_sample: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ConnectorManifestLifecycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    transitioned_by: str = Field(min_length=1, max_length=160)
    target_status: str = Field(min_length=1, max_length=80)
    actor_scopes: list[str] = Field(default_factory=list)
    required_scope: str = Field(default="connectors:manifest:lifecycle", min_length=1)
    transition_reason: str = Field(min_length=1, max_length=600)
    evidence_refs: list[str] = Field(default_factory=list)


class ConnectorManifestRecordView(BaseModel):
    tenant_id: str = Field(min_length=1)
    manifest_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    connector_type: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    version: str = Field(min_length=1)
    status: str = Field(min_length=1)
    runtime_boundary: str = Field(min_length=1)
    registered_by: str = Field(min_length=1)
    manifest: dict[str, Any] = Field(default_factory=dict)
    runtime_policy: dict[str, Any] = Field(default_factory=dict)
    preview_sample: dict[str, Any] = Field(default_factory=dict)
    audit_event_id: UUID | None = None
    audit_event_type: str = Field(min_length=1)
    notes: list[str] = Field(default_factory=list)
    created_at: datetime


class ManufacturingConnectorManifestRegistry(BaseModel):
    tenant_id: str = Field(min_length=1)
    plant_name: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    registry_status: OverviewStatus
    metrics: list[OverviewMetric] = Field(default_factory=list)
    manifests: list[ConnectorManifestRecordView] = Field(default_factory=list)
    manifest_notes: list[str] = Field(default_factory=list)


RAW_SECRET_FIELD_NAMES = {
    "api_key",
    "client_secret",
    "credential_value",
    "password",
    "secret",
    "token",
}

RAW_CONNECTION_FIELD_NAMES = {
    "connection_string",
    "database_url",
    "dsn",
    "host",
    "jdbc_url",
    "port",
}

RAW_QUERY_FIELD_NAMES = {
    "query",
    "raw_sql",
    "sql",
    "statement",
    "where_clause",
}

RAW_CONNECTION_MARKERS = ("postgres://", "postgresql://", "jdbc:")
RAW_QUERY_MARKERS = ("select ", "insert ", "update ", "delete ", "drop ")
MANIFEST_LIFECYCLE_TRANSITIONS = {
    "registered_preview_only": {"active_preview", "deprecated"},
    "active_preview": {"deprecated"},
    "deprecated": set(),
}
LIVE_MANIFEST_TARGETS = {
    "active_live",
    "enabled_live",
    "live_enabled",
    "production_enabled",
}


def build_connector_manifest_registry(
    repository: AxisPersistenceRepository,
    query: ConnectorManifestQuery,
) -> ManufacturingConnectorManifestRegistry:
    records = repository.list_connector_manifests(
        tenant_id=query.tenant_id,
        connector_id=query.connector_id,
        status=query.status,
        limit=query.limit,
    )
    manifests = [_record_from_persistence(record) for record in records]
    return ManufacturingConnectorManifestRegistry(
        tenant_id=query.tenant_id,
        plant_name="Ravenna Works",
        scenario="Plant Operations Cockpit",
        registry_status=OverviewStatus.READY if manifests else OverviewStatus.WATCH,
        metrics=[
            OverviewMetric(
                label="Persisted Manifests",
                value=str(len(manifests)),
                detail="Tenant-scoped connector manifest records",
                status=OverviewStatus.READY if manifests else OverviewStatus.WATCH,
            ),
            OverviewMetric(
                label="Raw Material",
                value="Rejected",
                detail="DSNs, SQL text and credential values are blocked",
                status=OverviewStatus.READY,
            ),
            OverviewMetric(
                label="Live Sync",
                value="Not Enabled",
                detail="Persisting a manifest does not start connector execution",
                status=OverviewStatus.WATCH,
            ),
        ],
        manifests=manifests,
        manifest_notes=[
            "Persisted connector manifests are tenant-scoped metadata records.",
            "Registration writes audit evidence but does not enable live sync.",
            "Raw connection strings, SQL text and credential values are rejected.",
        ],
    )


def record_demo_connector_manifest(
    repository: AxisPersistenceRepository,
    request: ConnectorManifestCreateRequest,
) -> ConnectorManifestRecordView:
    _validate_public_safe_manifest(request)
    try:
        manifest = ConnectorManifest.model_validate(request.manifest)
    except ValidationError as exc:
        raise ConnectorManifestValidationError(
            "Connector manifest payload is invalid.",
            "invalid_manifest_payload",
        ) from exc

    existing = repository.get_connector_manifest(request.tenant_id, manifest.connector_id)
    if existing is not None:
        raise ConnectorManifestConflict(existing.connector_id)

    try:
        runtime_policy_model = ConnectorRuntimePolicy.model_validate(request.runtime_policy)
    except ValidationError as exc:
        raise ConnectorManifestValidationError(
            "Connector runtime policy payload is invalid.",
            "invalid_runtime_policy_payload",
        ) from exc
    try:
        preview_sample_model = ConnectorPreviewSample.model_validate(request.preview_sample)
    except ValidationError as exc:
        raise ConnectorManifestValidationError(
            "Connector preview sample payload is invalid.",
            "invalid_preview_sample_payload",
        ) from exc
    manifest_payload = manifest.model_dump(mode="json")
    runtime_policy = runtime_policy_model.model_dump(mode="json")
    preview_sample = preview_sample_model.model_dump(mode="json")
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=request.tenant_id,
            actor_id=request.registered_by,
            event_type="connector.manifest.registered",
            payload={
                "connector_id": manifest.connector_id,
                "connector_type": manifest.connector_type,
                "source_type": manifest.source_type,
                "runtime_boundary": manifest.runtime_boundary,
                "sync_modes": manifest.sync_modes,
                "live_sync_enabled": "false",
            },
        )
    )
    record = repository.create_connector_manifest(
        ConnectorManifestCreate(
            tenant_id=request.tenant_id,
            connector_id=manifest.connector_id,
            display_name=manifest.display_name,
            connector_type=manifest.connector_type,
            source_type=manifest.source_type,
            version=manifest.version,
            status="registered_preview_only",
            runtime_boundary=manifest.runtime_boundary,
            registered_by=request.registered_by,
            manifest_payload=manifest_payload,
            runtime_policy=runtime_policy,
            preview_sample=preview_sample,
            audit_event_id=audit_event.id,
            audit_event_type="connector.manifest.registered",
            notes=request.notes,
        )
    )
    return _record_from_persistence(record)


def transition_demo_connector_manifest_lifecycle(
    repository: AxisPersistenceRepository,
    connector_id: str,
    request: ConnectorManifestLifecycleRequest,
) -> ConnectorManifestRecordView:
    if request.required_scope not in request.actor_scopes:
        raise ConnectorManifestLifecycleValidationError(
            "Connector manifest lifecycle transition requires lifecycle scope.",
            "missing_manifest_lifecycle_scope",
        )
    if request.target_status in LIVE_MANIFEST_TARGETS:
        raise ConnectorManifestLifecycleValidationError(
            "Connector manifest lifecycle cannot enable live connector operation.",
            "unsupported_manifest_lifecycle_target",
        )
    if request.target_status not in {"active_preview", "deprecated"}:
        raise ConnectorManifestLifecycleValidationError(
            "Connector manifest lifecycle target is not supported.",
            "unsupported_manifest_lifecycle_target",
        )

    manifest = repository.get_connector_manifest(request.tenant_id, connector_id)
    if manifest is None:
        raise ConnectorManifestLifecycleValidationError(
            "Connector manifest was not found.",
            "manifest_not_found",
        )
    allowed_targets = MANIFEST_LIFECYCLE_TRANSITIONS.get(manifest.status, set())
    if request.target_status not in allowed_targets:
        raise ConnectorManifestLifecycleValidationError(
            "Connector manifest lifecycle transition is not allowed.",
            "manifest_lifecycle_transition_not_allowed",
        )

    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=request.tenant_id,
            actor_id=request.transitioned_by,
            event_type="connector.manifest.lifecycle_transitioned",
            payload={
                "connector_id": connector_id,
                "from_status": manifest.status,
                "target_status": request.target_status,
                "required_scope": request.required_scope,
                "transition_reason": request.transition_reason,
                "evidence_refs": request.evidence_refs,
                "live_sync_enabled": "false",
            },
        )
    )
    try:
        updated = repository.update_connector_manifest_lifecycle(
            ConnectorManifestLifecycleUpdate(
                tenant_id=request.tenant_id,
                connector_id=connector_id,
                status=request.target_status,
                audit_event_id=audit_event.id,
                audit_event_type="connector.manifest.lifecycle_transitioned",
                note=f"Lifecycle transition: {request.target_status}",
            )
        )
    except PersistenceRecordNotFound as exc:
        raise ConnectorManifestLifecycleValidationError(
            "Connector manifest was not found.",
            "manifest_not_found",
        ) from exc
    return _record_from_persistence(updated)


def _record_from_persistence(record) -> ConnectorManifestRecordView:
    return ConnectorManifestRecordView(
        tenant_id=record.tenant_id,
        manifest_id=str(record.id),
        connector_id=record.connector_id,
        display_name=record.display_name,
        connector_type=record.connector_type,
        source_type=record.source_type,
        version=record.version,
        status=record.status,
        runtime_boundary=record.runtime_boundary,
        registered_by=record.registered_by,
        manifest=record.manifest_payload,
        runtime_policy=record.runtime_policy,
        preview_sample=record.preview_sample,
        audit_event_id=record.audit_event_id,
        audit_event_type=record.audit_event_type,
        notes=record.notes,
        created_at=record.created_at,
    )


def _validate_public_safe_manifest(request: ConnectorManifestCreateRequest) -> None:
    payload = request.model_dump(mode="json")
    keys = {key for key, _ in _walk_payload(payload)}
    values = [value for _, value in _walk_payload(payload)]
    if keys.intersection(RAW_CONNECTION_FIELD_NAMES) or any(
        marker in value for value in values for marker in RAW_CONNECTION_MARKERS
    ):
        raise ConnectorManifestValidationError(
            "Connector manifest cannot include raw connection material.",
            "raw_connection_field",
        )
    if keys.intersection(RAW_QUERY_FIELD_NAMES) or any(
        marker in value for value in values for marker in RAW_QUERY_MARKERS
    ):
        raise ConnectorManifestValidationError(
            "Connector manifest cannot include raw SQL or query text.",
            "raw_query_field",
        )
    if keys.intersection(RAW_SECRET_FIELD_NAMES):
        raise ConnectorManifestValidationError(
            "Connector manifest cannot include raw credential material.",
            "raw_secret_field",
        )


def _walk_payload(value: Any) -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            normalized_key = str(key).lower()
            yield normalized_key, ""
            yield from _walk_payload(nested_value)
    elif isinstance(value, list):
        for nested_value in value:
            yield from _walk_payload(nested_value)
    elif value is not None:
        yield "", str(value).lower()
