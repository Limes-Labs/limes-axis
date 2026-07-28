import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/components/console-page", () => ({
  ConsolePage: ({ children }: { children: ReactNode }) => <main>{children}</main>,
}));

vi.mock("@/components/ontology-entity-detail", () => ({
  OntologyEntityDetail: ({ nodeId }: { nodeId: string }) => (
    <output data-testid="entity-node-id">{nodeId}</output>
  ),
}));

import OntologyEntityPage, { generateMetadata } from "./page";

function routeParams(nodeId: string) {
  return { params: Promise.resolve({ nodeId }) };
}

describe("ontology entity page route boundary", () => {
  it("passes the decoded opaque node ID to the full-page entity detail", async () => {
    render(
      await OntologyEntityPage(
        routeParams("%20node%2Fwith%3F%23%20"),
      ),
    );

    expect(screen.getByTestId("entity-node-id").textContent).toBe(" node/with?# ");
  });

  it("uses the decoded node ID in metadata", async () => {
    await expect(generateMetadata(routeParams("asset%2Fline%3F2"))).resolves.toEqual({
      title: "Entity asset/line?2",
    });
  });

  it("renders a malformed percent escape without throwing", async () => {
    render(await OntologyEntityPage(routeParams("node%E0%A4%A")));

    expect(screen.getByTestId("entity-node-id")).toHaveTextContent("node%E0%A4%A");
  });
});
