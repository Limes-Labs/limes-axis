import { describe, expect, it } from "vitest";

import {
  allAuditFilter,
  defaultAuditExportBundle,
  defaultManufacturingAuditExplorer,
  filterAuditEvents,
  findAuditEventById,
  formatAuditLabel,
} from "./audit-demo";

describe("manufacturing audit explorer demo contract", () => {
  it("keeps a public-safe audit seed available without the API", () => {
    expect(defaultManufacturingAuditExplorer.scenario).toBe("Plant Operations Cockpit");
    expect(defaultManufacturingAuditExplorer.plant_name).toBe("Ravenna Works");
    expect(defaultManufacturingAuditExplorer.events).toHaveLength(9);
    expect(JSON.stringify(defaultManufacturingAuditExplorer)).not.toContain("@");
    expect(JSON.stringify(defaultManufacturingAuditExplorer).toLowerCase()).not.toContain("secret");
  });

  it("exposes tenant, event and scope filter options", () => {
    expect(defaultManufacturingAuditExplorer.filter_options.tenants).toEqual([
      "tenant_demo_manufacturing",
    ]);
    expect(defaultManufacturingAuditExplorer.filter_options.event_types).toContain(
      "agent.proposal.created",
    );
    expect(defaultManufacturingAuditExplorer.filter_options.scopes).toContain(
      "wf_supplier_delay_review",
    );
  });

  it("filters events by tenant, event type and scope", () => {
    const events = filterAuditEvents(defaultManufacturingAuditExplorer, {
      tenant: "tenant_demo_manufacturing",
      eventType: "agent.proposal.created",
      scope: "wf_supplier_delay_review",
    });

    expect(events).toHaveLength(1);
    expect(events[0].actor_id).toBe("supply-risk-agent");
  });

  it("keeps all events when filters are set to all", () => {
    expect(
      filterAuditEvents(defaultManufacturingAuditExplorer, {
        tenant: allAuditFilter,
        eventType: allAuditFilter,
        scope: allAuditFilter,
      }),
    ).toHaveLength(defaultManufacturingAuditExplorer.events.length);
  });

  it("finds audit events by id with a safe fallback", () => {
    expect(
      findAuditEventById(
        defaultManufacturingAuditExplorer,
        "audit_20260621_133900_egress_blocked",
      ).event_type,
    ).toBe("policy.egress.blocked");
    expect(findAuditEventById(defaultManufacturingAuditExplorer, "missing").event_type).toBe(
      "workflow.started",
    );
  });

  it("formats audit labels", () => {
    expect(formatAuditLabel("policy.egress.blocked")).toBe("Policy Egress Blocked");
    expect(formatAuditLabel("approvals:supply:decide")).toBe("Approvals Supply Decide");
  });

  it("keeps a public-safe audit export bundle available without the API", () => {
    expect(defaultAuditExportBundle.tenant_id).toBe("tenant_demo_manufacturing");
    expect(defaultAuditExportBundle.manifest.record_count).toBe(
      defaultManufacturingAuditExplorer.events.length,
    );
    expect(defaultAuditExportBundle.retention_policy.retention_days).toBe(365);
    expect(defaultAuditExportBundle.retention_policy.export_requires_review).toBe(true);
    expect(defaultAuditExportBundle.manifest.retention_enforced).toBe(true);
    expect(defaultAuditExportBundle.manifest.excluded_record_count).toBe(0);
    expect(defaultAuditExportBundle.integrity_proof.algorithm).toBe("sha256-hash-chain-v1");
    expect(defaultAuditExportBundle.manifest.integrity_chain_tip_sha256).toBe(
      defaultAuditExportBundle.integrity_proof.chain_tip_sha256,
    );
    expect(JSON.stringify(defaultAuditExportBundle)).not.toContain("@");
    expect(JSON.stringify(defaultAuditExportBundle).toLowerCase()).not.toContain("secret");
  });
});
