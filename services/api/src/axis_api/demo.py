from enum import StrEnum

from pydantic import BaseModel, Field

from axis_api.actions import ActionDefinition, ActionRiskLevel, ApprovalMode


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


class ActionRegistryPolicy(BaseModel):
    approval_role: str = Field(min_length=1)
    autonomy_ceiling: str = Field(pattern=r"^L[0-4]$")
    execution_mode: str = Field(min_length=1)
    runtime_adapter: str = Field(min_length=1)
    audit_event_type: str = Field(min_length=1)
    model_egress_policy: str = Field(min_length=1)
    idempotency_required: bool
    dry_run_supported: bool


class ActionRegistryEntry(BaseModel):
    definition: ActionDefinition
    description: str = Field(min_length=1)
    owner_role: str = Field(min_length=1)
    status: str = Field(min_length=1)
    side_effects: str = Field(min_length=1)
    policy: ActionRegistryPolicy
    connected_agents: list[str] = Field(min_length=1)
    workflow_bindings: list[str] = Field(default_factory=list)
    approval_refs: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(min_length=1)
    validation_checks: list[str] = Field(min_length=1)
    blocked_conditions: list[str] = Field(min_length=1)
    sample_input: dict[str, str] = Field(min_length=1)
    sample_output: dict[str, str] = Field(min_length=1)


class ActionRegistryFilterOptions(BaseModel):
    domains: list[str] = Field(min_length=1)
    risk_levels: list[ActionRiskLevel] = Field(min_length=1)
    approval_modes: list[ApprovalMode] = Field(min_length=1)
    statuses: list[str] = Field(min_length=1)


class ManufacturingActionRegistry(BaseModel):
    tenant_id: str = Field(min_length=1)
    plant_name: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    as_of: str = Field(min_length=1)
    registry_status: OverviewStatus
    schema_version: str = Field(min_length=1)
    metrics: list[OverviewMetric] = Field(min_length=1)
    filter_options: ActionRegistryFilterOptions
    actions: list[ActionRegistryEntry] = Field(min_length=1)
    registry_notes: list[str] = Field(min_length=1)


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


class AgentActionProposal(BaseModel):
    proposal_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    risk_level: str = Field(min_length=1)
    status: str = Field(min_length=1)
    approval_required: bool
    related_workflow_id: str | None = None
    related_approval_id: str | None = None


class AgentPolicyBoundary(BaseModel):
    autonomy_level: str = Field(pattern=r"^L[0-4]$")
    model_policy: str = Field(min_length=1)
    external_egress_allowed: bool
    max_action_level: str = Field(pattern=r"^L[0-4]$")
    required_permissions: list[str] = Field(min_length=1)
    guardrails: list[str] = Field(min_length=1)


class AgentRegistryEntry(BaseModel):
    agent_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    status: str = Field(min_length=1)
    owner_role: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    policy_boundary: AgentPolicyBoundary
    connected_systems: list[str] = Field(min_length=1)
    data_access: list[str] = Field(min_length=1)
    allowed_actions: list[str] = Field(min_length=1)
    blocked_actions: list[str] = Field(min_length=1)
    proposals: list[AgentActionProposal] = Field(default_factory=list)
    active_workflows: list[str] = Field(default_factory=list)
    pending_approvals: list[str] = Field(default_factory=list)
    last_audit_event: str = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)


class AgentRegistryFilterOptions(BaseModel):
    domains: list[str] = Field(min_length=1)
    autonomy_levels: list[str] = Field(min_length=1)
    statuses: list[str] = Field(min_length=1)
    model_policies: list[str] = Field(min_length=1)


class ManufacturingAgentRegistry(BaseModel):
    tenant_id: str = Field(min_length=1)
    plant_name: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    as_of: str = Field(min_length=1)
    registry_status: OverviewStatus
    metrics: list[OverviewMetric] = Field(min_length=1)
    filter_options: AgentRegistryFilterOptions
    agents: list[AgentRegistryEntry] = Field(min_length=1)
    registry_notes: list[str] = Field(min_length=1)


class AuditEvidence(BaseModel):
    event: str = Field(min_length=1)
    actor: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    result: str = Field(min_length=1)


class AuditLedgerEvent(BaseModel):
    audit_event_id: str = Field(min_length=1)
    occurred_at: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    actor_type: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    category: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    result: str = Field(min_length=1)
    severity: OverviewStatus
    source: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    permission_scope: str = Field(min_length=1)
    data_classification: str = Field(min_length=1)
    related_workflow_id: str | None = None
    related_approval_id: str | None = None
    related_agent_id: str | None = None
    evidence_refs: list[str] = Field(min_length=1)
    payload_preview: dict[str, str] = Field(min_length=1)


class AuditFilterOptions(BaseModel):
    tenants: list[str] = Field(min_length=1)
    event_types: list[str] = Field(default_factory=list)
    scopes: list[str] = Field(default_factory=list)
    actors: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)


class ManufacturingAuditExplorer(BaseModel):
    tenant_id: str = Field(min_length=1)
    plant_name: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    as_of: str = Field(min_length=1)
    ledger_status: OverviewStatus
    metrics: list[OverviewMetric] = Field(min_length=1)
    filter_options: AuditFilterOptions
    events: list[AuditLedgerEvent] = Field(default_factory=list)
    retention_notes: list[str] = Field(min_length=1)


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


class OntologyEntityRelationship(BaseModel):
    direction: str = Field(pattern=r"^(inbound|outbound)$")
    relationship: OntologyRelationship
    peer_node: OntologyNode


class ManufacturingOntologyEntityDetail(BaseModel):
    tenant_id: str = Field(min_length=1)
    plant_name: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    as_of: str = Field(min_length=1)
    node: OntologyNode
    connected_relationships: list[OntologyEntityRelationship] = Field(default_factory=list)
    inbound_count: int = Field(ge=0)
    outbound_count: int = Field(ge=0)
    required_permissions: list[str] = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    data_access: list[str] = Field(min_length=1)
    governed_by: list[str] = Field(default_factory=list)
    related_workflows: list[str] = Field(default_factory=list)
    related_approvals: list[str] = Field(default_factory=list)
    related_agents: list[str] = Field(default_factory=list)
    detail_notes: list[str] = Field(min_length=1)


class ModelProviderOption(BaseModel):
    provider_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    provider_type: str = Field(min_length=1)
    hosting_boundary: str = Field(min_length=1)
    status: str = Field(min_length=1)
    egress_mode: str = Field(min_length=1)
    cost_basis: str = Field(min_length=1)
    allowed_policies: list[str] = Field(min_length=1)
    notes: list[str] = Field(min_length=1)


class ModelRouteTelemetry(BaseModel):
    route_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    agent_name: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    provider_id: str = Field(min_length=1)
    provider_name: str = Field(min_length=1)
    model: str = Field(min_length=1)
    model_policy: str = Field(min_length=1)
    prompt_classification: str = Field(min_length=1)
    data_boundary: str = Field(min_length=1)
    external_egress_requested: bool
    external_egress_allowed: bool
    egress_decision: str = Field(min_length=1)
    decision_reason: str = Field(min_length=1)
    route_status: OverviewStatus
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_eur: float = Field(ge=0)
    latency_ms: int = Field(ge=0)
    cost_center: str = Field(min_length=1)
    required_permissions: list[str] = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    audit_event_id: str = Field(min_length=1)
    observability_events: list[str] = Field(min_length=1)


