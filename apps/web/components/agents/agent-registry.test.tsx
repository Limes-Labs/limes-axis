import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ManufacturingAgentRegistry } from "@/lib/agent-demo";

import { agentRegistryFixture } from "./agents-fixtures";

const mocks = vi.hoisted(() => ({
  axisFetchJson: vi.fn(),
  useAxisQuery: vi.fn(),
}));

vi.mock("@/lib/axis-api", () => ({
  axisFetchJson: mocks.axisFetchJson,
}));

vi.mock("@/lib/use-axis-query", () => ({
  useAxisQuery: mocks.useAxisQuery,
}));

vi.mock("@/lib/use-oidc-session", () => ({
  useOidcConsoleSession: () => ({ session: null }),
}));

import { AgentRegistry } from "../agent-registry";

function queryResult(result: {
  data: unknown;
  source: "loading" | "api" | "unavailable";
}) {
  return {
    data: result.data,
    source: result.source,
    error: result.source === "unavailable" ? "Axis API request failed." : null,
    isRefreshing: false,
    isLoading: result.source === "loading",
    isUnavailable: result.source === "unavailable",
  };
}

function mockRegistry(result: {
  data: ManufacturingAgentRegistry | null;
  source: "loading" | "api" | "unavailable";
}) {
  mocks.useAxisQuery.mockImplementation((path: string) => {
    if (path === "/demo/manufacturing/agents") {
      return queryResult(result);
    }
    return queryResult({ data: null, source: "loading" });
  });
}

beforeEach(() => {
  mocks.axisFetchJson.mockReset();
  mocks.useAxisQuery.mockReset();
});

describe("AgentRegistry states", () => {
  it("renders a loading skeleton without any error copy while loading", () => {
    mockRegistry({ data: null, source: "loading" });
    render(<AgentRegistry />);

    expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
    expect(screen.queryByText(/unavailable/i)).not.toBeInTheDocument();
  });

  it("renders the ErrorPanel when the agent API is unavailable", () => {
    mockRegistry({ data: null, source: "unavailable" });
    render(<AgentRegistry />);

    expect(
      screen.getByRole("heading", { name: "Agent API unavailable" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Local fallback agent records are disabled\./),
    ).toBeInTheDocument();
    // Endpoint stays demoted behind the technical-details expander.
    expect(screen.queryByText("/demo/manufacturing/agents")).not.toBeInTheDocument();
  });

  it("renders the EmptyPanel when the API responds with zero agents", () => {
    mockRegistry({
      data: {
        ...agentRegistryFixture,
        agents: [],
        metrics: [],
      },
      source: "api",
    });
    render(<AgentRegistry />);

    expect(
      screen.getByRole("heading", { name: "No agents registered yet" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/unavailable/i)).not.toBeInTheDocument();
  });
});

describe("AgentRegistry list and filters", () => {
  beforeEach(() => {
    mockRegistry({ data: agentRegistryFixture, source: "api" });
  });

  it("lists agents with name, domain and autonomy level chip", () => {
    render(<AgentRegistry />);

    const supplyItem = screen.getByRole("button", { name: /Supply Risk Agent/ });
    expect(supplyItem).toHaveTextContent("Supply");
    expect(supplyItem).toHaveTextContent("L2");
    expect(screen.getByRole("button", { name: /Quality Hold Agent/ })).toHaveTextContent("L1");
  });

  it("switches the detail panel when a list item is selected", async () => {
    const user = userEvent.setup();
    render(<AgentRegistry />);

    expect(screen.getByRole("heading", { name: "Supply Risk Agent" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Quality Hold Agent/ }));
    expect(screen.getByRole("heading", { name: "Quality Hold Agent" })).toBeInTheDocument();
  });

  it("filters the list by domain", async () => {
    const user = userEvent.setup();
    render(<AgentRegistry />);

    await user.selectOptions(screen.getByLabelText("Domain"), "Quality");

    expect(screen.queryByRole("button", { name: /Supply Risk Agent/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Quality Hold Agent/ })).toBeInTheDocument();
  });

  it("shows a zero-results EmptyPanel with a working reset action", async () => {
    const user = userEvent.setup();
    render(<AgentRegistry />);

    await user.selectOptions(screen.getByLabelText("Domain"), "Quality");
    await user.selectOptions(screen.getByLabelText("Autonomy"), "L2");

    expect(
      screen.getByRole("heading", { name: "No agents match the current filters" }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Reset filters" }));
    expect(screen.getByRole("button", { name: /Supply Risk Agent/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Quality Hold Agent/ })).toBeInTheDocument();
  });
});
