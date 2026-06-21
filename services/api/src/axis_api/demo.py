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


class WorkflowSignal(BaseModel):
    signal: str = Field(min_length=1)
    required_role: str = Field(min_length=1)
    status: str = Field(min_length=1)
    approval_id: str | None = None


class WorkflowTimelineEvent(BaseModel):
    event: str = Field(min_length=1)
    at: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    result: str = Field(min_length=1)
    summary: str = Field(min_length=1)


class WorkflowRun(BaseModel):
    workflow_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    state: str = Field(min_length=1)
    status: OverviewStatus
    owner_role: str = Field(min_length=1)
    runtime: str = Field(min_length=1)
    adapter: str = Field(min_length=1)
    autonomy_level: str = Field(pattern=r"^L[0-4]$")
    started_at: str = Field(min_length=1)
    eta: str = Field(min_length=1)
    blocker: str | None = None
    objective: str = Field(min_length=1)
    current_step: str = Field(min_length=1)
    related_risk: str = Field(min_length=1)
    related_assets: list[str] = Field(min_length=1)
    inputs: list[str] = Field(min_length=1)
    proposed_outputs: list[str] = Field(min_length=1)
    pending_signals: list[WorkflowSignal] = Field(min_length=1)
    controls: list[str] = Field(min_length=1)
    timeline: list[WorkflowTimelineEvent] = Field(min_length=1)
    audit_scope: str = Field(min_length=1)
    replay_ready: bool


class ManufacturingWorkflowConsole(BaseModel):
    tenant_id: str = Field(min_length=1)
    plant_name: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    as_of: str = Field(min_length=1)
    runtime_status: OverviewStatus
    metrics: list[OverviewMetric] = Field(min_length=1)
    workflow_runs: list[WorkflowRun] = Field(min_length=1)
    runtime_notes: list[str] = Field(min_length=1)


class ApprovalSummary(BaseModel):
    approval_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    risk_level: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    owner_role: str = Field(min_length=1)
    due: str = Field(min_length=1)


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"


class ApprovalDecisionOption(BaseModel):
    decision: ApprovalDecision
    label: str = Field(min_length=1)
    consequence: str = Field(min_length=1)


class ApprovalAuditPreview(BaseModel):
    event: str = Field(min_length=1)
    actor_role: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    result: str = Field(min_length=1)


class ApprovalInboxItem(BaseModel):
    approval_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    risk_level: str = Field(min_length=1)
    status: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    owner_role: str = Field(min_length=1)
    due: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)
    data_accessed: list[str] = Field(min_length=1)
    risks: list[str] = Field(min_length=1)
    alternatives: list[str] = Field(min_length=1)
    estimated_cost: str = Field(min_length=1)
    model_policy: str = Field(min_length=1)
    required_permission: str = Field(min_length=1)
    audit_event_preview: ApprovalAuditPreview
    decision_options: list[ApprovalDecisionOption] = Field(min_length=1)


class ManufacturingApprovalInbox(BaseModel):
    tenant_id: str = Field(min_length=1)
    plant_name: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    as_of: str = Field(min_length=1)
    queue_status: OverviewStatus
    policy_notes: list[str] = Field(min_length=1)
    approvals: list[ApprovalInboxItem] = Field(min_length=1)


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


class OntologyNodeType(StrEnum):
    ORGANIZATION = "organization"
    ASSET = "asset"
    PROCESS = "process"
    WORKFLOW = "workflow"
    RISK = "risk"
    APPROVAL = "approval"
    AGENT = "agent"
    SYSTEM = "system"
    POLICY = "policy"
    AUDIT_EVENT = "audit_event"


class OntologyNode(BaseModel):
    node_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    node_type: OntologyNodeType
    domain: str = Field(min_length=1)
    status: OverviewStatus
    source_system: str = Field(min_length=1)
    summary: str = Field(min_length=1)


class OntologyRelationship(BaseModel):
    relationship_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    relation_type: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    permission_scope: str = Field(min_length=1)


class ManufacturingOntology(BaseModel):
    tenant_id: str = Field(min_length=1)
    plant_name: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    as_of: str = Field(min_length=1)
    nodes: list[OntologyNode] = Field(min_length=1)
    relationships: list[OntologyRelationship] = Field(min_length=1)
    source_systems: list[str] = Field(min_length=1)
    permission_notes: list[str] = Field(min_length=1)


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


