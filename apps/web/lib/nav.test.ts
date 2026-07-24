import { describe, expect, it } from "vitest";

import { navGroups, navItems } from "./nav";

describe("grouped navigation model", () => {
  it("organizes the console into the four spec sections", () => {
    expect(navGroups.map((group) => group.label)).toEqual([
      "Operate",
      "Data & Models",
      "Governance",
      "Platform",
    ]);
  });

  it("keeps all 11 grouped console routes addressable exactly once", () => {
    const hrefs = navItems.map((item) => item.href);

    expect(hrefs).toHaveLength(11);
    expect(new Set(hrefs).size).toBe(11);
    expect([...hrefs].sort()).toEqual(
      [
        "/",
        "/agents",
        "/approvals",
        "/audit",
        "/connectors",
        "/model-routing",
        "/ontology",
        "/policies",
        "/simulation",
        "/tenants",
        "/workflows",
      ].sort(),
    );
  });

  it("leaves /settings out of the groups because the footer owns it", () => {
    // Listing it in both places would give the route two active states in the
    // sidebar at once.
    expect(navItems.map((item) => item.href)).not.toContain("/settings");
  });

  it("gives every item a unique icon", () => {
    const icons = navItems.map((item) => item.icon);

    expect(new Set(icons).size).toBe(icons.length);
  });

  it("reserves the badge slot for pending approvals", () => {
    const badged = navItems.filter((item) => item.badge);

    expect(badged).toEqual([
      expect.objectContaining({ href: "/approvals", badge: "approvals" }),
    ]);
  });
});
