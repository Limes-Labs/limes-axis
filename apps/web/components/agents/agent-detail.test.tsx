import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { glossary } from "@/lib/strings";

import {
  agentRunDetailFixture,
  agentRunListFixture,
  supplyAgentFixture,
} from "./agents-fixtures";

const mocks = vi.hoisted(() => ({
  useAxisQuery: vi.fn(),
}));

vi.mock("@/lib/use-axis-query", () => ({
  useAxisQuery: mocks.useAxisQuery,
}));

vi.mock("@/lib/use-oidc-session", () => ({
  useOidcConsoleSession: () => ({ session: null }),
}));

import { AgentDetail } from "./agent-detail";

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

beforeEach(() => {
  mocks.useAxisQuery.mockReset();
  mocks.useAxisQuery.mockImplementation((path: string) => {
    if (path.includes("/runs?")) {
      return queryResult({ data: agentRunListFixture, source: "api" });
    }
    if (path.includes("/runs/")) {
      return queryResult({ data: agentRunDetailFixture, source: "api" });
    }
    return queryResult({ data: null, source: "loading" });
  });
});

describe("AgentDetail tabs", () => {
  it("renders all four tabs with Overview active by default", () => {
    render(<AgentDetail agent={supplyAgentFixture} />);

    expect(screen.getByRole("tab", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Permissions & Guardrails" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Runs" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Evidence" })).toBeInTheDocument();

    // Overview content: owner and connected systems.
    expect(screen.getByText("plant-operations-owner")).toBeInTheDocument();
    expect(screen.getByText("Axis Audit")).toBeInTheDocument();
  });

  it("describes the policy boundary in plain language on the Overview tab", () => {
    render(<AgentDetail agent={supplyAgentFixture} />);

    // Plain-language boundary summary derived from policy_boundary fields.
    expect(
      screen.getByText(/data never leaves the platform/i),
    ).toBeInTheDocument();
    // The raw snake_case field names are not shown as primary copy.
    expect(screen.queryByText("model_policy")).not.toBeInTheDocument();
    expect(screen.queryByText("max_action_level")).not.toBeInTheDocument();
  });

  it("shows permissions as plain sentences with the raw scope demoted to mono", async () => {
    const user = userEvent.setup();
    render(<AgentDetail agent={supplyAgentFixture} />);

    await user.click(screen.getByRole("tab", { name: "Permissions & Guardrails" }));

    const panel = screen.getByRole("tabpanel");
    expect(within(panel).getByText("May decide supply approvals")).toBeInTheDocument();
    expect(within(panel).getByText("approvals:supply:decide")).toBeInTheDocument();
    expect(
      within(panel).getByText("Proposals only; execution requires owner approval."),
    ).toBeInTheDocument();
    expect(within(panel).getByText("Draft supplier expedite proposal")).toBeInTheDocument();
    expect(within(panel).getByText("Mutate supplier master data")).toBeInTheDocument();
  });

  it("links evidence records to workflows, approvals and audit on the Evidence tab", async () => {
    const user = userEvent.setup();
    render(<AgentDetail agent={supplyAgentFixture} />);

    await user.click(screen.getByRole("tab", { name: "Evidence" }));

    const panel = screen.getByRole("tabpanel");
    expect(within(panel).getByText("Request supplier expedite")).toBeInTheDocument();
    expect(within(panel).getByRole("link", { name: /wf_supply_fixture/ })).toHaveAttribute(
      "href",
      "/workflows",
    );
    expect(within(panel).getByRole("link", { name: /appr_supply_fixture/ })).toHaveAttribute(
      "href",
      "/approvals",
    );
    expect(
      within(panel).getByRole("link", { name: /audit_supply_fixture_event/ }),
    ).toHaveAttribute("href", "/audit?event_id=audit_supply_fixture_event");
  });
});

describe("AgentDetail runs tab", () => {
  it("only loads runs once the Runs tab is selected", async () => {
    const user = userEvent.setup();
    render(<AgentDetail agent={supplyAgentFixture} />);

    const runsPathCalls = () =>
      mocks.useAxisQuery.mock.calls.filter(([path]) => String(path).includes("/runs"));
    expect(runsPathCalls()).toHaveLength(0);
    expect(screen.queryByText("run_fixture_001")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Runs" }));

    expect(runsPathCalls().length).toBeGreaterThan(0);
    expect(await screen.findByText("run_fixture_001")).toBeInTheDocument();
    // The persisted step rail renders from the run detail record.
    expect(screen.getByText("Context read")).toBeInTheDocument();
    expect(screen.getByText("Model call")).toBeInTheDocument();
    expect(screen.getByText("Proposal")).toBeInTheDocument();
  });

  it("renders the EmptyPanel when the API returns zero runs", async () => {
    mocks.useAxisQuery.mockImplementation((path: string) => {
      if (path.includes("/runs?")) {
        return queryResult({
          data: { ...agentRunListFixture, runs: [] },
          source: "api",
        });
      }
      return queryResult({ data: null, source: "loading" });
    });
    const user = userEvent.setup();
    render(<AgentDetail agent={supplyAgentFixture} />);

    await user.click(screen.getByRole("tab", { name: "Runs" }));

    expect(
      screen.getByRole("heading", { name: "No runs recorded yet" }),
    ).toBeInTheDocument();
  });

  it("renders the ErrorPanel when the runs API is unavailable", async () => {
    mocks.useAxisQuery.mockImplementation((path: string) => {
      if (path.includes("/runs?")) {
        return queryResult({ data: null, source: "unavailable" });
      }
      return queryResult({ data: null, source: "loading" });
    });
    const user = userEvent.setup();
    render(<AgentDetail agent={supplyAgentFixture} />);

    await user.click(screen.getByRole("tab", { name: "Runs" }));

    expect(
      screen.getByRole("heading", { name: "Agent runs API unavailable" }),
    ).toBeInTheDocument();
  });
});

describe("AgentDetail glossary and inspect drawer", () => {
  it("explains the autonomy level through the glossary tooltip", async () => {
    const user = userEvent.setup();
    render(<AgentDetail agent={supplyAgentFixture} />);

    const term = screen.getByText("Autonomy level");
    await user.hover(term);
    const matches = await screen.findAllByText(glossary.autonomy_level.definition);
    expect(matches.length).toBeGreaterThan(0);
  });

  it("opens the InspectDrawer with the raw snake_case record fields", async () => {
    const user = userEvent.setup();
    render(<AgentDetail agent={supplyAgentFixture} />);

    await user.click(screen.getByRole("button", { name: "Inspect raw record" }));

    expect(await screen.findByText("policy_boundary.model_policy")).toBeInTheDocument();
    expect(screen.getByText("no-external-egress")).toBeInTheDocument();
    expect(screen.getByText("policy_boundary.max_action_level")).toBeInTheDocument();
  });
});