def get_manufacturing_workflow_console() -> ManufacturingWorkflowConsole:
    return ManufacturingWorkflowConsole(
        tenant_id="tenant_demo_manufacturing",
        plant_name="Ravenna Works",
        scenario="Plant Operations Cockpit",
        as_of="2026-06-21T16:30:00+02:00",
        runtime_status=OverviewStatus.WATCH,
        metrics=[
            OverviewMetric(
                label="Active Runs",
                value="3",
                detail="Supply, quality and maintenance workflows in the demo console",
                status=OverviewStatus.WATCH,
            ),
            OverviewMetric(
                label="Waiting Signals",
                value="3",
                detail="Each run has one human or owner signal before mutation",
                status=OverviewStatus.ACTION_REQUIRED,
            ),
            OverviewMetric(
                label="Runtime",
                value="Temporal OSS",
                detail="Hidden behind the Axis workflow runtime adapter",
                status=OverviewStatus.READY,
            ),
            OverviewMetric(
                label="Replay",
                value="Preview",
                detail="History preview exists; deterministic replay remains Platform work",
                status=OverviewStatus.WATCH,
            ),
        ],
        runtime_notes=[
            "The public workflow console seed is read-only and synthetic.",
            "Temporal remains behind the Axis workflow runtime adapter boundary.",
            "Signals shown here are pending governance signals, not live production mutations.",
            (
                "Durable replay, persisted history views and workflow signal execution remain "
                "Platform work."
            ),
        ],
        workflow_runs=[
            WorkflowRun(
                workflow_id="wf_supplier_delay_review",
                name="Supplier Delay Review",
                domain="Supply",
                state="waiting_for_approval",
                status=OverviewStatus.ACTION_REQUIRED,
                owner_role="plant-operations-owner",
                runtime="Temporal OSS",
                adapter="axis-temporal-adapter",
                autonomy_level="L2",
                started_at="2026-06-21T14:05:00+02:00",
                eta="Today 18:00",
                blocker="Approve expedite action or adjust production schedule",
                objective=(
                    "Resolve the delayed inbound motors batch before it blocks Line 2 packaging."
                ),
                current_step="Approval gate",
                related_risk="risk_supplier_delay",
                related_assets=["asset_motors_batch", "asset_line_2_packaging"],
                inputs=[
                    "Supplier portal delay signal",
                    "Line 2 packaging schedule",
                    "Rush order priority flag",
                ],
                proposed_outputs=[
                    "Expedite supplier batch action payload",
                    "Workflow signal for approval decision",
                    "Audit event for governance review",
                ],
                pending_signals=[
                    WorkflowSignal(
                        signal="approval.decision",
                        required_role="plant-operations-owner",
                        status="waiting",
                        approval_id="appr_expedite_supplier_batch",
                    )
                ],
                controls=[
                    "approvals:supply:decide",
                    "append-only-audit-required",
                    "no-external-egress",
                ],
                timeline=[
                    WorkflowTimelineEvent(
                        event="workflow.started",
                        at="2026-06-21T14:05:00+02:00",
                        actor="workflow-runtime",
                        result="started",
                        summary="Supplier delay workflow created from the supply risk signal.",
                    ),
                    WorkflowTimelineEvent(
                        event="agent.proposal.created",
                        at="2026-06-21T14:12:00+02:00",
                        actor="supply-risk-agent",
                        result="approval_required",
                        summary="L2 agent drafted an expedite action payload.",
                    ),
                    WorkflowTimelineEvent(
                        event="workflow.signal.awaiting",
                        at="2026-06-21T14:18:00+02:00",
                        actor="axis-temporal-adapter",
                        result="waiting_for_approval",
                        summary="Workflow paused at the human approval gate.",
                    ),
                ],
                audit_scope="wf_supplier_delay_review",
                replay_ready=False,
            ),
            WorkflowRun(
                workflow_id="wf_quality_hold_review",
                name="Quality Hold Review",
                domain="Quality",
                state="investigating",
                status=OverviewStatus.WATCH,
                owner_role="quality-owner",
                runtime="Temporal OSS",
                adapter="axis-temporal-adapter",
                autonomy_level="L2",
                started_at="2026-06-21T13:35:00+02:00",
                eta="Today 16:45",
                blocker="Quality owner must choose hold, sample expansion or manual review",
                objective="Decide whether Batch Q-1842 needs a quality hold before shipment.",
                current_step="Evidence review",
                related_risk="risk_quality_drift",
                related_assets=["asset_batch_q_1842"],
                inputs=[
                    "QMS sample inspection variance",
                    "Batch genealogy",
                    "Customer order priority",
                ],
                proposed_outputs=[
                    "Quality hold recommendation",
                    "Containment note for quality owner",
                    "Audit event for reviewed evidence",
                ],
                pending_signals=[
                    WorkflowSignal(
                        signal="quality.owner.review",
                        required_role="quality-owner",
                        status="waiting",
                        approval_id="appr_quality_hold_batch",
                    )
                ],
                controls=[
                    "approvals:quality:decide",
                    "quality-evidence-required",
                    "no-external-egress",
                ],
                timeline=[
                    WorkflowTimelineEvent(
                        event="workflow.started",
                        at="2026-06-21T13:35:00+02:00",
                        actor="workflow-runtime",
                        result="started",
                        summary="Quality workflow created from inspection variance.",
                    ),
                    WorkflowTimelineEvent(
                        event="policy.egress.blocked",
                        at="2026-06-21T13:39:00+02:00",
                        actor="model-router",
                        result="blocked_by_default",
                        summary="External model egress was blocked for quality evidence.",
                    ),
                    WorkflowTimelineEvent(
                        event="agent.proposal.created",
                        at="2026-06-21T13:44:00+02:00",
                        actor="quality-risk-agent",
                        result="review_required",
                        summary="L2 agent drafted a quality hold proposal.",
                    ),
                ],
                audit_scope="wf_quality_hold_review",
                replay_ready=False,
            ),
            WorkflowRun(
                workflow_id="wf_maintenance_reschedule",
                name="Maintenance Reschedule",
                domain="Maintenance",
                state="proposal_ready",
                status=OverviewStatus.WATCH,
                owner_role="maintenance-owner",
                runtime="Temporal OSS",
                adapter="axis-temporal-adapter",
                autonomy_level="L2",
                started_at="2026-06-21T15:10:00+02:00",
                eta="Tomorrow 09:00",
                blocker="Human review required before schedule mutation",
                objective="Move the Press 4 maintenance window without violating service policy.",
                current_step="Proposal review",
                related_risk="risk_maintenance_window",
                related_assets=["asset_press_4"],
                inputs=[
                    "CMMS maintenance window",
                    "MES rush order schedule",
                    "Service interval tolerance",
                ],
                proposed_outputs=[
                    "Maintenance reschedule payload",
                    "Owner review signal",
                    "Audit event for schedule decision",
                ],
                pending_signals=[
                    WorkflowSignal(
                        signal="maintenance.owner.review",
                        required_role="maintenance-owner",
                        status="waiting",
                        approval_id="appr_shift_maintenance_window",
                    )
                ],
                controls=[
                    "approvals:maintenance:decide",
                    "service-window-policy",
                    "append-only-audit-required",
                ],
                timeline=[
                    WorkflowTimelineEvent(
                        event="workflow.started",
                        at="2026-06-21T15:10:00+02:00",
                        actor="workflow-runtime",
                        result="started",
                        summary="Maintenance workflow created from schedule collision risk.",
                    ),
                    WorkflowTimelineEvent(
                        event="agent.proposal.created",
                        at="2026-06-21T15:18:00+02:00",
                        actor="maintenance-planner-agent",
                        result="proposal_ready",
                        summary="L2 agent drafted the schedule shift proposal.",
                    ),
                    WorkflowTimelineEvent(
                        event="workflow.signal.awaiting",
                        at="2026-06-21T15:25:00+02:00",
                        actor="axis-temporal-adapter",
                        result="waiting_for_owner_review",
                        summary="Workflow paused before mutating the maintenance schedule.",
                    ),
                ],
                audit_scope="wf_maintenance_reschedule",
                replay_ready=False,
            ),
        ],
    )


