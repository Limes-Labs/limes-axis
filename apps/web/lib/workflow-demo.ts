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

export const defaultManufacturingWorkflowConsole: ManufacturingWorkflowConsole = {
  tenant_id: "tenant_demo_manufacturing",
  plant_name: "Ravenna Works",
  scenario: "Plant Operations Cockpit",
  as_of: "2026-06-21T16:30:00+02:00",
  runtime_status: "watch",
  metrics: [
    {
      label: "Active Runs",
      value: "3",
      detail: "Supply, quality and maintenance workflows in the demo console",
      status: "watch",
    },
    {
      label: "Waiting Signals",
      value: "3",
      detail: "Each run has one human or owner signal before mutation",
      status: "action_required",
    },
    {
      label: "Runtime",
      value: "Temporal OSS",
      detail: "Hidden behind the Axis workflow runtime adapter",
      status: "ready",
    },
    {
      label: "Replay",
      value: "Preview",
      detail: "History preview exists; deterministic replay remains Platform work",
      status: "watch",
    },
  ],
  runtime_notes: [
    "The public workflow console seed is read-only and synthetic.",
    "Temporal remains behind the Axis workflow runtime adapter boundary.",
    "Signals shown here are pending governance signals, not live production mutations.",
    "Durable replay, persisted history views and workflow signal execution remain Platform work.",
  ],
  workflow_runs: [
    {
      workflow_id: "wf_supplier_delay_review",
      name: "Supplier Delay Review",
      domain: "Supply",
      state: "waiting_for_approval",
      status: "action_required",
      owner_role: "plant-operations-owner",
      runtime: "Temporal OSS",
      adapter: "axis-temporal-adapter",
      autonomy_level: "L2",
      started_at: "2026-06-21T14:05:00+02:00",
      eta: "Today 18:00",
      blocker: "Approve expedite action or adjust production schedule",
      objective: "Resolve the delayed inbound motors batch before it blocks Line 2 packaging.",
      current_step: "Approval gate",
      related_risk: "risk_supplier_delay",
      related_assets: ["asset_motors_batch", "asset_line_2_packaging"],
      inputs: [
        "Supplier portal delay signal",
        "Line 2 packaging schedule",
        "Rush order priority flag",
      ],
      proposed_outputs: [
        "Expedite supplier batch action payload",
        "Workflow signal for approval decision",
        "Audit event for governance review",
      ],
      pending_signals: [
        {
          signal: "approval.decision",
          required_role: "plant-operations-owner",
          status: "waiting",
          approval_id: "appr_expedite_supplier_batch",
        },
      ],
      controls: ["approvals:supply:decide", "append-only-audit-required", "no-external-egress"],
      timeline: [
        {
          event: "workflow.started",
          at: "2026-06-21T14:05:00+02:00",
          actor: "workflow-runtime",
          result: "started",
          summary: "Supplier delay workflow created from the supply risk signal.",
        },
        {
          event: "agent.proposal.created",
          at: "2026-06-21T14:12:00+02:00",
          actor: "supply-risk-agent",
          result: "approval_required",
          summary: "L2 agent drafted an expedite action payload.",
        },
        {
          event: "workflow.signal.awaiting",
          at: "2026-06-21T14:18:00+02:00",
          actor: "axis-temporal-adapter",
          result: "waiting_for_approval",
          summary: "Workflow paused at the human approval gate.",
        },
      ],
      audit_scope: "wf_supplier_delay_review",
      replay_ready: false,
    },
    {
      workflow_id: "wf_quality_hold_review",
      name: "Quality Hold Review",
      domain: "Quality",
      state: "investigating",
      status: "watch",
      owner_role: "quality-owner",
      runtime: "Temporal OSS",
      adapter: "axis-temporal-adapter",
      autonomy_level: "L2",
      started_at: "2026-06-21T13:35:00+02:00",
      eta: "Today 16:45",
      blocker: "Quality owner must choose hold, sample expansion or manual review",
      objective: "Decide whether Batch Q-1842 needs a quality hold before shipment.",
      current_step: "Evidence review",
      related_risk: "risk_quality_drift",
      related_assets: ["asset_batch_q_1842"],
      inputs: ["QMS sample inspection variance", "Batch genealogy", "Customer order priority"],
      proposed_outputs: [
        "Quality hold recommendation",
        "Containment note for quality owner",
        "Audit event for reviewed evidence",
      ],
      pending_signals: [
        {
          signal: "quality.owner.review",
          required_role: "quality-owner",
          status: "waiting",
          approval_id: "appr_quality_hold_batch",
        },
      ],
      controls: ["approvals:quality:decide", "quality-evidence-required", "no-external-egress"],
      timeline: [
        {
          event: "workflow.started",
          at: "2026-06-21T13:35:00+02:00",
          actor: "workflow-runtime",
          result: "started",
          summary: "Quality workflow created from inspection variance.",
        },
        {
          event: "policy.egress.blocked",
          at: "2026-06-21T13:39:00+02:00",
          actor: "model-router",
          result: "blocked_by_default",
          summary: "External model egress was blocked for quality evidence.",
        },
        {
          event: "agent.proposal.created",
          at: "2026-06-21T13:44:00+02:00",
          actor: "quality-risk-agent",
          result: "review_required",
          summary: "L2 agent drafted a quality hold proposal.",
        },
      ],
      audit_scope: "wf_quality_hold_review",
      replay_ready: false,
    },
    {
      workflow_id: "wf_maintenance_reschedule",
      name: "Maintenance Reschedule",
      domain: "Maintenance",
      state: "proposal_ready",
      status: "watch",
      owner_role: "maintenance-owner",
      runtime: "Temporal OSS",
      adapter: "axis-temporal-adapter",
      autonomy_level: "L2",
      started_at: "2026-06-21T15:10:00+02:00",
      eta: "Tomorrow 09:00",
      blocker: "Human review required before schedule mutation",
      objective: "Move the Press 4 maintenance window without violating service policy.",
      current_step: "Proposal review",
      related_risk: "risk_maintenance_window",
      related_assets: ["asset_press_4"],
      inputs: [
        "CMMS maintenance window",
        "MES rush order schedule",
        "Service interval tolerance",
      ],
      proposed_outputs: [
        "Maintenance reschedule payload",
        "Owner review signal",
        "Audit event for schedule decision",
      ],
      pending_signals: [
        {
          signal: "maintenance.owner.review",
          required_role: "maintenance-owner",
          status: "waiting",
          approval_id: "appr_shift_maintenance_window",
        },
      ],
      controls: [
        "approvals:maintenance:decide",
        "service-window-policy",
        "append-only-audit-required",
      ],
      timeline: [
        {
          event: "workflow.started",
          at: "2026-06-21T15:10:00+02:00",
          actor: "workflow-runtime",
          result: "started",
          summary: "Maintenance workflow created from schedule collision risk.",
        },
        {
          event: "agent.proposal.created",
          at: "2026-06-21T15:18:00+02:00",
          actor: "maintenance-planner-agent",
          result: "proposal_ready",
          summary: "L2 agent drafted the schedule shift proposal.",
        },
        {
          event: "workflow.signal.awaiting",
          at: "2026-06-21T15:25:00+02:00",
          actor: "axis-temporal-adapter",
          result: "waiting_for_owner_review",
          summary: "Workflow paused before mutating the maintenance schedule.",
        },
      ],
      audit_scope: "wf_maintenance_reschedule",
      replay_ready: false,
    },
  ],
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
