import { describe, expect, it } from "vitest";

import {
  buildConnectorSyncCheckpointClaimQueryPath,
  buildConnectorSyncCheckpointQueryPath,
  buildConnectorPromotionPolicyDraftRequest,
  buildConnectorPromotionPolicyEnableRequest,
  filterConnectorSyncCheckpointInvariantsByCheckpoints,
  filterConnectorSyncCheckpointClaimsByCheckpoints,
  filterConnectorSyncCheckpointsByConnector,
  findConnectorById,
  formatConnectorLabel,
  type ManufacturingConnectorSyncCheckpointClaimRegistry,
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
  evidence_invariants: [
    {
      checkpoint_id: "chk_external_db_sync_1",
      audit_event_id: null,
      reason: "checkpoint_audit_event_missing",
      detail: "Checkpoint must reference an append-only audit event.",
    },
    {
      checkpoint_id: "chk_file_csv_sync_1",
      audit_event_id: null,
      reason: "checkpoint_audit_event_missing",
      detail: "Checkpoint must reference an append-only audit event.",
    },
  ],
  checkpoint_notes: ["Sync checkpoints are tenant-scoped runtime evidence for retry/resume."],
};

const checkpointClaimRegistryFixture: ManufacturingConnectorSyncCheckpointClaimRegistry = {
  tenant_id: "tenant_demo_manufacturing",
  plant_name: "Ravenna Works",
  scenario: "Plant Operations Cockpit",
  registry_status: "ready",
  metrics: [],
  next_cursor: null,
  has_more: false,
  claims: [
    {
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "external_db_operational_mirror",
      run_id: "run_external_db_sync_20260625",
      checkpoint_id: "chk_external_db_sync_2",
      claim_id: "claim_external_db_sync_2_worker_b",
      status: "released",
      claimed_by: "axis-sync-worker-role-b",
      idempotency_key: "idem_claim_external_db_sync_2_worker_b",
      lease_duration_seconds: 900,
      lease_expires_at: "2026-06-25T08:30:00Z",
      renewed_at: null,
      renewed_by: null,
      renewal_count: 0,
      released_at: "2026-06-25T08:21:00Z",
      released_by: "axis-sync-worker-role-b",
      release_reason: "checkpoint handed back after retry planning",
      claim_result: {
        external_sync_started: false,
        secret_material_returned: false,
        worker_claim_only: true,
      },
      audit_event_id: "9ed40ef1-55bb-4f06-8aa5-d3b0a9100769",
      audit_event_type: "connector.run.sync_checkpoint_claim_released",
      notes: ["Released claim from the API response."],
      created_at: "2026-06-25T08:16:00Z",
    },
    {
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "file_csv_manufacturing_assets",
      run_id: "run_file_csv_sync_20260625",
      checkpoint_id: "chk_file_csv_sync_1",
      claim_id: "claim_file_csv_sync_1_worker",
      status: "claimed",
      claimed_by: "axis-sync-worker-role-file",
      idempotency_key: "idem_claim_file_csv_sync_1_worker",
      lease_duration_seconds: 900,
      lease_expires_at: "2026-06-25T08:25:00Z",
      renewed_at: null,
      renewed_by: null,
      renewal_count: 0,
      released_at: null,
      released_by: null,
      release_reason: null,
      claim_result: {
        external_sync_started: false,
        secret_material_returned: false,
        worker_claim_only: true,
      },
      audit_event_id: null,
      audit_event_type: "connector.run.sync_checkpoint_claimed",
      notes: [],
      created_at: "2026-06-25T08:11:00Z",
    },
    {
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "external_db_operational_mirror",
      run_id: "run_external_db_sync_20260625",
      checkpoint_id: "chk_external_db_sync_1",
      claim_id: "claim_external_db_sync_1_worker_a",
      status: "claimed",
      claimed_by: "axis-sync-worker-role-a",
      idempotency_key: "idem_claim_external_db_sync_1_worker_a",
      lease_duration_seconds: 600,
      lease_expires_at: "2026-06-25T08:15:00Z",
      renewed_at: "2026-06-25T08:08:00Z",
      renewed_by: "axis-sync-worker-role-a",
      renewal_count: 1,
      released_at: null,
      released_by: null,
      release_reason: null,
      claim_result: {
        external_sync_started: false,
        secret_material_returned: false,
        worker_claim_only: true,
      },
      audit_event_id: null,
      audit_event_type: "connector.run.sync_checkpoint_claim_renewed",
      notes: ["Active claim from the API response."],
      created_at: "2026-06-25T08:06:00Z",
    },
  ],
  claim_notes: ["Checkpoint claim records expose worker ownership and lease state."],
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

  it("filters checkpoint evidence invariants for selected connector checkpoints", () => {
    const checkpoints = filterConnectorSyncCheckpointsByConnector(
      checkpointRegistryFixture,
      "external_db_operational_mirror",
    );

    const invariants = filterConnectorSyncCheckpointInvariantsByCheckpoints(
      checkpointRegistryFixture,
      checkpoints,
    );

    expect(invariants).toEqual([
      {
        checkpoint_id: "chk_external_db_sync_1",
        audit_event_id: null,
        reason: "checkpoint_audit_event_missing",
        detail: "Checkpoint must reference an append-only audit event.",
      },
    ]);
    expect(JSON.stringify(invariants).toLowerCase()).not.toContain("credential_value");
    expect(JSON.stringify(invariants).toLowerCase()).not.toContain("password");
  });

  it("builds connector sync checkpoint query paths with the read scope", () => {
    const path = buildConnectorSyncCheckpointQueryPath("tenant_demo_manufacturing");

    expect(path).toBe(
      "/demo/manufacturing/connectors/runs/checkpoints?tenant_id=tenant_demo_manufacturing&actor_scopes=connectors%3Async%3Acheckpoint%3Aread",
    );
  });

  it("builds connector sync checkpoint query paths with created-before pagination", () => {
    const path = buildConnectorSyncCheckpointQueryPath("tenant_demo_manufacturing", {
      createdBefore: "2026-06-25T11:00:00Z",
    });

    expect(path).toBe(
      "/demo/manufacturing/connectors/runs/checkpoints?tenant_id=tenant_demo_manufacturing&actor_scopes=connectors%3Async%3Acheckpoint%3Aread&created_before=2026-06-25T11%3A00%3A00Z",
    );
  });

  it("builds connector sync checkpoint query paths with created-after windows", () => {
    const path = buildConnectorSyncCheckpointQueryPath("tenant_demo_manufacturing", {
      createdAfter: "2026-06-25T10:00:00Z",
      createdBefore: "2026-06-25T11:00:00Z",
    });

    expect(path).toBe(
      "/demo/manufacturing/connectors/runs/checkpoints?tenant_id=tenant_demo_manufacturing&actor_scopes=connectors%3Async%3Acheckpoint%3Aread&created_after=2026-06-25T10%3A00%3A00Z&created_before=2026-06-25T11%3A00%3A00Z",
    );
  });

  it("filters checkpoint claims for the selected checkpoint records without secret material", () => {
    const checkpoints = filterConnectorSyncCheckpointsByConnector(
      checkpointRegistryFixture,
      "external_db_operational_mirror",
    );
    const claims = filterConnectorSyncCheckpointClaimsByCheckpoints(
      checkpointClaimRegistryFixture,
      checkpoints,
    );

    expect(claims.map((claim) => claim.claim_id)).toEqual([
      "claim_external_db_sync_1_worker_a",
      "claim_external_db_sync_2_worker_b",
    ]);
    expect(JSON.stringify(claims).toLowerCase()).not.toContain("dsn");
    expect(JSON.stringify(claims).toLowerCase()).not.toContain("credential_value");
    expect(JSON.stringify(claims).toLowerCase()).not.toContain("password");
  });

  it("builds connector sync checkpoint claim query paths with the read scope", () => {
    const path = buildConnectorSyncCheckpointClaimQueryPath("tenant_demo_manufacturing");

    expect(path).toBe(
      "/demo/manufacturing/connectors/runs/checkpoints/claims?tenant_id=tenant_demo_manufacturing&actor_scopes=connectors%3Async%3Acheckpoint%3Aclaim%3Aread",
    );
  });

  it("builds connector sync checkpoint claim query paths with a cursor", () => {
    const path = buildConnectorSyncCheckpointClaimQueryPath("tenant_demo_manufacturing", {
      cursor: "opaque-cursor-page-2",
    });

    expect(path).toBe(
      "/demo/manufacturing/connectors/runs/checkpoints/claims?tenant_id=tenant_demo_manufacturing&actor_scopes=connectors%3Async%3Acheckpoint%3Aclaim%3Aread&cursor=opaque-cursor-page-2",
    );
  });

  it("builds connector sync checkpoint claim query paths with time windows", () => {
    const path = buildConnectorSyncCheckpointClaimQueryPath("tenant_demo_manufacturing", {
      createdAfter: "2026-06-25T10:15:00Z",
      createdBefore: "2026-06-25T10:25:00Z",
    });

    expect(path).toBe(
      "/demo/manufacturing/connectors/runs/checkpoints/claims?tenant_id=tenant_demo_manufacturing&actor_scopes=connectors%3Async%3Acheckpoint%3Aclaim%3Aread&created_after=2026-06-25T10%3A15%3A00Z&created_before=2026-06-25T10%3A25%3A00Z",
    );
  });
});
