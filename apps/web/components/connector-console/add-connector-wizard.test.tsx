import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ConnectorCsvPreviewResult } from "@/lib/connectors-demo";

import { csvConnectorFixture, dbConnectorFixture } from "./connector-fixtures";

const mocks = vi.hoisted(() => ({
  axisFetch: vi.fn(),
  useAxisQuery: vi.fn(),
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

import { ToastProvider } from "@/components/ui/toast";
import { AddConnectorWizard } from "./add-connector-wizard";

const csvPreviewReady: ConnectorCsvPreviewResult = {
  tenant_id: "tenant_demo_manufacturing",
  connector_id: "file_csv_manufacturing_assets",
  file_name: "plant-assets.csv",
  preview_status: "ready",
  sync_mode: "preview_only",
  record_count: 2,
  accepted_record_count: 2,
  rejected_record_count: 0,
  validation_issues: [],
  proposed_entities: [
    {
      node_id: "ast-9",
      node_type: "asset",
      ontology_type: "manufacturing_asset",
      field_summary: {},
      evidence_refs: [],
    },
  ],
  audit_event_preview: {
    event_type: "connector.preview.generated",
    scope: "file_csv_manufacturing_assets",
    actor_id: "connector-preview-service",
    result: "ready",
    evidence_refs: [],
    payload_preview: {},
  },
  preview_notes: [],
};

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function mockIdentity(
  identity: { authenticated: boolean; actor_id: string | null; api_auth_required?: boolean } | null,
) {
  mocks.useAxisQuery.mockImplementation(() => ({
    data: identity,
    source: identity ? "api" : "loading",
    error: null,
    isRefreshing: false,
    isLoading: identity === null,
    isUnavailable: false,
  }));
}

function renderWizard(overrides: { onCreated?: () => void; onOpenChange?: (open: boolean) => void } = {}) {
  return render(
    <ToastProvider>
      <AddConnectorWizard
        connectors={[csvConnectorFixture, dbConnectorFixture]}
        open
        onCreated={overrides.onCreated ?? vi.fn()}
        onOpenChange={overrides.onOpenChange ?? vi.fn()}
      />
    </ToastProvider>,
  );
}

async function uploadCsvAndPreview(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: /^CSV file/ }));
  await user.click(screen.getByRole("button", { name: "Next" }));

  const file = new File(
    ["asset_id,asset_name\nast-9,Grinder\nast-10,Lathe\n"],
    "plant-assets.csv",
    { type: "text/csv" },
  );
  await user.upload(screen.getByLabelText("CSV file", { selector: "input" }), file);

  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Preview file" })).toBeEnabled(),
  );
  await user.click(screen.getByRole("button", { name: "Preview file" }));
}

beforeEach(() => {
  mocks.axisFetch.mockReset();
  mocks.useAxisQuery.mockReset();
  mockIdentity({ authenticated: true, actor_id: "plant-operations-owner-role" });
});

