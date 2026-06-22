from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from axis_api.audit import AuditEventCreate
from axis_api.connectors import get_manufacturing_connector_registry
from axis_api.demo import OverviewMetric, OverviewStatus
from axis_api.permissions import PermissionDecision, PermissionRequest, evaluate_permission
from axis_api.persistence import AxisPersistenceRepository, ConnectorPromotionPolicySetCreate


class ConnectorPromotionPolicySetValidationError(ValueError):
    def __init__(self, message: str, reason: str) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason


class ConnectorPromotionPolicySetPermissionDenied(PermissionError):
    def __init__(self, required_permission: str, decision: PermissionDecision) -> None:
        super().__init__(decision.reason)
        self.required_permission = required_permission
        self.decision = decision


class ConnectorPromotionPolicySetConflict(ValueError):
    def __init__(self, policy_set_id: str, reason: str) -> None:
        super().__init__("Connector promotion policy set already exists or conflicts")
        self.policy_set_id = policy_set_id
        self.reason = reason


class ConnectorPromotionPolicySetQuery(BaseModel):
    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    connector_id: str | None = Field(default=None, min_length=1)
    status: str | None = Field(default=None, min_length=1)
    limit: int = Field(default=100, ge=1, le=200)


class ConnectorPromotionPolicySetActivateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    connector_id: str = Field(default="file_csv_manufacturing_assets", min_length=1)
    policy_set_id: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    policy_set_version: str = Field(min_length=1, max_length=80)
    status: str = Field(default="active", min_length=1, max_length=80)
    activated_by: str = Field(min_length=1, max_length=160)
    actor_scopes: list[str] = Field(default_factory=list)
    policy_ids: list[str] = Field(min_length=1, max_length=20)
    activation_reason: str = Field(min_length=1, max_length=600)
    replaces_policy_set_id: str | None = Field(default=None, min_length=1, max_length=180)
    replacement_approval_id: str | None = Field(default=None, min_length=1, max_length=180)
    replacement_decision: str | None = Field(default=None, min_length=1, max_length=40)
    replacement_workflow_signal_status: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
    )
    notes: list[str] = Field(default_factory=list)


