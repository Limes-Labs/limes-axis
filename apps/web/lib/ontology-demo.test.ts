import { describe, expect, it } from "vitest";

import {
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
});
