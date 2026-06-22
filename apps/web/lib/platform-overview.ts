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
