import { describe, expect, it } from "vitest";

import {
  buildOntologyEntityRoute,
  decodeOntologyEntityRouteParam,
} from "./ontology-routes";

describe("ontology entity routes", () => {
  it("round-trips an opaque ID containing path and query delimiters", () => {
    const nodeId = " node/with?# ";
    const route = buildOntologyEntityRoute(nodeId);

    expect(route).toBe("/ontology/%20node%2Fwith%3F%23%20");
    expect(decodeOntologyEntityRouteParam(route.slice("/ontology/".length))).toBe(nodeId);
  });

  it("decodes the dynamic route segment exactly once", () => {
    expect(decodeOntologyEntityRouteParam("node%252Fwith%2520escape")).toBe(
      "node%2Fwith%20escape",
    );
  });

  it("retains malformed percent escapes as an opaque ID", () => {
    expect(decodeOntologyEntityRouteParam("node%E0%A4%A")).toBe("node%E0%A4%A");
  });
});
