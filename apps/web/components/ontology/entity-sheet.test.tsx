import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { buildOntologyEntityDetail } from "@/lib/ontology-demo";

import { ontologyFixture } from "./ontology-fixtures";

const mocks = vi.hoisted(() => ({
  useAxisQuery: vi.fn(),
  axisFetch: vi.fn(),
  refreshNonce: 0,
}));

vi.mock("@/lib/use-axis-query", () => ({
  useAxisQuery: mocks.useAxisQuery,
}));

vi.mock("@/lib/axis-api", () => ({
  axisFetch: mocks.axisFetch,
  decodeAxisJson: (_path: string, body: unknown, decoder: (value: unknown) => unknown) =>
    decoder(body),
}));

vi.mock("@/lib/use-oidc-session", () => ({
  useOidcConsoleSession: () => ({ session: null }),
}));

vi.mock("@/providers/console-provider", () => ({
  useConsole: () => ({ refreshNonce: mocks.refreshNonce }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import { OntologyExplorer } from "../ontology-explorer";
import { OntologyEntitySheet } from "./entity-sheet";

const entityDetail = buildOntologyEntityDetail(ontologyFixture, "asset_line_2");
if (!entityDetail) {
  throw new Error("fixture entity missing");
}

function fulfillEntity() {
  mocks.axisFetch.mockResolvedValue({
    headers: { get: () => null },
    ok: true,
    status: 200,
    json: async () => entityDetail,
  });
}

beforeEach(() => {
  mocks.axisFetch.mockReset();
  mocks.refreshNonce = 0;
});

describe("OntologyEntitySheet", () => {
  it("renders nothing (and fetches nothing) while closed", () => {
    render(<OntologyEntitySheet nodeId={null} onOpenChange={vi.fn()} />);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(mocks.axisFetch).not.toHaveBeenCalled();
  });

  it("shows the entity detail with an 'Open full page' deep link", async () => {
    fulfillEntity();

    render(<OntologyEntitySheet nodeId="asset_line_2" onOpenChange={vi.fn()} />);

    const dialog = await screen.findByRole("dialog");
    expect(
      await within(dialog).findByRole("heading", { name: "Line 2 Packaging" }),
    ).toBeInTheDocument();
    expect(within(dialog).getByRole("link", { name: /Open full page/ })).toHaveAttribute(
      "href",
      "/ontology/asset_line_2",
    );
    // The presentational entity core renders inside the sheet.
    expect(within(dialog).getByText("Read-only entity context")).toBeInTheDocument();
    expect(within(dialog).getByText(/connected$/)).toBeInTheDocument();
    expect(mocks.axisFetch).toHaveBeenCalledWith(
      "/demo/manufacturing/ontology/entities/asset_line_2",
      expect.anything(),
    );
  });

  it("swaps to a peer entity in place instead of navigating", async () => {
    fulfillEntity();
    const onNavigateToNode = vi.fn();

    render(
      <OntologyEntitySheet
        nodeId="asset_line_2"
        onNavigateToNode={onNavigateToNode}
        onOpenChange={vi.fn()}
      />,
    );

    const dialog = await screen.findByRole("dialog");
    await userEvent.click(await within(dialog).findByRole("button", { name: "Fixture Plant" }));

    expect(onNavigateToNode).toHaveBeenCalledWith("org_fixture_plant");
  });

  it("shows the error state when the entity API is unavailable", async () => {
    mocks.axisFetch.mockRejectedValue(new Error("api down"));

    render(<OntologyEntitySheet nodeId="asset_line_2" onOpenChange={vi.fn()} />);

    expect(
      await screen.findByRole("heading", { name: "Entity API unavailable" }),
    ).toBeInTheDocument();
  });

  it("keeps validated entity data visible when a refresh fails", async () => {
    fulfillEntity();
    const { rerender } = render(
      <OntologyEntitySheet nodeId="asset_line_2" onOpenChange={vi.fn()} />,
    );
    expect(
      await screen.findByRole("heading", { name: "Line 2 Packaging" }),
    ).toBeInTheDocument();

    mocks.axisFetch.mockRejectedValueOnce(new Error("refresh failed"));
    mocks.refreshNonce = 1;
    rerender(<OntologyEntitySheet nodeId="asset_line_2" onOpenChange={vi.fn()} />);

    expect(
      await screen.findByText("Live refresh failed. Showing the last validated entity data."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Line 2 Packaging" })).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Entity API unavailable" }),
    ).not.toBeInTheDocument();
  });

  it("shows the not-found state for a 404", async () => {
    mocks.axisFetch.mockResolvedValue({ ok: false, status: 404, json: async () => ({}) });

    render(<OntologyEntitySheet nodeId="ghost_node" onOpenChange={vi.fn()} />);

    expect(await screen.findByRole("heading", { name: "Entity not found" })).toBeInTheDocument();
  });
});

describe("OntologyExplorer entity slide-over", () => {
  it("opens from graph node activation and preserves graph state on close", async () => {
    mocks.useAxisQuery.mockReturnValue({ data: ontologyFixture, source: "api" });
    fulfillEntity();

    render(<OntologyExplorer />);

    // Zoom in so we can assert the graph view survives the sheet round trip.
    const svg = screen.getByTestId("ontology-graph");
    const initialViewBox = svg.getAttribute("viewBox");
    await userEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    const zoomedViewBox = svg.getAttribute("viewBox");
    expect(zoomedViewBox).not.toBe(initialViewBox);

    await userEvent.click(screen.getByRole("link", { name: /Line 2 Packaging — Asset/ }));

    const dialog = await screen.findByRole("dialog");
    expect(
      await within(dialog).findByRole("heading", { name: "Line 2 Packaging" }),
    ).toBeInTheDocument();

    await userEvent.click(within(dialog).getByRole("button", { name: "Close" }));

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    // No navigation happened and the zoomed view is still applied.
    expect(screen.getByTestId("ontology-graph").getAttribute("viewBox")).toBe(zoomedViewBox);
  });

  it("opens from a list row without navigating", async () => {
    mocks.useAxisQuery.mockReturnValue({ data: ontologyFixture, source: "api" });
    fulfillEntity();

    render(<OntologyExplorer />);

    await userEvent.click(screen.getByRole("button", { name: "List" }));
    const nodesTable = screen.getByRole("table", { name: "Ontology nodes" });
    await userEvent.click(within(nodesTable).getByRole("button", { name: "Line 2 Packaging" }));

    const dialog = await screen.findByRole("dialog");
    expect(
      await within(dialog).findByRole("heading", { name: "Line 2 Packaging" }),
    ).toBeInTheDocument();
  });
});
