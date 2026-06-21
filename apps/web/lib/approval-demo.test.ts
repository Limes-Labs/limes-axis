import { describe, expect, it } from "vitest";

import {
  approvalDecisionActorId,
  approvalDecisionActorScopes,
  approvalDecisionLabel,
  approvalRiskClass,
  buildApprovalDecisionPayload,
  defaultManufacturingApprovalInbox,
  findApprovalById,
} from "./approval-demo";

describe("manufacturing approval inbox demo contract", () => {
  it("keeps a public-safe approval seed available without the API", () => {
    expect(defaultManufacturingApprovalInbox.scenario).toBe("Plant Operations Cockpit");
    expect(defaultManufacturingApprovalInbox.plant_name).toBe("Ravenna Works");
    expect(defaultManufacturingApprovalInbox.approvals).toHaveLength(3);
    expect(defaultManufacturingApprovalInbox.approvals.some((item) => item.risk_level === "high"))
      .toBe(true);
    expect(JSON.stringify(defaultManufacturingApprovalInbox)).not.toContain("@");
  });

  it("keeps every approval tied to evidence, permissions and decisions", () => {
    for (const approval of defaultManufacturingApprovalInbox.approvals) {
      expect(approval.status).toBe("pending");
      expect(approval.evidence.length).toBeGreaterThan(0);
      expect(approval.data_accessed.length).toBeGreaterThan(0);
      expect(approval.required_permission).toContain("approvals:");
      expect(approval.audit_event_preview.event).toBe("approval.decision.recorded");
      expect(approval.decision_options.map((option) => option.decision)).toEqual([
        "approve",
        "reject",
        "request_changes",
      ]);
    }
  });

  it("formats approval risk and local decision states", () => {
    expect(approvalRiskClass("high")).toBe("signal-action-required");
    expect(approvalRiskClass("medium")).toBe("signal-watch");
    expect(approvalDecisionLabel("request_changes")).toBe("Changes Requested");
  });

  it("finds approvals by id with a safe fallback", () => {
    expect(
      findApprovalById(defaultManufacturingApprovalInbox, "appr_quality_hold_batch").action,
    ).toBe("Place Batch Q-1842 on quality hold");
    expect(findApprovalById(defaultManufacturingApprovalInbox, "missing").action).toBe(
      "Expedite supplier batch",
    );
  });

  it("builds public-safe persisted decision payloads", () => {
    const approval = findApprovalById(
      defaultManufacturingApprovalInbox,
      "appr_expedite_supplier_batch",
    );
    const payload = buildApprovalDecisionPayload(approval, "approve");

    expect(approvalDecisionActorId(approval)).toBe("plant-operations-owner-role");
    expect(approvalDecisionActorScopes(approval)).toEqual(["approvals:supply:decide"]);
    expect(payload).toEqual({
      decision: "approve",
      actor_id: "plant-operations-owner-role",
      actor_scopes: ["approvals:supply:decide"],
      note: "Console decision recorded for appr_expedite_supplier_batch.",
    });
    expect(JSON.stringify(payload)).not.toContain("@");
  });
});
