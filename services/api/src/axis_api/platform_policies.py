from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from axis_api.actions import ActionRiskLevel
from axis_api.audit import AuditEventCreate
from axis_api.permissions import PermissionDecision, PermissionRequest, evaluate_permission
from axis_api.persistence import (
    AxisPersistenceRepository,
    PlatformPolicyCreate,
)


class PlatformPolicyScope(StrEnum):
    ACTION_EXECUTION = "action_execution"
    APPROVAL_REQUIREMENT = "approval_requirement"


class PlatformPolicyEffect(StrEnum):
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"
    ALLOW_WITH_EVIDENCE = "allow_with_evidence"


class PlatformPolicyValidationError(ValueError):
    def __init__(self, message: str, reason: str) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason


class PlatformPolicyPermissionDenied(PermissionError):
    def __init__(self, required_permission: str, decision: PermissionDecision) -> None:
        super().__init__(decision.reason)
        self.required_permission = required_permission
        self.decision = decision


class PlatformPolicyConflict(ValueError):
    def __init__(self, policy_id: str) -> None:
        super().__init__("Platform policy already exists")
        self.policy_id = policy_id


class PlatformPolicyRevisionConflict(ValueError):
    def __init__(self, policy_id: str, idempotency_key: str) -> None:
        super().__init__("Platform policy revision idempotency key already exists")
        self.policy_id = policy_id
        self.idempotency_key = idempotency_key


class PlatformPolicyNotFound(LookupError):
    pass


class PlatformPolicyEnforcementDenied(ValueError):
    def __init__(
        self,
        decision: "PlatformPolicyDecision",
        audit_event_id: UUID,
        audit_event_type: str,
    ) -> None:
        super().__init__("A platform policy denies this transition")
        self.decision = decision
        self.audit_event_id = audit_event_id
        self.audit_event_type = audit_event_type


REQUIRED_AUTHORING_SCOPE = "platform:policy:author"
REQUIRED_REVISE_SCOPE = "platform:policy:revise"
REQUIRED_READ_SCOPE = "platform:policy:read"
REQUIRED_EVALUATE_SCOPE = "platform:policy:evaluate"
AUTHORED_AUDIT_EVENT_TYPE = "platform.policy.authored"
REVISED_AUDIT_EVENT_TYPE = "platform.policy.revised"
ENFORCEMENT_DENIED_AUDIT_EVENT_TYPE = "platform.policy.enforcement.denied"
SUPPORTED_AUTONOMY_LEVELS = {"L0", "L1", "L2", "L3", "L4"}
SUPPORTED_RISK_LEVELS = {level.value for level in ActionRiskLevel}
DEFAULT_ALLOW_EFFECT = "allow"
PRECEDENCE_RULE = "effect_severity_then_policy_id"
_EFFECT_PRECEDENCE = {
    PlatformPolicyEffect.DENY.value: 0,
    PlatformPolicyEffect.REQUIRE_APPROVAL.value: 1,
    PlatformPolicyEffect.ALLOW_WITH_EVIDENCE.value: 2,
}


class PlatformPolicyRuleConditions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_domains: list[str] = Field(default_factory=list)
    risk_levels: list[str] = Field(default_factory=list)
    autonomy_levels: list[str] = Field(default_factory=list)
    requested_amount_at_least: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @field_validator("action_domains")
    @classmethod
    def validate_action_domains(cls, action_domains: list[str]) -> list[str]:
        for domain in action_domains:
            if not domain or domain != domain.strip():
                raise ValueError("Platform policy action domains must be non-empty trimmed values.")
        return action_domains

    @field_validator("risk_levels")
    @classmethod
    def validate_risk_levels(cls, risk_levels: list[str]) -> list[str]:
        for risk_level in risk_levels:
            if risk_level not in SUPPORTED_RISK_LEVELS:
                raise ValueError(f"Unsupported platform policy risk level: {risk_level}")
        return risk_levels

    @field_validator("autonomy_levels")
    @classmethod
    def validate_autonomy_levels(cls, autonomy_levels: list[str]) -> list[str]:
        for autonomy_level in autonomy_levels:
            if autonomy_level not in SUPPORTED_AUTONOMY_LEVELS:
                raise ValueError(f"Unsupported platform policy autonomy level: {autonomy_level}")
        return autonomy_levels

    @model_validator(mode="after")
    def validate_at_least_one_condition(self) -> "PlatformPolicyRuleConditions":
        if (
            not self.action_domains
            and not self.risk_levels
            and not self.autonomy_levels
            and self.requested_amount_at_least is None
        ):
            raise ValueError("Platform policy rule conditions must declare at least one condition.")
        return self


