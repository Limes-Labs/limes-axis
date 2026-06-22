import { describe, expect, it } from "vitest";

import {
  buildConnectorPromotionPolicyDraftRequest,
  buildConnectorPromotionPolicyEnableRequest,
  findConnectorById,
  formatConnectorLabel,
  type ManufacturingConnectorRegistry,
} from "./connectors-demo";

const connectorRegistryFixture: ManufacturingConnectorRegistry = {
  tenant_id: "tenant_demo_manufacturing",
  plant_name: "Ravenna Works",
  scenario: "Plant Operations Cockpit",
  registry_status: "ready",
  metrics: [],
  connectors: [
    {
      connector_status: "ready",
      manifest: {
        connector_id: "file_csv_manufacturing_assets",
        display_name: "Manufacturing assets CSV",
        connector_type: "file_csv",
        version: "2026-06-22",
        source_type: "file",
        sync_modes: ["preview", "manual_import"],
        runtime_boundary: "axis-connector-sandbox",
        required_permissions: ["connectors:read", "connectors:file_csv:preview"],
        credential_requirements: {
          storage: "none",
          required_secret_refs: [],
          notes: ["No credentials required for local CSV preview requests."],
        },
        schema_fields: [
          {
            source_column: "asset_id",
            target_field: "node_id",
            ontology_target: "manufacturing_asset",
            data_type: "string",
            required: true,
            description: "Stable asset identifier used as the ontology node id.",
          },
        ],
        mapping_notes: ["Fixture local to this test file, not exported by runtime code."],
      },
      runtime_policy: {
        allowed_operations: ["schema_validate"],
        blocked_operations: ["live_sync"],
        egress_policy: "none",
        max_file_size_mb: 5,
        row_limit: 500,
        payload_policy: "metadata_only",
      },
      preview_sample: {
        file_name: "manufacturing-assets-demo.csv",
        record_count: 0,
        headers: ["asset_id"],
        sample_rows: [],
      },
    },
    {
      connector_status: "watch",
      manifest: {
        connector_id: "external_db_operational_mirror",
        display_name: "Postgres operational mirror",
        connector_type: "external_db",
        version: "2026-06-22",
        source_type: "database",
        sync_modes: ["schema_preview", "manual_import"],
        runtime_boundary: "axis-connector-sandbox",
        required_permissions: ["connectors:read", "connectors:external_db:preview"],
        credential_requirements: {
          storage: "external_reference",
          required_secret_refs: ["cred_external_db_readonly"],
          notes: ["Credential material must remain outside Axis."],
        },
        schema_fields: [
          {
            source_column: "order_id",
            target_field: "node_id",
            ontology_target: "production_order",
            data_type: "string",
            required: true,
            description: "Order identifier from the external operational mirror.",
          },
        ],
        mapping_notes: ["Metadata-only test fixture."],
      },
      runtime_policy: {
        allowed_operations: ["schema_validate", "metadata_preview"],
        blocked_operations: ["live_query", "credential_material_read"],
        egress_policy: "approved_private_endpoint",
        max_file_size_mb: 0,
        row_limit: 0,
        payload_policy: "metadata_only",
      },
      preview_sample: {
        file_name: "operations.production_orders",
        record_count: 0,
        headers: ["order_id"],
        sample_rows: [],
      },
    },
  ],
  connector_notes: [],
};

describe("manufacturing connector helpers", () => {
  it("finds connectors from caller-provided records without runtime defaults", () => {
    expect(
      findConnectorById(connectorRegistryFixture, "external_db_operational_mirror").manifest
        .display_name,
    ).toBe("Postgres operational mirror");
    expect(findConnectorById(connectorRegistryFixture, "missing").manifest.connector_id).toBe(
      "file_csv_manufacturing_assets",
    );
  });

  it("formats connector labels for API values", () => {
    expect(formatConnectorLabel("file_csv")).toBe("File Csv");
    expect(formatConnectorLabel("axis-egress-policy-enforcer")).toBe(
      "Axis Egress Policy Enforcer",
    );
  });

  it("builds connector promotion policy authoring requests without raw payloads", () => {
    const request = buildConnectorPromotionPolicyDraftRequest({
      connector_id: "external_db_operational_mirror",
      policy_id: "policy_connector_ops_readonly_v1",
      status: "enabled",
      enforcement_mode: "required",
    });

    expect(request).toMatchObject({
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "external_db_operational_mirror",
      policy_id: "policy_connector_ops_readonly_v1",
      policy_version: "2026-06-22-ui",
      status: "enabled",
      enforcement_mode: "required",
      created_by: "platform-governance-owner-role",
      actor_scopes: ["connectors:promotion_policy:author"],
      required_scopes: ["connectors:ontology:promote"],
      required_manual_import_status: "approval_approved",
      required_workflow_signal_status: "manual_import_signal_requested",
      allowed_risk_levels: ["high", "medium"],
      allowed_ontology_types: ["manufacturing_asset"],
      review_window_hours: 24,
    });
    expect(JSON.stringify(request).toLowerCase()).not.toContain("csv_content");
    expect(JSON.stringify(request).toLowerCase()).not.toContain("password");
    expect(JSON.stringify(request).toLowerCase()).not.toContain("credential_value");
  });

  it("builds connector promotion policy enable requests without raw payloads", () => {
    const request = buildConnectorPromotionPolicyEnableRequest({
      policy_id: "policy_connector_ops_readonly_v1",
    });

    expect(request).toMatchObject({
      tenant_id: "tenant_demo_manufacturing",
      policy_id: "policy_connector_ops_readonly_v1",
      enabled_by: "platform-governance-owner-role",
      actor_scopes: ["connectors:promotion_policy:enable"],
      approval_id: "appr_policy_enable_connector_ops_readonly_v1",
      approval_decision: "approve",
      workflow_signal_status: "policy_enable_signal_recorded",
    });
    expect(JSON.stringify(request).toLowerCase()).not.toContain("csv_content");
    expect(JSON.stringify(request).toLowerCase()).not.toContain("password");
    expect(JSON.stringify(request).toLowerCase()).not.toContain("credential_value");
  });
});
