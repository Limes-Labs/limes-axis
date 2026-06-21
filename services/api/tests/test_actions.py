import pytest

from axis_api.actions import ActionDefinition, ActionRiskLevel, ApprovalMode


def test_high_risk_action_requires_approval() -> None:
    action = ActionDefinition(
        action_id="create_purchase_request",
        display_name="Create purchase request",
        domain="procurement",
        risk_level=ActionRiskLevel.HIGH,
        approval_mode=ApprovalMode.REQUIRED,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        required_permissions=["procurement:write"],
    )
    assert action.requires_approval is True


def test_high_risk_action_without_approval_is_rejected() -> None:
    with pytest.raises(ValueError, match="require approval"):
        ActionDefinition(
            action_id="create_purchase_request",
            display_name="Create purchase request",
            domain="procurement",
            risk_level=ActionRiskLevel.HIGH,
            approval_mode=ApprovalMode.NOT_REQUIRED,
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            required_permissions=["procurement:write"],
        )
