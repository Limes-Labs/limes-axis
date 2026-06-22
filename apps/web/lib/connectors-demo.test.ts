import { describe, expect, it } from "vitest";

import {
  buildDefaultCsvPreviewRequest,
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