class ModelRoutingFilterOptions(BaseModel):
    domains: list[str] = Field(min_length=1)
    providers: list[str] = Field(min_length=1)
    model_policies: list[str] = Field(min_length=1)
    egress_decisions: list[str] = Field(min_length=1)
    statuses: list[OverviewStatus] = Field(min_length=1)


class ManufacturingModelRouting(BaseModel):
    tenant_id: str = Field(min_length=1)
    plant_name: str = Field(min_length=1)
    scenario: str = Field(min_length=1)
    as_of: str = Field(min_length=1)
    routing_status: OverviewStatus
    metrics: list[OverviewMetric] = Field(min_length=1)
    filter_options: ModelRoutingFilterOptions
    provider_options: list[ModelProviderOption] = Field(min_length=1)
    routes: list[ModelRouteTelemetry] = Field(min_length=1)
    budget_notes: list[str] = Field(min_length=1)
    observability_notes: list[str] = Field(min_length=1)


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
            AgentSummary(
                agent_id="agent_maintenance_planner",
                name="Maintenance Planner Agent",
                autonomy_level="L2",
                status="proposal_ready",
                proposals_pending=1,
                model_policy="local-or-approved-provider",
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


def _action_registry_filter_options(
    actions: list[ActionRegistryEntry],
) -> ActionRegistryFilterOptions:
    return ActionRegistryFilterOptions(
        domains=sorted({action.definition.domain for action in actions}),
        risk_levels=sorted({action.definition.risk_level for action in actions}),
        approval_modes=sorted({action.definition.approval_mode for action in actions}),
        statuses=sorted({action.status for action in actions}),
    )


def get_manufacturing_action_registry() -> ManufacturingActionRegistry:
    actions = [
        ActionRegistryEntry(
            definition=ActionDefinition(
                action_id="generate_daily_plant_brief",
                display_name="Generate daily plant brief",
                domain="Operations",
                risk_level=ActionRiskLevel.LOW,
                approval_mode=ApprovalMode.NOT_REQUIRED,
                input_schema={
                    "type": "object",
                    "required": ["tenant_id", "scope", "evidence_refs"],
                    "properties": {
                        "tenant_id": {"type": "string"},
                        "scope": {"type": "string"},
                        "evidence_refs": {"type": "array", "items": {"type": "string"}},
                    },
                },
                output_schema={
                    "type": "object",
                    "required": ["brief_id", "summary", "cited_evidence"],
                    "properties": {
                        "brief_id": {"type": "string"},
                        "summary": {"type": "string"},
                        "cited_evidence": {"type": "array", "items": {"type": "string"}},
                    },
                },
                required_permissions=["briefs:generate", "audit:read", "workflows:read"],
            ),
            description=(
                "Build a read-only daily plant brief from workflow, approval and audit evidence."
            ),
            owner_role="plant-operations-owner",
            status="available_for_preview",
            side_effects="No external mutation; produces owner-facing summary only.",
            policy=ActionRegistryPolicy(
                approval_role="plant-operations-owner",
                autonomy_ceiling="L1",
                execution_mode="preview_only",
                runtime_adapter="axis-action-preview",
                audit_event_type="action.preview.generated",
                model_egress_policy="local-or-approved-provider",
                idempotency_required=False,
                dry_run_supported=True,
            ),
            connected_agents=["agent_daily_brief"],
            workflow_bindings=["wf_supplier_delay_review", "wf_quality_hold_review"],
            approval_refs=[],
            guardrails=[
                "Must cite existing workflow, approval or audit evidence.",
                "Cannot approve or signal workflow state.",
                "External model egress remains blocked unless tenant policy allows it.",
            ],
            validation_checks=[
                "tenant_id matches request context",
                "evidence_refs exist in accessible audit scope",
                "scope is limited to plant operations cockpit",
            ],
            blocked_conditions=[
                "missing evidence references",
                "cross-tenant evidence requested",
                "unapproved external model route",
            ],
            sample_input={
                "tenant_id": "tenant_demo_manufacturing",
                "scope": "daily_operations",
                "evidence_refs": "wf_supplier_delay_review,audit_20260621_154000_ontology_read",
            },
            sample_output={
                "brief_id": "brief_20260621_demo",
                "summary": "Three governed operational risks require owner review.",
                "cited_evidence": "wf_supplier_delay_review,audit_20260621_154000_ontology_read",
            },
        ),
        ActionRegistryEntry(
            definition=ActionDefinition(
                action_id="request_supplier_expedite",
                display_name="Request supplier expedite",
                domain="Supply",
                risk_level=ActionRiskLevel.HIGH,
                approval_mode=ApprovalMode.REQUIRED,
                input_schema={
                    "type": "object",
                    "required": [
                        "supplier_batch_id",
                        "target_arrival",
                        "reason",
                        "cost_ceiling_eur",
                    ],
                    "properties": {
                        "supplier_batch_id": {"type": "string"},
                        "target_arrival": {"type": "string"},
                        "reason": {"type": "string"},
                        "cost_ceiling_eur": {"type": "string"},
                    },
                },
                output_schema={
                    "type": "object",
                    "required": ["request_id", "approval_id", "audit_event_id"],
                    "properties": {
                        "request_id": {"type": "string"},
                        "approval_id": {"type": "string"},
                        "audit_event_id": {"type": "string"},
                    },
                },
                required_permissions=["supply:read", "approvals:supply:request"],
            ),
            description="Prepare an expedite request for delayed inbound material.",
            owner_role="plant-operations-owner",
            status="approval_required",
            side_effects=(
                "Would request supplier action after owner approval; demo is dry-run only."
            ),
            policy=ActionRegistryPolicy(
                approval_role="plant-operations-owner",
                autonomy_ceiling="L2",
                execution_mode="approval_gated_dry_run",
                runtime_adapter="axis-temporal-adapter",
                audit_event_type="action.proposal.created",
                model_egress_policy="no-external-egress",
                idempotency_required=True,
                dry_run_supported=True,
            ),
            connected_agents=["agent_supply_risk"],
            workflow_bindings=["wf_supplier_delay_review"],
            approval_refs=["appr_expedite_supplier_batch"],
            guardrails=[
                "High-risk supply action must enter approval inbox before execution.",
                "Agent can draft payload but cannot book priority freight.",
                "Cost ceiling and target arrival must be visible to the owner.",
            ],
            validation_checks=[
                "supplier_batch_id maps to accessible supplier risk evidence",
                "cost_ceiling_eur is present",
                "approval role matches plant operations owner",
                "idempotency key exists before runtime signal",
            ],
            blocked_conditions=[
                "missing approval",
                "external freight booking requested directly",
                "supplier batch outside tenant scope",
            ],
            sample_input={
                "supplier_batch_id": "asset_motors_batch",
                "target_arrival": "2026-06-22T08:00:00+02:00",
                "reason": "Line 2 packaging risk",
                "cost_ceiling_eur": "1200",
            },
            sample_output={
                "request_id": "act_supplier_expedite_preview",
                "approval_id": "appr_expedite_supplier_batch",
                "audit_event_id": "audit_20260621_141200_agent_proposal",
            },
        ),
        ActionRegistryEntry(
            definition=ActionDefinition(
                action_id="place_quality_hold",
                display_name="Place quality hold",
                domain="Quality",
                risk_level=ActionRiskLevel.HIGH,
                approval_mode=ApprovalMode.REQUIRED,
                input_schema={
                    "type": "object",
                    "required": ["batch_id", "hold_reason", "evidence_refs"],
                    "properties": {
                        "batch_id": {"type": "string"},
                        "hold_reason": {"type": "string"},
                        "evidence_refs": {"type": "array", "items": {"type": "string"}},
                    },
                },
                output_schema={
                    "type": "object",
                    "required": ["hold_request_id", "approval_id", "audit_event_id"],
                    "properties": {
                        "hold_request_id": {"type": "string"},
                        "approval_id": {"type": "string"},
                        "audit_event_id": {"type": "string"},
                    },
                },
                required_permissions=["quality:read", "approvals:quality:request"],
            ),
            description="Draft a quality hold proposal for owner review.",
            owner_role="quality-owner",
            status="review_required",
            side_effects="Would hold a production batch only after quality owner approval.",
            policy=ActionRegistryPolicy(
                approval_role="quality-owner",
                autonomy_ceiling="L2",
                execution_mode="approval_gated_dry_run",
                runtime_adapter="axis-temporal-adapter",
                audit_event_type="action.proposal.created",
                model_egress_policy="no-external-egress",
                idempotency_required=True,
                dry_run_supported=True,
            ),
            connected_agents=["agent_quality_risk"],
            workflow_bindings=["wf_quality_hold_review"],
            approval_refs=["appr_quality_hold_batch"],
            guardrails=[
                "Quality evidence must remain inside tenant systems.",
                "Agent cannot release or hold a batch without owner decision.",
                "Proposal must include batch genealogy evidence.",
            ],
            validation_checks=[
                "batch_id maps to accessible quality risk evidence",
                "evidence_refs include audit event and risk node",
                "approval role matches quality owner",
            ],
            blocked_conditions=[
                "missing batch genealogy",
                "owner approval absent",
                "external model route requested for quality data",
            ],
            sample_input={
                "batch_id": "asset_batch_q_1842",
                "hold_reason": "Inspection variance crossed watch threshold",
                "evidence_refs": "risk_quality_drift,audit_20260621_134400_quality_proposal",
            },
            sample_output={
                "hold_request_id": "act_quality_hold_preview",
                "approval_id": "appr_quality_hold_batch",
                "audit_event_id": "audit_20260621_134400_quality_proposal",
            },
        ),
        ActionRegistryEntry(
            definition=ActionDefinition(
                action_id="shift_maintenance_window",
                display_name="Shift maintenance window",
                domain="Maintenance",
                risk_level=ActionRiskLevel.MEDIUM,
                approval_mode=ApprovalMode.CONDITIONAL,
                input_schema={
                    "type": "object",
                    "required": [
                        "asset_id",
                        "current_window",
                        "proposed_window",
                        "policy_check_id",
                    ],
                    "properties": {
                        "asset_id": {"type": "string"},
                        "current_window": {"type": "string"},
                        "proposed_window": {"type": "string"},
                        "policy_check_id": {"type": "string"},
                    },
                },
                output_schema={
                    "type": "object",
                    "required": ["proposal_id", "approval_id", "audit_event_id"],
                    "properties": {
                        "proposal_id": {"type": "string"},
                        "approval_id": {"type": "string"},
                        "audit_event_id": {"type": "string"},
                    },
                },
                required_permissions=[
                    "maintenance:read",
                    "approvals:maintenance:request",
                ],
            ),
            description="Draft a service-window-safe maintenance reschedule proposal.",
            owner_role="maintenance-owner",
            status="conditional_approval_required",
            side_effects="Would update CMMS schedule only after policy and owner gates.",
            policy=ActionRegistryPolicy(
                approval_role="maintenance-owner",
                autonomy_ceiling="L2",
                execution_mode="conditional_approval_dry_run",
                runtime_adapter="axis-temporal-adapter",
                audit_event_type="action.proposal.created",
                model_egress_policy="local-or-approved-provider",
                idempotency_required=True,
                dry_run_supported=True,
            ),
            connected_agents=["agent_maintenance_planner"],
            workflow_bindings=["wf_maintenance_reschedule"],
            approval_refs=["appr_shift_maintenance_window"],
            guardrails=[
                "Service-window policy must pass before owner review.",
                "Agent cannot mutate CMMS schedule directly.",
                "Schedule shift must preserve maintenance interval tolerance.",
            ],
            validation_checks=[
                "asset_id maps to accessible maintenance risk evidence",
                "policy_check_id is present",
                "proposed_window stays inside allowed service tolerance",
            ],
            blocked_conditions=[
                "service-window policy failed",
                "maintenance owner approval absent",
                "CMMS mutation requested before workflow signal",
            ],
            sample_input={
                "asset_id": "asset_press_4",
                "current_window": "2026-06-22T09:00:00+02:00",
                "proposed_window": "2026-06-22T13:00:00+02:00",
                "policy_check_id": "service-window-policy",
            },
            sample_output={
                "proposal_id": "act_maintenance_shift_preview",
                "approval_id": "appr_shift_maintenance_window",
                "audit_event_id": "audit_20260621_151800_maintenance_proposal",
            },
        ),
    ]

    return ManufacturingActionRegistry(
        tenant_id="tenant_demo_manufacturing",
        plant_name="Ravenna Works",
        scenario="Plant Operations Cockpit",
        as_of="2026-06-21T16:30:00+02:00",
        registry_status=OverviewStatus.WATCH,
        schema_version="2026-06-21",
        metrics=[
            OverviewMetric(
                label="Registered Actions",
                value="4",
                detail="Typed action definitions for the manufacturing demo tenant",
                status=OverviewStatus.READY,
            ),
            OverviewMetric(
                label="Approval Required",
                value="3",
                detail="High and conditional actions are routed to owner review",
                status=OverviewStatus.ACTION_REQUIRED,
            ),
            OverviewMetric(
                label="Runtime Execution",
                value="0 live",
                detail="Public demo remains preview and dry-run only",
                status=OverviewStatus.WATCH,
            ),
            OverviewMetric(
                label="External Egress",
                value="0 allowed",
                detail="Action payloads stay inside the tenant boundary",
                status=OverviewStatus.READY,
            ),
        ],
        filter_options=_action_registry_filter_options(actions),
        actions=actions,
        registry_notes=[
            "This public action registry seed is synthetic and safe for dry-run requests.",
            "Actions are typed and policy-gated, but live runtime execution is not enabled.",
            "High-risk actions require owner approval before any production signal.",
            "Action run requests can be persisted with idempotency and append-only audit.",
        ],
    )


def _agent_registry_filter_options(
    agents: list[AgentRegistryEntry],
) -> AgentRegistryFilterOptions:
    return AgentRegistryFilterOptions(
        domains=sorted({agent.domain for agent in agents}),
        autonomy_levels=sorted({agent.policy_boundary.autonomy_level for agent in agents}),
        statuses=sorted({agent.status for agent in agents}),
        model_policies=sorted({agent.policy_boundary.model_policy for agent in agents}),
    )


def get_manufacturing_agent_registry() -> ManufacturingAgentRegistry:
    agents = [
        AgentRegistryEntry(
            agent_id="agent_daily_brief",
            name="Daily Brief Agent",
            domain="Operations",
            status="recommending",
            owner_role="plant-operations-owner",
            purpose="Summarize plant risks, pending workflow gates and audit evidence for owners.",
            policy_boundary=AgentPolicyBoundary(
                autonomy_level="L1",
                model_policy="local-or-approved-provider",
                external_egress_allowed=False,
                max_action_level="L1",
                required_permissions=["agents:read", "audit:read", "workflows:read"],
                guardrails=[
                    "Summaries only; no action payload execution.",
                    "No external model egress unless tenant policy explicitly allows it.",
                    "Must cite workflow, approval or audit evidence for operational claims.",
                ],
            ),
            connected_systems=["Axis Audit", "Temporal", "TypeDB Boundary"],
            data_access=[
                "workflow summaries",
                "approval queue summaries",
                "audit event summaries",
                "ontology relationship summaries",
            ],
            allowed_actions=[
                "Generate daily plant brief",
                "Rank open governance gates",
                "Prepare owner-facing evidence summary",
            ],
            blocked_actions=[
                "Execute workflow signal",
                "Approve action payload",
                "Read unrestricted source-system records",
            ],
            proposals=[
                AgentActionProposal(
                    proposal_id="proposal_daily_brief_20260621",
                    action="Generate daily plant brief",
                    risk_level="low",
                    status="ready_for_owner_review",
                    approval_required=False,
                    related_workflow_id="wf_supplier_delay_review",
                )
            ],
            active_workflows=["wf_supplier_delay_review", "wf_quality_hold_review"],
            pending_approvals=[],
            last_audit_event="audit_20260621_154000_ontology_read",
            evidence_refs=["wf_supplier_delay_review", "audit_20260621_154000_ontology_read"],
        ),
        AgentRegistryEntry(
            agent_id="agent_supply_risk",
            name="Supply Risk Agent",
            domain="Supply",
            status="waiting_for_approval",
            owner_role="plant-operations-owner",
            purpose="Detect supplier delay risk and draft governed supply actions.",
            policy_boundary=AgentPolicyBoundary(
                autonomy_level="L2",
                model_policy="no-external-egress",
                external_egress_allowed=False,
                max_action_level="L2",
                required_permissions=["agents:read", "supply:read", "approvals:supply:request"],
                guardrails=[
                    "Can draft action payloads, but cannot execute supplier changes.",
                    "High-risk supply actions require plant operations owner approval.",
                    "Must keep supplier and production context inside tenant boundary.",
                ],
            ),
            connected_systems=["Supplier Portal", "MES", "ERP", "Axis Audit"],
            data_access=[
                "inbound shipment status",
                "Line 2 packaging schedule",
                "rush order priority flag",
                "supply approval history",
            ],
            allowed_actions=[
                "Draft expedite supplier batch action",
                "Prepare supplier delay evidence",
                "Request supply owner approval",
            ],
            blocked_actions=[
                "Book priority freight",
                "Mutate supplier order",
                "Signal workflow completion",
            ],
            proposals=[
                AgentActionProposal(
                    proposal_id="proposal_expedite_supplier_batch",
                    action="Expedite supplier batch",
                    risk_level="high",
                    status="approval_required",
                    approval_required=True,
                    related_workflow_id="wf_supplier_delay_review",
                    related_approval_id="appr_expedite_supplier_batch",
                )
            ],
            active_workflows=["wf_supplier_delay_review"],
            pending_approvals=["appr_expedite_supplier_batch"],
            last_audit_event="audit_20260621_141200_agent_proposal",
            evidence_refs=[
                "risk_supplier_delay",
                "asset_motors_batch",
                "audit_20260621_141200_agent_proposal",
            ],
        ),
        AgentRegistryEntry(
            agent_id="agent_quality_risk",
            name="Quality Risk Agent",
            domain="Quality",
            status="drafting_actions",
            owner_role="quality-owner",
            purpose="Review quality drift evidence and draft quality hold recommendations.",
            policy_boundary=AgentPolicyBoundary(
                autonomy_level="L2",
                model_policy="no-external-egress",
                external_egress_allowed=False,
                max_action_level="L2",
                required_permissions=["agents:read", "quality:read", "approvals:quality:request"],
                guardrails=[
                    "Can draft quality hold recommendations, but cannot release or hold batches.",
                    "Quality evidence must stay inside approved tenant systems.",
                    "External model egress is blocked by default for quality evidence.",
                ],
            ),
            connected_systems=["QMS", "MES", "ERP", "Axis Audit"],
            data_access=[
                "sample inspection variance",
                "batch genealogy",
                "customer order priority",
                "quality proposal audit trail",
            ],
            allowed_actions=[
                "Draft quality hold proposal",
                "Prepare evidence for quality owner",
                "Request quality owner review",
            ],
            blocked_actions=[
                "Release batch",
                "Place batch on hold without approval",
                "Use external model provider for quality data",
            ],
            proposals=[
                AgentActionProposal(
                    proposal_id="proposal_quality_hold_batch_q_1842",
                    action="Place Batch Q-1842 on quality hold",
                    risk_level="high",
                    status="review_required",
                    approval_required=True,
                    related_workflow_id="wf_quality_hold_review",
                    related_approval_id="appr_quality_hold_batch",
                )
            ],
            active_workflows=["wf_quality_hold_review"],
            pending_approvals=["appr_quality_hold_batch"],
            last_audit_event="audit_20260621_134400_quality_proposal",
            evidence_refs=[
                "risk_quality_drift",
                "asset_batch_q_1842",
                "audit_20260621_133900_egress_blocked",
            ],
        ),
        AgentRegistryEntry(
            agent_id="agent_maintenance_planner",
            name="Maintenance Planner Agent",
            domain="Maintenance",
            status="proposal_ready",
            owner_role="maintenance-owner",
            purpose="Draft maintenance schedule changes while preserving service-window policy.",
            policy_boundary=AgentPolicyBoundary(
                autonomy_level="L2",
                model_policy="local-or-approved-provider",
                external_egress_allowed=False,
                max_action_level="L2",
                required_permissions=[
                    "agents:read",
                    "maintenance:read",
                    "approvals:maintenance:request",
                ],
                guardrails=[
                    "Can draft schedule shifts, but cannot mutate CMMS state.",
                    "Service-window policy must be checked before owner review.",
                    "Schedule changes require maintenance owner approval.",
                ],
            ),
            connected_systems=["CMMS", "MES", "ERP", "Axis Audit"],
            data_access=[
                "Press 4 maintenance window",
                "rush order schedule",
                "service interval tolerance",
                "maintenance proposal audit trail",
            ],
            allowed_actions=[
                "Draft maintenance reschedule proposal",
                "Prepare service-window evidence",
                "Request maintenance owner review",
            ],
            blocked_actions=[
                "Mutate CMMS schedule",
                "Delay maintenance beyond policy",
                "Close workflow without owner signal",
            ],
            proposals=[
                AgentActionProposal(
                    proposal_id="proposal_shift_press_4_maintenance",
                    action="Shift Press 4 maintenance window",
                    risk_level="medium",
                    status="proposal_ready",
                    approval_required=True,
                    related_workflow_id="wf_maintenance_reschedule",
                    related_approval_id="appr_shift_maintenance_window",
                )
            ],
            active_workflows=["wf_maintenance_reschedule"],
            pending_approvals=["appr_shift_maintenance_window"],
            last_audit_event="audit_20260621_151800_maintenance_proposal",
            evidence_refs=[
                "risk_maintenance_window",
                "asset_press_4",
                "audit_20260621_151800_maintenance_proposal",
            ],
        ),
    ]

    return ManufacturingAgentRegistry(
        tenant_id="tenant_demo_manufacturing",
        plant_name="Ravenna Works",
        scenario="Plant Operations Cockpit",
        as_of="2026-06-21T16:30:00+02:00",
        registry_status=OverviewStatus.WATCH,
        metrics=[
            OverviewMetric(
                label="Registered Agents",
                value=str(len(agents)),
                detail="Governed L1-L2 agents in the manufacturing demo tenant",
                status=OverviewStatus.READY,
            ),
            OverviewMetric(
                label="Pending Proposals",
                value="4",
                detail="One brief proposal and three action proposals under owner review",
                status=OverviewStatus.WATCH,
            ),
            OverviewMetric(
                label="Approval Gates",
                value="3",
                detail="High and medium risk agent proposals require human owners",
                status=OverviewStatus.ACTION_REQUIRED,
            ),
            OverviewMetric(
                label="External Egress",
                value="0 allowed",
                detail="All demo agents remain inside the tenant boundary",
                status=OverviewStatus.READY,
            ),
        ],
        filter_options=_agent_registry_filter_options(agents),
        agents=agents,
        registry_notes=[
            "This public agent registry seed is read-only and synthetic.",
            "Agents can draft or recommend inside their autonomy level, but cannot mutate systems.",
            "External model egress is disabled unless tenant policy explicitly enables it.",
            "A production action registry, runtime execution and persisted agent state "
            "remain Platform work.",
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
                "Approval decisions can signal the runtime; durable replay and persisted "
                "history views remain Platform work."
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


def _audit_filter_options(events: list[AuditLedgerEvent]) -> AuditFilterOptions:
    return AuditFilterOptions(
        tenants=sorted({event.tenant_id for event in events}),
        event_types=sorted({event.event_type for event in events}),
        scopes=sorted({event.scope for event in events}),
        actors=sorted({event.actor_id for event in events}),
        categories=sorted({event.category for event in events}),
    )


def get_manufacturing_audit_explorer() -> ManufacturingAuditExplorer:
    events = [
        AuditLedgerEvent(
            audit_event_id="audit_20260621_140500_workflow_started",
            occurred_at="2026-06-21T14:05:00+02:00",
            tenant_id="tenant_demo_manufacturing",
            actor_id="workflow-runtime",
            actor_type="service",
            event_type="workflow.started",
            category="workflow",
            domain="Supply",
            scope="wf_supplier_delay_review",
            result="started",
            severity=OverviewStatus.READY,
            source="Temporal",
            summary="Supplier delay workflow created from the supply risk signal.",
            permission_scope="workflows:read",
            data_classification="public-demo",
            related_workflow_id="wf_supplier_delay_review",
            evidence_refs=["risk_supplier_delay", "asset_motors_batch"],
            payload_preview={
                "workflow_id": "wf_supplier_delay_review",
                "runtime": "Temporal OSS",
                "adapter": "axis-temporal-adapter",
            },
        ),
        AuditLedgerEvent(
            audit_event_id="audit_20260621_141200_agent_proposal",
            occurred_at="2026-06-21T14:12:00+02:00",
            tenant_id="tenant_demo_manufacturing",
            actor_id="supply-risk-agent",
            actor_type="agent",
            event_type="agent.proposal.created",
            category="agent",
            domain="Supply",
            scope="wf_supplier_delay_review",
            result="approval_required",
            severity=OverviewStatus.ACTION_REQUIRED,
            source="Axis",
            summary="L2 agent drafted an expedite supplier batch action payload.",
            permission_scope="agents:read",
            data_classification="public-demo",
            related_workflow_id="wf_supplier_delay_review",
            related_approval_id="appr_expedite_supplier_batch",
            related_agent_id="agent_supply_risk",
            evidence_refs=["appr_expedite_supplier_batch", "asset_line_2_packaging"],
            payload_preview={
                "action": "Expedite supplier batch",
                "autonomy_level": "L2",
                "risk_level": "high",
            },
        ),
        AuditLedgerEvent(
            audit_event_id="audit_20260621_141800_signal_awaiting",
            occurred_at="2026-06-21T14:18:00+02:00",
            tenant_id="tenant_demo_manufacturing",
            actor_id="axis-temporal-adapter",
            actor_type="service",
            event_type="workflow.signal.awaiting",
            category="workflow",
            domain="Supply",
            scope="wf_supplier_delay_review",
            result="waiting_for_approval",
            severity=OverviewStatus.ACTION_REQUIRED,
            source="Axis Workflow Runtime",
            summary="Workflow paused at the human approval gate.",
            permission_scope="workflows:read",
            data_classification="public-demo",
            related_workflow_id="wf_supplier_delay_review",
            related_approval_id="appr_expedite_supplier_batch",
            evidence_refs=["appr_expedite_supplier_batch"],
            payload_preview={
                "signal": "approval.decision",
                "required_role": "plant-operations-owner",
                "status": "waiting",
            },
        ),
        AuditLedgerEvent(
            audit_event_id="audit_20260621_133900_egress_blocked",
            occurred_at="2026-06-21T13:39:00+02:00",
            tenant_id="tenant_demo_manufacturing",
            actor_id="model-router",
            actor_type="service",
            event_type="policy.egress.blocked",
            category="policy",
            domain="Security",
            scope="agent_quality_risk",
            result="blocked_by_default",
            severity=OverviewStatus.READY,
            source="Axis Policy",
            summary="External model egress was blocked for quality evidence.",
            permission_scope="security:read",
            data_classification="public-demo",
            related_agent_id="agent_quality_risk",
            evidence_refs=["policy_external_egress", "wf_quality_hold_review"],
            payload_preview={
                "model_policy": "no-external-egress",
                "provider": "external",
                "decision": "blocked",
            },
        ),
        AuditLedgerEvent(
            audit_event_id="audit_20260621_134400_quality_proposal",
            occurred_at="2026-06-21T13:44:00+02:00",
            tenant_id="tenant_demo_manufacturing",
            actor_id="quality-risk-agent",
            actor_type="agent",
            event_type="agent.proposal.created",
            category="agent",
            domain="Quality",
            scope="wf_quality_hold_review",
            result="review_required",
            severity=OverviewStatus.WATCH,
            source="Axis",
            summary="L2 agent drafted a quality hold proposal for Batch Q-1842.",
            permission_scope="agents:read",
            data_classification="public-demo",
            related_workflow_id="wf_quality_hold_review",
            related_approval_id="appr_quality_hold_batch",
            related_agent_id="agent_quality_risk",
            evidence_refs=["risk_quality_drift", "asset_batch_q_1842"],
            payload_preview={
                "action": "Place Batch Q-1842 on quality hold",
                "autonomy_level": "L2",
                "risk_level": "high",
            },
        ),
        AuditLedgerEvent(
            audit_event_id="audit_20260621_151800_maintenance_proposal",
            occurred_at="2026-06-21T15:18:00+02:00",
            tenant_id="tenant_demo_manufacturing",
            actor_id="maintenance-planner-agent",
            actor_type="agent",
            event_type="agent.proposal.created",
            category="agent",
            domain="Maintenance",
            scope="wf_maintenance_reschedule",
            result="proposal_ready",
            severity=OverviewStatus.WATCH,
            source="Axis",
            summary="L2 agent drafted the Press 4 maintenance schedule shift proposal.",
            permission_scope="agents:read",
            data_classification="public-demo",
            related_workflow_id="wf_maintenance_reschedule",
            related_approval_id="appr_shift_maintenance_window",
            evidence_refs=["risk_maintenance_window", "asset_press_4"],
            payload_preview={
                "action": "Shift Press 4 maintenance window",
                "autonomy_level": "L2",
                "risk_level": "medium",
            },
        ),
        AuditLedgerEvent(
            audit_event_id="audit_20260621_152500_maintenance_signal",
            occurred_at="2026-06-21T15:25:00+02:00",
            tenant_id="tenant_demo_manufacturing",
            actor_id="axis-temporal-adapter",
            actor_type="service",
            event_type="workflow.signal.awaiting",
            category="workflow",
            domain="Maintenance",
            scope="wf_maintenance_reschedule",
            result="waiting_for_owner_review",
            severity=OverviewStatus.WATCH,
            source="Axis Workflow Runtime",
            summary="Workflow paused before mutating the maintenance schedule.",
            permission_scope="workflows:read",
            data_classification="public-demo",
            related_workflow_id="wf_maintenance_reschedule",
            related_approval_id="appr_shift_maintenance_window",
            evidence_refs=["appr_shift_maintenance_window"],
            payload_preview={
                "signal": "maintenance.owner.review",
                "required_role": "maintenance-owner",
                "status": "waiting",
            },
        ),
        AuditLedgerEvent(
            audit_event_id="audit_20260621_153200_permission_check",
            occurred_at="2026-06-21T15:32:00+02:00",
            tenant_id="tenant_demo_manufacturing",
            actor_id="axis-permission-engine",
            actor_type="service",
            event_type="permission.check.evaluated",
            category="permission",
            domain="Supply",
            scope="approvals:supply:decide",
            result="allowed_for_owner_role",
            severity=OverviewStatus.READY,
            source="Axis Permissions",
            summary="Supply approval decision permission evaluated for the owner role.",
            permission_scope="permissions:read",
            data_classification="public-demo",
            related_approval_id="appr_expedite_supplier_batch",
            evidence_refs=["plant-operations-owner", "appr_expedite_supplier_batch"],
            payload_preview={
                "role": "plant-operations-owner",
                "permission": "approvals:supply:decide",
                "decision": "allowed",
            },
        ),
        AuditLedgerEvent(
            audit_event_id="audit_20260621_154000_ontology_read",
            occurred_at="2026-06-21T15:40:00+02:00",
            tenant_id="tenant_demo_manufacturing",
            actor_id="plant-operations-owner-role",
            actor_type="role",
            event_type="ontology.relationship.read",
            category="ontology",
            domain="Operations",
            scope="asset_line_2_packaging",
            result="allowed",
            severity=OverviewStatus.READY,
            source="TypeDB Boundary",
            summary="Operations owner inspected supplier delay relationships for Line 2.",
            permission_scope="operations:read",
            data_classification="public-demo",
            related_workflow_id="wf_supplier_delay_review",
            evidence_refs=["asset_line_2_packaging", "risk_supplier_delay"],
            payload_preview={
                "node": "asset_line_2_packaging",
                "relation": "impacts",
                "decision": "allowed",
            },
        ),
    ]

    return ManufacturingAuditExplorer(
        tenant_id="tenant_demo_manufacturing",
        plant_name="Ravenna Works",
        scenario="Plant Operations Cockpit",
        as_of="2026-06-21T16:30:00+02:00",
        ledger_status=OverviewStatus.WATCH,
        metrics=[
            OverviewMetric(
                label="Audit Events",
                value=str(len(events)),
                detail="Synthetic public-safe events for the manufacturing demo",
                status=OverviewStatus.READY,
            ),
            OverviewMetric(
                label="Action Gates",
                value="3",
                detail="Approval and workflow signal events are visible",
                status=OverviewStatus.ACTION_REQUIRED,
            ),
            OverviewMetric(
                label="Policy Blocks",
                value="1",
                detail="External model egress block is recorded",
                status=OverviewStatus.READY,
            ),
            OverviewMetric(
                label="Replay",
                value="Pending",
                detail="Events are shaped for replay, but replay is not implemented yet",
                status=OverviewStatus.WATCH,
            ),
        ],
        filter_options=_audit_filter_options(events),
        events=events,
        retention_notes=[
            "This public audit explorer seed is read-only and synthetic.",
            "Payload previews are redacted and contain no customer data or credentials.",
            "Production audit events must be append-only and tenant-scoped.",
            "Export, retention policy enforcement and replay remain Platform work.",
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


def _ontology_detail_overrides() -> dict[str, dict[str, list[str]]]:
    return {
        "asset_line_2_packaging": {
            "evidence_refs": [
                "risk_supplier_delay",
                "wf_supplier_delay_review",
                "audit_20260621_154000_ontology_read",
            ],
            "data_access": [
                "MES line status summary",
                "supplier delay risk relationship",
                "approval gate summary",
            ],
            "detail_notes": [
                "This detail page is read-only and derived from the public ontology seed.",
                "Operations can inspect the line context, but cannot execute workflow "
                "signals here.",
                "The supplier delay risk is visible because the relationship scope allows it.",
            ],
        },
        "risk_supplier_delay": {
            "evidence_refs": [
                "asset_motors_batch",
                "asset_line_2_packaging",
                "wf_supplier_delay_review",
            ],
            "data_access": [
                "supplier risk summary",
                "impacted production line",
                "workflow blocker summary",
            ],
            "detail_notes": [
                "Risk detail is derived from TypeDB-shaped relationships in the demo seed.",
                "The risk can drive action proposals, but does not execute actions directly.",
            ],
        },
        "wf_supplier_delay_review": {
            "evidence_refs": [
                "risk_supplier_delay",
                "appr_expedite_supplier_batch",
                "audit_20260621_141800_signal_awaiting",
            ],
            "data_access": [
                "workflow state summary",
                "pending signal metadata",
                "approval requirement relationship",
            ],
            "detail_notes": [
                "Workflow detail is inspectable without exposing runtime mutation controls.",
                "Approval decisions signal this workflow through the Axis runtime adapter.",
            ],
        },
        "appr_expedite_supplier_batch": {
            "evidence_refs": [
                "wf_supplier_delay_review",
                "agent_supply_risk",
                "audit_20260621_141200_agent_proposal",
            ],
            "data_access": [
                "approval summary",
                "requesting agent relationship",
                "workflow requirement relationship",
            ],
            "detail_notes": [
                "Approval detail links the proposed action to the owner review gate.",
                "Decisions are preview-only until persisted approval state is implemented.",
            ],
        },
        "agent_supply_risk": {
            "evidence_refs": [
                "appr_expedite_supplier_batch",
                "risk_supplier_delay",
                "audit_20260621_141200_agent_proposal",
            ],
            "data_access": [
                "agent relationship summary",
                "proposal approval reference",
                "supply risk evidence",
            ],
            "detail_notes": [
                "Agent detail is scoped to declared tenant and domain relationships.",
                "Agent runtime state remains outside this read-only ontology detail slice.",
            ],
        },
        "policy_external_egress": {
            "evidence_refs": [
                "agent_quality_risk",
                "audit_policy_egress_blocked",
                "audit_20260621_133900_egress_blocked",
            ],
            "data_access": [
                "policy summary",
                "governed agent relationship",
                "audit evidence relationship",
            ],
            "detail_notes": [
                "Policy detail shows governance relationships, not policy editing controls.",
                "External model egress remains blocked unless tenant policy explicitly allows it.",
            ],
        },
    }


def _default_ontology_detail_lists(node: OntologyNode) -> dict[str, list[str]]:
    return {
        "evidence_refs": [node.node_id],
        "data_access": [
            f"{node.source_system} public-demo summary",
            f"{node.domain} relationship context",
            f"{node.node_type.value} metadata",
        ],
        "detail_notes": [
            "This entity detail is read-only and synthetic.",
            "Production entity details will require tenant-scoped graph query permissions.",
        ],
    }


def get_manufacturing_ontology_entity_detail(
    node_id: str,
) -> ManufacturingOntologyEntityDetail | None:
    ontology = get_manufacturing_ontology()
    node_by_id = {node.node_id: node for node in ontology.nodes}
    node = node_by_id.get(node_id)

    if node is None:
        return None

    connected_relationships: list[OntologyEntityRelationship] = []
    inbound_count = 0
    outbound_count = 0

    for relationship in ontology.relationships:
        if relationship.source_id == node_id:
            peer_node = node_by_id[relationship.target_id]
            connected_relationships.append(
                OntologyEntityRelationship(
                    direction="outbound",
                    relationship=relationship,
                    peer_node=peer_node,
                )
            )
            outbound_count += 1
        elif relationship.target_id == node_id:
            peer_node = node_by_id[relationship.source_id]
            connected_relationships.append(
                OntologyEntityRelationship(
                    direction="inbound",
                    relationship=relationship,
                    peer_node=peer_node,
                )
            )
            inbound_count += 1

    permissions = sorted(
        {item.relationship.permission_scope for item in connected_relationships}
        or {f"{node.domain.lower()}:read"}
    )
    detail_lists = _default_ontology_detail_lists(node) | _ontology_detail_overrides().get(
        node_id,
        {},
    )

    return ManufacturingOntologyEntityDetail(
        tenant_id=ontology.tenant_id,
        plant_name=ontology.plant_name,
        scenario=ontology.scenario,
        as_of=ontology.as_of,
        node=node,
        connected_relationships=connected_relationships,
        inbound_count=inbound_count,
        outbound_count=outbound_count,
        required_permissions=permissions,
        evidence_refs=detail_lists["evidence_refs"],
        data_access=detail_lists["data_access"],
        governed_by=sorted(
            {
                item.peer_node.node_id
                for item in connected_relationships
                if item.relationship.relation_type == "governs"
            }
        ),
        related_workflows=sorted(
            {
                item.peer_node.node_id
                for item in connected_relationships
                if item.peer_node.node_type == OntologyNodeType.WORKFLOW
            }
            | ({node.node_id} if node.node_type == OntologyNodeType.WORKFLOW else set())
        ),
        related_approvals=sorted(
            {
                item.peer_node.node_id
                for item in connected_relationships
                if item.peer_node.node_type == OntologyNodeType.APPROVAL
            }
            | ({node.node_id} if node.node_type == OntologyNodeType.APPROVAL else set())
        ),
        related_agents=sorted(
            {
                item.peer_node.node_id
                for item in connected_relationships
                if item.peer_node.node_type == OntologyNodeType.AGENT
            }
            | ({node.node_id} if node.node_type == OntologyNodeType.AGENT else set())
        ),
        detail_notes=detail_lists["detail_notes"],
    )


def _model_routing_filter_options(
    routes: list[ModelRouteTelemetry],
) -> ModelRoutingFilterOptions:
    return ModelRoutingFilterOptions(
        domains=sorted({route.domain for route in routes}),
        providers=sorted({route.provider_id for route in routes}),
        model_policies=sorted({route.model_policy for route in routes}),
        egress_decisions=sorted({route.egress_decision for route in routes}),
        statuses=sorted({route.route_status for route in routes}),
    )


def get_manufacturing_model_routing() -> ManufacturingModelRouting:
    providers = [
        ModelProviderOption(
            provider_id="local-vllm",
            display_name="Local vLLM Gateway",
            provider_type="self-hosted",
            hosting_boundary="tenant-private-runtime",
            status="available",
            egress_mode="no-external-egress",
            cost_basis="infrastructure-metered",
            allowed_policies=["local-or-approved-provider", "no-external-egress"],
            notes=[
                "Default route for sensitive operational prompts.",
                "Runs inside the tenant-controlled runtime boundary.",
            ],
        ),
        ModelProviderOption(
            provider_id="eu-approved-provider",
            display_name="EU Approved Provider",
            provider_type="managed-private-endpoint",
            hosting_boundary="eu-region-approved-boundary",
            status="policy_gated",
            egress_mode="approved-private-endpoint",
            cost_basis="token-metered",
            allowed_policies=["local-or-approved-provider"],
            notes=[
                "Allowed only when tenant policy enables the approved endpoint.",
                "No public internet model route is implied by this demo seed.",
            ],
        ),
        ModelProviderOption(
            provider_id="external-general-llm",
            display_name="External General LLM",
            provider_type="external",
            hosting_boundary="outside-tenant-boundary",
            status="blocked_by_default",
            egress_mode="external-egress",
            cost_basis="not-executed",
            allowed_policies=["explicit-exception-required"],
            notes=[
                "Shown to make blocked egress observable.",
                "The public demo never sends prompt or operational data to this route.",
            ],
        ),
    ]
    routes = [
        ModelRouteTelemetry(
            route_id="route_daily_brief_local",
            agent_id="agent_daily_brief",
            agent_name="Daily Brief Agent",
            domain="Operations",
            provider_id="local-vllm",
            provider_name="Local vLLM Gateway",
            model="axis-local-brief-7b",
            model_policy="local-or-approved-provider",
            prompt_classification="operational-summary",
            data_boundary="tenant-private-runtime",
            external_egress_requested=False,
            external_egress_allowed=False,
            egress_decision="local_allowed",
            decision_reason="Local provider satisfies the tenant model policy.",
            route_status=OverviewStatus.READY,
            input_tokens=1860,
            output_tokens=420,
            estimated_cost_eur=0.18,
            latency_ms=840,
            cost_center="plant-operations",
            required_permissions=["agents:read", "audit:read", "workflows:read"],
            evidence_refs=["wf_supplier_delay_review", "audit_20260621_154000_ontology_read"],
            audit_event_id="audit_20260621_model_route_daily_brief",
            observability_events=[
                "model.route.selected",
                "model.tokens.estimated",
                "model.cost.estimated",
            ],
        ),
        ModelRouteTelemetry(
            route_id="route_supply_risk_local",
            agent_id="agent_supply_risk",
            agent_name="Supply Risk Agent",
            domain="Supply",
            provider_id="local-vllm",
            provider_name="Local vLLM Gateway",
            model="axis-local-risk-13b",
            model_policy="no-external-egress",
            prompt_classification="supplier-risk-evidence",
            data_boundary="tenant-private-runtime",
            external_egress_requested=False,
            external_egress_allowed=False,
            egress_decision="local_allowed",
            decision_reason="Supply evidence remains inside the tenant boundary.",
            route_status=OverviewStatus.READY,
            input_tokens=2440,
            output_tokens=610,
            estimated_cost_eur=0.27,
            latency_ms=1160,
            cost_center="supply",
            required_permissions=["agents:read", "supply:read"],
            evidence_refs=["risk_supplier_delay", "asset_motors_batch"],
            audit_event_id="audit_20260621_model_route_supply_risk",
            observability_events=[
                "model.route.selected",
                "model.policy.evaluated",
                "model.cost.estimated",
            ],
        ),
        ModelRouteTelemetry(
            route_id="route_quality_external_blocked",
            agent_id="agent_quality_risk",
            agent_name="Quality Risk Agent",
            domain="Quality",
            provider_id="external-general-llm",
            provider_name="External General LLM",
            model="external-quality-general",
            model_policy="no-external-egress",
            prompt_classification="quality-evidence",
            data_boundary="outside-tenant-boundary",
            external_egress_requested=True,
            external_egress_allowed=False,
            egress_decision="blocked_by_default",
            decision_reason="Tenant policy blocks external model egress for quality evidence.",
            route_status=OverviewStatus.READY,
            input_tokens=0,
            output_tokens=0,
            estimated_cost_eur=0,
            latency_ms=18,
            cost_center="quality",
            required_permissions=["agents:read", "quality:read", "security:read"],
            evidence_refs=["policy_external_egress", "audit_20260621_133900_egress_blocked"],
            audit_event_id="audit_20260621_133900_egress_blocked",
            observability_events=[
                "model.policy.evaluated",
                "model.egress.blocked",
                "audit.event.recorded",
            ],
        ),
        ModelRouteTelemetry(
            route_id="route_maintenance_approved_private",
            agent_id="agent_maintenance_planner",
            agent_name="Maintenance Planner Agent",
            domain="Maintenance",
            provider_id="eu-approved-provider",
            provider_name="EU Approved Provider",
            model="eu-operation-copilot",
            model_policy="local-or-approved-provider",
            prompt_classification="maintenance-schedule-summary",
            data_boundary="eu-region-approved-boundary",
            external_egress_requested=False,
            external_egress_allowed=False,
            egress_decision="approved_private_endpoint",
            decision_reason="Tenant policy allows this approved private endpoint path.",
            route_status=OverviewStatus.WATCH,
            input_tokens=1980,
            output_tokens=530,
            estimated_cost_eur=0.31,
            latency_ms=920,
            cost_center="maintenance",
            required_permissions=["agents:read", "maintenance:read"],
            evidence_refs=["risk_maintenance_window", "asset_press_4"],
            audit_event_id="audit_20260621_model_route_maintenance",
            observability_events=[
                "model.route.selected",
                "model.provider.policy_gated",
                "model.cost.estimated",
            ],
        ),
    ]

    total_cost = sum(route.estimated_cost_eur for route in routes)
    blocked_routes = sum(route.egress_decision == "blocked_by_default" for route in routes)

    return ManufacturingModelRouting(
        tenant_id="tenant_demo_manufacturing",
        plant_name="Ravenna Works",
        scenario="Plant Operations Cockpit",
        as_of="2026-06-21T16:30:00+02:00",
        routing_status=OverviewStatus.WATCH,
        metrics=[
            OverviewMetric(
                label="Route Decisions",
                value=str(len(routes)),
                detail="Synthetic route decisions observed for governed demo agents",
                status=OverviewStatus.READY,
            ),
            OverviewMetric(
                label="External Egress",
                value=f"{blocked_routes} blocked",
                detail="No public demo route sends operational data outside the tenant boundary",
                status=OverviewStatus.READY,
            ),
            OverviewMetric(
                label="Estimated Spend",
                value=f"EUR {total_cost:.2f}",
                detail="Synthetic token-cost estimate for the visible demo routes",
                status=OverviewStatus.WATCH,
            ),
            OverviewMetric(
                label="Coverage",
                value="4 agents",
                detail="Every registered demo agent has a visible routing posture",
                status=OverviewStatus.READY,
            ),
        ],
        filter_options=_model_routing_filter_options(routes),
        provider_options=providers,
        routes=routes,
        budget_notes=[
            "Cost values are synthetic observability estimates, not product pricing.",
            "Production budgets must be tenant-scoped and enforced before route execution.",
            "Blocked routes keep token and cost counters at zero because no prompt is sent.",
            "Provider-specific billing adapters remain Platform work.",
        ],
        observability_notes=[
            "The seed models route selection, policy evaluation, token estimates and audit refs.",
            (
                "OpenTelemetry spans, persisted usage records and live provider meters remain "
                "Platform work."
            ),
            (
                "External model egress is blocked by default unless tenant policy explicitly "
                "enables it."
            ),
        ],
    )
