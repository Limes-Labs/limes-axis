import { describe, expect, it } from "vitest";

import {
  allModelRoutingFilter,
  countBlockedModelRoutes,
  defaultManufacturingModelRouting,
  filterModelRoutes,
  findModelRouteById,
  formatEuroCost,
  formatModelRoutingLabel,
  sumEstimatedModelCost,
} from "./model-routing-demo";

describe("manufacturing model routing demo contract", () => {
  it("keeps a public-safe routing seed available without the API", () => {
    expect(defaultManufacturingModelRouting.scenario).toBe("Plant Operations Cockpit");
    expect(defaultManufacturingModelRouting.plant_name).toBe("Ravenna Works");
    expect(defaultManufacturingModelRouting.routes).toHaveLength(4);
    expect(defaultManufacturingModelRouting.provider_options).toHaveLength(3);
    expect(JSON.stringify(defaultManufacturingModelRouting)).not.toContain("@");
    expect(JSON.stringify(defaultManufacturingModelRouting).toLowerCase()).not.toContain(
      "secret",
    );
  });

  it("keeps blocked external routes at zero estimated cost", () => {
    const blocked = defaultManufacturingModelRouting.routes.filter(
      (route) => route.egress_decision === "blocked_by_default",
    );

    expect(blocked).toHaveLength(1);
    expect(blocked[0].external_egress_requested).toBe(true);
    expect(blocked[0].external_egress_allowed).toBe(false);
    expect(blocked[0].estimated_cost_eur).toBe(0);
  });

  it("exposes filter options for domain, provider and decision", () => {
    expect(defaultManufacturingModelRouting.filter_options.domains).toContain("Quality");
    expect(defaultManufacturingModelRouting.filter_options.providers).toContain("local-vllm");
    expect(defaultManufacturingModelRouting.filter_options.egress_decisions).toContain(
      "blocked_by_default",
    );
  });

  it("filters route telemetry locally", () => {
    const routes = filterModelRoutes(defaultManufacturingModelRouting, {
      domain: "Quality",
      provider: "external-general-llm",
      decision: "blocked_by_default",
    });

    expect(routes).toHaveLength(1);
    expect(routes[0].route_id).toBe("route_quality_external_blocked");
  });

  it("keeps all routes when filters are set to all", () => {
    expect(
      filterModelRoutes(defaultManufacturingModelRouting, {
        domain: allModelRoutingFilter,
        provider: allModelRoutingFilter,
        decision: allModelRoutingFilter,
      }),
    ).toHaveLength(defaultManufacturingModelRouting.routes.length);
  });

  it("finds routes by id with a safe fallback", () => {
    expect(
      findModelRouteById(defaultManufacturingModelRouting, "route_supply_risk_local")
        .agent_name,
    ).toBe("Supply Risk Agent");
    expect(findModelRouteById(defaultManufacturingModelRouting, "missing").agent_name).toBe(
      "Daily Brief Agent",
    );
  });

  it("counts blocked routes and formats labels and cost", () => {
    expect(countBlockedModelRoutes(defaultManufacturingModelRouting)).toBe(1);
    expect(sumEstimatedModelCost(defaultManufacturingModelRouting)).toBeCloseTo(0.76);
    expect(formatModelRoutingLabel("approved_private_endpoint")).toBe(
      "Approved Private Endpoint",
    );
    expect(formatEuroCost(0)).toBe("EUR 0.00");
  });
});
