import { describe, expect, it } from "vitest";

import {
  buildDefaultConnectorConfigurationRequest,
  buildDefaultCsvPreviewRequest,
  defaultConnectorConfigurationRegistry,
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
