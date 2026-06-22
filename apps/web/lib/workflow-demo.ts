import type { PlatformStatus } from "./platform-overview";

export type WorkflowSignal = {
  signal: string;
  required_role: string;
  status: string;
  approval_id: string | null;
};

export type WorkflowTimelineEvent = {
  event: string;
  at: string;
  actor: string;
  result: string;
  summary: string;
};

export type WorkflowRun = {
  workflow_id: string;
  name: string;
  domain: string;
  state: string;
  status: PlatformStatus;
  owner_role: string;
  runtime: string;
  adapter: string;
  autonomy_level: "L0" | "L1" | "L2" | "L3" | "L4";
  started_at: string;
  eta: string;
  blocker: string | null;
  objective: string;
  current_step: string;
  related_risk: string;
  related_assets: string[];
  inputs: string[];
  proposed_outputs: string[];
  pending_signals: WorkflowSignal[];
  controls: string[];
  timeline: WorkflowTimelineEvent[];
  audit_scope: string;
  replay_ready: boolean;
};

export type ManufacturingWorkflowConsole = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  as_of: string;
  runtime_status: PlatformStatus;
  metrics: {
    label: string;
    value: string;
    detail: string;
    status: PlatformStatus;
  }[];
  workflow_runs: WorkflowRun[];
  runtime_notes: string[];
};

export function findWorkflowById(
  console: ManufacturingWorkflowConsole,
  workflowId: string,
): WorkflowRun {
  return console.workflow_runs.find((run) => run.workflow_id === workflowId) ?? console.workflow_runs[0];
}

export function countWaitingWorkflowSignals(console: ManufacturingWorkflowConsole): number {
  return console.workflow_runs.reduce(
    (total, run) =>
      total + run.pending_signals.filter((signal) => signal.status === "waiting").length,
    0,
  );
}

export function formatWorkflowState(state: string): string {
  return state
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function shouldUsePersistedWorkflowData(
  console: ManufacturingWorkflowConsole,
): boolean {
  return console.workflow_runs.length > 0;
}
