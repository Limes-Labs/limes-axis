import { describe, expect, it } from "vitest";

import {
  allAgentFilter,
  countPendingAgentProposals,
  defaultManufacturingAgentRegistry,
  filterAgents,
  findAgentById,
  formatAgentLabel,
} from "./agent-demo";

describe("manufacturing agent registry demo contract", () => {
  it("keeps a public-safe agent registry seed available without the API", () => {
    expect(defaultManufacturingAgentRegistry.scenario).toBe("Plant Operations Cockpit");
    expect(defaultManufacturingAgentRegistry.plant_name).toBe("Ravenna Works");
    expect(defaultManufacturingAgentRegistry.agents).toHaveLength(4);
    expect(JSON.stringify(defaultManufacturingAgentRegistry)).not.toContain("@");
    expect(JSON.stringify(defaultManufacturingAgentRegistry).toLowerCase()).not.toContain("secret");
  });

  it("keeps every agent inside an explicit policy boundary", () => {
    for (const agent of defaultManufacturingAgentRegistry.agents) {
      expect(agent.policy_boundary.autonomy_level).toMatch(/^L[0-4]$/);
      expect(agent.policy_boundary.external_egress_allowed).toBe(false);
      expect(agent.policy_boundary.required_permissions.length).toBeGreaterThan(0);
      expect(agent.policy_boundary.guardrails.length).toBeGreaterThan(0);
      expect(agent.connected_systems.length).toBeGreaterThan(0);
    }
  });

  it("exposes filter options for domain, autonomy and status", () => {
    expect(defaultManufacturingAgentRegistry.filter_options.domains).toContain("Supply");
    expect(defaultManufacturingAgentRegistry.filter_options.autonomy_levels).toEqual(["L1", "L2"]);
    expect(defaultManufacturingAgentRegistry.filter_options.statuses).toContain(
      "waiting_for_approval",
    );
  });

  it("filters agents locally", () => {
    const agents = filterAgents(defaultManufacturingAgentRegistry, {
      domain: "Supply",
      autonomyLevel: "L2",
      status: "waiting_for_approval",
    });

    expect(agents).toHaveLength(1);
    expect(agents[0].agent_id).toBe("agent_supply_risk");
  });

  it("keeps all agents when filters are set to all", () => {
    expect(
      filterAgents(defaultManufacturingAgentRegistry, {
        domain: allAgentFilter,
        autonomyLevel: allAgentFilter,
        status: allAgentFilter,
      }),
    ).toHaveLength(defaultManufacturingAgentRegistry.agents.length);
  });

  it("finds agents by id with a safe fallback", () => {
    expect(findAgentById(defaultManufacturingAgentRegistry, "agent_quality_risk").name).toBe(
      "Quality Risk Agent",
    );
    expect(findAgentById(defaultManufacturingAgentRegistry, "missing").name).toBe(
      "Daily Brief Agent",
    );
  });

  it("counts proposals and formats labels", () => {
    expect(countPendingAgentProposals(defaultManufacturingAgentRegistry)).toBe(4);
    expect(formatAgentLabel("waiting_for_approval")).toBe("Waiting For Approval");
    expect(formatAgentLabel("approvals:supply:request")).toBe("Approvals Supply Request");
  });
});
