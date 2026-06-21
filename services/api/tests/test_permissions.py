from axis_api.permissions import PermissionDecision, PermissionRequest, evaluate_permission


def test_permission_denied_without_required_scope() -> None:
    request = PermissionRequest(
        tenant_id="tenant_demo",
        actor_id="actor_quality",
        actor_scopes=["quality:read"],
        required_scopes=["quality:write"],
        attributes={"risk_level": "medium"},
    )
    decision = evaluate_permission(request)
    assert decision == PermissionDecision(
        allowed=False,
        reason="missing_scope:quality:write",
    )


def test_permission_allows_actor_with_required_scope() -> None:
    request = PermissionRequest(
        tenant_id="tenant_demo",
        actor_id="actor_quality",
        actor_scopes=["quality:read", "quality:write"],
        required_scopes=["quality:write"],
        attributes={"risk_level": "low"},
    )
    decision = evaluate_permission(request)
    assert decision.allowed is True