class PlatformPolicyQuery(BaseModel):
    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    scope: PlatformPolicyScope | None = None
    status: str | None = Field(default=None, min_length=1)
    limit: int = Field(default=100, ge=1, le=200)


class PlatformPolicyCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    policy_id: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    policy_version: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=600)
    scope: PlatformPolicyScope
    effect: PlatformPolicyEffect
    conditions: dict
    created_by: str = Field(min_length=1, max_length=160)
    actor_scopes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PlatformPolicyReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    policy_id: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    policy_version: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=600)
    effect: PlatformPolicyEffect
    conditions: dict
    updated_by: str = Field(min_length=1, max_length=160)
    actor_scopes: list[str] = Field(default_factory=list)
    idempotency_key: str = Field(min_length=1, max_length=200)
    notes: list[str] = Field(default_factory=list)


class PlatformPolicyRecord(BaseModel):
    tenant_id: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    revision_number: int = Field(ge=1)
    policy_version: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    scope: PlatformPolicyScope
    effect: PlatformPolicyEffect
    conditions: PlatformPolicyRuleConditions
    status: str = Field(min_length=1)
    created_by: str = Field(min_length=1)
    required_authoring_scope: str = Field(min_length=1)
    permission_decision: PermissionDecision
    audit_event_id: UUID | None = None
    audit_event_type: str = Field(min_length=1)
    revises_revision_number: int | None = None
    replaced_by_revision_number: int | None = None
    revision_idempotency_key: str | None = None
    idempotent_replay: bool = False
    notes: list[str] = Field(default_factory=list)
    created_at: datetime


class PlatformPolicyDetail(BaseModel):
    tenant_id: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    current_revision: PlatformPolicyRecord
    revisions: list[PlatformPolicyRecord] = Field(min_length=1)


class PlatformPolicyRegistry(BaseModel):
    tenant_id: str = Field(min_length=1)
    policy_count: int = Field(ge=0)
    active_policy_count: int = Field(ge=0)
    policies: list[PlatformPolicyRecord] = Field(default_factory=list)
    policy_notes: list[str] = Field(default_factory=list)


class PlatformPolicyEvaluationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str | None = Field(default=None, min_length=1, max_length=180)
    action_domain: str | None = Field(default=None, min_length=1, max_length=160)
    risk_level: str | None = Field(default=None, min_length=1, max_length=40)
    autonomy_level: str | None = Field(default=None, pattern=r"^L[0-4]$")
    requested_amount: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class PlatformPolicyEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    actor_id: str = Field(min_length=1, max_length=160)
    actor_scopes: list[str] = Field(default_factory=list)
    scope: PlatformPolicyScope
    context: PlatformPolicyEvaluationContext


class PlatformPolicyMatch(BaseModel):
    policy_id: str = Field(min_length=1)
    revision_number: int = Field(ge=1)
    policy_version: str = Field(min_length=1)
    effect: PlatformPolicyEffect
    matched_constraints: dict = Field(default_factory=dict)


class PlatformPolicyDecision(BaseModel):
    tenant_id: str = Field(min_length=1)
    scope: PlatformPolicyScope
    effect: str = Field(min_length=1)
    matched: bool
    matched_policy_id: str | None = None
    matched_revision_number: int | None = None
    matched_policy_version: str | None = None
    evaluated_policy_count: int = Field(ge=0)
    matched_policies: list[PlatformPolicyMatch] = Field(default_factory=list)
    precedence_rule: str = Field(default=PRECEDENCE_RULE, min_length=1)
    evidence: dict = Field(default_factory=dict)


def build_platform_policy_registry(
    repository: AxisPersistenceRepository,
    tenant_id: str = "tenant_demo_manufacturing",
    scope: PlatformPolicyScope | None = None,
    status: str | None = None,
    limit: int = 100,
) -> PlatformPolicyRegistry:
    records = repository.list_platform_policies(
        tenant_id=tenant_id,
        scope=scope.value if scope is not None else None,
        status=status,
        limit=limit,
    )
    policies = [_policy_from_record(record) for record in records]
    active_count = sum(1 for policy in policies if policy.status == "active")
    return PlatformPolicyRegistry(
        tenant_id=tenant_id,
        policy_count=len(policies),
        active_policy_count=active_count,
        policies=policies,
        policy_notes=[
            "Platform policies govern action execution and approval requirements per tenant.",
            "Policy revisions are append-only and idempotent; superseded revisions stay readable.",
            "Policy evaluation is deterministic and never calls a model provider "
            "or external system.",
            "Deny decisions take precedence over approval requirements and "
            "evidence-only allowances.",
        ],
    )


