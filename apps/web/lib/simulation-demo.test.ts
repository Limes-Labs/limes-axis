import { describe, expect, it } from "vitest";

import {
  countChangedPolicyResults,
  defaultManufacturingReplaySimulation,
  findReplayArtifactById,
  shouldUsePersistedReplayData,
} from "./simulation-demo";

describe("manufacturing replay simulation demo contract", () => {
  it("ships a public-safe replay artifact seed", () => {
    const artifact = defaultManufacturingReplaySimulation.artifacts[0];

    expect(defaultManufacturingReplaySimulation.tenant_id).toBe("tenant_demo_manufacturing");
    expect(defaultManufacturingReplaySimulation.metrics[0]).toMatchObject({
      label: "Replay Artifacts",
      value: "3",
    });
    expect(artifact.workflow_id).toBe("wf_supplier_delay_review");
    expect(artifact.replay_mode).toBe("governance-preview");
    expect(artifact.policy_results[0]).toMatchObject({
      policy_id: "human-approval-required",
      simulated_decision: "blocked_until_human_approval",
    });
    expect(JSON.stringify(defaultManufacturingReplaySimulation).toLowerCase()).not.toContain(
      "secret",
    );
  });

  it("finds artifacts and counts policy outcome changes", () => {
    expect(
      findReplayArtifactById(defaultManufacturingReplaySimulation, "wf_quality_hold_review")
        .workflow_name,
    ).toBe("Quality Hold Review");
    expect(countChangedPolicyResults(defaultManufacturingReplaySimulation)).toBe(2);
  });

  it("uses persisted replay data only when artifacts are available", () => {
    expect(shouldUsePersistedReplayData(defaultManufacturingReplaySimulation)).toBe(true);
    expect(
      shouldUsePersistedReplayData({
        ...defaultManufacturingReplaySimulation,
        simulation_status: "watch",
        artifacts: [],
      }),
    ).toBe(false);
  });
});
