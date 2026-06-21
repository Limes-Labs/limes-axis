from enum import StrEnum

from pydantic import BaseModel, Field


class OverviewStatus(StrEnum):
    READY = "ready"
    WATCH = "watch"
    ACTION_REQUIRED = "action_required"


class OverviewMetric(BaseModel):
    label: str = Field(min_length=1)
    value: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    status: OverviewStatus


class RiskSignal(BaseModel):
    title: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    severity: OverviewStatus
    owner_role: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    related_asset: str = Field(min_length=1)


class WorkflowSummary(BaseModel):
    workflow_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    state: str = Field(min_length=1)
    owner_role: str = Field(min_length=1)
    blocker: str | None = None
    eta: str = Field(min_length=1)


class ApprovalSummary(BaseModel):
    approval_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    risk_level: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    owner_role: str = Field(min_length=1)
    due: str = Field(min_length=1)


class AgentSummary(BaseModel):
    agent_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    autonomy_level: str = Field(pattern=r"^L[0-4]$")
    status: str = Field(min_length=1)
    proposals_pending: int = Field(ge=0)
    model_policy: str = Field(min_length=1)


class AuditEvidence(BaseModel):
    event: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    result: str = Field(min_length=1)


class ManufacturingOverview(BaseModel):
    tenant_id: str = Field(min_length=1)
    plant_name: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    as_of: str = Field(min_length=1)
    metrics: list[OverviewMetric] = Field(min_length=1)
    risk_signals: list[RiskSignal] = Field(min_length=1)
    workflows: list[WorkflowSummary] = Field(min_length=1)
    approvals: list[ApprovalSummary] = Field(min_length=1)
    agents: list[AgentSummary] = Field(min_length=1)
    audit_events: list[AuditEvidence] = Field(min_length=1)


def get_manufacturing_overview() -> ManufacturingOverview:
    return ManufacturingOverview(
        tenant_id="tenant_demo_manufacturing",
        plant_name="Ravenna Works",
        scenario="Plant Operations Cockpit",
        as_of="2026-06-21T16:30:00+02:00",
        metrics=[
            OverviewMetric(
                label="Workflow Load",
                value="7 active",
                detail="3 production, 2 quality, 1 maintenance, 1 supplier flow",
                status=OverviewStatus.WATCH,
            ),
            OverviewMetric(
                label="Approvals",
                value="3 pending",
                detail="2 high-risk actions require human approval today",
                status=OverviewStatus.ACTION_REQUIRED,
            ),
            OverviewMetric(
                label="Agents",
                value="4 governed",
                detail="All agents remain within L0-L2 autonomy for the demo tenant",
                status=OverviewStatus.READY,
            ),
            OverviewMetric(
                label="Audit",
                value="128 events",
                detail="Reads, proposals, workflow signals and decisions are recorded",
                status=OverviewStatus.READY,
            ),
        ],
        risk_signals=[
            RiskSignal(
                title="Supplier delay may block Line 2 packaging",
                domain="Supply",
                severity=OverviewStatus.ACTION_REQUIRED,
                owner_role="supply-planning-owner",
                evidence="Inbound motors batch is 18 hours late against the production window.",
                related_asset="line-2-packaging",
            ),
            RiskSignal(
                title="Quality drift detected on Batch Q-1842",
                domain="Quality",
                severity=OverviewStatus.WATCH,
                owner_role="quality-owner",
                evidence="Inspection variance crossed the watch threshold for two samples.",
                related_asset="batch-q-1842",
            ),
            RiskSignal(
                title="Press 4 maintenance window is at risk",
                domain="Maintenance",
                severity=OverviewStatus.WATCH,
                owner_role="maintenance-owner",
                evidence="Planned downtime overlaps with a rush order unless rescheduled.",
                related_asset="press-4",
            ),
        ],
        workflows=[
            WorkflowSummary(
                workflow_id="wf_supplier_delay_review",
                name="Supplier Delay Review",
                state="waiting_for_approval",
                owner_role="plant-operations-owner",
                blocker="Approve expedite action or adjust production schedule",
                eta="Today 18:00",
            ),
            WorkflowSummary(
                workflow_id="wf_quality_hold_review",
                name="Quality Hold Review",
                state="investigating",
                owner_role="quality-owner",
                blocker=None,
                eta="Today 16:45",
            ),
            WorkflowSummary(
                workflow_id="wf_maintenance_reschedule",
                name="Maintenance Reschedule",
                state="proposal_ready",
                owner_role="maintenance-owner",
                blocker="Human review required before schedule mutation",
                eta="Tomorrow 09:00",
            ),
        ],
        approvals=[
            ApprovalSummary(
                approval_id="appr_expedite_supplier_batch",
                action="Expedite supplier batch",
                risk_level="high",
                requested_by="supply-risk-agent",
                owner_role="plant-operations-owner",
                due="Today 17:30",
            ),
            ApprovalSummary(
                approval_id="appr_quality_hold_batch",
                action="Place Batch Q-1842 on quality hold",
                risk_level="high",
                requested_by="quality-risk-agent",
                owner_role="quality-owner",
                due="Today 16:45",
            ),
            ApprovalSummary(
                approval_id="appr_shift_maintenance_window",
                action="Shift Press 4 maintenance window",
                risk_level="medium",
                requested_by="maintenance-planner-agent",
                owner_role="maintenance-owner",
                due="Tomorrow 08:30",
            ),
        ],
        agents=[
            AgentSummary(
                agent_id="agent_daily_brief",
                name="Daily Brief Agent",
                autonomy_level="L1",
                status="recommending",
                proposals_pending=1,
                model_policy="local-or-approved-provider",
            ),
            AgentSummary(
                agent_id="agent_quality_risk",
                name="Quality Risk Agent",
                autonomy_level="L2",
                status="drafting_actions",
                proposals_pending=1,
                model_policy="no-external-egress",
            ),
            AgentSummary(
                agent_id="agent_supply_risk",
                name="Supply Risk Agent",
                autonomy_level="L2",
                status="waiting_for_approval",
                proposals_pending=1,
                model_policy="no-external-egress",
            ),
        ],
        audit_events=[
            AuditEvidence(
                event="agent.proposal.created",
                actor="supply-risk-agent",
                scope="wf_supplier_delay_review",
                result="approval_required",
            ),
            AuditEvidence(
                event="policy.egress.blocked",
                actor="model-router",
                scope="quality-risk-agent",
                result="blocked_by_default",
            ),
            AuditEvidence(
                event="workflow.signal.requested",
                actor="plant-operations-owner-role",
                scope="wf_quality_hold_review",
                result="recorded",
            ),
        ],
    )