describe("AddConnectorWizard CSV flow", () => {
  it("uploads a file, posts its parsed content to the preview endpoint, and shows the result", async () => {
    const user = userEvent.setup();
    mocks.axisFetch.mockResolvedValueOnce(jsonResponse(csvPreviewReady));
    renderWizard();

    await uploadCsvAndPreview(user);

    await waitFor(() => expect(screen.getByText("Preview ready")).toBeInTheDocument());

    const [previewPath, previewOptions] = mocks.axisFetch.mock.calls[0];
    expect(previewPath).toBe("/demo/manufacturing/connectors/file-csv/preview");
    expect(previewOptions.body).toEqual({
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "file_csv_manufacturing_assets",
      file_name: "plant-assets.csv",
      csv_content: "asset_id,asset_name\nast-9,Grinder\nast-10,Lathe\n",
    });

    // Preview table renders the proposed entities from the API response.
    expect(screen.getByText("ast-9")).toBeInTheDocument();
    expect(screen.getByText(/2 rows/)).toBeInTheDocument();
  });

  it("keeps Next disabled until the preview is ready, then advances to review", async () => {
    const user = userEvent.setup();
    mocks.axisFetch.mockResolvedValueOnce(jsonResponse(csvPreviewReady));
    renderWizard();

    await user.click(screen.getByRole("button", { name: /^CSV file/ }));
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();

    const file = new File(["asset_id\nast-9\n"], "plant-assets.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText("CSV file", { selector: "input" }), file);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Preview file" })).toBeEnabled(),
    );
    await user.click(screen.getByRole("button", { name: "Preview file" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Next" })).toBeEnabled());

    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(screen.getByText("Review and register")).toBeInTheDocument();
    expect(screen.getByLabelText("Connector id")).toHaveValue("file_csv_plant_assets");
  });

  it("posts the manifest payload derived from the template and the uploaded file", async () => {
    const user = userEvent.setup();
    const onCreated = vi.fn();
    mocks.axisFetch
      .mockResolvedValueOnce(jsonResponse(csvPreviewReady))
      .mockResolvedValueOnce(jsonResponse({ manifest_id: "m1" }, 201));
    renderWizard({ onCreated });

    await uploadCsvAndPreview(user);
    await waitFor(() => expect(screen.getByRole("button", { name: "Next" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Register connector" }));

    await waitFor(() => expect(onCreated).toHaveBeenCalled());

    const [manifestPath, manifestOptions] = mocks.axisFetch.mock.calls[1];
    expect(manifestPath).toBe("/demo/manufacturing/connectors/manifests");
    expect(manifestOptions.method).toBe("POST");
    expect(manifestOptions.body).toEqual({
      tenant_id: "tenant_demo_manufacturing",
      registered_by: "plant-operations-owner-role",
      manifest: {
        ...csvConnectorFixture.manifest,
        connector_id: "file_csv_plant_assets",
        display_name: "plant-assets",
      },
      runtime_policy: csvConnectorFixture.runtime_policy,
      preview_sample: {
        file_name: "plant-assets.csv",
        record_count: 2,
        headers: ["asset_id", "asset_name"],
        sample_rows: [
          { asset_id: "ast-9", asset_name: "Grinder" },
          { asset_id: "ast-10", asset_name: "Lathe" },
        ],
      },
      notes: ["Registered from the connector console wizard."],
    });
    expect(screen.getByText("Connector registered")).toBeInTheDocument();
  });

  it("shows the already-exists message inline on a 409", async () => {
    const user = userEvent.setup();
    mocks.axisFetch
      .mockResolvedValueOnce(jsonResponse(csvPreviewReady))
      .mockResolvedValueOnce(
        jsonResponse({ detail: { reason: "manifest_already_exists" } }, 409),
      );
    renderWizard();

    await uploadCsvAndPreview(user);
    await waitFor(() => expect(screen.getByRole("button", { name: "Next" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Register connector" }));

    expect(
      await screen.findByText(/A connector with this id already exists/),
    ).toBeInTheDocument();
  });

  it("explains a 403 in plain language with the raw reason in mono", async () => {
    const user = userEvent.setup();
    mocks.axisFetch
      .mockResolvedValueOnce(jsonResponse(csvPreviewReady))
      .mockResolvedValueOnce(jsonResponse({ detail: { reason: "tenant_mismatch" } }, 403));
    renderWizard();

    await uploadCsvAndPreview(user);
    await waitFor(() => expect(screen.getByRole("button", { name: "Next" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Register connector" }));

    expect(
      await screen.findByText(/not allowed to register connectors/),
    ).toBeInTheDocument();
    expect(screen.getByText("tenant_mismatch")).toBeInTheDocument();
  });
});

describe("AddConnectorWizard external DB flow", () => {
  it("posts the profile form to the external-db preview endpoint", async () => {
    const user = userEvent.setup();
    mocks.axisFetch.mockResolvedValueOnce(
      jsonResponse({
        tenant_id: "tenant_demo_manufacturing",
        connector_id: "external_db_operational_mirror",
        connection_profile_id: "profile_postgres_ops_readonly",
        source_type: "postgres_metadata",
        preview_status: "ready",
        sync_mode: "preview_only",
        live_query_executed: false,
        validation_issues: [],
        inspected_table: {
          schema_name: "operations",
          table_name: "production_orders",
          table_ref: "operations.production_orders",
          record_count_estimate: "~1000",
          sample_limit: 2,
          columns: [
            {
              source_column: "asset_id",
              target_field: "node_id",
              ontology_target: "manufacturing_asset",
              data_type: "string",
              nullable: false,
            },
          ],
          sample_rows: [],
        },
        proposed_entities: [],
        audit_event_preview: csvPreviewReady.audit_event_preview,
        preview_notes: [],
      }),
    );
    renderWizard();

    await user.click(screen.getByRole("button", { name: /^External database/ }));
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Preview metadata" }));

    await waitFor(() =>
      expect(screen.getByText("Metadata preview ready")).toBeInTheDocument(),
    );

    const [path, options] = mocks.axisFetch.mock.calls[0];
    expect(path).toBe("/demo/manufacturing/connectors/external-db/preview");
    expect(options.body).toMatchObject({
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "external_db_operational_mirror",
      connection_profile_id: "profile_postgres_ops_readonly",
      schema_name: "operations",
      table_name: "production_orders",
      credential_handle_id: "cred_external_db_readonly",
      metadata: {},
    });

    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByLabelText("Connector id")).toHaveValue(
      "external_db_operations_production_orders",
    );
  });
});

describe("AddConnectorWizard SSO gate", () => {
  it("disables submission with the sign-in message when the session is confirmed unauthenticated", async () => {
    const user = userEvent.setup();
    mockIdentity({ authenticated: false, actor_id: null, api_auth_required: true });
    mocks.axisFetch.mockResolvedValueOnce(jsonResponse(csvPreviewReady));
    renderWizard();

    await uploadCsvAndPreview(user);
    await waitFor(() => expect(screen.getByRole("button", { name: "Next" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(screen.getByText("Sign in with SSO to register connectors.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Register connector" })).toBeDisabled();
  });
});