def _approval_decision_options() -> list[ApprovalDecisionOption]:
    return [
        ApprovalDecisionOption(
            decision=ApprovalDecision.APPROVE,
            label="Approve",
            consequence="Signal the workflow adapter that the action may proceed.",
        ),
        ApprovalDecisionOption(
            decision=ApprovalDecision.REJECT,
            label="Reject",
            consequence="Record a denial and keep the workflow blocked.",
        ),
        ApprovalDecisionOption(
            decision=ApprovalDecision.REQUEST_CHANGES,
            label="Request changes",
            consequence="Return the proposal to the agent with required review notes.",
        ),
    ]


def get_manufacturing_approval_inbox() -> ManufacturingApprovalInbox:
    return ManufacturingApprovalInbox(
        tenant_id="tenant_demo_manufacturing",
        plant_name="Ravenna Works",
        scenario="Plant Operations Cockpit",
        as_of="2026-06-21T16:30:00+02:00",
        queue_status=OverviewStatus.ACTION_REQUIRED,
        policy_notes=[
            "Critical operations require a human owner role before workflow mutation.",
            "External model egress remains blocked unless policy explicitly enables it.",
            "Approval decisions must become append-only audit events before execution.",
            "This public seed is read-only; production persistence remains Platform work.",
        ],
        approvals=[
            ApprovalInboxItem(
                approval_id="appr_expedite_supplier_batch",
                action="Expedite supplier batch",
                risk_level="high",
                status="pending",
                requested_by="supply-risk-agent",
                owner_role="plant-operations-owner",
                due="Today 17:30",
                workflow_id="wf_supplier_delay_review",
                domain="Supply",
                summary=(
                    "Expedite the delayed inbound motors batch so Line 2 packaging can keep the "
                    "rush order window."
                ),
                evidence=[
                    "Inbound motors batch is 18 hours late against the production window.",
                    "Line 2 packaging has no equivalent substitute batch in the demo seed.",
                    "Supplier portal confirms an available priority freight slot.",
                ],
                data_accessed=[
                    "Supplier Portal: inbound shipment status",
                    "MES: Line 2 packaging schedule",
                    "ERP: rush order priority flag",
                    "Axis Audit: supply-risk-agent proposal trail",
                ],
                risks=[
                    "Expedite fee may exceed standard logistics budget.",
                    "Priority freight could still miss the production window.",
                    "Approval without audit evidence would violate the action policy.",
                ],
                alternatives=[
                    "Hold the rush order and preserve standard freight.",
                    "Shift Line 2 to a lower-priority packaging batch.",
                    "Request supplier split shipment before approving expedite.",
                ],
                estimated_cost="EUR 4,800 priority freight exposure",
                model_policy="no-external-egress",
                required_permission="approvals:supply:decide",
                audit_event_preview=ApprovalAuditPreview(
                    event="approval.decision.recorded",
                    actor_role="plant-operations-owner",
                    scope="wf_supplier_delay_review",
                    result="workflow_signal_ready",
                ),
                decision_options=_approval_decision_options(),
            ),
            ApprovalInboxItem(
                approval_id="appr_quality_hold_batch",
                action="Place Batch Q-1842 on quality hold",
                risk_level="high",
                status="pending",
                requested_by="quality-risk-agent",
                owner_role="quality-owner",
                due="Today 16:45",
                workflow_id="wf_quality_hold_review",
                domain="Quality",
                summary=(
                    "Hold Batch Q-1842 while the quality team reviews inspection variance and "
                    "containment impact."
                ),
                evidence=[
                    "Two samples crossed the inspection variance watch threshold.",
                    "QMS notes show no released deviation waiver for the batch.",
                    "The batch is linked to a customer order with regulated documentation.",
                ],
                data_accessed=[
                    "QMS: sample inspection variance",
                    "MES: batch genealogy",
                    "ERP: customer order priority",
                    "Axis Audit: quality-risk-agent proposal trail",
                ],
                risks=[
                    "Holding the batch may delay a customer shipment.",
                    "Releasing the batch without review may create quality exposure.",
                    "Escalation requires quality role approval, not autonomous execution.",
                ],
                alternatives=[
                    "Increase sampling without placing the full batch on hold.",
                    "Release unaffected lots while holding only the suspect segment.",
                    "Request manual quality engineer review before any hold signal.",
                ],
                estimated_cost="EUR 12,000 shipment delay exposure",
                model_policy="no-external-egress",
                required_permission="approvals:quality:decide",
                audit_event_preview=ApprovalAuditPreview(
                    event="approval.decision.recorded",
                    actor_role="quality-owner",
                    scope="wf_quality_hold_review",
                    result="quality_hold_signal_ready",
                ),
                decision_options=_approval_decision_options(),
            ),
            ApprovalInboxItem(
                approval_id="appr_shift_maintenance_window",
                action="Shift Press 4 maintenance window",
                risk_level="medium",
                status="pending",
                requested_by="maintenance-planner-agent",
                owner_role="maintenance-owner",
                due="Tomorrow 08:30",
                workflow_id="wf_maintenance_reschedule",
                domain="Maintenance",
                summary=(
                    "Move the Press 4 maintenance slot to avoid overlap with a rush production "
                    "order while keeping the service interval inside policy."
                ),
                evidence=[
                    "Planned downtime overlaps a rush order by 90 minutes.",
                    "CMMS service interval remains within tolerance after the proposed shift.",
                    "Production schedule has an alternate window tomorrow morning.",
                ],
                data_accessed=[
                    "CMMS: Press 4 maintenance plan",
                    "MES: rush order schedule",
                    "ERP: production priority",
                    "Axis Audit: maintenance-planner-agent proposal trail",
                ],
                risks=[
                    "Delaying maintenance may increase equipment risk.",
                    "Moving the slot could collide with the next shift handoff.",
                    "Planner approval is required before mutating the schedule.",
                ],
                alternatives=[
                    "Keep the original maintenance slot and delay the rush order.",
                    "Perform a shorter inspection-only maintenance window.",
                    "Escalate to plant operations for joint production review.",
                ],
                estimated_cost="No direct spend; production disruption risk",
                model_policy="local-or-approved-provider",
                required_permission="approvals:maintenance:decide",
                audit_event_preview=ApprovalAuditPreview(
                    event="approval.decision.recorded",
                    actor_role="maintenance-owner",
                    scope="wf_maintenance_reschedule",
                    result="maintenance_signal_ready",
                ),
                decision_options=_approval_decision_options(),
            ),
        ],
    )


