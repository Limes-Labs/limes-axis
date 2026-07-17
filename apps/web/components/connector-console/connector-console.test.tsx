import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  connectorEndpointFixtures,
  connectorRegistryFixture,
  manifestRegistryFixture,
} from "./connector-fixtures";

const mocks = vi.hoisted(() => ({
  axisFetch: vi.fn(),
  useAxisQuery: vi.fn(),
  triggerRefresh: vi.fn(),
}));

vi.mock("@/lib/axis-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/axis-api")>()),
  axisFetch: mocks.axisFetch,
}));

vi.mock("@/lib/use-axis-query", () => ({
  useAxisQuery: mocks.useAxisQuery,
}));

vi.mock("@/lib/use-oidc-session", () => ({
  useOidcConsoleSession: () => ({ session: null }),
}));

vi.mock("@/providers/console-provider", () => ({
  useConsole: () => ({
    refreshNonce: 0,
    triggerRefresh: mocks.triggerRefresh,
    apiBaseUrl: "http://localhost:8000",
    apiStatus: { state: "ok", label: "Ready", detail: "" },
  }),
}));

import { ToastProvider } from "@/components/ui/toast";
import { ConnectorConsole } from "./index";

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

/** Serve fixtures for every endpoint, with optional per-path overrides. */
function mockQueries(overrides: Record<string, { data: unknown; source: Source }> = {}) {
  mocks.useAxisQuery.mockImplementation((path: string) => {
    const override = overrides[path];
    if (override) {
      return queryResult(override.data, override.source);
    }
    if (path in connectorEndpointFixtures) {
      return queryResult(connectorEndpointFixtures[path], "api");
    }
    return queryResult(null, "loading");
  });
}

function renderConsole() {
  return render(
    <ToastProvider>
      <ConnectorConsole />
    </ToastProvider>,
  );
}

beforeEach(() => {
  mocks.axisFetch.mockReset();
  mocks.useAxisQuery.mockReset();
  mocks.triggerRefresh.mockReset();
  window.history.replaceState(null, "", "/connectors");
});

