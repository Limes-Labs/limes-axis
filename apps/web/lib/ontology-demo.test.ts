import { describe, expect, it } from "vitest";

import {
  buildOntologyEntityDetail,
  countNodesByType,
  defaultManufacturingOntology,
  formatNodeType,
  nodeLabelById,
} from "./ontology-demo";

describe("manufacturing ontology demo contract", () => {
  it("keeps relationship endpoints resolvable", () => {
    const labels = nodeLabelById(defaultManufacturingOntology);

    expect(labels.get("asset_line_2_packaging")).toBe("Line 2 Packaging");
    expect(
      defaultManufacturingOntology.relationships.every(
        (relationship) =>
          labels.has(relationship.source_id) && labels.has(relationship.target_id),
      ),
    ).toBe(true);
  });

  it("tracks assets, risks, workflows, approvals and agents", () => {
    const counts = countNodesByType(defaultManufacturingOntology);

    expect(counts.get("asset")).toBeGreaterThanOrEqual(5);
    expect(counts.get("risk")).toBe(3);
    expect(counts.get("workflow")).toBe(3);
    expect(counts.get("approval")).toBe(2);
    expect(counts.get("agent")).toBe(2);
  });

  it("formats node type labels for the UI", () => {
    expect(formatNodeType("audit_event")).toBe("Audit Event");
    expect(formatNodeType("workflow")).toBe("Workflow");
  });

  it("builds connected entity detail pages from the graph seed", () => {
    const detail = buildOntologyEntityDetail(
      defaultManufacturingOntology,
      "asset_line_2_packaging",
    );

    expect(detail?.node.label).toBe("Line 2 Packaging");
    expect(detail?.inbound_count).toBe(2);
    expect(detail?.outbound_count).toBe(0);
    expect(detail?.required_permissions).toContain("operations:read");
    expect(detail?.required_permissions).toContain("supply:read");
    expect(detail?.evidence_refs).toContain("risk_supplier_delay");
    expect(
      detail?.connected_relationships.some(
        (relationship) => relationship.relationship.relation_type === "impacts",
      ),
    ).toBe(true);
  });

  it("returns null when a detail node is missing", () => {
    expect(buildOntologyEntityDetail(defaultManufacturingOntology, "missing")).toBeNull();
  });

  it("keeps entity detail public-safe", () => {
    const detail = buildOntologyEntityDetail(
      defaultManufacturingOntology,
      "risk_supplier_delay",
    );

    expect(JSON.stringify(detail)).not.toContain("@");
    expect(JSON.stringify(detail).toLowerCase()).not.toContain("secret");
    expect(detail?.related_workflows).toEqual(["wf_supplier_delay_review"]);
  });
});
