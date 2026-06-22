import type { AuditLedgerEvent } from "./audit-demo";
import { defaultManufacturingAuditExplorer } from "./audit-demo";
import type { PlatformStatus } from "./platform-overview";
import type { WorkflowRun, WorkflowTimelineEvent } from "./workflow-demo";
import { defaultManufacturingWorkflowConsole } from "./workflow-demo";

export type PolicySimulationResult = {
  policy_id: string;
  policy_name: string;
  baseline_decision: string;
  simulated_decision: string;
  changed_outcome: boolean;
  evidence_refs: string[];
  summary: string;
};

export type PolicySetVersionDiff = {
  diff_id: string;
  connector_id: string;
  baseline_policy_set_id: string;
  baseline_policy_set_version: string;
  candidate_policy_set_id: string;
  candidate_policy_set_version: string;
  historical_event_count: number;
  changed_policy_ids: string[];
  baseline_decision: string;
  candidate_decision: string;
  changed_outcome: boolean;
  diff_status: string;
  audit_event_type: string;
  evidence_refs: string[];
  summary: string;
};

export type ReplayArtifact = {
  artifact_id: string;
  workflow_id: string;
  workflow_name: string;
  audit_scope: string;
  replay_mode: string;
  replay_ready: boolean;
  determinism_status: string;
  timeline_event_count: number;
  audit_event_count: number;
  evidence_refs: string[];
  timeline: WorkflowTimelineEvent[];
  audit_events: AuditLedgerEvent[];
  policy_results: PolicySimulationResult[];
  policy_set_diffs: PolicySetVersionDiff[];
};

export type ReplaySimulationOutputRecord = {
  tenant_id: string;
  simulation_output_id: string;
  workflow_id: string;
  artifact_id: string;
  idempotency_key: string;
  status: string;
  requested_by: string;
  required_scope: string;
  replay_mode: string;
  determinism_status: string;
  output_hash: string;
  retention_window_days: number;
  permission_decision: {
    allowed: boolean;
    reason: string;
  };
  artifact: ReplayArtifact;
  evidence_refs: string[];
  audit_event_id: string | null;
  audit_event_type: string;
  reason: string;
  notes: string[];
  idempotent_replay: boolean;
  created_at: string;
};

export type ReplayRetentionWindow = {
  policy_id: string;
  retention_days: number;
  legal_hold: boolean;
  retention_enforced: boolean;
  retention_window_start: string;
  disposal_action: string;
  excluded_timeline_event_count: number;
  excluded_audit_event_count: number;
  excluded_output_count: number;
  notes: string[];
};

export type ManufacturingReplaySimulation = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  as_of: string;
  simulation_status: PlatformStatus;
  metrics: {
    label: string;
    value: string;
    detail: string;
    status: PlatformStatus;
  }[];
  retention_window: ReplayRetentionWindow;
  artifacts: ReplayArtifact[];
  persisted_outputs: ReplaySimulationOutputRecord[];
  simulation_notes: string[];
};

function relatedAuditEvents(workflow: WorkflowRun): AuditLedgerEvent[] {
  return defaultManufacturingAuditExplorer.events.filter(
    (event) =>
      event.related_workflow_id === workflow.workflow_id || event.scope === workflow.audit_scope,
  );
}

function uniqueEvidenceRefs(workflow: WorkflowRun, auditEvents: AuditLedgerEvent[]): string[] {
  const refs = new Set<string>([
    workflow.workflow_id,
    workflow.audit_scope,
    workflow.related_risk,
    ...workflow.related_assets,
  ]);
  workflow.pending_signals.forEach((signal) => {
    if (signal.approval_id) {
      refs.add(signal.approval_id);
    }
  });
  auditEvents.forEach((event) => {
    event.evidence_refs.forEach((ref) => refs.add(ref));
    if (event.related_approval_id) {
      refs.add(event.related_approval_id);
    }
  });
  return Array.from(refs).sort();
}

