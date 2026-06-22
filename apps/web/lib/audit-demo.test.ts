import { describe, expect, it } from "vitest";

import {
  allAuditFilter,
  filterAuditEvents,
  findAuditEventById,
  formatAuditLabel,
  type ManufacturingAuditExplorer,
} from "./audit-demo";

const auditExplorerFixture: ManufacturingAuditExplorer = {
  tenant_id: "tenant_fixture",
  plant_name: "Fixture Plant",
  scenario: "Runtime contract fixture",
  as_of: "2026-06-22T09:00:00+02:00",
  ledger_status: "ready",
  metrics: [],
  filter_options: {
    tenants: ["tenant_fixture"],
    event_types: ["agent.proposal.created", "policy.egress.blocked"],
    scopes: ["wf_supply_fixture", "model_route_fixture"],
    actors: ["agent_supply_fixture", "model-router"],
    categories: ["agent", "policy"],
  },
  events: [
    {
      audit_event_id: "audit_supply_fixture",
      occurred_at: "2026-06-22T09:01:00+02:00",
      tenant_id: "tenant_fixture",
      actor_id: "agent_supply_fixture",
      actor_type: "agent",
      event_type: "agent.proposal.created",
      category: "agent",
      domain: "Supply",
      scope: "wf_supply_fixture",
      result: "pending_owner_review",
      severity: "watch",
      source: "axis-agent-runtime",
      summary: "Agent proposed a governed supply action.",
      permission_scope: "approvals:supply:request",
      data_classification: "internal",
      related_workflow_id: "wf_supply_fixture",
      related_approval_id: "appr_supply_fixture",
      related_agent_id: "agent_supply_fixture",
      evidence_refs: ["risk_supply_fixture"],
      payload_preview: { action_id: "expedite_fixture_batch" },
    },
    {
      audit_event_id: "audit_egress_fixture",
      occurred_at: "2026-06-22T09:02:00+02:00",
      tenant_id: "tenant_fixture",
      actor_id: "model-router",
      actor_type: "service",
      event_type: "policy.egress.blocked",
      category: "policy",
      domain: "Quality",
      scope: "model_route_fixture",
      result: "blocked",
      severity: "action_required",
      source: "axis-model-router",
      summary: "External model egress was blocked by policy.",
      permission_scope: "models:route",
      data_classification: "restricted",
      related_workflow_id: null,
      related_approval_id: null,
      related_agent_id: null,
      evidence_refs: ["route_quality_fixture"],
      payload_preview: { provider: "external-general-llm" },
    },
  ],
  retention_notes: ["Fixture data is scoped to tests."],
};

describe("audit explorer helpers", () => {
  it("filters events by tenant, event type and scope", () => {
    const events = filterAuditEvents(auditExplorerFixture, {
      tenant: "tenant_fixture",
      eventType: "agent.proposal.created",
      scope: "wf_supply_fixture",
    });

    expect(events).toHaveLength(1);
    expect(events[0].actor_id).toBe("agent_supply_fixture");
  });

  it("keeps all events when filters are set to all", () => {
    expect(
      filterAuditEvents(auditExplorerFixture, {
        tenant: allAuditFilter,
        eventType: allAuditFilter,
        scope: allAuditFilter,
      }),
    ).toHaveLength(auditExplorerFixture.events.length);
  });

  it("finds audit events by id with a safe fallback", () => {
    expect(findAuditEventById(auditExplorerFixture, "audit_egress_fixture").event_type).toBe(
      "policy.egress.blocked",
    );
    expect(findAuditEventById(auditExplorerFixture, "missing").event_type).toBe(
      "agent.proposal.created",
    );
  });

  it("formats audit labels", () => {
    expect(formatAuditLabel("policy.egress.blocked")).toBe("Policy Egress Blocked");
    expect(formatAuditLabel("approvals:supply:decide")).toBe("Approvals Supply Decide");
  });
});