class ConnectorPromotionPolicySetRecord(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    policy_set_id: str = Field(min_length=1)
    policy_set_version: str = Field(min_length=1)
    status: str = Field(min_length=1)
    activated_by: str = Field(min_length=1)
    activation_scope: str = Field(min_length=1)
    policy_ids: list[str] = Field(min_length=1)
    permission_decision: PermissionDecision
    audit_event_id: UUID | None = None
    audit_event_type: str = Field(min_length=1)
    activation_reason: str = Field(min_length=1)
    replaces_policy_set_id: str | None = None
    replaced_by_policy_set_id: str | None = None
    replacement_approval_id: str | None = None
    replacement_decision: str | None = None
    replacement_workflow_signal_status: str | None = None
    replaced_at: datetime | None = None
    notes: list[str] = Field(default_factory=list)
    created_at: datetime


class ManufacturingConnectorPromotionPolicySetRegistry(BaseModel):
    tenant_id: str = Field(min_length=1)
    plant_name: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    registry_status: OverviewStatus
    metrics: list[OverviewMetric] = Field(default_factory=list)
    policy_sets: list[ConnectorPromotionPolicySetRecord] = Field(default_factory=list)
    policy_set_notes: list[str] = Field(default_factory=list)


REQUIRED_POLICY_SET_ACTIVATION_SCOPE = "connectors:promotion_policy_set:activate"
POLICY_SET_AUDIT_EVENT_TYPE = "connector.promotion_policy_set.activated"
POLICY_SET_REPLACED_AUDIT_EVENT_TYPE = "connector.promotion_policy_set.replaced"
REQUIRED_POLICY_SET_REPLACEMENT_SIGNAL = "policy_set_replacement_signal_recorded"
SUPPORTED_POLICY_SET_STATUSES = {"active"}


def build_connector_promotion_policy_set_registry(
    repository: AxisPersistenceRepository,
    tenant_id: str = "tenant_demo_manufacturing",
    connector_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> ManufacturingConnectorPromotionPolicySetRegistry:
    records = repository.list_connector_promotion_policy_sets(
        tenant_id=tenant_id,
        connector_id=connector_id,
        status=status,
        limit=limit,
    )
    policy_sets = [_policy_set_from_record(record) for record in records]
    active_count = sum(1 for policy_set in policy_sets if policy_set.status == "active")
    policy_count = sum(len(policy_set.policy_ids) for policy_set in policy_sets)
    return ManufacturingConnectorPromotionPolicySetRegistry(
        tenant_id=tenant_id,
        plant_name="Ravenna Works",
        scenario="Plant Operations Cockpit",
        registry_status=OverviewStatus.READY if policy_sets else OverviewStatus.WATCH,
        metrics=[
            OverviewMetric(
                label="Policy Sets",
                value=str(len(policy_sets)),
                detail="Versioned connector promotion policy sets",
                status=OverviewStatus.READY if policy_sets else OverviewStatus.WATCH,
            ),
            OverviewMetric(
                label="Active Sets",
                value=str(active_count),
                detail="Policy sets selected for automatic required gates",
                status=OverviewStatus.READY if active_count else OverviewStatus.WATCH,
            ),
            OverviewMetric(
                label="Set Policies",
                value=str(policy_count),
                detail="Required policy references inside versioned sets",
                status=OverviewStatus.READY if policy_count else OverviewStatus.WATCH,
            ),
        ],
        policy_sets=policy_sets,
        policy_set_notes=[
            "Policy sets resolve multi-policy required gates without implicit selection.",
            "Activation requires each referenced policy to be enabled and required.",
            "Active set replacement requires approval and workflow signal evidence.",
        ],
    )


def record_demo_connector_promotion_policy_set(
    repository: AxisPersistenceRepository,
    request: ConnectorPromotionPolicySetActivateRequest,
) -> ConnectorPromotionPolicySetRecord:
    _manifest_for_connector(request.connector_id)
    _validate_policy_set_status(request.status)
    _validate_policy_ids_unique(request.policy_ids)
    existing = repository.get_connector_promotion_policy_set(
        request.tenant_id,
        request.policy_set_id,
    )
    if existing is not None:
        raise ConnectorPromotionPolicySetConflict(
            existing.policy_set_id,
            "policy_set_already_exists",
        )
    active_sets = repository.list_active_connector_promotion_policy_sets(
        request.tenant_id,
        request.connector_id,
    )
    active_policy_set = _active_policy_set_for_replacement(active_sets, request)
    if active_sets and active_policy_set is None:
        raise ConnectorPromotionPolicySetConflict(
            active_sets[0].policy_set_id,
            "policy_set_active_exists",
        )
    if not active_sets and request.replaces_policy_set_id is not None:
        raise ConnectorPromotionPolicySetValidationError(
            "Connector promotion policy set replacement target is not active.",
            "policy_set_replacement_target_not_found",
        )
    if active_policy_set is not None:
        _validate_replacement_evidence(request)
    policies = _validate_referenced_policies(repository, request)
    permission_decision = _evaluate_activation_permission(request)
    audit_event_type = (
        POLICY_SET_REPLACED_AUDIT_EVENT_TYPE
        if active_policy_set is not None
        else POLICY_SET_AUDIT_EVENT_TYPE
    )
    audit_payload = {
        "connector_id": request.connector_id,
        "policy_set_id": request.policy_set_id,
        "policy_set_version": request.policy_set_version,
        "status": request.status,
        "policy_ids": request.policy_ids,
        "policy_versions": [policy.policy_version for policy in policies],
        "activation_scope": REQUIRED_POLICY_SET_ACTIVATION_SCOPE,
        "permission_decision": permission_decision.model_dump(),
        "activation_reason": request.activation_reason,
    }
    if active_policy_set is not None:
        audit_payload.update(
            {
                "previous_policy_set_id": active_policy_set.policy_set_id,
                "previous_policy_set_version": active_policy_set.policy_set_version,
                "previous_status": active_policy_set.status,
                "replacement_approval_id": request.replacement_approval_id,
                "replacement_decision": request.replacement_decision,
                "replacement_workflow_signal_status": request.replacement_workflow_signal_status,
            }
        )
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=request.tenant_id,
            actor_id=request.activated_by,
            event_type=audit_event_type,
            payload=audit_payload,
        )
    )
    create_record = ConnectorPromotionPolicySetCreate(
        tenant_id=request.tenant_id,
        connector_id=request.connector_id,
        policy_set_id=request.policy_set_id,
        policy_set_version=request.policy_set_version,
        status=request.status,
        activated_by=request.activated_by,
        activation_scope=REQUIRED_POLICY_SET_ACTIVATION_SCOPE,
        policy_ids=request.policy_ids,
        permission_decision=permission_decision.model_dump(),
        audit_event_id=audit_event.id,
        audit_event_type=audit_event.event_type,
        activation_reason=request.activation_reason,
        replaces_policy_set_id=request.replaces_policy_set_id,
        replacement_approval_id=request.replacement_approval_id,
        replacement_decision=request.replacement_decision,
        replacement_workflow_signal_status=request.replacement_workflow_signal_status,
        notes=request.notes,
    )
    if active_policy_set is None:
        policy_set = repository.create_connector_promotion_policy_set(create_record)
    else:
        policy_set = repository.replace_connector_promotion_policy_set(
            active_policy_set,
            create_record,
        )
    return _policy_set_from_record(policy_set)