function policyResult(workflow: WorkflowRun, evidenceRefs: string[]): PolicySimulationResult {
  const changedOutcome = workflow.workflow_id !== "wf_quality_hold_review";
  return {
    policy_id: "human-approval-required",
    policy_name: "Human approval before external mutation",
    baseline_decision: workflow.state,
    simulated_decision: changedOutcome ? "blocked_until_human_approval" : workflow.state,
    changed_outcome: changedOutcome,
    evidence_refs: evidenceRefs.slice(0, 8),
    summary: changedOutcome
      ? "Replay preview blocks the workflow until the required owner approval signal is present."
      : "Replay preview preserves the current evidence-review state while owner review remains open.",
  };
}

function policySetDiff(
  workflow: WorkflowRun,
  auditEvents: AuditLedgerEvent[],
  evidenceRefs: string[],
): PolicySetVersionDiff {
  return {
    diff_id: `policy-set-diff-${workflow.workflow_id}-seed`,
    connector_id: "file_csv_manufacturing_assets",
    baseline_policy_set_id: "policy_set_connector_asset_required_20260622_v2",
    baseline_policy_set_version: "2026-06-22.2",
    candidate_policy_set_id: "policy_set_connector_asset_required_20260622_rollback",
    candidate_policy_set_version: "2026-06-22.3",
    historical_event_count: workflow.timeline.length + auditEvents.length,
    changed_policy_ids: ["connector.asset.required"],
    baseline_decision: "allow_after_manifest_validation",
    candidate_decision: "block_until_required_asset_gate",
    changed_outcome: true,
    diff_status: "changed_outcome_detected",
    audit_event_type: "connector.promotion_policy_set.simulated_diff",
    evidence_refs: evidenceRefs.slice(0, 8),
    summary:
      "Historical workflow and audit evidence would be re-gated by the rollback policy set before connector promotion.",
  };
}

function artifactFromWorkflow(workflow: WorkflowRun, index: number): ReplayArtifact {
  const auditEvents = relatedAuditEvents(workflow);
  const evidenceRefs = uniqueEvidenceRefs(workflow, auditEvents);
  return {
    artifact_id: `replay-${workflow.workflow_id}-seed-${index + 1}`,
    workflow_id: workflow.workflow_id,
    workflow_name: workflow.name,
    audit_scope: workflow.audit_scope,
    replay_mode: "governance-preview",
    replay_ready: workflow.replay_ready,
    determinism_status: "preview_only",
    timeline_event_count: workflow.timeline.length,
    audit_event_count: auditEvents.length,
    evidence_refs: evidenceRefs,
    timeline: workflow.timeline,
    audit_events: auditEvents,
    policy_results: [policyResult(workflow, evidenceRefs)],
    policy_set_diffs: [policySetDiff(workflow, auditEvents, evidenceRefs)],
  };
}

const defaultArtifacts = defaultManufacturingWorkflowConsole.workflow_runs.map(artifactFromWorkflow);
const defaultPersistedOutputs: ReplaySimulationOutputRecord[] = [
  {
    tenant_id: "tenant_demo_manufacturing",
    simulation_output_id: "replay_output_supplier_delay_review_20260622",
    workflow_id: defaultArtifacts[0].workflow_id,
    artifact_id: defaultArtifacts[0].artifact_id,
    idempotency_key: "idem_replay_output_supplier_delay_review_20260622",
    status: "persisted",
    requested_by: "simulation-governance-owner-role",
    required_scope: "simulation:replay:persist",
    replay_mode: defaultArtifacts[0].replay_mode,
    determinism_status: defaultArtifacts[0].determinism_status,
    output_hash: "1b7f6b7d2c98b4c808ffed1a7f740ba946bda215f6d19c2ddf84c3c596f6b8cb",
    retention_window_days: 30,
    permission_decision: {
      allowed: true,
      reason: "allowed",
    },
    artifact: defaultArtifacts[0],
    evidence_refs: defaultArtifacts[0].evidence_refs,
    audit_event_id: "audit_replay_output_supplier_delay_review_20260622",
    audit_event_type: "simulation.replay_output.persisted",
    reason: "Persist replay output for governance review.",
    notes: ["Governed replay output retained for design partner review."],
    idempotent_replay: false,
    created_at: "2026-06-21T16:30:00+02:00",
  },
];

