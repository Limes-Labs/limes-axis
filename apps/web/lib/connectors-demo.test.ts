import { describe, expect, it } from "vitest";

import {
  buildDefaultConnectorConfigurationRequest,
  buildDefaultCsvPreviewRequest,
  defaultConnectorConfigurationRegistry,
  defaultConnectorCredentialHandleRegistry,
  defaultConnectorRunRegistry,
  defaultManufacturingConnectorRegistry,
  defaultManufacturingConnectorPreview,
  findConnectorById,
  formatConnectorLabel,
} from "./connectors-demo";

describe("manufacturing connector demo contract", () => {
  it("keeps a public-safe file CSV connector manifest available without the API", () => {
    expect(defaultManufacturingConnectorRegistry.tenant_id).toBe("tenant_demo_manufacturing");
    expect(defaultManufacturingConnectorRegistry.connectors).toHaveLength(1);

    const connector = defaultManufacturingConnectorRegistry.connectors[0];
    expect(connector.manifest.connector_id).toBe("file_csv_manufacturing_assets");
    expect(connector.manifest.connector_type).toBe("file_csv");
    expect(connector.manifest.sync_modes).toEqual(["preview", "manual_import"]);
    expect(connector.manifest.credential_requirements.storage).toBe("none");
    expect(connector.manifest.schema_fields.map((field) => field.source_column)).toEqual([
      "asset_id",
      "asset_name",
      "domain",
      "station",
      "risk_level",
    ]);
    expect(JSON.stringify(defaultManufacturingConnectorRegistry)).not.toContain("@");
    expect(JSON.stringify(defaultManufacturingConnectorRegistry).toLowerCase()).not.toContain(
      "password",
    );
    expect(JSON.stringify(defaultManufacturingConnectorRegistry).toLowerCase()).not.toContain(
      "api_key",
    );
  });

  it("keeps a preview-only CSV mapping result", () => {
    expect(defaultManufacturingConnectorPreview.preview_status).toBe("ready");
    expect(defaultManufacturingConnectorPreview.sync_mode).toBe("preview_only");
    expect(defaultManufacturingConnectorPreview.record_count).toBe(2);
    expect(defaultManufacturingConnectorPreview.proposed_entities[0]).toMatchObject({
      node_id: "asset_line_2_packaging",
      ontology_type: "manufacturing_asset",
    });
    expect(defaultManufacturingConnectorPreview.audit_event_preview.event_type).toBe(
      "connector.preview.generated",
    );
    expect(JSON.stringify(defaultManufacturingConnectorPreview)).not.toContain("csv_content");
  });

  it("builds the demo preview request without credentials", () => {
    expect(buildDefaultCsvPreviewRequest()).toMatchObject({
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "file_csv_manufacturing_assets",
      file_name: "manufacturing-assets-demo.csv",
    });
    expect(buildDefaultCsvPreviewRequest().csv_content).toContain("asset_id,asset_name");
    expect(buildDefaultCsvPreviewRequest().csv_content.toLowerCase()).not.toContain("password");
  });

  it("keeps tenant-scoped connector configuration fallback public-safe", () => {
    expect(defaultConnectorConfigurationRegistry.tenant_id).toBe("tenant_demo_manufacturing");
    expect(defaultConnectorConfigurationRegistry.configurations).toHaveLength(1);
    expect(defaultConnectorConfigurationRegistry.metrics[0]).toMatchObject({
      label: "Configured Connectors",
      value: "1",
    });

    const configuration = defaultConnectorConfigurationRegistry.configurations[0];
    expect(configuration.connector_id).toBe("file_csv_manufacturing_assets");
    expect(configuration.status).toBe("configured_preview_only");
    expect(configuration.sync_mode).toBe("preview");
    expect(configuration.runtime_boundary).toBe("axis-connector-sandbox");
    expect(configuration.credential_ref_ids).toEqual([]);
    expect(configuration.configuration_payload).toMatchObject({
      file_name_pattern: "*.csv",
      mapping_profile: "manufacturing_asset_v1",
    });
    expect(JSON.stringify(defaultConnectorConfigurationRegistry).toLowerCase()).not.toContain(
      "password",
    );
    expect(JSON.stringify(defaultConnectorConfigurationRegistry).toLowerCase()).not.toContain(
      "api_key",
    );
    expect(JSON.stringify(defaultConnectorConfigurationRegistry).toLowerCase()).not.toContain(
      "credential_value",
    );
  });

  it("builds the demo connector configuration request without raw credentials", () => {
    const request = buildDefaultConnectorConfigurationRequest();

    expect(request).toMatchObject({
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "file_csv_manufacturing_assets",
      display_name: "Manufacturing assets CSV intake",
      sync_mode: "preview",
      created_by: "plant-operations-owner-role",
      credential_ref_ids: [],
    });
    expect(request.configuration_payload).toMatchObject({
      file_name_pattern: "*.csv",
      mapping_profile: "manufacturing_asset_v1",
    });
    expect(JSON.stringify(request).toLowerCase()).not.toContain("password");
    expect(JSON.stringify(request).toLowerCase()).not.toContain("api_key");
    expect(JSON.stringify(request).toLowerCase()).not.toContain("credential_value");
  });

  it("keeps credential handle fallback metadata-only and rotation-aware", () => {
    expect(defaultConnectorCredentialHandleRegistry.tenant_id).toBe("tenant_demo_manufacturing");
    expect(defaultConnectorCredentialHandleRegistry.handles).toHaveLength(1);
    expect(defaultConnectorCredentialHandleRegistry.metrics[0]).toMatchObject({
      label: "Credential Handles",
      value: "1",
    });

    const handle = defaultConnectorCredentialHandleRegistry.handles[0];
    expect(handle.handle_id).toBe("cred_file_csv_readonly");
    expect(handle.secret_provider).toBe("external_vault");
    expect(handle.secret_ref).toBe("vault://axis/demo/connectors/file-csv-readonly");
    expect(handle.rotation_status).toBe("healthy");
    expect(handle.rotation_count).toBe(1);
    expect(handle.last_rotation?.evidence_ref).toBe("change-window-2026-06-22");
    expect(JSON.stringify(defaultConnectorCredentialHandleRegistry).toLowerCase()).not.toContain(
      "password",
    );
    expect(JSON.stringify(defaultConnectorCredentialHandleRegistry).toLowerCase()).not.toContain(
      "api_key",
    );
    expect(JSON.stringify(defaultConnectorCredentialHandleRegistry).toLowerCase()).not.toContain(
      "credential_value",
    );
  });

  it("keeps connector run fallback audit-backed and redacted", () => {
    expect(defaultConnectorRunRegistry.tenant_id).toBe("tenant_demo_manufacturing");
    expect(defaultConnectorRunRegistry.runs).toHaveLength(1);
    expect(defaultConnectorRunRegistry.metrics[0]).toMatchObject({
      label: "Connector Runs",
      value: "1",
    });

    const run = defaultConnectorRunRegistry.runs[0];
    expect(run.run_id).toBe("run_file_csv_assets_preview_20260622");
    expect(run.status).toBe("recorded_preview_only");
    expect(run.audit_event_type).toBe("connector.run.recorded");
    expect(run.credential_handle_ids).toEqual(["cred_file_csv_readonly"]);
    expect(JSON.stringify(defaultConnectorRunRegistry).toLowerCase()).not.toContain("csv_content");
    expect(JSON.stringify(defaultConnectorRunRegistry).toLowerCase()).not.toContain("password");
    expect(JSON.stringify(defaultConnectorRunRegistry).toLowerCase()).not.toContain(
      "credential_value",
    );
  });

  it("finds connectors and formats connector labels", () => {
    expect(
      findConnectorById(defaultManufacturingConnectorRegistry, "file_csv_manufacturing_assets")
        .manifest.display_name,
    ).toBe("Manufacturing assets CSV");
    expect(
      findConnectorById(defaultManufacturingConnectorRegistry, "missing").manifest.connector_id,
    ).toBe("file_csv_manufacturing_assets");
    expect(formatConnectorLabel("file_csv")).toBe("File Csv");
  });
});
