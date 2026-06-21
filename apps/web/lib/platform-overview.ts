export type PlatformStatus = "ready" | "watch" | "action_required";

export type OverviewMetric = {
  label: string;
  value: string;
  detail: string;
  status: PlatformStatus;
};

export type RiskSignal = {
  title: string;
  domain: string;
  severity: PlatformStatus;
  owner_role: string;
  evidence: string;
  related_asset: string;
};

export type WorkflowSummary = {
  workflow_id: string;
  name: string;
  state: string;
  owner_role: string;
  blocker: string | null;
  eta: string;
};

export type ApprovalSummary = {
  approval_id: string;
  action: string;
  risk_level: string;
  requested_by: string;
  owner_role: string;
  due: string;
};

export type AgentSummary = {
  agent_id: string;
  name: string;
  autonomy_level: "L0" | "L1" | "L2" | "L3" | "L4";
  status: string;
  proposals_pending: number;
  model_policy: string;
};

export type AuditEvidence = {
  event: string;
  actor: string;
  scope: string;
  result: string;
};

export type ManufacturingOverview = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  as_of: string;
  metrics: OverviewMetric[];
  risk_signals: RiskSignal[];
  workflows: WorkflowSummary[];
  approvals: ApprovalSummary[];
  agents: AgentSummary[];
  audit_events: AuditEvidence[];
};

export const defaultManufacturingOverview: ManufacturingOverview = {
  tenant_id: "tenant_demo_manufacturing",
  plant_name: "Ravenna Works",
  scenario: "Plant Operations Cockpit",
  as_of: "2026-06-21T16:30:00+02:00",
  metrics: [
    {
      label: "Workflow Load",
      value: "7 active",
      detail: "3 production, 2 quality, 1 maintenance, 1 supplier flow",
      status: "watch",
    },
    {
      label: "Approvals",
      value: "3 pending",
      detail: "2 high-risk actions require human approval today",
      status: "action_required",
    },
    {
      label: "Agents",
      value: "4 governed",
      detail: "All agents remain within L0-L2 autonomy for the demo tenant",
      status: "ready",
    },
    {
      label: "Audit",
      value: "128 events",
      detail: "Reads, proposals, workflow signals and decisions are recorded",
      status: "ready",
    },
  ],
  risk_signals: [
    {
      title: "Supplier delay may block Line 2 packaging",
      domain: "Supply",
      severity: "action_required",
      owner_role: "supply-planning-owner",
      evidence: "Inbound motors batch is 18 hours late against the production window.",
      related_asset: "line-2-packaging",
    },
    {
      title: "Quality drift detected on Batch Q-1842",
      domain: "Quality",
      severity: "watch",
      owner_role: "quality-owner",
      evidence: "Inspection variance crossed the watch threshold for two samples.",
      related_asset: "batch-q-1842",
    },
    {
      title: "Press 4 maintenance window is at risk",
      domain: "Maintenance",
      severity: "watch",
      owner_role: "maintenance-owner",
      evidence: "Planned downtime overlaps with a rush order unless rescheduled.",
      related_asset: "press-4",
    },
  ],
  workflows: [
    {
      workflow_id: "wf_supplier_delay_review",
      name: "Supplier Delay Review",
      state: "waiting_for_approval",
      owner_role: "plant-operations-owner",
      blocker: "Approve expedite action or adjust production schedule",
      eta: "Today 18:00",
    },
    {
      workflow_id: "wf_quality_hold_review",
      name: "Quality Hold Review",
      state: "investigating",
      owner_role: "quality-owner",
      blocker: null,
      eta: "Today 16:45",
    },
    {
      workflow_id: "wf_maintenance_reschedule",
      name: "Maintenance Reschedule",
      state: "proposal_ready",
      owner_role: "maintenance-owner",
      blocker: "Human review required before schedule mutation",
      eta: "Tomorrow 09:00",
    },
  ],
  approvals: [
    {
      approval_id: "appr_expedite_supplier_batch",
      action: "Expedite supplier batch",
      risk_level: "high",
      requested_by: "supply-risk-agent",
      owner_role: "plant-operations-owner",
      due: "Today 17:30",
    },
    {
      approval_id: "appr_quality_hold_batch",
      action: "Place Batch Q-1842 on quality hold",
      risk_level: "high",
      requested_by: "quality-risk-agent",
      owner_role: "quality-owner",
      due: "Today 16:45",
    },
    {
      approval_id: "appr_shift_maintenance_window",
      action: "Shift Press 4 maintenance window",
      risk_level: "medium",
      requested_by: "maintenance-planner-agent",
      owner_role: "maintenance-owner",
      due: "Tomorrow 08:30",
    },
  ],
  agents: [
    {
      agent_id: "agent_daily_brief",
      name: "Daily Brief Agent",
      autonomy_level: "L1",
      status: "recommending",
      proposals_pending: 1,
      model_policy: "local-or-approved-provider",
    },
    {
      agent_id: "agent_quality_risk",
      name: "Quality Risk Agent",
      autonomy_level: "L2",
      status: "drafting_actions",
      proposals_pending: 1,
      model_policy: "no-external-egress",
    },
    {
      agent_id: "agent_supply_risk",
      name: "Supply Risk Agent",
      autonomy_level: "L2",
      status: "waiting_for_approval",
      proposals_pending: 1,
      model_policy: "no-external-egress",
    },
  ],
  audit_events: [
    {
      event: "agent.proposal.created",
      actor: "supply-risk-agent",
      scope: "wf_supplier_delay_review",
      result: "approval_required",
    },
    {
      event: "policy.egress.blocked",
      actor: "model-router",
      scope: "quality-risk-agent",
      result: "blocked_by_default",
    },
    {
      event: "workflow.signal.requested",
      actor: "plant-operations-owner-role",
      scope: "wf_quality_hold_review",
      result: "recorded",
    },
  ],
};

export function platformStatusLabel(status: PlatformStatus): string {
  if (status === "action_required") {
    return "Action Required";
  }

  return status === "watch" ? "Watch" : "Ready";
}

export function platformStatusClass(status: PlatformStatus): string {
  return `signal-${status.replace("_", "-")}`;
}

export function formatOverviewTimestamp(value: string): string {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
