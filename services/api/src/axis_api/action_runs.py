from uuid import UUID

from pydantic import BaseModel, Field

from axis_api.audit import AuditEventCreate
from axis_api.demo import ActionRegistryEntry, get_manufacturing_action_registry
from axis_api.permissions import PermissionDecision, PermissionRequest, evaluate_permission
from axis_api.persistence import ActionRunCreate, AxisPersistenceRepository


class DemoActionNotFound(LookupError):
    pass


class ActionPayloadValidationError(ValueError):
    def __init__(self, issues: list[str]) -> None:
        super().__init__("Action payload validation failed")
        self.issues = issues


class ActionPermissionDenied(PermissionError):
    def __init__(self, required_permissions: list[str], decision: PermissionDecision) -> None:
        super().__init__(decision.reason)
        self.required_permissions = required_permissions
        self.decision = decision


class ActionRunIdempotencyConflict(ValueError):
    def __init__(self, action_run_id: UUID) -> None:
        super().__init__("Idempotency key already exists with a different payload")
        self.action_run_id = action_run_id


class ActionRunRequest(BaseModel):
    actor_id: str = Field(min_length=1)
    actor_scopes: list[str] = Field(default_factory=list)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)
    payload: dict = Field(default_factory=dict)


class ActionRunPersistenceResult(BaseModel):
    tenant_id: str = Field(min_length=1)
    action_run_id: UUID
    action_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    status: str = Field(min_length=1)
    execution_mode: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    approval_required: bool
    approval_id: str | None = None
    workflow_id: str | None = None
    persisted: bool
    idempotent_replay: bool
    permission_decision: PermissionDecision
    audit_event_id: UUID | None = None
    audit_event_type: str | None = None


def _find_demo_action(action_id: str) -> tuple[str, ActionRegistryEntry]:
    registry = get_manufacturing_action_registry()
    for action in registry.actions:
        if action.definition.action_id == action_id:
            return registry.tenant_id, action

    raise DemoActionNotFound("Action not found")


def _field_type_matches(value: object, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str) and value != ""
    if expected_type == "array":
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
    return True


def _validate_payload(action: ActionRegistryEntry, payload: dict) -> None:
    schema = action.definition.input_schema
    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))
    issues: list[str] = []

    for field_name in required_fields:
        if field_name not in payload:
            issues.append(f"missing_required:{field_name}")

    for field_name, value in payload.items():
        field_schema = properties.get(field_name)
        if field_schema is None:
            issues.append(f"unknown_field:{field_name}")
            continue

        expected_type = field_schema.get("type")
        if expected_type and not _field_type_matches(value, expected_type):
            issues.append(f"invalid_type:{field_name}:{expected_type}")

    if issues:
        raise ActionPayloadValidationError(issues)


def _evaluate_action_permission(
    tenant_id: str,
    action: ActionRegistryEntry,
    request: ActionRunRequest,
) -> PermissionDecision:
    decision = evaluate_permission(
        PermissionRequest(
            tenant_id=tenant_id,
            actor_id=request.actor_id,
            actor_scopes=request.actor_scopes,
            required_scopes=action.definition.required_permissions,
            attributes={
                "action_id": action.definition.action_id,
                "domain": action.definition.domain,
                "risk_level": action.definition.risk_level.value,
                "approval_mode": action.definition.approval_mode.value,
                "owner_role": action.owner_role,
                "execution_mode": action.policy.execution_mode,
            },
        )
    )
    if not decision.allowed:
        raise ActionPermissionDenied(action.definition.required_permissions, decision)

    return decision


def _action_status(action: ActionRegistryEntry) -> str:
    if action.definition.requires_approval:
        return "approval_required"
    return "preview_generated"


def _idempotency_key(
    tenant_id: str,
    action: ActionRegistryEntry,
    request: ActionRunRequest,
) -> str:
    if request.idempotency_key:
        return request.idempotency_key

    if action.policy.idempotency_required:
        raise ActionPayloadValidationError(["missing_idempotency_key"])

    return f"{tenant_id}:{action.definition.action_id}:{request.actor_id}:preview"


