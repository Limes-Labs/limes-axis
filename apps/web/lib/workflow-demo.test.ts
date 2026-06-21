import { describe, expect, it } from "vitest";

import {
  countWaitingWorkflowSignals,
  defaultManufacturingWorkflowConsole,
  findWorkflowById,
  formatWorkflowState,
} from "./workflow-demo";

describe("manufacturing workflow console demo contract", () => {
  it("keeps a read-only workflow seed available without the API", () => {
    expect(defaultManufacturingWorkflowConsole.scenario).toBe("Plant Operations Cockpit");
    expect(defaultManufacturingWorkflowConsole.plant_name).toBe("Ravenna Works");
    expect(defaultManufacturingWorkflowConsole.workflow_runs).toHaveLength(3);
    expect(JSON.stringify(defaultManufacturingWorkflowConsole)).not.toContain("@");
  });

  it("ties every workflow to runtime metadata, signals and timeline evidence", () => {
    for (const run of defaultManufacturingWorkflowConsole.workflow_runs) {
      expect(run.runtime).toBe("Temporal OSS");
      expect(run.adapter).toBe("axis-temporal-adapter");
      expect(run.pending_signals.length).toBeGreaterThan(0);
      expect(run.timeline.length).toBeGreaterThan(0);
      expect(run.controls.length).toBeGreaterThan(0);
      expect(run.replay_ready).toBe(false);
    }
  });

  it("counts waiting workflow signals", () => {
    expect(countWaitingWorkflowSignals(defaultManufacturingWorkflowConsole)).toBe(3);
  });

  it("finds workflows by id with a safe fallback", () => {
    expect(
      findWorkflowById(defaultManufacturingWorkflowConsole, "wf_quality_hold_review").name,
    ).toBe("Quality Hold Review");
    expect(findWorkflowById(defaultManufacturingWorkflowConsole, "missing").name).toBe(
      "Supplier Delay Review",
    );
  });

  it("formats workflow state labels", () => {
    expect(formatWorkflowState("waiting_for_approval")).toBe("Waiting For Approval");
    expect(formatWorkflowState("proposal_ready")).toBe("Proposal Ready");
  });
});