def record_platform_policy(
    repository: AxisPersistenceRepository,
    request: PlatformPolicyCreateRequest,
) -> PlatformPolicyRecord:
    conditions = _validate_rule_conditions(request.conditions)
    existing = repository.get_platform_policy(request.tenant_id, request.policy_id)
    if existing is not None:
        raise PlatformPolicyConflict(existing.policy_id)

    permission_decision = _evaluate_authoring_permission(request)
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=request.tenant_id,
            actor_id=request.created_by,
            event_type=AUTHORED_AUDIT_EVENT_TYPE,
            payload={
                "policy_id": request.policy_id,
                "policy_version": request.policy_version,
                "revision_number": 1,
                "display_name": request.display_name,
                "scope": request.scope.value,
                "effect": request.effect.value,
                "conditions": conditions.model_dump(),
                "status": "active",
                "required_authoring_scope": REQUIRED_AUTHORING_SCOPE,
                "permission_decision": permission_decision.model_dump(),
            },
        )
    )
    policy = repository.create_platform_policy(
        PlatformPolicyCreate(
            tenant_id=request.tenant_id,
            policy_id=request.policy_id,
            revision_number=1,
            policy_version=request.policy_version,
            display_name=request.display_name,
            description=request.description,
            scope=request.scope.value,
            effect=request.effect.value,
            conditions=conditions.model_dump(),
            status="active",
            created_by=request.created_by,
            required_authoring_scope=REQUIRED_AUTHORING_SCOPE,
            permission_decision=permission_decision.model_dump(),
            audit_event_id=audit_event.id,
            audit_event_type=audit_event.event_type,
            notes=request.notes,
        )
    )
    return _policy_from_record(policy)


def revise_platform_policy(
    repository: AxisPersistenceRepository,
    request: PlatformPolicyReviseRequest,
) -> PlatformPolicyRecord:
    conditions = _validate_rule_conditions(request.conditions)
    existing_replay = repository.get_platform_policy_by_revision_idempotency_key(
        request.tenant_id,
        request.idempotency_key,
    )
    if existing_replay is not None:
        if existing_replay.policy_id != request.policy_id or not _revision_matches_request(
            existing_replay,
            request,
            conditions,
        ):
            raise PlatformPolicyRevisionConflict(request.policy_id, request.idempotency_key)
        return _policy_from_record(existing_replay, idempotent_replay=True)

    current_policy = repository.get_platform_policy(request.tenant_id, request.policy_id)
    if current_policy is None:
        raise PlatformPolicyNotFound()

    permission_decision = _evaluate_revision_permission(request)
    revision_number = current_policy.revision_number + 1
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=request.tenant_id,
            actor_id=request.updated_by,
            event_type=REVISED_AUDIT_EVENT_TYPE,
            payload={
                "policy_id": request.policy_id,
                "policy_version": request.policy_version,
                "previous_policy_version": current_policy.policy_version,
                "revision_number": revision_number,
                "revises_revision_number": current_policy.revision_number,
                "display_name": request.display_name,
                "scope": current_policy.scope,
                "effect": request.effect.value,
                "conditions": conditions.model_dump(),
                "status": "active",
                "idempotency_key": request.idempotency_key,
                "required_revision_scope": REQUIRED_REVISE_SCOPE,
                "permission_decision": permission_decision.model_dump(),
            },
        )
    )
    revised_policy = repository.append_platform_policy_revision(
        current_policy,
        PlatformPolicyCreate(
            tenant_id=request.tenant_id,
            policy_id=request.policy_id,
            revision_number=revision_number,
            policy_version=request.policy_version,
            display_name=request.display_name,
            description=request.description,
            scope=current_policy.scope,
            effect=request.effect.value,
            conditions=conditions.model_dump(),
            status="active",
            created_by=request.updated_by,
            required_authoring_scope=REQUIRED_REVISE_SCOPE,
            permission_decision=permission_decision.model_dump(),
            audit_event_id=audit_event.id,
            audit_event_type=audit_event.event_type,
            revises_revision_number=current_policy.revision_number,
            revision_idempotency_key=request.idempotency_key,
            notes=request.notes,
        ),
    )
    return _policy_from_record(revised_policy)