def _stored_payload(action: ActionRegistryEntry, request: ActionRunRequest) -> dict:
    return {
        "input": request.payload,
        "schema_version": get_manufacturing_action_registry().schema_version,
        "dry_run": action.policy.dry_run_supported,
    }


def _result_from_action_run(
    *,
    tenant_id: str,
    action: ActionRegistryEntry,
    action_run_id: UUID,
    idempotency_key: str,
    status: str,
    requested_by: str,
    permission_decision: PermissionDecision,
    audit_event_id: UUID | None,
    audit_event_type: str | None,
    idempotent_replay: bool,
) -> ActionRunPersistenceResult:
    return ActionRunPersistenceResult(
        tenant_id=tenant_id,
        action_run_id=action_run_id,
        action_id=action.definition.action_id,
        idempotency_key=idempotency_key,
        status=status,
        execution_mode=action.policy.execution_mode,
        requested_by=requested_by,
        approval_required=action.definition.requires_approval,
        approval_id=action.approval_refs[0] if action.approval_refs else None,
        workflow_id=action.workflow_bindings[0] if action.workflow_bindings else None,
        persisted=True,
        idempotent_replay=idempotent_replay,
        permission_decision=permission_decision,
        audit_event_id=audit_event_id,
        audit_event_type=audit_event_type,
    )


def record_demo_action_run(
    repository: AxisPersistenceRepository,
    action_id: str,
    request: ActionRunRequest,
) -> ActionRunPersistenceResult:
    tenant_id, action = _find_demo_action(action_id)
    _validate_payload(action, request.payload)
    permission_decision = _evaluate_action_permission(tenant_id, action, request)
    idempotency_key = _idempotency_key(tenant_id, action, request)
    payload = _stored_payload(action, request)

    existing = repository.get_action_run_by_idempotency_key(
        tenant_id,
        action.definition.action_id,
        idempotency_key,
    )
    if existing is not None:
        if existing.payload != payload:
            raise ActionRunIdempotencyConflict(existing.id)

        return _result_from_action_run(
            tenant_id=tenant_id,
            action=action,
            action_run_id=existing.id,
            idempotency_key=idempotency_key,
            status=existing.status,
            requested_by=existing.requested_by,
            permission_decision=permission_decision,
            audit_event_id=None,
            audit_event_type=None,
            idempotent_replay=True,
        )

    status = _action_status(action)
    action_run = repository.create_action_run(
        ActionRunCreate(
            tenant_id=tenant_id,
            action_id=action.definition.action_id,
            idempotency_key=idempotency_key,
            execution_mode=action.policy.execution_mode,
            requested_by=request.actor_id,
            approval_id=action.approval_refs[0] if action.approval_refs else None,
            workflow_id=action.workflow_bindings[0] if action.workflow_bindings else None,
            payload=payload,
            status=status,
        )
    )
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=tenant_id,
            actor_id=request.actor_id,
            event_type=action.policy.audit_event_type,
            payload={
                "action_id": action.definition.action_id,
                "action_run_id": str(action_run.id),
                "idempotency_key": idempotency_key,
                "status": status,
                "execution_mode": action.policy.execution_mode,
                "approval_required": action.definition.requires_approval,
                "approval_id": action.approval_refs[0] if action.approval_refs else None,
                "workflow_id": action.workflow_bindings[0] if action.workflow_bindings else None,
                "risk_level": action.definition.risk_level.value,
                "approval_mode": action.definition.approval_mode.value,
                "permission_decision": permission_decision.model_dump(),
                "payload_field_names": sorted(request.payload.keys()),
                "payload_recorded": "true",
            },
        )
    )

    return _result_from_action_run(
        tenant_id=tenant_id,
        action=action,
        action_run_id=action_run.id,
        idempotency_key=idempotency_key,
        status=action_run.status,
        requested_by=action_run.requested_by,
        permission_decision=permission_decision,
        audit_event_id=audit_event.id,
        audit_event_type=audit_event.event_type,
        idempotent_replay=False,
    )
