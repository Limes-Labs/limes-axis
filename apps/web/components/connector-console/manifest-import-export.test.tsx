import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import type { ConnectorListEntry } from "@/lib/connectors-console";
import type { IdentitySessionReadModel } from "@/lib/platform-overview";

import { csvConnectorFixture, manifestRegistryFixture } from "./connector-fixtures";
import { ManifestExportPanel } from "./manifest-export-panel";
import {
  MANIFESTS_ENDPOINT,
  MANIFEST_VALIDATION_ENDPOINT,
  ManifestImportPanel,
} from "./manifest-import-panel";

const mocks = vi.hoisted(() => ({
  axisFetch: vi.fn(),
  onApplied: vi.fn(),
}));

vi.mock("@/lib/axis-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/axis-api")>()),
  axisFetch: mocks.axisFetch,
}));

vi.mock("@/lib/use-oidc-session", () => ({
  useOidcConsoleSession: () => ({ session: null }),
}));

const tenantId = "tenant_demo_manufacturing";
const identitySession: IdentitySessionReadModel = {
  authenticated: true,
  actor_id: "plant-operations-owner-role",
  api_auth_required: true,
  audience: "axis-console",
  capabilities: [],
  enterprise_sso_ready: true,
  expires_at: null,
  issuer: "test",
  jwks_source: "test",
  limitations: [],
  mode: "test",
  notes: [],
  readiness_status: "ready",
  scopes: [],
  session_boundary: "test",
  tenant_id: tenantId,
};

const entry: ConnectorListEntry = {
  connector: csvConnectorFixture,
  source: "reference",
  manifestRecord: manifestRegistryFixture.manifests[0],
};

function documentFor(connectorId: string) {
  return {
    manifest: { ...csvConnectorFixture.manifest, connector_id: connectorId },
    runtime_policy: csvConnectorFixture.runtime_policy,
    preview_sample: csvConnectorFixture.preview_sample,
    notes: [],
  };
}

