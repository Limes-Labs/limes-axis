import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ontologyFixture } from "./ontology/ontology-fixtures";

const mocks = vi.hoisted(() => ({
  useAxisQuery: vi.fn(),
  axisFetch: vi.fn(),
}));

vi.mock("@/lib/use-axis-query", () => ({
  useAxisQuery: mocks.useAxisQuery,
}));

vi.mock("@/lib/axis-api", () => ({
  axisFetch: mocks.axisFetch,
}));

vi.mock("@/lib/use-oidc-session", () => ({
  useOidcConsoleSession: () => ({ session: null }),
}));

vi.mock("@/providers/console-provider", () => ({
  useConsole: () => ({ refreshNonce: 0 }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

import { OntologyExplorer } from "./ontology-explorer";

describe("OntologyExplorer", () => {
  it("renders no per-type metric cards", () => {
    mocks.useAxisQuery.mockReturnValue({ data: ontologyFixture, source: "api" });

    render(<OntologyExplorer />);

    expect(screen.queryByText("Mapped demo ontology nodes")).not.toBeInTheDocument();
  });

  it("shows node-type counts inside the graph legend", () => {
    mocks.useAxisQuery.mockReturnValue({ data: ontologyFixture, source: "api" });

    render(<OntologyExplorer />);

    const legend = screen.getByLabelText("Ontology graph legend");
    expect(within(legend).getByText("Organization ×1")).toBeInTheDocument();
    expect(within(legend).getByText("Asset ×2")).toBeInTheDocument();
    expect(within(legend).getByText("Policy ×1")).toBeInTheDocument();
    // The existing legend markers stay in the same row.
    expect(within(legend).getByText("Entity")).toBeInTheDocument();
    expect(within(legend).getByText("Relation")).toBeInTheDocument();
  });

  it("zooms the graph with the +/− controls and resets the view", async () => {
    mocks.useAxisQuery.mockReturnValue({ data: ontologyFixture, source: "api" });

    render(<OntologyExplorer />);

    const svg = screen.getByTestId("ontology-graph");
    const initialViewBox = svg.getAttribute("viewBox");
    expect(initialViewBox).toBeTruthy();

    await userEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    expect(svg.getAttribute("viewBox")).not.toBe(initialViewBox);

    await userEvent.click(screen.getByRole("button", { name: "Zoom out" }));
    expect(svg.getAttribute("viewBox")).toBe(initialViewBox);

    await userEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    await userEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    await userEvent.click(screen.getByRole("button", { name: "Reset view" }));
    expect(svg.getAttribute("viewBox")).toBe(initialViewBox);
  });

  it("keeps the graph and list views working", async () => {
    mocks.useAxisQuery.mockReturnValue({ data: ontologyFixture, source: "api" });

    render(<OntologyExplorer />);

    expect(screen.getByTestId("ontology-graph")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "List" }));

    expect(screen.queryByTestId("ontology-graph")).not.toBeInTheDocument();
    const nodesTable = screen.getByRole("table", { name: "Ontology nodes" });
    expect(within(nodesTable).getByText("Line 2 Packaging")).toBeInTheDocument();
  });
});