def _active_policy_set_for_replacement(
    active_sets: list,
    request: ConnectorPromotionPolicySetActivateRequest,
):
    if not active_sets:
        return None
    if request.replaces_policy_set_id is None:
        return None
    for active_set in active_sets:
        if active_set.policy_set_id == request.replaces_policy_set_id:
            return active_set
    raise ConnectorPromotionPolicySetValidationError(
        "Connector promotion policy set replacement target does not match the active set.",
        "policy_set_replacement_target_mismatch",
    )


def _validate_replacement_evidence(request: ConnectorPromotionPolicySetActivateRequest) -> None:
    if request.replacement_approval_id is None:
        raise ConnectorPromotionPolicySetValidationError(
            "Connector promotion policy set replacement requires approval evidence.",
            "policy_set_replacement_approval_required",
        )
    if request.replacement_decision != "approve":
        raise ConnectorPromotionPolicySetValidationError(
            "Connector promotion policy set replacement requires an approved decision.",
            "policy_set_replacement_not_approved",
        )
    if request.replacement_workflow_signal_status != REQUIRED_POLICY_SET_REPLACEMENT_SIGNAL:
        raise ConnectorPromotionPolicySetValidationError(
            "Connector promotion policy set replacement requires workflow signal evidence.",
            "policy_set_replacement_signal_required",
        )


def _evaluate_activation_permission(
    request: ConnectorPromotionPolicySetActivateRequest,
) -> PermissionDecision:
    decision = evaluate_permission(
        PermissionRequest(
            tenant_id=request.tenant_id,
            actor_id=request.activated_by,
            actor_scopes=request.actor_scopes,
            required_scopes=[REQUIRED_POLICY_SET_ACTIVATION_SCOPE],
            attributes={
                "connector_id": request.connector_id,
                "policy_set_id": request.policy_set_id,
                "policy_set_version": request.policy_set_version,
            },
        )
    )
    if not decision.allowed:
        raise ConnectorPromotionPolicySetPermissionDenied(
            REQUIRED_POLICY_SET_ACTIVATION_SCOPE,
            decision,
        )
    return decision


def _validate_policy_set_status(status: str) -> None:
    if status in SUPPORTED_POLICY_SET_STATUSES:
        return
    raise ConnectorPromotionPolicySetValidationError(
        "Connector promotion policy sets can only be activated in this slice.",
        "unsupported_policy_set_status",
    )


def _validate_policy_ids_unique(policy_ids: list[str]) -> None:
    if len(set(policy_ids)) == len(policy_ids):
        return
    raise ConnectorPromotionPolicySetValidationError(
        "Connector promotion policy sets cannot reference duplicate policies.",
        "policy_set_duplicate_policy",
    )


def _validate_referenced_policies(
    repository: AxisPersistenceRepository,
    request: ConnectorPromotionPolicySetActivateRequest,
) -> list:
    policies = []
    for policy_id in request.policy_ids:
        policy = repository.get_connector_promotion_policy(request.tenant_id, policy_id)
        if policy is None:
            raise ConnectorPromotionPolicySetValidationError(
                "Connector promotion policy set references an unknown policy.",
                "policy_set_policy_not_found",
            )
        if policy.connector_id != request.connector_id:
            raise ConnectorPromotionPolicySetValidationError(
                "Connector promotion policy set references a policy for another connector.",
                "policy_set_connector_mismatch",
            )
        if policy.status != "enabled" or policy.enforcement_mode != "required":
            raise ConnectorPromotionPolicySetValidationError(
                "Connector promotion policy set references a policy that is not enabled required.",
                "policy_set_policy_not_enabled_required",
            )
        policies.append(policy)
    return policies


def _manifest_for_connector(connector_id: str):
    registry = get_manufacturing_connector_registry()
    for connector in registry.connectors:
        if connector.manifest.connector_id == connector_id:
            return connector.manifest
    raise ConnectorPromotionPolicySetValidationError(
        f"Unsupported connector_id: {connector_id}",
        "unsupported_connector_id",
    )


def _policy_set_from_record(record) -> ConnectorPromotionPolicySetRecord:
    return ConnectorPromotionPolicySetRecord(
        tenant_id=record.tenant_id,
        connector_id=record.connector_id,
        policy_set_id=record.policy_set_id,
        policy_set_version=record.policy_set_version,
        status=record.status,
        activated_by=record.activated_by,
        activation_scope=record.activation_scope,
        policy_ids=record.policy_ids,
        permission_decision=PermissionDecision.model_validate(record.permission_decision),
        audit_event_id=record.audit_event_id,
        audit_event_type=record.audit_event_type,
        activation_reason=record.activation_reason,
        replaces_policy_set_id=record.replaces_policy_set_id,
        replaced_by_policy_set_id=record.replaced_by_policy_set_id,
        replacement_approval_id=record.replacement_approval_id,
        replacement_decision=record.replacement_decision,
        replacement_workflow_signal_status=record.replacement_workflow_signal_status,
        replaced_at=record.replaced_at,
        notes=record.notes,
        created_at=record.created_at,
    )