export const defaultManufacturingReplaySimulation: ManufacturingReplaySimulation = {
  tenant_id: "tenant_demo_manufacturing",
  plant_name: "Ravenna Works",
  scenario: "Plant Operations Cockpit",
  as_of: "2026-06-21T16:30:00+02:00",
  simulation_status: "ready",
  metrics: [
    {
      label: "Replay Artifacts",
      value: String(defaultArtifacts.length),
      detail: "Workflow histories with matching audit evidence",
      status: "ready",
    },
    {
      label: "History Events",
      value: String(
        defaultArtifacts.reduce(
          (total, artifact) =>
            total + artifact.timeline_event_count + artifact.audit_event_count,
          0,
        ),
      ),
      detail: "Timeline and audit events included in replay previews",
      status: "ready",
    },
    {
      label: "Policy Simulations",
      value: String(
        defaultArtifacts.reduce((total, artifact) => total + artifact.policy_results.length, 0),
      ),
      detail: "Deterministic policy previews evaluated against history",
      status: "ready",
    },
    {
      label: "Policy Set Diffs",
      value: String(
        defaultArtifacts.reduce((total, artifact) => total + artifact.policy_set_diffs.length, 0),
      ),
      detail: "Versioned connector policy-set comparisons over historical events",
      status: "ready",
    },
    {
      label: "Persisted Outputs",
      value: String(defaultPersistedOutputs.length),
      detail: "Governed replay outputs retained with audit evidence",
      status: "ready",
    },
    {
      label: "Replay Window",
      value: "365d",
      detail: "Query-time retention window enforced before replay response",
      status: "ready",
    },
    {
      label: "Retention Excluded",
      value: "0",
      detail: "Timeline, audit and output records outside the replay window",
      status: "ready",
    },
    {
      label: "Deterministic Replay",
      value: "0",
      detail: "Full Temporal replay remains behind a future runtime path",
      status: "watch",
    },
  ],
  retention_window: {
    policy_id: "axis-demo-replay-retention",
    retention_days: 365,
    legal_hold: false,
    retention_enforced: true,
    retention_window_start: "2025-06-21T16:30:00+02:00",
    disposal_action: "enforced_exclusion",
    excluded_timeline_event_count: 0,
    excluded_audit_event_count: 0,
    excluded_output_count: 0,
    notes: [
      "Replay windows are enforced before artifacts and persisted outputs are returned.",
      "Persisted outputs use the stricter of the query window and the output retention window.",
      "Replay retention excluded 0 expired records from this response.",
      "Physical deletion jobs and legal hold workflows remain separate platform work.",
    ],
  },
  artifacts: defaultArtifacts,
  persisted_outputs: defaultPersistedOutputs,
  simulation_notes: [
    "Replay artifacts are derived from workflow history and audit evidence.",
    "Policy simulation is deterministic preview logic, not live workflow replay.",
    "Policy-set version diffs compare governed connector policy sets over historical events without activating a new set.",
    "Persisted simulation outputs are governed audit artifacts with retention metadata.",
    "Replay retention windows are enforced at query time; legal hold suspends exclusion.",
    "Raw action payloads are not exposed in replay artifacts.",
    "Temporal replay and physical retention deletion jobs remain Platform work.",
  ],
};

export function shouldUsePersistedReplayData(data: ManufacturingReplaySimulation): boolean {
  return data.simulation_status === "ready" && data.artifacts.length > 0;
}

export function findReplayArtifactById(
  data: ManufacturingReplaySimulation,
  artifactIdOrWorkflowId: string,
): ReplayArtifact {
  return (
    data.artifacts.find(
      (artifact) =>
        artifact.artifact_id === artifactIdOrWorkflowId ||
        artifact.workflow_id === artifactIdOrWorkflowId,
    ) ?? data.artifacts[0]
  );
}

export function countChangedPolicyResults(data: ManufacturingReplaySimulation): number {
  return data.artifacts.reduce(
    (total, artifact) =>
      total + artifact.policy_results.filter((result) => result.changed_outcome).length,
    0,
  );
}

export function countChangedPolicySetDiffs(data: ManufacturingReplaySimulation): number {
  return data.artifacts.reduce(
    (total, artifact) =>
      total + (artifact.policy_set_diffs ?? []).filter((diff) => diff.changed_outcome).length,
    0,
  );
}

export function formatSimulationLabel(value: string): string {
  return value
    .split(/[_-]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
