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

  it("keeps all 12 console routes addressable exactly once", () => {
    const hrefs = navItems.map((item) => item.href);

    expect(hrefs).toHaveLength(12);
    expect(new Set(hrefs).size).toBe(12);
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
        "/settings",
        "/simulation",
        "/tenants",
        "/workflows",
      ].sort(),
    );
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
