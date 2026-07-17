import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";

const mocks = vi.hoisted(() => ({
  axisFetchParsedJson: vi.fn(),
  triggerRefresh: vi.fn(),
  useAxisQuery: vi.fn(),
}));

vi.mock("@/lib/axis-api", () => ({
  axisFetchParsedJson: mocks.axisFetchParsedJson,
}));

vi.mock("@/lib/use-axis-query", () => ({
  useAxisQuery: mocks.useAxisQuery,
}));

vi.mock("@/lib/use-oidc-session", () => ({
  useOidcConsoleSession: () => ({ session: null }),
}));

vi.mock("@/providers/console-provider", () => ({
  useConsole: () => ({
    apiBaseUrl: "http://localhost:8000",
    apiStatus: { state: "ready", label: "ready", detail: "" },
    refreshNonce: 0,
    triggerRefresh: mocks.triggerRefresh,
  }),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

import { PlatformOverview } from "./platform-overview";
import {
  approvalInboxFixture,
  auditEventsFixture,
  identitySessionFixture,
  modelRoutingFixture,
  overviewFixture,
  policyRegistryFixture,
  snapshotFixture,
} from "./overview/overview-fixtures";

type Source = "loading" | "api" | "unavailable";

function queryResult(data: unknown, source: Source, errorStatus: number | null = null) {
  return {
    data,
    source,
    error: source === "unavailable" ? "Axis API request failed." : null,
    errorStatus,
    isRefreshing: false,
    isLoading: source === "loading",
    isUnavailable: source === "unavailable",
  };
}

/** Count-bearing registry payloads that drive the onboarding checklist. */
function onboardingRegistryFixtures(count: number): [string, unknown][] {
  const items = (key: string) => Array.from({ length: count }, (_, i) => ({ [key]: `${key}${i}` }));
  return [
    ["/demo/manufacturing/connectors", { connectors: items("connector_id") }],
    ["/demo/manufacturing/ontology", { nodes: items("node_id") }],
    ["/demo/manufacturing/agents", { agents: items("agent_id") }],
    ["/demo/manufacturing/workflows", { workflow_runs: items("workflow_id") }],
  ];
}

type MockOptions = {
  /** Endpoints answering 404 (tenant not bootstrapped) instead of failing. */
  notFoundPaths?: string[];
  /** Overrides every checklist registry count, including /platform/policies. */
  onboardingCount?: number;
};

/** Route the per-path mock so each endpoint can succeed or fail independently. */
function mockQueriesByPath(unavailablePaths: string[] = [], options: MockOptions = {}) {
  const fixtures: [string, unknown][] = [
    ...(options.onboardingCount !== undefined
      ? ([
          [
            "/platform/policies",
            {
              ...policyRegistryFixture,
              policy_count: options.onboardingCount,
              active_policy_count: options.onboardingCount,
            },
          ],
        ] as [string, unknown][])
      : []),
    ["/demo/manufacturing/overview", overviewFixture],
    ["/demo/manufacturing/operations/snapshot", snapshotFixture],
    ["/demo/manufacturing/model-routing", modelRoutingFixture],
    ["/demo/manufacturing/audit/events", auditEventsFixture],
    ["/demo/manufacturing/approvals", approvalInboxFixture],
    ["/platform/policies", policyRegistryFixture],
    ["/identity/session", identitySessionFixture],
    ...onboardingRegistryFixtures(options.onboardingCount ?? 1),
  ];

  mocks.useAxisQuery.mockImplementation((path: string) => {
    const match = fixtures.find(([prefix]) => path.startsWith(prefix));
    if (!match) {
      throw new Error(`Unexpected overview query path: ${path}`);
    }
    if (options.notFoundPaths?.some((prefix) => path.startsWith(prefix))) {
      return queryResult(null, "unavailable", 404);
    }
    if (unavailablePaths.some((prefix) => path.startsWith(prefix))) {
      return queryResult(null, "unavailable");
    }
    return queryResult(match[1], "api");
  });
}

function renderOverview() {
  return render(
    <ToastProvider>
      <PlatformOverview />
    </ToastProvider>,
  );
}

beforeEach(() => {
  mocks.axisFetchParsedJson.mockReset();
  mocks.triggerRefresh.mockReset();
  mocks.useAxisQuery.mockReset();
});

describe("PlatformOverview hero", () => {
  it("renders the cockpit name exactly once, without the duplicated prefix", () => {
    mockQueriesByPath();
    renderOverview();

    expect(screen.getAllByText("Plant Operations Cockpit")).toHaveLength(1);
    expect(screen.queryByText(/Operations Plant Operations Cockpit/)).not.toBeInTheDocument();
  });

  it("shows the same audit registry count in the hero and the evidence feed", () => {
    mockQueriesByPath();
    renderOverview();

    const heroCount = screen.getByTestId("hero-audit-count");
    expect(heroCount).toHaveTextContent(/^4$/);
    expect(screen.getByText("4 recent events")).toBeInTheDocument();
    // The static seeded "Audit" metric string never renders anywhere.
    expect(screen.queryByText(/128 events/)).not.toBeInTheDocument();
  });
});

describe("PlatformOverview per-section degradation", () => {
  it("keeps the evidence feed and posture cards when the overview endpoint fails", () => {
    mockQueriesByPath(["/demo/manufacturing/overview"]);
    renderOverview();

    expect(
      screen.getByRole("heading", { name: "Operations API unavailable" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Approval Decision Recorded/ }),
    ).toBeInTheDocument();
    const modelsCard = screen
      .getAllByRole("listitem")
      .find((item) => within(item).queryByText("Models"));
    expect(modelsCard).toBeDefined();
    expect(within(modelsCard as HTMLElement).getByText("2")).toBeInTheDocument();
  });

  it("keeps the hero and needs-attention strip when the audit endpoint fails", () => {
    mockQueriesByPath(["/demo/manufacturing/audit/events"]);
    renderOverview();

    expect(screen.getByText("Plant Operations Cockpit")).toBeInTheDocument();
    expect(screen.getByText("Expedite supplier batch")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Audit evidence API unavailable" }),
    ).toBeInTheDocument();
  });

  it("shows section-level error panels when every endpoint fails", () => {
    mockQueriesByPath([
      "/demo/manufacturing",
      "/platform/policies",
      "/identity/session",
    ]);
    renderOverview();

    expect(
      screen.getByRole("heading", { name: "Operations API unavailable" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Audit evidence API unavailable" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Attention items unavailable" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Local fallback overview records are disabled.", { exact: false }),
    ).toBeInTheDocument();
  });
});

describe("PlatformOverview onboarding checklist", () => {
  it("replaces the control room with the setup checklist when the overview 404s on a healthy API", () => {
    mockQueriesByPath([], {
      notFoundPaths: ["/demo/manufacturing/overview"],
      onboardingCount: 0,
    });
    renderOverview();

    expect(
      screen.getByRole("heading", { name: "Set up your governed platform" }),
    ).toBeInTheDocument();
    expect(screen.getByText("0 of 5 setup steps complete")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open connectors" })).toHaveAttribute(
      "href",
      "/connectors",
    );
    // No error wall: the 404 means "not bootstrapped", not "API down".
    expect(
      screen.queryByRole("heading", { name: "Operations API unavailable" }),
    ).not.toBeInTheDocument();
  });

  it("keeps the error wall when the API is down instead of showing the checklist", () => {
    mockQueriesByPath([
      "/demo/manufacturing",
      "/platform/policies",
      "/identity/session",
    ]);
    renderOverview();

    expect(
      screen.getByRole("heading", { name: "Operations API unavailable" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Set up your governed platform" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/setup steps complete/)).not.toBeInTheDocument();
  });

  it("shows the compact setup strip on the control room when onboarding is partial", () => {
    mockQueriesByPath(["/demo/manufacturing/ontology"]);
    renderOverview();

    expect(screen.getByText("4 of 5 setup steps complete")).toBeInTheDocument();
    // The control room still renders around the strip.
    expect(screen.getByText("Plant Operations Cockpit")).toBeInTheDocument();
  });

  it("hides the checklist entirely once every setup step is complete", () => {
    mockQueriesByPath();
    renderOverview();

    expect(screen.queryByText(/setup steps complete/)).not.toBeInTheDocument();
  });
});

describe("PlatformOverview demo bootstrap CTA", () => {
  function renderEmptyTenant() {
    mockQueriesByPath([], {
      notFoundPaths: ["/demo/manufacturing/overview"],
      onboardingCount: 0,
    });
    return renderOverview();
  }

  it("POSTs the bootstrap request, toasts, and refreshes the console on success", async () => {
    mocks.axisFetchParsedJson.mockResolvedValue({
      tenant_id: "tenant_demo_manufacturing",
      scenario: "Plant Operations Cockpit",
      plant_name: "Ravenna Works",
      bootstrapped: true,
      surfaces: [],
      audit_event_id: "11111111-1111-4111-8111-111111111111",
      idempotent_replay: false,
    });
    const user = userEvent.setup();
    renderEmptyTenant();

    const demoButton = screen.getByRole("button", { name: "Explore with demo data" });
    expect(demoButton).toBeEnabled();
    await user.click(demoButton);

    expect(mocks.axisFetchParsedJson).toHaveBeenCalledTimes(1);
    const [endpoint, , options] = mocks.axisFetchParsedJson.mock.calls[0];
    expect(endpoint).toBe("/demo/manufacturing/bootstrap");
    expect(options).toMatchObject({
      method: "POST",
      body: {
        tenant_id: "tenant_demo_manufacturing",
        actor_scopes: ["demo:scenario:bootstrap"],
      },
    });
    expect((options as { body: { requested_by: string } }).body.requested_by).toBeTruthy();

    expect(await screen.findByText("Demo data loaded")).toBeInTheDocument();
    expect(mocks.triggerRefresh).toHaveBeenCalledTimes(1);
  });

  it("renders the bootstrap failure inline on the checklist without refreshing", async () => {
    mocks.axisFetchParsedJson.mockRejectedValue(new Error("Axis API request failed with 403"));
    const user = userEvent.setup();
    renderEmptyTenant();

    await user.click(screen.getByRole("button", { name: "Explore with demo data" }));

    expect(await screen.findByText("Axis API request failed with 403")).toBeInTheDocument();
    expect(mocks.triggerRefresh).not.toHaveBeenCalled();
    expect(screen.queryByText("Demo data loaded")).not.toBeInTheDocument();
    // The checklist stays actionable for a retry.
    expect(screen.getByRole("button", { name: "Explore with demo data" })).toBeEnabled();
  });
});

describe("PlatformOverview dropped surfaces", () => {
  it("no longer renders the demo-readiness, domain-graph, or routing-strip panels", () => {
    mockQueriesByPath();
    renderOverview();

    expect(screen.queryByText("Feedback environment")).not.toBeInTheDocument();
    expect(screen.queryByText("Domain graph")).not.toBeInTheDocument();
    expect(screen.queryByText("Persisted routing posture")).not.toBeInTheDocument();
    expect(screen.queryByText(/records across/)).not.toBeInTheDocument();
  });
});
