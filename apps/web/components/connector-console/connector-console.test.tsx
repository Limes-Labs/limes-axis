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
  useConsoleTenantScope: vi.fn(),
  triggerRefresh: vi.fn(),
}));

vi.mock("@/lib/axis-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/axis-api")>()),
  axisFetch: mocks.axisFetch,
}));

vi.mock("@/lib/use-axis-query", () => ({
  useAxisQuery: mocks.useAxisQuery,
}));

vi.mock("@/lib/use-console-tenant-scope", () => ({
  IDENTITY_SESSION_ENDPOINT: "/identity/session",
  useConsoleTenantScope: mocks.useConsoleTenantScope,
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
import { OPERATIONS_API_PREFIX } from "@/lib/tenant-scope";

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
    const basePath = path.split("?")[0];
    const override = overrides[path] ?? overrides[basePath];
    if (override) {
      return queryResult(override.data, override.source);
    }
    const fixture = connectorEndpointFixtures[path]
      ?? connectorEndpointFixtures[basePath]
      ?? connectorEndpointFixtures[`${basePath}?tenant_id=tenant_demo_manufacturing`];
    if (fixture) {
      return queryResult(fixture, "api");
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
  mocks.useConsoleTenantScope.mockReset();
  mocks.triggerRefresh.mockReset();
  mocks.useConsoleTenantScope.mockReturnValue({
    identity: queryResult({
      authenticated: false,
      actor_id: null,
      api_auth_required: false,
      tenant_id: null,
    }, "api"),
    tenantScope: { mode: "demo", tenantId: "tenant_demo_manufacturing" },
    tenantId: "tenant_demo_manufacturing",
    tenantQueriesEnabled: true,
  });
  window.history.replaceState(null, "", "/connectors");
});

describe("ConnectorConsole states", () => {
  it("scopes every connector registry read to the verified tenant", () => {
    mocks.useConsoleTenantScope.mockReturnValue({
      identity: queryResult({
        authenticated: true,
        actor_id: "acme-owner",
        api_auth_required: true,
        tenant_id: "tenant_acme",
      }, "api"),
      tenantScope: { mode: "authenticated", tenantId: "tenant_acme" },
      tenantId: "tenant_acme",
      tenantQueriesEnabled: true,
    });
    mockQueries();
    renderConsole();

    const connectorCalls = mocks.useAxisQuery.mock.calls.filter(
      ([path]) => typeof path === "string" && path.startsWith(`${OPERATIONS_API_PREFIX}/connectors`),
    );
    expect(new Set(connectorCalls.map(([path]) => path)).size).toBe(10);
    connectorCalls.forEach(([path, options]) => {
      expect(path).toContain("tenant_id=tenant_acme");
      expect(options).toMatchObject({ expectedTenantId: "tenant_acme" });
      expect(options.enabled).toBe(
        path.includes("/evidence-invariants/snapshots") ? false : true,
      );
    });
  });

  it("fails closed when the identity API cannot verify a tenant", () => {
    mocks.useConsoleTenantScope.mockReturnValue({
      identity: queryResult(null, "unavailable"),
      tenantScope: { mode: "unresolved", tenantId: null },
      tenantId: null,
      tenantQueriesEnabled: false,
    });
    mockQueries();
    renderConsole();

    expect(screen.getByRole("heading", { name: "Tenant identity unavailable" })).toBeInTheDocument();
    expect(
      mocks.useAxisQuery.mock.calls.every(([, options]) => options.enabled === false),
    ).toBe(true);
  });

  it("renders loading skeletons without error copy while the registry loads", () => {
    mockQueries({
      [`${OPERATIONS_API_PREFIX}/connectors`]: { data: null, source: "loading" },
    });
    renderConsole();

    expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
    expect(screen.queryByText(/unavailable/i)).not.toBeInTheDocument();
  });

  it("renders the ErrorPanel when the registry API is unreachable", () => {
    mockQueries({
      [`${OPERATIONS_API_PREFIX}/connectors`]: { data: null, source: "unavailable" },
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
      [`${OPERATIONS_API_PREFIX}/connectors`]: {
        data: { ...connectorRegistryFixture, connectors: [] },
        source: "api",
      },
      // A truly empty tenant has no persisted manifests either; a manifest
      // record alone would legitimately render as a connector entry.
      [`${OPERATIONS_API_PREFIX}/connectors/manifests`]: {
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
      [`${OPERATIONS_API_PREFIX}/connectors/egress-policies`]: { data: null, source: "unavailable" },
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
    expect(window.location.search).toContain("connector_id=external_db_operational_mirror");
    expect(
      screen.getByRole("heading", { name: "Operational mirror DB" }),
    ).toBeInTheDocument();
  });

  it("renders the exact snapshot requested by a deep link", () => {
    window.history.replaceState(
      null,
      "",
      "/connectors?snapshot_id=snapshot_fixture&connector_id=file_csv_manufacturing_assets",
    );
    mockQueries({
      [`${OPERATIONS_API_PREFIX}/connectors/evidence-invariants/snapshots`]: {
        source: "api",
        data: {
          tenant_id: "tenant_demo_manufacturing",
          plant_name: "Ravenna Works",
          scenario: "Plant Operations Cockpit",
          history_status: "ready",
          metrics: [],
          snapshots: [{
            tenant_id: "tenant_demo_manufacturing",
            snapshot_id: "snapshot_fixture",
            status: "persisted",
            connector_id: "file_csv_manufacturing_assets",
            requested_by: "fixture-operator",
            idempotency_key: "snapshot-fixture-key",
            reason: "Regression fixture",
            invariant_count: 1,
            invariant_counts: { credential_lease: 1 },
            subject_ids: ["lease_csv_active"],
            report_digest_sha256: "a".repeat(64),
            report_hash_algorithm: "sha256",
            permission_decision: { allowed: true, reason: "required_scope_present" },
            audit_event_id: null,
            audit_event_type: "connector.evidence_invariants.snapshot_persisted",
            idempotent_replay: false,
            notes: [],
          }],
          history_notes: [],
        },
      },
    });
    renderConsole();

    expect(
      screen.getByRole("heading", { name: "Requested evidence snapshot" }),
    ).toBeInTheDocument();
    expect(screen.getByText("snapshot_fixture")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Manufacturing assets CSV" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Governance & Evidence" })).toHaveAttribute(
      "data-state",
      "active",
    );
  });

  it("does not fall back to the first connector for an unknown snapshot", () => {
    window.history.replaceState(null, "", "/connectors?snapshot_id=snapshot_unknown");
    mockQueries({
      [`${OPERATIONS_API_PREFIX}/connectors/evidence-invariants/snapshots`]: {
        source: "api",
        data: {
          tenant_id: "tenant_demo_manufacturing",
          plant_name: "Ravenna Works",
          scenario: "Plant Operations Cockpit",
          history_status: "watch",
          metrics: [],
          snapshots: [],
          history_notes: [],
        },
      },
    });
    renderConsole();

    expect(
      screen.getByRole("heading", { name: "Requested snapshot is not available" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Manufacturing assets CSV" }),
    ).not.toBeInTheDocument();
  });

  it("shows the registered manifest state on the overview tab", () => {
    renderConsole();

    expect(screen.getByText("Registered manifest")).toBeInTheDocument();
    expect(screen.getAllByText("Active Preview").length).toBeGreaterThan(0);
    expect(screen.getByText("Current revision")).toBeInTheDocument();
    expect(screen.getByText("2", { selector: "dd" })).toBeInTheDocument();
    const history = screen.getByRole("table", { name: "Revision history" });
    expect(within(history).getByText("0.9.0")).toBeInTheDocument();
    expect(within(history).getByText("1.0.0")).toBeInTheDocument();
  });

  it("renders the schema mapping and sample rows on the Data & Schema tab", async () => {
    const user = userEvent.setup();
    renderConsole();

    await user.click(screen.getByRole("tab", { name: "Data & Schema" }));
    expect(window.location.search).toContain("tab=schema");

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

  it("shows the evidence invariants error state when that registry is unavailable", async () => {
    const user = userEvent.setup();
    mockQueries({
      [`${OPERATIONS_API_PREFIX}/connectors/evidence-invariants`]: { data: null, source: "unavailable" },
    });
    renderConsole();

    await user.click(screen.getByRole("tab", { name: "Governance & Evidence" }));

    // `invariantReport?.invariants.length === 0` used to be `undefined === 0`
    // (false) when the fetch failed, so this error never rendered and the
    // section silently looked empty/clear instead.
    expect(
      screen.getByRole("heading", {
        name: "Evidence invariant findings could not be loaded.",
      }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("All evidence invariants hold — every governed record has audit evidence."),
    ).not.toBeInTheDocument();
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

  it("does not persist a validate result panel across a connector switch", async () => {
    const user = userEvent.setup();
    mocks.axisFetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          tenant_id: "tenant_demo_manufacturing",
          connector_id: "file_csv_manufacturing_assets",
          file_name: "assets.csv",
          preview_status: "ready",
          sync_mode: "preview_only",
          record_count: 2,
          accepted_record_count: 2,
          rejected_record_count: 0,
          validation_issues: [],
          proposed_entities: [],
          audit_event_preview: {
            event_type: "connector.preview.generated",
            scope: "file_csv_manufacturing_assets",
            actor_id: "connector-preview-service",
            result: "ready",
            evidence_refs: [],
            payload_preview: {},
          },
          preview_notes: [],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    renderConsole();

    // Validate the CSV connector (Manufacturing assets CSV, selected by
    // default) and confirm the result panel commits.
    await user.click(screen.getByRole("tab", { name: "Runs" }));
    await user.click(screen.getByRole("button", { name: "Validate" }));
    expect(await screen.findByText("Validation passed")).toBeInTheDocument();

    // Switching to the other connector must remount the whole detail pane
    // (ConnectorDetail's `key`), clearing ConnectorRuns' validate state —
    // without the key, this used to keep showing connector A's result.
    await user.click(screen.getByRole("button", { name: /Operational mirror DB/ }));
    await user.click(screen.getByRole("tab", { name: "Runs" }));

    expect(screen.queryByText("Validation passed")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Validate" })).toBeInTheDocument();
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
      [`${OPERATIONS_API_PREFIX}/connectors/manifests`]: {
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
