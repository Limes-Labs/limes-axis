import { describe, expect, it } from "vitest";

import {
  buildConnectorSyncCheckpointQueryPath,
  buildConnectorPromotionPolicyDraftRequest,
  buildConnectorPromotionPolicyEnableRequest,
  filterConnectorSyncCheckpointsByConnector,
  findConnectorById,
  formatConnectorLabel,
  type ManufacturingConnectorSyncCheckpointRegistry,
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

const checkpointRegistryFixture: ManufacturingConnectorSyncCheckpointRegistry = {
  tenant_id: "tenant_demo_manufacturing",
  plant_name: "Ravenna Works",
  scenario: "Plant Operations Cockpit",
  registry_status: "ready",
  metrics: [],
  checkpoints: [
    {
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "external_db_operational_mirror",
      run_id: "run_external_db_sync_20260625",
      checkpoint_id: "chk_external_db_sync_2",
      checkpoint_type: "sync_execution",
      status: "sync_execution_completed",
      sequence: 2,
      runtime_boundary: "axis-workflow-runtime-adapter",
      adapter: "axis-postgres-external-db-sync-executor",
      cursor: {
        high_watermark_kind: "timestamp",
        high_watermark_value: "2026-06-25T10:15:00+02:00",
      },
      result_summary: {
        external_query_started: "false",
        credential_material_returned: "false",
      },
      evidence_refs: ["audit-external-db-sync-2"],
      audit_event_id: "7b104c64-0c3a-48f1-aa6d-828c3a51b16c",
      audit_event_type: "connector.run.sync_execution_completed",
      notes: ["Checkpoint evidence from the API response."],
      created_at: "2026-06-25T08:15:00Z",
    },
    {
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "file_csv_manufacturing_assets",
      run_id: "run_file_csv_sync_20260625",
      checkpoint_id: "chk_file_csv_sync_1",
      checkpoint_type: "sync_execution",
      status: "sync_execution_deferred",
      sequence: 1,
      runtime_boundary: "axis-workflow-runtime-adapter",
      adapter: "axis-file-csv-sync-executor",
      cursor: { asset_ref: "obj://axis/demo/file-csv" },
      result_summary: { external_query_started: "false" },
      evidence_refs: ["audit-file-csv-sync-1"],
      audit_event_id: null,
      audit_event_type: "connector.run.sync_execution_deferred",
      notes: [],
      created_at: "2026-06-25T08:10:00Z",
    },
    {
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "external_db_operational_mirror",
      run_id: "run_external_db_sync_20260625",
      checkpoint_id: "chk_external_db_sync_1",
      checkpoint_type: "sync_execution",
      status: "sync_execution_preflight_passed",
      sequence: 1,
      runtime_boundary: "axis-workflow-runtime-adapter",
      adapter: "axis-postgres-external-db-sync-executor",
      cursor: { high_watermark_kind: "timestamp" },
      result_summary: { live_query_preflight_status: "passed" },
      evidence_refs: ["audit-external-db-sync-1"],
      audit_event_id: null,
      audit_event_type: "connector.run.sync_execution_preflight_passed",
      notes: [],
      created_at: "2026-06-25T08:05:00Z",
    },
  ],
  checkpoint_notes: ["Sync checkpoints are tenant-scoped runtime evidence for retry/resume."],
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

  it("filters connector sync checkpoints for the selected connector without secret material", () => {
    const checkpoints = filterConnectorSyncCheckpointsByConnector(
      checkpointRegistryFixture,
      "external_db_operational_mirror",
    );

    expect(checkpoints.map((checkpoint) => checkpoint.checkpoint_id)).toEqual([
      "chk_external_db_sync_1",
      "chk_external_db_sync_2",
    ]);
    expect(JSON.stringify(checkpoints).toLowerCase()).not.toContain("dsn");
    expect(JSON.stringify(checkpoints).toLowerCase()).not.toContain("credential_value");
    expect(JSON.stringify(checkpoints).toLowerCase()).not.toContain("password");
  });

  it("builds connector sync checkpoint query paths with the read scope", () => {
    const path = buildConnectorSyncCheckpointQueryPath("tenant_demo_manufacturing");

    expect(path).toBe(
      "/demo/manufacturing/connectors/runs/checkpoints?tenant_id=tenant_demo_manufacturing&actor_scopes=connectors%3Async%3Acheckpoint%3Aread",
    );
  });
});
