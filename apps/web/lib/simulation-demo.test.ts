import { describe, expect, it } from "vitest";

import {
  countChangedPolicySetDiffs,
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
    expect(artifact.policy_set_diffs[0]).toMatchObject({
      connector_id: "file_csv_manufacturing_assets",
      baseline_policy_set_id: "policy_set_connector_asset_required_20260622_v2",
      candidate_policy_set_id: "policy_set_connector_asset_required_20260622_rollback",
      diff_status: "changed_outcome_detected",
      audit_event_type: "connector.promotion_policy_set.simulated_diff",
    });
    expect(
      defaultManufacturingReplaySimulation.metrics.find(
        (metric) => metric.label === "Policy Set Diffs",
      ),
    ).toMatchObject({ value: "3" });
    expect(
      defaultManufacturingReplaySimulation.metrics.find(
        (metric) => metric.label === "Persisted Outputs",
      ),
    ).toMatchObject({ value: "1" });
    expect(
      defaultManufacturingReplaySimulation.metrics.find(
        (metric) => metric.label === "Replay Window",
      ),
    ).toMatchObject({ value: "365d" });
    expect(
      defaultManufacturingReplaySimulation.metrics.find(
        (metric) => metric.label === "Retention Excluded",
      ),
    ).toMatchObject({ value: "0" });
    expect(defaultManufacturingReplaySimulation.retention_window).toMatchObject({
      policy_id: "axis-demo-replay-retention",
      retention_days: 365,
      retention_enforced: true,
      disposal_action: "enforced_exclusion",
      excluded_output_count: 0,
    });
    expect(defaultManufacturingReplaySimulation.persisted_outputs[0]).toMatchObject({
      simulation_output_id: "replay_output_supplier_delay_review_20260622",
      audit_event_type: "simulation.replay_output.persisted",
      required_scope: "simulation:replay:persist",
      retention_window_days: 30,
    });
    expect(defaultManufacturingReplaySimulation.persisted_outputs[0].artifact.workflow_id).toBe(
      "wf_supplier_delay_review",
    );
    expect(defaultManufacturingReplaySimulation.simulation_notes).toContain(
      "Persisted simulation outputs are governed audit artifacts with retention metadata.",
    );
    expect(defaultManufacturingReplaySimulation.simulation_notes).toContain(
      "Replay retention windows are enforced at query time; legal hold suspends exclusion.",
    );
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
    expect(countChangedPolicySetDiffs(defaultManufacturingReplaySimulation)).toBe(3);
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
