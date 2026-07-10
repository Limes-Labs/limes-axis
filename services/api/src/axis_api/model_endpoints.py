"""Tenant-scoped model endpoint registry.

Endpoints are the governed routing targets of the model router: metadata-only
records describing where a model is hosted (``self_hosted``,
``approved_private_endpoint`` or ``external``), which tasks it serves and what
it costs. The registry never stores credential material — endpoints may only
reference an existing connector credential handle (which itself stores a
``secret_provider`` + ``secret_ref``, never a raw value). Non-self-hosted
endpoints must declare the egress policy that will be validated at invocation
time; registration alone never authorizes egress.
"""

from datetime import datetime
from decimal import Decimal
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from axis_api.audit import AuditEventCreate
from axis_api.connector_credential_handles import RAW_SECRET_MARKERS
from axis_api.permissions import PermissionDecision, PermissionRequest, evaluate_permission
from axis_api.persistence import (
    AxisPersistenceRepository,
    ModelEndpointCreate,
    ModelEndpointStatusUpdate,
    PersistenceRecordNotFound,
)

MODEL_ENDPOINT_ADMIN_SCOPE = "platform:model:endpoint:admin"
MODEL_ENDPOINT_READ_SCOPE = "platform:model:endpoint:read"
MODEL_ENDPOINT_REGISTERED_AUDIT_EVENT_TYPE = "model.endpoint.registered"
MODEL_ENDPOINT_STATUS_CHANGED_AUDIT_EVENT_TYPE = "model.endpoint.status_changed"

SELF_HOSTED_BOUNDARY = "self_hosted"
APPROVED_PRIVATE_ENDPOINT_BOUNDARY = "approved_private_endpoint"
EXTERNAL_BOUNDARY = "external"
SUPPORTED_HOSTING_BOUNDARIES = (
    SELF_HOSTED_BOUNDARY,
    APPROVED_PRIVATE_ENDPOINT_BOUNDARY,
    EXTERNAL_BOUNDARY,
)
SUPPORTED_PROVIDER_TYPES = ("openai_compatible",)
SUPPORTED_ENDPOINT_STATUSES = ("enabled", "disabled")


class ModelEndpointValidationError(ValueError):
    def __init__(self, message: str, reason: str) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason


class ModelEndpointPermissionDenied(PermissionError):
    def __init__(self, required_permission: str, decision: PermissionDecision) -> None:
        super().__init__(decision.reason)
        self.required_permission = required_permission
        self.decision = decision


class ModelEndpointConflict(ValueError):
    def __init__(self, endpoint_id: str) -> None:
        super().__init__("Model endpoint already exists")
        self.endpoint_id = endpoint_id


class ModelEndpointNotFound(LookupError):
    def __init__(self, endpoint_id: str) -> None:
        super().__init__("Model endpoint not found")
        self.endpoint_id = endpoint_id


class ModelEndpointCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    endpoint_id: str = Field(min_length=1, max_length=160, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    display_name: str = Field(min_length=1, max_length=200)
    provider_type: str = Field(min_length=1, max_length=80)
    hosting_boundary: str = Field(min_length=1, max_length=80)
    base_url: str = Field(min_length=1, max_length=500)
    default_model: str = Field(min_length=1, max_length=160)
    task_types: list[str] = Field(min_length=1)
    status: str = Field(default="enabled", min_length=1, max_length=40)
    credential_handle_id: str | None = Field(default=None, min_length=1, max_length=160)
    egress_policy_id: str | None = Field(default=None, min_length=1, max_length=180)
    cost_input_per_1k: Decimal = Field(default=Decimal("0"), ge=0)
    cost_output_per_1k: Decimal = Field(default=Decimal("0"), ge=0)
    created_by: str = Field(min_length=1, max_length=160)
    actor_scopes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ModelEndpointStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    target_status: str = Field(min_length=1, max_length=40)
    reason: str = Field(min_length=1, max_length=600)
    updated_by: str = Field(min_length=1, max_length=160)
    actor_scopes: list[str] = Field(default_factory=list)


class ModelEndpointRecord(BaseModel):
    tenant_id: str = Field(min_length=1)
    endpoint_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    provider_type: str = Field(min_length=1)
    hosting_boundary: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    default_model: str = Field(min_length=1)
    task_types: list[str] = Field(min_length=1)
    status: str = Field(min_length=1)
    credential_handle_id: str | None = None
    egress_policy_id: str | None = None
    cost_input_per_1k: float = Field(ge=0)
    cost_output_per_1k: float = Field(ge=0)
    created_by: str = Field(min_length=1)
    audit_event_id: UUID | None = None
    audit_event_type: str = Field(min_length=1)
    notes: list[str] = Field(default_factory=list)
    created_at: datetime


class ModelEndpointRegistry(BaseModel):
    tenant_id: str = Field(min_length=1)
    endpoint_count: int = Field(ge=0)
    enabled_endpoint_count: int = Field(ge=0)
    endpoints: list[ModelEndpointRecord] = Field(default_factory=list)
    endpoint_notes: list[str] = Field(default_factory=list)


def record_model_endpoint(
    repository: AxisPersistenceRepository,
    request: ModelEndpointCreateRequest,
) -> ModelEndpointRecord:
    permission_decision = _evaluate_admin_permission(
        tenant_id=request.tenant_id,
        actor_id=request.created_by,
        actor_scopes=request.actor_scopes,
        attributes={
            "endpoint_id": request.endpoint_id,
            "provider_type": request.provider_type,
            "hosting_boundary": request.hosting_boundary,
            "operation": "record_model_endpoint",
        },
    )
    _validate_endpoint_request(repository, request)

    existing = repository.get_model_endpoint(request.tenant_id, request.endpoint_id)
    if existing is not None:
        raise ModelEndpointConflict(existing.endpoint_id)

    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=request.tenant_id,
            actor_id=request.created_by,
            event_type=MODEL_ENDPOINT_REGISTERED_AUDIT_EVENT_TYPE,
            payload={
                "endpoint_id": request.endpoint_id,
                "display_name": request.display_name,
                "provider_type": request.provider_type,
                "hosting_boundary": request.hosting_boundary,
                "default_model": request.default_model,
                "task_types": sorted(request.task_types),
                "status": request.status,
                "credential_handle_id": request.credential_handle_id,
                "egress_policy_id": request.egress_policy_id,
                "cost_input_per_1k": str(request.cost_input_per_1k),
                "cost_output_per_1k": str(request.cost_output_per_1k),
                "required_permission": MODEL_ENDPOINT_ADMIN_SCOPE,
                "permission_decision": permission_decision.model_dump(),
            },
        )
    )
    endpoint = repository.create_model_endpoint(
        ModelEndpointCreate(
            tenant_id=request.tenant_id,
            endpoint_id=request.endpoint_id,
            display_name=request.display_name,
            provider_type=request.provider_type,
            hosting_boundary=request.hosting_boundary,
            base_url=request.base_url,
            default_model=request.default_model,
            task_types=sorted(set(request.task_types)),
            status=request.status,
            credential_handle_id=request.credential_handle_id,
            egress_policy_id=request.egress_policy_id,
            cost_input_per_1k=request.cost_input_per_1k,
            cost_output_per_1k=request.cost_output_per_1k,
            created_by=request.created_by,
            audit_event_id=audit_event.id,
            audit_event_type=audit_event.event_type,
            notes=request.notes,
        )
    )
    return model_endpoint_record(endpoint)


def update_model_endpoint_status(
    repository: AxisPersistenceRepository,
    endpoint_id: str,
    request: ModelEndpointStatusUpdateRequest,
) -> ModelEndpointRecord:
    """Governed enable/disable transition for a registered model endpoint.

    Disabled endpoints are skipped by :func:`decide_model_route`, so this is
    the sanctioned way to take a mis-registered endpoint out of routing
    without deleting its audit history. The transition itself writes a
    ``model.endpoint.status_changed`` audit event before persisting.
    """
    permission_decision = _evaluate_admin_permission(
        tenant_id=request.tenant_id,
        actor_id=request.updated_by,
        actor_scopes=request.actor_scopes,
        attributes={
            "endpoint_id": endpoint_id,
            "target_status": request.target_status,
            "operation": "update_model_endpoint_status",
        },
    )
    if request.target_status not in SUPPORTED_ENDPOINT_STATUSES:
        raise ModelEndpointValidationError(
            f"Unsupported model endpoint status: {request.target_status}",
            "unsupported_endpoint_status",
        )

    endpoint = repository.get_model_endpoint(request.tenant_id, endpoint_id)
    if endpoint is None:
        raise ModelEndpointNotFound(endpoint_id)

    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=request.tenant_id,
            actor_id=request.updated_by,
            event_type=MODEL_ENDPOINT_STATUS_CHANGED_AUDIT_EVENT_TYPE,
            payload={
                "endpoint_id": endpoint_id,
                "from_status": endpoint.status,
                "target_status": request.target_status,
                "reason": request.reason,
                "required_permission": MODEL_ENDPOINT_ADMIN_SCOPE,
                "permission_decision": permission_decision.model_dump(),
            },
        )
    )
    try:
        updated = repository.update_model_endpoint_status(
            ModelEndpointStatusUpdate(
                tenant_id=request.tenant_id,
                endpoint_id=endpoint_id,
                status=request.target_status,
                audit_event_id=audit_event.id,
                audit_event_type=audit_event.event_type,
                note=f"Status transition: {request.target_status} ({request.reason})",
            )
        )
    except PersistenceRecordNotFound as exc:
        raise ModelEndpointNotFound(endpoint_id) from exc
    return model_endpoint_record(updated)


