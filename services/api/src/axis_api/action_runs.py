from uuid import UUID

from pydantic import BaseModel, Field

from axis_api.action_reference import get_persisted_manufacturing_action_registry
from axis_api.audit import AuditEventCreate
from axis_api.demo import (
    ActionRegistryEntry,
    get_manufacturing_ontology,
)
from axis_api.permissions import PermissionDecision, PermissionRequest, evaluate_permission
from axis_api.persistence import ActionRunCreate, AxisPersistenceRepository
from axis_api.workflow_runtime import (
    DeferredWorkflowSignalRuntime,
    WorkflowActionSignalRequest,
    WorkflowSignalError,
    WorkflowSignalResult,
    WorkflowSignalRuntime,
    workflow_action_signal_failure_result,
)


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
    workflow_signal: WorkflowSignalResult | None = None
    workflow_signal_status: str = Field(default="not_required", min_length=1)


def _find_demo_action(
    repository: AxisPersistenceRepository,
    action_id: str,
) -> tuple[str, ActionRegistryEntry, str]:
    registry = get_persisted_manufacturing_action_registry(repository)
    for action in registry.actions:
        if action.definition.action_id == action_id:
            return registry.tenant_id, action, registry.schema_version

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


def _payload_ontology_refs(action: ActionRegistryEntry, payload: dict) -> list[str]:
    properties = action.definition.input_schema.get("properties", {})
    refs: set[str] = set()
    for field_name, field_schema in properties.items():
        if not isinstance(field_schema, dict) or not field_schema.get("x-axis-ontology-ref"):
            continue

        value = payload.get(field_name)
        if isinstance(value, str) and value:
            refs.add(value)
        elif isinstance(value, list):
            refs.update(item for item in value if isinstance(item, str) and item)

    return sorted(refs)


def _relationship_scopes_for_refs(resource_refs: list[str]) -> list[str]:
    if not resource_refs:
        return []

    ref_ids = set(resource_refs)
    ontology = get_manufacturing_ontology()
    return sorted(
        {
            relationship.permission_scope
            for relationship in ontology.relationships
            if relationship.source_id in ref_ids or relationship.target_id in ref_ids
        }
    )


def _evaluate_action_permission(
    tenant_id: str,
    action: ActionRegistryEntry,
    request: ActionRunRequest,
) -> PermissionDecision:
    resource_refs = _payload_ontology_refs(action, request.payload)
    relationship_scopes = _relationship_scopes_for_refs(resource_refs)
    decision = evaluate_permission(
        PermissionRequest(
            tenant_id=tenant_id,
            actor_id=request.actor_id,
            actor_scopes=request.actor_scopes,
            required_scopes=action.definition.required_permissions,
            relationship_scopes=relationship_scopes,
            attributes={
                "action_id": action.definition.action_id,
                "domain": action.definition.domain,
                "risk_level": action.definition.risk_level.value,
                "approval_mode": action.definition.approval_mode.value,
                "owner_role": action.owner_role,
                "execution_mode": action.policy.execution_mode,
                "resource_refs": resource_refs,
                "relationship_scopes": relationship_scopes,
            },
        )
    )
    if not decision.allowed:
        raise ActionPermissionDenied(
            sorted(set(action.definition.required_permissions) | set(relationship_scopes)),
            decision,
        )

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


def _stored_payload(
    action: ActionRegistryEntry,
    request: ActionRunRequest,
    schema_version: str,
) -> dict:
    return {
        "input": request.payload,
        "schema_version": schema_version,
        "dry_run": action.policy.dry_run_supported,
    }


def _should_signal_workflow(action: ActionRegistryEntry) -> bool:
    return (
        bool(action.workflow_bindings) and action.policy.runtime_adapter == "axis-temporal-adapter"
    )


def _workflow_signal_status(workflow_signal: WorkflowSignalResult | None) -> str:
    if workflow_signal is None:
        return "not_required"
    return workflow_signal.status


async def _signal_action_workflow(
    workflow_runtime: WorkflowSignalRuntime,
    *,
    tenant_id: str,
    action: ActionRegistryEntry,
    action_run_id: UUID,
    idempotency_key: str,
    request: ActionRunRequest,
) -> WorkflowSignalResult | None:
    if not _should_signal_workflow(action):
        return None

    signal_request = WorkflowActionSignalRequest(
        tenant_id=tenant_id,
        workflow_id=action.workflow_bindings[0],
        action_id=action.definition.action_id,
        action_run_id=action_run_id,
        idempotency_key=idempotency_key,
        approval_id=action.approval_refs[0] if action.approval_refs else None,
        execution_mode=action.policy.execution_mode,
        payload=request.payload,
    )
    try:
        return await workflow_runtime.signal_action_run(signal_request)
    except WorkflowSignalError as exc:
        return workflow_action_signal_failure_result(signal_request, reason=str(exc))


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
    workflow_signal: WorkflowSignalResult | None = None,
    workflow_signal_status: str | None = None,
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
        workflow_signal=workflow_signal,
        workflow_signal_status=workflow_signal_status or _workflow_signal_status(workflow_signal),
    )


async def record_demo_action_run(
    repository: AxisPersistenceRepository,
    action_id: str,
    request: ActionRunRequest,
    workflow_runtime: WorkflowSignalRuntime | None = None,
) -> ActionRunPersistenceResult:
    tenant_id, action, schema_version = _find_demo_action(repository, action_id)
    _validate_payload(action, request.payload)
    permission_decision = _evaluate_action_permission(tenant_id, action, request)
    idempotency_key = _idempotency_key(tenant_id, action, request)
    payload = _stored_payload(action, request, schema_version)
    runtime = workflow_runtime or DeferredWorkflowSignalRuntime()

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
            workflow_signal_status="idempotent_replay",
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
    workflow_signal = await _signal_action_workflow(
        runtime,
        tenant_id=tenant_id,
        action=action,
        action_run_id=action_run.id,
        idempotency_key=idempotency_key,
        request=request,
    )
    workflow_signal_status = _workflow_signal_status(workflow_signal)
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
                "relationship_scopes": _relationship_scopes_for_refs(
                    _payload_ontology_refs(action, request.payload)
                ),
                "payload_field_names": sorted(request.payload.keys()),
                "payload_recorded": "true",
                "workflow_signal_status": workflow_signal_status,
                "workflow_signal": workflow_signal.model_dump() if workflow_signal else None,
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
        workflow_signal=workflow_signal,
        workflow_signal_status=workflow_signal_status,
    )
