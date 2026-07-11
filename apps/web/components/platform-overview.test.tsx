import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";

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

vi.mock("@/providers/console-provider", () => ({
  useConsole: () => ({
    apiBaseUrl: "http://localhost:8000",
    apiStatus: { state: "ready", label: "ready", detail: "" },
    refreshNonce: 0,
    triggerRefresh: vi.fn(),
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

function queryResult(data: unknown, source: Source) {
  return {
    data,
    source,
    error: source === "unavailable" ? "Axis API request failed." : null,
    isRefreshing: false,
    isLoading: source === "loading",
    isUnavailable: source === "unavailable",
  };
}

/** Route the per-path mock so each endpoint can succeed or fail independently. */
function mockQueriesByPath(unavailablePaths: string[] = []) {
  const fixtures: [string, unknown][] = [
    ["/demo/manufacturing/overview", overviewFixture],
    ["/demo/manufacturing/operations/snapshot", snapshotFixture],
    ["/demo/manufacturing/model-routing", modelRoutingFixture],
    ["/demo/manufacturing/audit/events", auditEventsFixture],
    ["/demo/manufacturing/approvals", approvalInboxFixture],
    ["/platform/policies", policyRegistryFixture],
    ["/identity/session", identitySessionFixture],
  ];

  mocks.useAxisQuery.mockImplementation((path: string) => {
    const match = fixtures.find(([prefix]) => path.startsWith(prefix));
    if (!match) {
      throw new Error(`Unexpected overview query path: ${path}`);
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
  mocks.axisFetchJson.mockReset();
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
