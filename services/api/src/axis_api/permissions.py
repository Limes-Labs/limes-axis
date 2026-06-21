from pydantic import BaseModel, Field


class PermissionRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    actor_scopes: list[str]
    required_scopes: list[str]
    relationship_scopes: list[str] = Field(default_factory=list)
    attributes: dict


class PermissionDecision(BaseModel):
    allowed: bool
    reason: str


def evaluate_permission(request: PermissionRequest) -> PermissionDecision:
    actor_scopes = set(request.actor_scopes)
    for scope in request.required_scopes:
        if scope not in actor_scopes:
            return PermissionDecision(allowed=False, reason=f"missing_scope:{scope}")
    for scope in request.relationship_scopes:
        if scope not in actor_scopes:
            return PermissionDecision(
                allowed=False,
                reason=f"missing_relationship_scope:{scope}",
            )
    return PermissionDecision(allowed=True, reason="allowed")