def get_platform_policy_detail(
    repository: AxisPersistenceRepository,
    tenant_id: str,
    policy_id: str,
) -> PlatformPolicyDetail:
    revisions = repository.list_platform_policy_revisions(tenant_id, policy_id)
    if not revisions:
        raise PlatformPolicyNotFound()

    records = [_policy_from_record(revision) for revision in revisions]
    current_revision = next(
        (record for record in reversed(records) if record.status == "active"),
        records[-1],
    )
    return PlatformPolicyDetail(
        tenant_id=tenant_id,
        policy_id=policy_id,
        current_revision=current_revision,
        revisions=records,
    )


def evaluate_platform_policy_request(
    repository: AxisPersistenceRepository,
    request: PlatformPolicyEvaluationRequest,
) -> PlatformPolicyDecision:
    _evaluate_evaluation_permission(request)
    return evaluate_platform_policies(
        repository,
        tenant_id=request.tenant_id,
        scope=request.scope,
        context=request.context,
    )


def evaluate_platform_policies(
    repository: AxisPersistenceRepository,
    *,
    tenant_id: str,
    scope: PlatformPolicyScope,
    context: PlatformPolicyEvaluationContext,
) -> PlatformPolicyDecision:
    policies = repository.list_active_platform_policies_for_scope(tenant_id, scope.value)
    matches: list[PlatformPolicyMatch] = []
    for policy in policies:
        conditions = PlatformPolicyRuleConditions.model_validate(policy.conditions)
        matched, matched_constraints = _conditions_match(conditions, context)
        if matched:
            matches.append(
                PlatformPolicyMatch(
                    policy_id=policy.policy_id,
                    revision_number=policy.revision_number,
                    policy_version=policy.policy_version,
                    effect=PlatformPolicyEffect(policy.effect),
                    matched_constraints=matched_constraints,
                )
            )

    matches.sort(
        key=lambda match: (
            _EFFECT_PRECEDENCE[match.effect.value],
            match.policy_id,
            -match.revision_number,
        )
    )
    winning = matches[0] if matches else None
    return PlatformPolicyDecision(
        tenant_id=tenant_id,
        scope=scope,
        effect=winning.effect.value if winning else DEFAULT_ALLOW_EFFECT,
        matched=winning is not None,
        matched_policy_id=winning.policy_id if winning else None,
        matched_revision_number=winning.revision_number if winning else None,
        matched_policy_version=winning.policy_version if winning else None,
        evaluated_policy_count=len(policies),
        matched_policies=matches,
        precedence_rule=PRECEDENCE_RULE,
        evidence={
            "context": context.model_dump(),
            "matched_constraints": winning.matched_constraints if winning else {},
            "default_effect": DEFAULT_ALLOW_EFFECT,
        },
    )


def enforce_platform_policy_deny(
    repository: AxisPersistenceRepository,
    *,
    tenant_id: str,
    actor_id: str,
    scope: PlatformPolicyScope,
    context: PlatformPolicyEvaluationContext,
    enforcement_point: str,
    audit_payload: dict,
) -> PlatformPolicyDecision:
    decision = evaluate_platform_policies(
        repository,
        tenant_id=tenant_id,
        scope=scope,
        context=context,
    )
    if decision.effect != PlatformPolicyEffect.DENY.value:
        return decision

    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=tenant_id,
            actor_id=actor_id,
            event_type=ENFORCEMENT_DENIED_AUDIT_EVENT_TYPE,
            payload={
                **audit_payload,
                "enforcement_point": enforcement_point,
                "status": "policy_denied",
                "policy_id": decision.matched_policy_id,
                "policy_revision_number": decision.matched_revision_number,
                "policy_version": decision.matched_policy_version,
                "policy_scope": decision.scope.value,
                "policy_effect": decision.effect,
                "platform_policy_decision": decision.model_dump(),
            },
        )
    )
    raise PlatformPolicyEnforcementDenied(decision, audit_event.id, audit_event.event_type)


