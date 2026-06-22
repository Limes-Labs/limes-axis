import { describe, expect, it } from "vitest";

import {
  countWaitingWorkflowSignals,
  findWorkflowById,
  formatWorkflowState,
  shouldUsePersistedWorkflowData,
  type ManufacturingWorkflowConsole,
} from "./workflow-demo";

const workflowConsoleFixture: ManufacturingWorkflowConsole = {
  tenant_id: "tenant_fixture",
  plant_name: "Fixture Plant",
  scenario: "Runtime contract fixture",
  as_of: "2026-06-22T09:00:00+02:00",
  runtime_status: "watch",
  metrics: [],
  workflow_runs: [
    {
      workflow_id: "wf_supply_fixture",
      name: "Supply Fixture Review",
      domain: "Supply",
      state: "waiting_for_approval",
      status: "action_required",
      owner_role: "supply-owner",
      runtime: "Temporal OSS",
      adapter: "axis-temporal-adapter",
      autonomy_level: "L2",
      started_at: "2026-06-22T08:30:00+02:00",
      eta: "Today 17:30",
      blocker: "Owner approval required",
      objective: "Resolve a delayed supplier batch.",
      current_step: "Approval gate",
      related_risk: "risk_supply_fixture",
      related_assets: ["asset_fixture_line"],
      inputs: ["Supplier status"],
      proposed_outputs: ["Expedite fixture batch"],
      pending_signals: [
        {
          signal: "approval_decision",
          required_role: "supply-owner",
          status: "waiting",
          approval_id: "appr_supply_fixture",
        },
      ],
      controls: ["Human approval required"],
      timeline: [
        {
          event: "workflow.started",
          at: "2026-06-22T08:30:00+02:00",
          actor: "axis-workflow-runtime",
          result: "started",
          summary: "Workflow started.",
        },
      ],
      audit_scope: "wf_supply_fixture",
      replay_ready: false,
    },
    {
      workflow_id: "wf_ops_fixture",
      name: "Operations Fixture Brief",
      domain: "Operations",
      state: "proposal_ready",
      status: "ready",
      owner_role: "operations-owner",
      runtime: "Temporal OSS",
      adapter: "axis-temporal-adapter",
      autonomy_level: "L1",
      started_at: "2026-06-22T08:45:00+02:00",
      eta: "Today 12:00",
      blocker: null,
      objective: "Prepare read-only shift summary.",
      current_step: "Review summary",
      related_risk: "risk_ops_fixture",
      related_assets: ["asset_fixture_line"],
      inputs: ["Shift status"],
      proposed_outputs: ["Daily brief"],
      pending_signals: [],
      controls: ["Read-only output"],
      timeline: [
        {
          event: "proposal.ready",
          at: "2026-06-22T08:50:00+02:00",
          actor: "agent_ops_fixture",
          result: "ready",
          summary: "Proposal prepared.",
        },
      ],
      audit_scope: "wf_ops_fixture",
      replay_ready: true,
    },
  ],
  runtime_notes: ["Fixture data is scoped to tests."],
};

describe("workflow console helpers", () => {
  it("counts waiting workflow signals", () => {
    expect(countWaitingWorkflowSignals(workflowConsoleFixture)).toBe(1);
  });

  it("finds workflows by id with a safe fallback", () => {
    expect(findWorkflowById(workflowConsoleFixture, "wf_ops_fixture").name).toBe(
      "Operations Fixture Brief",
    );
    expect(findWorkflowById(workflowConsoleFixture, "missing").name).toBe(
      "Supply Fixture Review",
    );
  });

  it("formats workflow state labels", () => {
    expect(formatWorkflowState("waiting_for_approval")).toBe("Waiting For Approval");
    expect(formatWorkflowState("proposal_ready")).toBe("Proposal Ready");
  });

  it("uses persisted workflow data only when workflow runs exist", () => {
    expect(shouldUsePersistedWorkflowData(workflowConsoleFixture)).toBe(true);
    expect(
      shouldUsePersistedWorkflowData({
        ...workflowConsoleFixture,
        workflow_runs: [],
      }),
    ).toBe(false);
  });
});
