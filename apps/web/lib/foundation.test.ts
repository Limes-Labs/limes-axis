import { describe, expect, it } from "vitest";

import { autonomyLevels, foundationMetrics, navigationItems } from "./foundation";

describe("foundation console contracts", () => {
  it("keeps the expected top-level sections addressable", () => {
    expect(navigationItems.map((item) => item.href)).toEqual([
      "/",
      "/approvals",
      "/workflows",
      "/agents",
      "/ontology",
      "/connectors",
      "/model-routing",
      "/policies",
      "/audit",
      "/simulation",
      "/tenants",
      "/settings",
    ]);
  });

  it("represents the full L0-L4 autonomy model", () => {
    expect(autonomyLevels.map((item) => item.level)).toEqual(["L0", "L1", "L2", "L3", "L4"]);
  });

  it("keeps model egress guarded by default", () => {
    expect(foundationMetrics).toContainEqual(
      expect.objectContaining({
        label: "Egress",
        value: "Closed",
        status: "guarded",
      }),
    );
  });
});