def _conditions_match(
    conditions: PlatformPolicyRuleConditions,
    context: PlatformPolicyEvaluationContext,
) -> tuple[bool, dict]:
    matched_constraints: dict = {}
    if conditions.action_domains:
        if context.action_domain not in conditions.action_domains:
            return False, {}
        matched_constraints["action_domain"] = context.action_domain
    if conditions.risk_levels:
        if context.risk_level not in conditions.risk_levels:
            return False, {}
        matched_constraints["risk_level"] = context.risk_level
    if conditions.autonomy_levels:
        if context.autonomy_level not in conditions.autonomy_levels:
            return False, {}
        matched_constraints["autonomy_level"] = context.autonomy_level
    if conditions.requested_amount_at_least is not None:
        if (
            context.requested_amount is None
            or context.requested_amount < conditions.requested_amount_at_least
        ):
            return False, {}
        matched_constraints["requested_amount"] = context.requested_amount
        matched_constraints["requested_amount_at_least"] = conditions.requested_amount_at_least
    return True, matched_constraints


def _validate_rule_conditions(conditions: dict) -> PlatformPolicyRuleConditions:
    try:
        return PlatformPolicyRuleConditions.model_validate(conditions)
    except ValueError as exc:
        raise PlatformPolicyValidationError(
            "Platform policy rule conditions are malformed.",
            "invalid_rule_conditions",
        ) from exc


def _revision_matches_request(
    record,
    request: PlatformPolicyReviseRequest,
    conditions: PlatformPolicyRuleConditions,
) -> bool:
    return (
        record.policy_version == request.policy_version
        and record.display_name == request.display_name
        and record.description == request.description
        and record.effect == request.effect.value
        and record.conditions == conditions.model_dump()
        and record.notes == request.notes
    )


def _evaluate_authoring_permission(
    request: PlatformPolicyCreateRequest,
) -> PermissionDecision:
    decision = evaluate_permission(
        PermissionRequest(
            tenant_id=request.tenant_id,
            actor_id=request.created_by,
            actor_scopes=request.actor_scopes,
            required_scopes=[REQUIRED_AUTHORING_SCOPE],
            attributes={
                "policy_id": request.policy_id,
                "scope": request.scope.value,
                "effect": request.effect.value,
            },
        )
    )
    if not decision.allowed:
        raise PlatformPolicyPermissionDenied(REQUIRED_AUTHORING_SCOPE, decision)
    return decision


def _evaluate_revision_permission(
    request: PlatformPolicyReviseRequest,
) -> PermissionDecision:
    decision = evaluate_permission(
        PermissionRequest(
            tenant_id=request.tenant_id,
            actor_id=request.updated_by,
            actor_scopes=request.actor_scopes,
            required_scopes=[REQUIRED_REVISE_SCOPE],
            attributes={
                "policy_id": request.policy_id,
                "effect": request.effect.value,
                "idempotency_key": request.idempotency_key,
            },
        )
    )
    if not decision.allowed:
        raise PlatformPolicyPermissionDenied(REQUIRED_REVISE_SCOPE, decision)
    return decision


def _evaluate_evaluation_permission(
    request: PlatformPolicyEvaluationRequest,
) -> PermissionDecision:
    decision = evaluate_permission(
        PermissionRequest(
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            actor_scopes=request.actor_scopes,
            required_scopes=[REQUIRED_EVALUATE_SCOPE],
            attributes={
                "scope": request.scope.value,
                "operation": "evaluate_platform_policies",
            },
        )
    )
    if not decision.allowed:
        raise PlatformPolicyPermissionDenied(REQUIRED_EVALUATE_SCOPE, decision)
    return decision


def _policy_from_record(record, idempotent_replay: bool = False) -> PlatformPolicyRecord:
    return PlatformPolicyRecord(
        tenant_id=record.tenant_id,
        policy_id=record.policy_id,
        revision_number=record.revision_number,
        policy_version=record.policy_version,
        display_name=record.display_name,
        description=record.description,
        scope=PlatformPolicyScope(record.scope),
        effect=PlatformPolicyEffect(record.effect),
        conditions=PlatformPolicyRuleConditions.model_validate(record.conditions),
        status=record.status,
        created_by=record.created_by,
        required_authoring_scope=record.required_authoring_scope,
        permission_decision=PermissionDecision.model_validate(record.permission_decision),
        audit_event_id=record.audit_event_id,
        audit_event_type=record.audit_event_type,
        revises_revision_number=record.revises_revision_number,
        replaced_by_revision_number=record.replaced_by_revision_number,
        revision_idempotency_key=record.revision_idempotency_key,
        idempotent_replay=idempotent_replay,
        notes=record.notes,
        created_at=record.created_at,
    )