describe("ConnectorConsole states", () => {
  it("renders loading skeletons without error copy while the registry loads", () => {
    mockQueries({
      "/demo/manufacturing/connectors": { data: null, source: "loading" },
    });
    renderConsole();

    expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
    expect(screen.queryByText(/unavailable/i)).not.toBeInTheDocument();
  });

  it("renders the ErrorPanel when the registry API is unreachable", () => {
    mockQueries({
      "/demo/manufacturing/connectors": { data: null, source: "unavailable" },
    });
    renderConsole();

    expect(
      screen.getByRole("heading", { name: "Connector API unavailable" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Local fallback connector records are disabled\./),
    ).toBeInTheDocument();
  });

  it("renders the EmptyPanel with a wizard CTA when the registry has zero connectors", async () => {
    const user = userEvent.setup();
    mockQueries({
      "/demo/manufacturing/connectors": {
        data: { ...connectorRegistryFixture, connectors: [] },
        source: "api",
      },
      // A truly empty tenant has no persisted manifests either; a manifest
      // record alone would legitimately render as a connector entry.
      "/demo/manufacturing/connectors/manifests": {
        data: { ...manifestRegistryFixture, manifests: [] },
        source: "api",
      },
    });
    renderConsole();

    expect(screen.getByRole("heading", { name: "No connectors yet" })).toBeInTheDocument();
    expect(screen.queryByText(/unavailable/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Add your first connector" }));
    expect(screen.getByRole("dialog", { name: "Add connector" })).toBeInTheDocument();
  });
});

describe("ConnectorConsole metrics", () => {
  it("renders exactly the five user-relevant metrics from the registries", () => {
    mockQueries();
    renderConsole();

    const metrics = screen.getAllByRole("listitem");
    expect(metrics).toHaveLength(5);

    const labels = metrics.map(
      (metric) => within(metric).getAllByText(/.+/)[0].textContent,
    );
    expect(labels).toEqual([
      "Connectors",
      "Runs",
      "Pending proposals",
      "Egress policies",
      "Evidence issues",
    ]);
    expect(within(metrics[0]).getByText("2")).toBeInTheDocument();
    expect(within(metrics[1]).getByText("1")).toBeInTheDocument();
  });

  it("shows a placeholder value for a metric whose registry is unavailable", () => {
    mockQueries({
      "/demo/manufacturing/connectors/egress-policies": { data: null, source: "unavailable" },
    });
    renderConsole();

    const metrics = screen.getAllByRole("listitem");
    expect(within(metrics[3]).getByText("—")).toBeInTheDocument();
  });
});

describe("ConnectorConsole list and detail", () => {
  beforeEach(() => {
    mockQueries();
  });

  it("lists connectors and shows the selected connector's detail tabs", () => {
    renderConsole();

    expect(
      screen.getByRole("button", { name: /Manufacturing assets CSV/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Manufacturing assets CSV" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Data & Schema" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Runs" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Governance & Evidence" })).toBeInTheDocument();
  });

  it("switches the detail panel when another connector is selected", async () => {
    const user = userEvent.setup();
    renderConsole();

    await user.click(screen.getByRole("button", { name: /Operational mirror DB/ }));
    expect(
      screen.getByRole("heading", { name: "Operational mirror DB" }),
    ).toBeInTheDocument();
  });

  it("shows the registered manifest state on the overview tab", () => {
    renderConsole();

    expect(screen.getByText("Registered manifest")).toBeInTheDocument();
    expect(screen.getByText("Active Preview")).toBeInTheDocument();
  });

  it("renders the schema mapping and sample rows on the Data & Schema tab", async () => {
    const user = userEvent.setup();
    renderConsole();

    await user.click(screen.getByRole("tab", { name: "Data & Schema" }));

    const mapping = screen.getByRole("table", { name: "Field mapping" });
    expect(within(mapping).getByText("asset_id")).toBeInTheDocument();
    expect(within(mapping).getAllByText("manufacturing_asset").length).toBeGreaterThan(0);

    const sample = screen.getByRole("table", { name: "Sample rows" });
    expect(within(sample).getByText("CNC Mill")).toBeInTheDocument();
  });

  it("renders governance records with plain sections instead of metric tiles", async () => {
    const user = userEvent.setup();
    renderConsole();

    await user.click(screen.getByRole("tab", { name: "Governance & Evidence" }));

    expect(screen.getByText("Credential handles")).toBeInTheDocument();
    expect(screen.getByText("CSV read-only handle")).toBeInTheDocument();
    expect(screen.getByText("Credential leases")).toBeInTheDocument();
    // "Egress policies" appears both as a metric label and a governance section.
    expect(screen.getAllByText("Egress policies")).toHaveLength(2);
    // The db-scoped egress policy does not belong to the selected CSV connector.
    expect(
      screen.getByText("No egress policies are recorded for this connector."),
    ).toBeInTheDocument();
    expect(screen.getByText("Evidence invariants")).toBeInTheDocument();
    expect(
      screen.getByText(/Credential lease lease_csv_active has no linked audit event\./),
    ).toBeInTheDocument();
  });

  it("lists recorded runs for the selected connector on the Runs tab", async () => {
    const user = userEvent.setup();
    renderConsole();

    await user.click(screen.getByRole("tab", { name: "Runs" }));

    const runsTable = screen.getByRole("table", { name: "Governed runs" });
    expect(within(runsTable).getByText("run_seeded_1")).toBeInTheDocument();
    expect(within(runsTable).getByText("Sync Schedule Deferred")).toBeInTheDocument();
  });

  it("opens the wizard from the header action", async () => {
    const user = userEvent.setup();
    renderConsole();

    await user.click(screen.getByRole("button", { name: "Add connector" }));
    expect(screen.getByRole("dialog", { name: "Add connector" })).toBeInTheDocument();
  });
});

describe("ConnectorConsole merged manifest entries", () => {
  const wizardManifest = {
    ...manifestRegistryFixture.manifests[0],
    manifest_id: "manifest-wizard",
    connector_id: "file_csv_press_shop_assets",
    display_name: "Press shop assets",
    status: "registered_preview_only",
    manifest: {
      ...manifestRegistryFixture.manifests[0].manifest,
      connector_id: "file_csv_press_shop_assets",
      display_name: "Press shop assets",
    },
  };

  function mockWithWizardManifest() {
    mockQueries({
      "/demo/manufacturing/connectors/manifests": {
        data: {
          ...manifestRegistryFixture,
          manifests: [...manifestRegistryFixture.manifests, wizardManifest],
        },
        source: "api",
      },
    });
  }

  it("shows a wizard-registered manifest in the list with a Registered pill", () => {
    mockWithWizardManifest();
    renderConsole();

    const item = screen.getByRole("button", { name: /Press shop assets/ });
    expect(within(item).getByText("Registered")).toBeInTheDocument();
  });

  it("counts reference plus persisted-unique connectors in the Connectors metric", () => {
    mockWithWizardManifest();
    renderConsole();

    // 2 reference connectors + 1 manifest-only record; the fixture manifest
    // for file_csv_manufacturing_assets dedupes against its reference entry.
    const metrics = screen.getAllByRole("listitem");
    expect(within(metrics[0]).getByText("3")).toBeInTheDocument();
  });

  it("dedupes manifests that match a reference connector by connector_id", () => {
    mockQueries();
    renderConsole();

    const metrics = screen.getAllByRole("listitem");
    expect(within(metrics[0]).getByText("2")).toBeInTheDocument();
    expect(screen.queryByText("Registered")).not.toBeInTheDocument();
  });

  it("renders the simplified detail for a manifest-only entry", async () => {
    const user = userEvent.setup();
    mockWithWizardManifest();
    renderConsole();

    await user.click(screen.getByRole("button", { name: /Press shop assets/ }));
    expect(screen.getByRole("heading", { name: "Press shop assets" })).toBeInTheDocument();
    // Overview renders from the manifest record's own fields.
    expect(screen.getByText("Registered Preview Only")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Runs" }));
    expect(
      screen.getByRole("heading", { name: "Sync activation pending" }),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Data & Schema" }));
    expect(
      screen.getByRole("heading", { name: "Sync activation pending" }),
    ).toBeInTheDocument();
  });
});
