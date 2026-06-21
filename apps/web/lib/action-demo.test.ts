import { describe, expect, it } from "vitest";

import {
  allActionFilter,
  actionRunWorkflowSignalLabel,
  buildActionRunIdempotencyKey,
  buildActionRunRequest,
  buildTypedActionPayload,
  countApprovalGatedActions,
  defaultManufacturingActionRegistry,
  filterActions,
  findActionById,
  formatActionLabel,
  formatSchemaFields,
} from "./action-demo";

describe("manufacturing action registry demo contract", () => {
  it("keeps a public-safe action registry seed available without the API", () => {
    expect(defaultManufacturingActionRegistry.scenario).toBe("Plant Operations Cockpit");
    expect(defaultManufacturingActionRegistry.plant_name).toBe("Ravenna Works");
    expect(defaultManufacturingActionRegistry.actions).toHaveLength(4);
    expect(JSON.stringify(defaultManufacturingActionRegistry)).not.toContain("@");
    expect(JSON.stringify(defaultManufacturingActionRegistry).toLowerCase()).not.toContain(
      "secret",
    );
  });

  it("keeps high-risk actions behind approval gates", () => {
    for (const action of defaultManufacturingActionRegistry.actions) {
      if (action.definition.risk_level === "high") {
        expect(action.definition.approval_mode).toBe("required");
      }

      expect(action.policy.dry_run_supported).toBe(true);
      expect(action.policy.execution_mode).not.toBe("live_execution");
      expect(action.validation_checks.length).toBeGreaterThan(0);
      expect(action.blocked_conditions.length).toBeGreaterThan(0);
    }
  });

  it("exposes filter options for domain, risk, approval and status", () => {
    expect(defaultManufacturingActionRegistry.filter_options.domains).toContain("Supply");
    expect(defaultManufacturingActionRegistry.filter_options.risk_levels).toContain("high");
    expect(defaultManufacturingActionRegistry.filter_options.approval_modes).toContain("required");
    expect(defaultManufacturingActionRegistry.filter_options.statuses).toContain(
      "approval_required",
    );
  });

  it("filters actions locally", () => {
    const actions = filterActions(defaultManufacturingActionRegistry, {
      domain: "Supply",
      riskLevel: "high",
      approvalMode: "required",
      status: "approval_required",
    });

    expect(actions).toHaveLength(1);
    expect(actions[0].definition.action_id).toBe("request_supplier_expedite");
  });

  it("keeps all actions when filters are set to all", () => {
    expect(
      filterActions(defaultManufacturingActionRegistry, {
        domain: allActionFilter,
        riskLevel: allActionFilter,
        approvalMode: allActionFilter,
        status: allActionFilter,
      }),
    ).toHaveLength(defaultManufacturingActionRegistry.actions.length);
  });

  it("finds actions by id with a safe fallback", () => {
    expect(
      findActionById(defaultManufacturingActionRegistry, "place_quality_hold").definition
        .display_name,
    ).toBe("Place quality hold");
    expect(findActionById(defaultManufacturingActionRegistry, "missing").definition.display_name)
      .toBe("Generate daily plant brief");
  });

  it("counts gated actions and formats labels", () => {
    expect(countApprovalGatedActions(defaultManufacturingActionRegistry)).toBe(3);
    expect(formatActionLabel("approval_gated_dry_run")).toBe("Approval Gated Dry Run");
    expect(formatActionLabel("approvals:supply:request")).toBe("Approvals Supply Request");
  });

  it("formats schema fields with required markers", () => {
    const supplyAction = findActionById(
      defaultManufacturingActionRegistry,
      "request_supplier_expedite",
    );

    expect(formatSchemaFields(supplyAction.definition.input_schema)).toContain(
      "supplier_batch_id: string (required)",
    );
  });

  it("builds typed action run requests from sample payloads", () => {
    const qualityAction = findActionById(defaultManufacturingActionRegistry, "place_quality_hold");
    const payload = buildTypedActionPayload(qualityAction);
    const request = buildActionRunRequest(defaultManufacturingActionRegistry, qualityAction);

    expect(payload.evidence_refs).toEqual([
      "risk_quality_drift",
      "audit_20260621_134400_quality_proposal",
    ]);
    expect(request).toMatchObject({
      actor_id: "agent_quality_risk",
      actor_scopes: ["quality:read", "approvals:quality:request"],
      idempotency_key: "tenant_demo_manufacturing:place_quality_hold:appr_quality_hold_batch",
    });
  });

  it("keeps action run idempotency keys stable for approval-gated actions", () => {
    const supplyAction = findActionById(
      defaultManufacturingActionRegistry,
      "request_supplier_expedite",
    );

    expect(buildActionRunIdempotencyKey(defaultManufacturingActionRegistry, supplyAction)).toBe(
      "tenant_demo_manufacturing:request_supplier_expedite:appr_expedite_supplier_batch",
    );
  });

  it("formats action run workflow signal status for persisted results", () => {
    expect(
      actionRunWorkflowSignalLabel({
        workflow_signal_status: "action_signal_requested",
        workflow_signal: {
          adapter: "axis-temporal-adapter",
          signal_name: "action_requested",
        },
      }),
    ).toBe("action_signal_requested via axis-temporal-adapter / action_requested");

    expect(actionRunWorkflowSignalLabel({ workflow_signal_status: "not_required" })).toBe(
      "workflow signal not required",
    );
  });
});
