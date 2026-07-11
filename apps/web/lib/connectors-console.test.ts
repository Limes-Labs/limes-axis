import { describe, expect, it } from "vitest";

import type {
  ConnectorCredentialLeaseRecord,
  ConnectorManifestRecord,
  ConnectorOntologyProposalRecord,
  ConnectorPreviewSample,
  ConnectorRegistryItem,
} from "./connectors-demo";
import {
  buildCsvFromPreviewSample,
  buildExternalDbPreviewRequest,
  buildManifestCreateRequest,
  buildPreviewSyncPlan,
  deriveConnectorId,
  findActiveLeaseForConnector,
  manifestRecordForConnector,
  parseCsvText,
  pendingProposalCount,
} from "./connectors-console";

const previewSample: ConnectorPreviewSample = {
  file_name: "assets.csv",
  record_count: 2,
  headers: ["asset_id", "asset_name"],
  sample_rows: [
    { asset_id: "ast-1", asset_name: "CNC Mill, hall \"A\"" },
    { asset_id: "ast-2", asset_name: "Press" },
  ],
};

const templateConnector: ConnectorRegistryItem = {
  manifest: {
    connector_id: "file_csv_manufacturing_assets",
    display_name: "Manufacturing assets CSV",
    connector_type: "file_csv",
    version: "1.0.0",
    source_type: "csv_upload",
    sync_modes: ["preview"],
    runtime_boundary: "self_hosted",
    required_permissions: ["connectors:preview"],
    credential_requirements: {
      storage: "none",
      required_secret_refs: [],
      notes: [],
    },
    schema_fields: [
      {
        source_column: "asset_id",
        target_field: "node_id",
        ontology_target: "manufacturing_asset",
        data_type: "string",
        required: true,
        description: "Asset identifier",
      },
    ],
    mapping_notes: [],
  },
  runtime_policy: {
    allowed_operations: ["preview"],
    blocked_operations: ["live_query"],
    egress_policy: "no-external-egress",
    max_file_size_mb: 5,
    row_limit: 100,
    payload_policy: "metadata_only",
  },
  preview_sample: previewSample,
  connector_status: "watch",
};

function leaseRecord(
  overrides: Partial<ConnectorCredentialLeaseRecord>,
): ConnectorCredentialLeaseRecord {
  return {
    tenant_id: "tenant_demo_manufacturing",
    connector_id: "file_csv_manufacturing_assets",
    handle_id: "handle_a",
    lease_id: "lease_a",
    status: "active",
    lease_mode: "read_only",
    runtime_boundary: "self_hosted",
    requested_by: "worker",
    lease_purpose: "sync",
    secret_provider: "vault",
    secret_ref: "vault://x",
    vault_kms_policy: {},
    permission_decision: { allowed: true, reason: "scope_present" },
    lease_result: {},
    granted_at: "2026-07-10T00:00:00Z",
    expires_at: "2999-01-01T00:00:00Z",
    renewal_due_at: "2999-01-01T00:00:00Z",
    renewed_at: null,
    renewed_by: null,
    renewal_count: 0,
    revoked_at: null,
    revoked_by: null,
    revocation_reason: null,
    audit_event_id: null,
    audit_event_type: "connector.credential.lease",
    notes: [],
    created_at: "2026-07-10T00:00:00Z",
    ...overrides,
  };
}

describe("parseCsvText", () => {
  it("parses headers and rows", () => {
    const parsed = parseCsvText("asset_id,asset_name\nast-1,CNC Mill\nast-2,Press\n");

    expect(parsed.headers).toEqual(["asset_id", "asset_name"]);
    expect(parsed.rows).toEqual([
      { asset_id: "ast-1", asset_name: "CNC Mill" },
      { asset_id: "ast-2", asset_name: "Press" },
    ]);
  });

  it("handles quoted fields containing commas, quotes and newlines", () => {
    const parsed = parseCsvText(
      'asset_id,asset_name\nast-1,"Mill, hall ""A"""\nast-2,"Two\nlines"',
    );

    expect(parsed.rows[0].asset_name).toBe('Mill, hall "A"');
    expect(parsed.rows[1].asset_name).toBe("Two\nlines");
  });

  it("returns empty rows for a header-only file", () => {
    const parsed = parseCsvText("asset_id,asset_name");

    expect(parsed.headers).toEqual(["asset_id", "asset_name"]);
    expect(parsed.rows).toEqual([]);
  });
});

describe("buildCsvFromPreviewSample", () => {
  it("round-trips the recorded sample through the CSV format", () => {
    const csv = buildCsvFromPreviewSample(previewSample);
    const parsed = parseCsvText(csv);

    expect(parsed.headers).toEqual(previewSample.headers);
    expect(parsed.rows).toEqual(previewSample.sample_rows);
  });
});

describe("deriveConnectorId", () => {
  it("builds a safe snake_case id from a file name", () => {
    expect(deriveConnectorId("Plant Assets (Q3).csv", "file_csv")).toBe(
      "file_csv_plant_assets_q3",
    );
  });

  it("falls back to a generic id for unusable names", () => {
    expect(deriveConnectorId("###.csv", "external_db")).toBe("external_db_connector");
  });
});