def get_manufacturing_ontology() -> ManufacturingOntology:
    return ManufacturingOntology(
        tenant_id="tenant_demo_manufacturing",
        plant_name="Ravenna Works",
        scenario="Plant Operations Cockpit",
        as_of="2026-06-21T16:30:00+02:00",
        source_systems=["ERP", "MES", "QMS", "CMMS", "Supplier Portal", "Axis Audit"],
        permission_notes=[
            "Operations roles can inspect plant, line, workflow and approval nodes.",
            "Quality roles can inspect quality risks, batches and quality approvals.",
            "Agents can only read nodes inside their declared domain and tenant scope.",
            "External model egress remains blocked unless policy explicitly enables it.",
        ],
        nodes=[
            OntologyNode(
                node_id="org_ravenna_operations",
                label="Ravenna Operations",
                node_type=OntologyNodeType.ORGANIZATION,
                domain="Operations",
                status=OverviewStatus.READY,
                source_system="Axis",
                summary="Demo tenant operating unit for the manufacturing reference scenario.",
            ),
            OntologyNode(
                node_id="asset_ravenna_works",
                label="Ravenna Works",
                node_type=OntologyNodeType.ASSET,
                domain="Plant",
                status=OverviewStatus.READY,
                source_system="MES",
                summary="Fictional plant used by the public Platform demo seed.",
            ),
            OntologyNode(
                node_id="asset_line_2_packaging",
                label="Line 2 Packaging",
                node_type=OntologyNodeType.ASSET,
                domain="Production",
                status=OverviewStatus.ACTION_REQUIRED,
                source_system="MES",
                summary="Packaging line exposed to supplier delay risk.",
            ),
            OntologyNode(
                node_id="asset_press_4",
                label="Press 4",
                node_type=OntologyNodeType.ASSET,
                domain="Maintenance",
                status=OverviewStatus.WATCH,
                source_system="CMMS",
                summary="Press with a maintenance window that may need rescheduling.",
            ),
            OntologyNode(
                node_id="asset_batch_q_1842",
                label="Batch Q-1842",
                node_type=OntologyNodeType.ASSET,
                domain="Quality",
                status=OverviewStatus.WATCH,
                source_system="QMS",
                summary="Batch with inspection variance above the watch threshold.",
            ),
            OntologyNode(
                node_id="asset_motors_batch",
                label="Inbound Motors Batch",
                node_type=OntologyNodeType.ASSET,
                domain="Supply",
                status=OverviewStatus.ACTION_REQUIRED,
                source_system="Supplier Portal",
                summary="Inbound component batch delayed against the production window.",
            ),
            OntologyNode(
                node_id="risk_supplier_delay",
                label="Supplier Delay Risk",
                node_type=OntologyNodeType.RISK,
                domain="Supply",
                status=OverviewStatus.ACTION_REQUIRED,
                source_system="Axis",
                summary="Risk signal that may block Line 2 packaging.",
            ),
            OntologyNode(
                node_id="risk_quality_drift",
                label="Quality Drift Risk",
                node_type=OntologyNodeType.RISK,
                domain="Quality",
                status=OverviewStatus.WATCH,
                source_system="Axis",
                summary="Risk signal generated from QMS inspection variance.",
            ),
            OntologyNode(
                node_id="risk_maintenance_window",
                label="Maintenance Window Risk",
                node_type=OntologyNodeType.RISK,
                domain="Maintenance",
                status=OverviewStatus.WATCH,
                source_system="Axis",
                summary="Risk that planned downtime overlaps a rush order.",
            ),
            OntologyNode(
                node_id="wf_supplier_delay_review",
                label="Supplier Delay Review",
                node_type=OntologyNodeType.WORKFLOW,
                domain="Supply",
                status=OverviewStatus.ACTION_REQUIRED,
                source_system="Temporal",
                summary="Workflow waiting for a human decision on expedite or reschedule.",
            ),
            OntologyNode(
                node_id="wf_quality_hold_review",
                label="Quality Hold Review",
                node_type=OntologyNodeType.WORKFLOW,
                domain="Quality",
                status=OverviewStatus.WATCH,
                source_system="Temporal",
                summary="Workflow investigating whether the batch should be held.",
            ),
            OntologyNode(
                node_id="wf_maintenance_reschedule",
                label="Maintenance Reschedule",
                node_type=OntologyNodeType.WORKFLOW,
                domain="Maintenance",
                status=OverviewStatus.WATCH,
                source_system="Temporal",
                summary="Workflow preparing a schedule change for Press 4.",
            ),
            OntologyNode(
                node_id="appr_expedite_supplier_batch",
                label="Expedite Supplier Batch",
                node_type=OntologyNodeType.APPROVAL,
                domain="Supply",
                status=OverviewStatus.ACTION_REQUIRED,
                source_system="Axis",
                summary="High-risk approval gate for supplier expedite action.",
            ),
            OntologyNode(
                node_id="appr_quality_hold_batch",
                label="Place Batch Q-1842 On Hold",
                node_type=OntologyNodeType.APPROVAL,
                domain="Quality",
                status=OverviewStatus.ACTION_REQUIRED,
                source_system="Axis",
                summary="High-risk approval gate for quality hold action.",
            ),
            OntologyNode(
                node_id="agent_supply_risk",
                label="Supply Risk Agent",
                node_type=OntologyNodeType.AGENT,
                domain="Supply",
                status=OverviewStatus.ACTION_REQUIRED,
                source_system="Axis",
                summary="L2 agent that drafts supplier risk actions.",
            ),
            OntologyNode(
                node_id="agent_quality_risk",
                label="Quality Risk Agent",
                node_type=OntologyNodeType.AGENT,
                domain="Quality",
                status=OverviewStatus.WATCH,
                source_system="Axis",
                summary="L2 agent that drafts quality hold recommendations.",
            ),
            OntologyNode(
                node_id="policy_external_egress",
                label="External Model Egress Policy",
                node_type=OntologyNodeType.POLICY,
                domain="Security",
                status=OverviewStatus.READY,
                source_system="Axis",
                summary="Policy that blocks external model egress by default.",
            ),
            OntologyNode(
                node_id="audit_policy_egress_blocked",
                label="Egress Blocked Audit Event",
                node_type=OntologyNodeType.AUDIT_EVENT,
                domain="Security",
                status=OverviewStatus.READY,
                source_system="Axis Audit",
                summary="Evidence that the model router blocked external egress.",
            ),
        ],
        relationships=[
            OntologyRelationship(
                relationship_id="rel_org_owns_plant",
                source_id="org_ravenna_operations",
                target_id="asset_ravenna_works",
                relation_type="owns",
                summary="Operating unit owns the demo plant context.",
                permission_scope="operations:read",
            ),
            OntologyRelationship(
                relationship_id="rel_plant_contains_line",
                source_id="asset_ravenna_works",
                target_id="asset_line_2_packaging",
                relation_type="contains",
                summary="Plant contains Line 2 packaging operations.",
                permission_scope="operations:read",
            ),
            OntologyRelationship(
                relationship_id="rel_plant_contains_press",
                source_id="asset_ravenna_works",
                target_id="asset_press_4",
                relation_type="contains",
                summary="Plant contains Press 4 maintenance context.",
                permission_scope="maintenance:read",
            ),
            OntologyRelationship(
                relationship_id="rel_supplier_batch_impacts_line",
                source_id="asset_motors_batch",
                target_id="asset_line_2_packaging",
                relation_type="impacts",
                summary="Delayed inbound batch may block the packaging line.",
                permission_scope="supply:read",
            ),
            OntologyRelationship(
                relationship_id="rel_quality_batch_impacts_risk",
                source_id="asset_batch_q_1842",
                target_id="risk_quality_drift",
                relation_type="raises",
                summary="Inspection variance raises the quality drift risk.",
                permission_scope="quality:read",
            ),
            OntologyRelationship(
                relationship_id="rel_supplier_risk_blocks_workflow",
                source_id="risk_supplier_delay",
                target_id="wf_supplier_delay_review",
                relation_type="drives",
                summary="Supplier delay risk drives the review workflow.",
                permission_scope="supply:read",
            ),
            OntologyRelationship(
                relationship_id="rel_quality_risk_drives_workflow",
                source_id="risk_quality_drift",
                target_id="wf_quality_hold_review",
                relation_type="drives",
                summary="Quality drift risk drives the quality hold workflow.",
                permission_scope="quality:read",
            ),
            OntologyRelationship(
                relationship_id="rel_maintenance_risk_drives_workflow",
                source_id="risk_maintenance_window",
                target_id="wf_maintenance_reschedule",
                relation_type="drives",
                summary="Maintenance risk drives the reschedule workflow.",
                permission_scope="maintenance:read",
            ),
            OntologyRelationship(
                relationship_id="rel_supplier_workflow_requires_approval",
                source_id="wf_supplier_delay_review",
                target_id="appr_expedite_supplier_batch",
                relation_type="requires_approval",
                summary="Workflow cannot execute expedite action without approval.",
                permission_scope="approvals:read",
            ),
            OntologyRelationship(
                relationship_id="rel_quality_workflow_requires_approval",
                source_id="wf_quality_hold_review",
                target_id="appr_quality_hold_batch",
                relation_type="requires_approval",
                summary="Workflow cannot place the batch on hold without approval.",
                permission_scope="approvals:read",
            ),
            OntologyRelationship(
                relationship_id="rel_supply_agent_proposes_approval",
                source_id="agent_supply_risk",
                target_id="appr_expedite_supplier_batch",
                relation_type="proposes",
                summary="Supply Risk Agent drafts the expedite approval payload.",
                permission_scope="agents:read",
            ),
            OntologyRelationship(
                relationship_id="rel_quality_agent_proposes_approval",
                source_id="agent_quality_risk",
                target_id="appr_quality_hold_batch",
                relation_type="proposes",
                summary="Quality Risk Agent drafts the quality hold payload.",
                permission_scope="agents:read",
            ),
            OntologyRelationship(
                relationship_id="rel_policy_governs_agent",
                source_id="policy_external_egress",
                target_id="agent_quality_risk",
                relation_type="governs",
                summary="Model egress policy governs quality agent model calls.",
                permission_scope="security:read",
            ),
            OntologyRelationship(
                relationship_id="rel_policy_records_audit",
                source_id="policy_external_egress",
                target_id="audit_policy_egress_blocked",
                relation_type="records",
                summary="Policy decision is recorded in the append-only audit trail.",
                permission_scope="audit:read",
            ),
        ],
    )
