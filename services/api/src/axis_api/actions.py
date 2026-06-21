from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class ActionRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalMode(StrEnum):
    NOT_REQUIRED = "not_required"
    REQUIRED = "required"
    CONDITIONAL = "conditional"


class ActionDefinition(BaseModel):
    action_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    risk_level: ActionRiskLevel
    approval_mode: ApprovalMode
    input_schema: dict
    output_schema: dict
    required_permissions: list[str]

    @property
    def requires_approval(self) -> bool:
        return self.approval_mode in {ApprovalMode.REQUIRED, ApprovalMode.CONDITIONAL}

    @model_validator(mode="after")
    def validate_risk_and_approval(self) -> "ActionDefinition":
        if (
            self.risk_level in {ActionRiskLevel.HIGH, ActionRiskLevel.CRITICAL}
            and self.approval_mode == ApprovalMode.NOT_REQUIRED
        ):
            raise ValueError("High and critical risk actions require approval.")
        return self