function response(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function validationResponse(
  results: Array<{
    connector_id: string | null;
    outcome: "would_register" | "already_registered" | "invalid";
    errors?: Array<{ field_path: string; message: string; reason: string }>;
  }>,
) {
  return {
    tenant_id: tenantId,
    summary: {
      would_register: results.filter((result) => result.outcome === "would_register").length,
      already_registered: results.filter((result) => (
        result.outcome === "already_registered"
      )).length,
      invalid: results.filter((result) => result.outcome === "invalid").length,
    },
    results: results.map((result) => ({ ...result, errors: result.errors ?? [] })),
  };
}

function renderImport(extra?: React.ReactNode) {
  return render(
    <ToastProvider>
      {extra}
      <ManifestImportPanel
        identitySession={identitySession}
        onApplied={mocks.onApplied}
        tenantId={tenantId}
      />
    </ToastProvider>,
  );
}

function setJson(value: unknown) {
  fireEvent.change(screen.getByLabelText("Registration document JSON", { selector: "textarea:not([readonly])" }), {
    target: { value: typeof value === "string" ? value : JSON.stringify(value) },
  });
}

beforeEach(() => {
  mocks.axisFetch.mockReset();
  mocks.onApplied.mockReset();
});

describe("ManifestImportPanel", () => {
  it("renders each outcome and field-level errors for a mixed batch", async () => {
    const user = userEvent.setup();
    const documents = [documentFor("new-connector"), documentFor("existing-connector"), {}];
    mocks.axisFetch.mockResolvedValueOnce(response(validationResponse([
      { connector_id: "new-connector", outcome: "would_register" },
      { connector_id: "existing-connector", outcome: "already_registered" },
      {
        connector_id: null,
        outcome: "invalid",
        errors: [{
          field_path: "preview_sample.file_name",
          message: "Field required",
          reason: "invalid_preview_sample_payload",
        }],
      },
    ])));
    renderImport();

    setJson(documents);
    await user.click(screen.getByRole("button", { name: "Check" }));

    const table = await screen.findByRole("table", { name: "Import connector manifests" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(within(rows[0]).getByText("Would register")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Already registered")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Invalid")).toBeInTheDocument();
    expect(within(rows[2]).getByText("preview_sample.file_name")).toBeInTheDocument();
    expect(within(rows[2]).getByText(/Field required/)).toBeInTheDocument();
    expect(screen.getAllByText("1", { selector: "p.text-xl" })).toHaveLength(3);
  });

  it("keeps Apply disabled while any checked document is invalid", async () => {
    const user = userEvent.setup();
    mocks.axisFetch.mockResolvedValueOnce(response(validationResponse([
      { connector_id: "valid", outcome: "would_register" },
      {
        connector_id: "invalid",
        outcome: "invalid",
        errors: [{ field_path: "preview_sample", message: "Field required", reason: "missing" }],
      },
    ])));
    renderImport();

    setJson([documentFor("valid"), documentFor("invalid")]);
    await user.click(screen.getByRole("button", { name: "Check" }));

    expect(await screen.findByText("1 of 2 will be rejected: 1 invalid, 0 already registered. Apply stays disabled until every document can be registered.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review apply" })).toBeDisabled();
  });

  it("keeps Apply disabled and surfaces the count for already-registered documents", async () => {
    const user = userEvent.setup();
    mocks.axisFetch.mockResolvedValueOnce(response(validationResponse([
      { connector_id: "valid", outcome: "would_register" },
      { connector_id: "existing", outcome: "already_registered" },
    ])));
    renderImport();

    setJson([documentFor("valid"), documentFor("existing")]);
    await user.click(screen.getByRole("button", { name: "Check" }));

    expect(await screen.findByText("1 of 2 will be rejected: 0 invalid, 1 already registered. Apply stays disabled until every document can be registered.")).toBeInTheDocument();
    expect(screen.getByText("Already registered", { selector: ".status-pill" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review apply" })).toBeDisabled();
    expect(mocks.axisFetch).toHaveBeenCalledTimes(1);
  });

  it("stops after a partial apply failure and identifies landed, failed, and untouched documents", async () => {
    const user = userEvent.setup();
    const documents = [documentFor("landed"), documentFor("failed"), documentFor("untouched")];
    mocks.axisFetch
      .mockResolvedValueOnce(response(validationResponse(documents.map((document) => ({
        connector_id: document.manifest.connector_id,
        outcome: "would_register" as const,
      })))))
      .mockResolvedValueOnce(response({ manifest_id: "created" }, 201))
      .mockResolvedValueOnce(response({ detail: { reason: "write_failed" } }, 500));
    renderImport();

    setJson(documents);
    await user.click(screen.getByRole("button", { name: "Check" }));
    await user.click(await screen.findByRole("button", { name: "Review apply" }));
    await user.click(screen.getByRole("button", { name: "Apply manifests" }));

    expect(await screen.findAllByText("1 of 3 manifests were created. The remaining documents were not applied.")).toHaveLength(2);
    const rows = within(screen.getByRole("table", { name: "Import connector manifests" }))
      .getAllByRole("row")
      .slice(1);
    expect(within(rows[0]).getByText("Created")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Failed")).toBeInTheDocument();
    expect(within(rows[2]).getByText("Not applied")).toBeInTheDocument();
    expect(mocks.axisFetch.mock.calls.filter(([path]) => path === MANIFESTS_ENDPOINT)).toHaveLength(2);
    expect(mocks.onApplied).toHaveBeenCalledTimes(1);
  });

  it("rejects more than 50 documents before making a request", async () => {
    const user = userEvent.setup();
    renderImport();

    setJson(Array.from({ length: 51 }, (_, index) => documentFor(`connector-${index}`)));
    await user.click(screen.getByRole("button", { name: "Check" }));

    expect(screen.getByRole("alert")).toHaveTextContent("51 documents were provided. Check at most 50 at a time.");
    expect(mocks.axisFetch).not.toHaveBeenCalled();
  });

  it("shows malformed JSON locally without making a request", async () => {
    const user = userEvent.setup();
    renderImport();

    setJson("{not-json");
    await user.click(screen.getByRole("button", { name: "Check" }));

    expect(screen.getByRole("alert")).toHaveTextContent("This is not valid JSON");
    expect(mocks.axisFetch).not.toHaveBeenCalled();
  });

  it("rejects an empty array locally without making a request", async () => {
    const user = userEvent.setup();
    renderImport();

    setJson([]);
    await user.click(screen.getByRole("button", { name: "Check" }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Provide one JSON object or a non-empty array of JSON objects.",
    );
    expect(mocks.axisFetch).not.toHaveBeenCalled();
  });

  it("applies a valid batch sequentially and refreshes once after every document lands", async () => {
    const user = userEvent.setup();
    const documents = [documentFor("first"), documentFor("second")];
    mocks.axisFetch
      .mockResolvedValueOnce(response(validationResponse(documents.map((document) => ({
        connector_id: document.manifest.connector_id,
        outcome: "would_register" as const,
      })))))
      .mockResolvedValueOnce(response({ manifest_id: "first" }, 201))
      .mockResolvedValueOnce(response({ manifest_id: "second" }, 201));
    renderImport();

    setJson(documents);
    await user.click(screen.getByRole("button", { name: "Check" }));
    await user.click(await screen.findByRole("button", { name: "Review apply" }));
    await user.click(screen.getByRole("button", { name: "Apply manifests" }));

    expect(await screen.findAllByText("2 of 2 manifests were created.")).toHaveLength(2);
    expect(mocks.axisFetch.mock.calls.map(([path]) => path)).toEqual([
      MANIFEST_VALIDATION_ENDPOINT,
      MANIFESTS_ENDPOINT,
      MANIFESTS_ENDPOINT,
    ]);
    expect(mocks.onApplied).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Review apply" })).toBeDisabled();
  });

  it("loads a JSON file into the same checked import flow", async () => {
    const user = userEvent.setup();
    const document = documentFor("uploaded");
    mocks.axisFetch.mockResolvedValueOnce(response(validationResponse([
      { connector_id: "uploaded", outcome: "would_register" },
    ])));
    renderImport();

    await user.upload(
      screen.getByLabelText("Upload JSON file"),
      new File([JSON.stringify(document)], "connector.json", { type: "application/json" }),
    );
    await waitFor(() => expect(screen.getByRole("button", { name: "Check" })).toBeEnabled());
    await user.click(screen.getByRole("button", { name: "Check" }));

    expect(await screen.findByText("uploaded")).toBeInTheDocument();
    expect(mocks.axisFetch).toHaveBeenCalledWith(
      MANIFEST_VALIDATION_ENDPOINT,
      expect.objectContaining({ body: expect.objectContaining({ manifests: [document] }) }),
    );
  });
});

describe("manifest export round trip", () => {
  it("feeds the exact formatted export into import and reports it as already registered", async () => {
    const user = userEvent.setup();
    mocks.axisFetch.mockResolvedValueOnce(response(validationResponse([
      {
        connector_id: csvConnectorFixture.manifest.connector_id,
        outcome: "already_registered",
      },
    ])));
    renderImport(<ManifestExportPanel entry={entry} />);

    await user.click(screen.getByRole("button", { name: "Export manifest" }));
    const exportedJson = (screen.getByLabelText("Registration document JSON", {
      selector: "textarea[readonly]",
    }) as HTMLTextAreaElement).value;
    setJson(exportedJson);
    await user.click(screen.getByRole("button", { name: "Check" }));

    expect(await screen.findByText("Already registered", {
      selector: ".status-pill",
    })).toBeInTheDocument();
    expect(mocks.axisFetch).toHaveBeenCalledWith(
      MANIFEST_VALIDATION_ENDPOINT,
      expect.objectContaining({
        body: expect.objectContaining({ manifests: [JSON.parse(exportedJson)] }),
      }),
    );
    expect(JSON.parse(exportedJson).preview_sample).toEqual(csvConnectorFixture.preview_sample);
  });

  it("copies and downloads the formatted registration document", async () => {
    const user = userEvent.setup();
    const createObjectURL = vi.fn(() => "blob:manifest");
    const revokeObjectURL = vi.fn();
    Object.assign(URL, { createObjectURL, revokeObjectURL });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    render(
      <ToastProvider>
        <ManifestExportPanel entry={entry} />
      </ToastProvider>,
    );

    await user.click(screen.getByRole("button", { name: "Export manifest" }));
    const json = (screen.getByLabelText("Registration document JSON") as HTMLTextAreaElement).value;
    await user.click(screen.getByRole("button", { name: "Copy JSON" }));
    expect(await navigator.clipboard.readText()).toBe(json);
    await user.click(screen.getByRole("button", { name: "Download JSON" }));

    expect(createObjectURL).toHaveBeenCalledWith(expect.any(Blob));
    expect(click).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:manifest");
    click.mockRestore();
  });
});
