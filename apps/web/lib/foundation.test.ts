import { describe, expect, it } from "vitest";

import { navigationItems, statusLabel } from "./foundation";

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

  it("labels the foundation statuses for pills", () => {
    expect(statusLabel("ready")).toBe("Ready");
    expect(statusLabel("guarded")).toBe("Guarded");
    expect(statusLabel("planned")).toBe("Planned");
  });
});
