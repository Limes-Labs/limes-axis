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


def test_permission_denies_missing_relationship_scope_after_action_scopes_pass() -> None:
    request = PermissionRequest(
        tenant_id="tenant_demo",
        actor_id="agent_supply_risk",
        actor_scopes=["supply:read", "approvals:supply:request"],
        required_scopes=["supply:read", "approvals:supply:request"],
        relationship_scopes=["quality:read"],
        attributes={
            "action_id": "request_supplier_expedite",
            "resource_refs": ["asset_batch_q_1842"],
        },
    )

    decision = evaluate_permission(request)

    assert decision == PermissionDecision(
        allowed=False,
        reason="missing_relationship_scope:quality:read",
    )