describe("buildManifestCreateRequest", () => {
  it("copies the template and overrides identity, preview sample and notes", () => {
    const request = buildManifestCreateRequest({
      tenantId: "tenant_demo_manufacturing",
      registeredBy: "plant-operations-owner-role",
      template: templateConnector,
      connectorId: "file_csv_new_assets",
      displayName: "New assets",
      previewSample: previewSample,
    });

    expect(request.tenant_id).toBe("tenant_demo_manufacturing");
    expect(request.registered_by).toBe("plant-operations-owner-role");
    expect(request.manifest.connector_id).toBe("file_csv_new_assets");
    expect(request.manifest.display_name).toBe("New assets");
    expect(request.manifest.connector_type).toBe("file_csv");
    expect(request.manifest.schema_fields).toEqual(templateConnector.manifest.schema_fields);
    expect(request.runtime_policy).toEqual(templateConnector.runtime_policy);
    expect(request.preview_sample).toEqual(previewSample);
    // The template object must not be mutated.
    expect(templateConnector.manifest.connector_id).toBe("file_csv_manufacturing_assets");
  });
});

describe("buildExternalDbPreviewRequest", () => {
  it("selects the template's schema columns and keeps metadata public-safe", () => {
    const request = buildExternalDbPreviewRequest({
      tenantId: "tenant_demo_manufacturing",
      connectorId: "external_db_operational_mirror",
      connectionProfileId: "profile_postgres_ops_readonly",
      schemaName: "operations",
      tableName: "production_orders",
      credentialHandleId: "cred_external_db_readonly",
      template: templateConnector,
    });

    expect(request.selected_columns).toEqual(["asset_id"]);
    expect(request.metadata).toEqual({});
    expect(request.sample_limit).toBeGreaterThan(0);
  });
});

describe("findActiveLeaseForConnector", () => {
  const now = new Date("2026-07-11T00:00:00Z");

  it("returns the first active unexpired lease for the connector", () => {
    const leases = [
      leaseRecord({ lease_id: "lease_other", connector_id: "other" }),
      leaseRecord({ lease_id: "lease_expired", expires_at: "2020-01-01T00:00:00Z" }),
      leaseRecord({ lease_id: "lease_revoked", status: "revoked" }),
      leaseRecord({ lease_id: "lease_good" }),
    ];

    expect(
      findActiveLeaseForConnector(leases, "file_csv_manufacturing_assets", now)?.lease_id,
    ).toBe("lease_good");
  });

  it("returns null when nothing matches", () => {
    expect(findActiveLeaseForConnector([], "file_csv_manufacturing_assets", now)).toBeNull();
  });
});

describe("buildPreviewSyncPlan", () => {
  it("derives run, dispatch and execute payloads with idempotency keys from one token", () => {
    const plan = buildPreviewSyncPlan({
      tenantId: "tenant_demo_manufacturing",
      connectorId: "file_csv_manufacturing_assets",
      actorId: "plant-operations-owner-role",
      lease: leaseRecord({}),
      now: new Date("2026-07-11T08:00:00Z"),
      token: "abc123",
    });

    expect(plan.runId).toBe("run_console_abc123");
    expect(plan.runId).toMatch(/^[a-z0-9][a-z0-9_-]*$/);
    expect(plan.create).toEqual({
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "file_csv_manufacturing_assets",
      run_id: "run_console_abc123",
      execution_mode: "scheduled_sync_plan",
      requested_by: "plant-operations-owner-role",
      credential_handle_ids: ["handle_a"],
      credential_lease_id: "lease_a",
      schedule_id: "sched_console_abc123",
      schedule_cadence: "manual_preview",
      schedule_timezone: "UTC",
      next_run_at: "2026-07-11T08:00:00.000Z",
      input_summary: { trigger: "connector-console-preview-sync" },
      result_summary: {},
      notes: ["Preview sync started from the connector console."],
    });
    expect(plan.dispatch.dispatch_id).toBe("dispatch_console_abc123");
    expect(plan.dispatch.actor_scopes).toEqual(["connectors:sync:dispatch"]);
    expect(plan.dispatch.credential_lease_id).toBe("lease_a");
    expect(plan.dispatch.idempotency_key).toBe("idem_dispatch_console_abc123");
    expect(plan.execute.execution_id).toBe("exec_console_abc123");
    expect(plan.execute.actor_scopes).toEqual(["connectors:sync:execute"]);
    expect(plan.execute.idempotency_key).toBe("idem_exec_console_abc123");
  });
});

describe("registry summaries", () => {
  it("counts proposals that have not been promoted yet", () => {
    const proposals = [
      { promoted_at: null },
      { promoted_at: "2026-07-10T00:00:00Z" },
      { promoted_at: null },
    ] as ConnectorOntologyProposalRecord[];

    expect(pendingProposalCount(proposals)).toBe(2);
  });

  it("finds the persisted manifest record for a connector", () => {
    const manifests = [
      { connector_id: "a", status: "registered_preview_only" },
      { connector_id: "b", status: "active_preview" },
    ] as ConnectorManifestRecord[];

    expect(manifestRecordForConnector(manifests, "b")?.status).toBe("active_preview");
    expect(manifestRecordForConnector(manifests, "missing")).toBeNull();
  });
});