def build_model_endpoint_registry(
    repository: AxisPersistenceRepository,
    tenant_id: str = "tenant_demo_manufacturing",
    status: str | None = None,
    limit: int = 100,
) -> ModelEndpointRegistry:
    records = repository.list_model_endpoints(
        tenant_id=tenant_id,
        status=status,
        limit=limit,
    )
    endpoints = [model_endpoint_record(record) for record in records]
    enabled_count = sum(1 for endpoint in endpoints if endpoint.status == "enabled")
    return ModelEndpointRegistry(
        tenant_id=tenant_id,
        endpoint_count=len(endpoints),
        enabled_endpoint_count=enabled_count,
        endpoints=endpoints,
        endpoint_notes=[
            "Model endpoints are metadata-only routing targets; no credential material "
            "is ever stored.",
            "Non-self-hosted endpoints must declare an egress policy; egress evidence is "
            "validated on every invocation.",
            "Route decisions are deterministic and fail closed when no enabled endpoint "
            "matches the requested task.",
        ],
    )


def model_endpoint_record(record) -> ModelEndpointRecord:
    return ModelEndpointRecord(
        tenant_id=record.tenant_id,
        endpoint_id=record.endpoint_id,
        display_name=record.display_name,
        provider_type=record.provider_type,
        hosting_boundary=record.hosting_boundary,
        base_url=record.base_url,
        default_model=record.default_model,
        task_types=list(record.task_types),
        status=record.status,
        credential_handle_id=record.credential_handle_id,
        egress_policy_id=record.egress_policy_id,
        cost_input_per_1k=float(record.cost_input_per_1k),
        cost_output_per_1k=float(record.cost_output_per_1k),
        created_by=record.created_by,
        audit_event_id=record.audit_event_id,
        audit_event_type=record.audit_event_type,
        notes=list(record.notes),
        created_at=record.created_at,
    )


def _validate_endpoint_request(
    repository: AxisPersistenceRepository,
    request: ModelEndpointCreateRequest,
) -> None:
    if request.provider_type not in SUPPORTED_PROVIDER_TYPES:
        raise ModelEndpointValidationError(
            f"Unsupported model endpoint provider type: {request.provider_type}",
            "unsupported_provider_type",
        )
    if request.hosting_boundary not in SUPPORTED_HOSTING_BOUNDARIES:
        raise ModelEndpointValidationError(
            f"Unsupported model endpoint hosting boundary: {request.hosting_boundary}",
            "unsupported_hosting_boundary",
        )
    if request.status not in SUPPORTED_ENDPOINT_STATUSES:
        raise ModelEndpointValidationError(
            f"Unsupported model endpoint status: {request.status}",
            "unsupported_endpoint_status",
        )
    if any(not task_type.strip() for task_type in request.task_types):
        raise ModelEndpointValidationError(
            "Model endpoint task types must be non-empty values.",
            "invalid_task_types",
        )
    _validate_base_url(request.base_url)
    if (
        request.hosting_boundary != SELF_HOSTED_BOUNDARY
        and not request.egress_policy_id
    ):
        raise ModelEndpointValidationError(
            "Non-self-hosted model endpoints must reference an egress policy.",
            "egress_policy_required",
        )
    if request.credential_handle_id is not None:
        handle = repository.get_connector_credential_handle(
            request.tenant_id,
            request.credential_handle_id,
        )
        if handle is None:
            raise ModelEndpointValidationError(
                "The referenced connector credential handle was not found.",
                "credential_handle_not_found",
            )


def _validate_base_url(base_url: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ModelEndpointValidationError(
            "Model endpoint base URLs must be absolute http(s) URLs.",
            "invalid_base_url",
        )
    if parsed.username is not None or parsed.password is not None:
        raise ModelEndpointValidationError(
            "Model endpoint base URLs cannot embed userinfo credentials.",
            "base_url_contains_secret",
        )
    lowered = base_url.lower()
    if any(marker in lowered for marker in RAW_SECRET_MARKERS):
        raise ModelEndpointValidationError(
            "Model endpoint base URLs cannot include inline credential values.",
            "base_url_contains_secret",
        )


def _evaluate_admin_permission(
    *,
    tenant_id: str,
    actor_id: str,
    actor_scopes: list[str],
    attributes: dict[str, str],
) -> PermissionDecision:
    decision = evaluate_permission(
        PermissionRequest(
            tenant_id=tenant_id,
            actor_id=actor_id,
            actor_scopes=actor_scopes,
            required_scopes=[MODEL_ENDPOINT_ADMIN_SCOPE],
            attributes=attributes,
        )
    )
    if not decision.allowed:
        raise ModelEndpointPermissionDenied(MODEL_ENDPOINT_ADMIN_SCOPE, decision)
    return decision
