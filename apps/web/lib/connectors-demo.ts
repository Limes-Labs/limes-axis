import type { PlatformStatus } from "./platform-overview";

export type ConnectorCredentialRequirements = {
  storage: string;
  required_secret_refs: string[];
  notes: string[];
};

export type ConnectorSchemaField = {
  source_column: string;
  target_field: string;
  ontology_target: string;
  data_type: string;
  required: boolean;
  description: string;
};

export type ConnectorManifest = {
  connector_id: string;
  display_name: string;
  connector_type: string;
  version: string;
  source_type: string;
  sync_modes: string[];
  runtime_boundary: string;
  required_permissions: string[];
  credential_requirements: ConnectorCredentialRequirements;
  schema_fields: ConnectorSchemaField[];
  mapping_notes: string[];
};

export type ConnectorRuntimePolicy = {
  allowed_operations: string[];
  blocked_operations: string[];
  egress_policy: string;
  max_file_size_mb: number;
  row_limit: number;
  payload_policy: string;
};

export type ConnectorPreviewSample = {
  file_name: string;
  record_count: number;
  headers: string[];
  sample_rows: Record<string, string>[];
};

export type ConnectorRegistryItem = {
  manifest: ConnectorManifest;
  runtime_policy: ConnectorRuntimePolicy;
  preview_sample: ConnectorPreviewSample;
  connector_status: PlatformStatus;
};

export type ManufacturingConnectorRegistry = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  registry_status: PlatformStatus;
  metrics: {
    label: string;
    value: string;
    detail: string;
    status: PlatformStatus;
  }[];
  connectors: ConnectorRegistryItem[];
  connector_notes: string[];
};

export type ConnectorManifestRecord = {
  tenant_id: string;
  manifest_id: string;
  connector_id: string;
  display_name: string;
  connector_type: string;
  source_type: string;
  version: string;
  status: string;
  runtime_boundary: string;
  registered_by: string;
  manifest: ConnectorManifest;
  runtime_policy: ConnectorRuntimePolicy;
  preview_sample: ConnectorPreviewSample;
  audit_event_id: string | null;
  audit_event_type: string;
  notes: string[];
  created_at: string;
};

export type ManufacturingConnectorManifestRegistry = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  registry_status: PlatformStatus;
  metrics: {
    label: string;
    value: string;
    detail: string;
    status: PlatformStatus;
  }[];
  manifests: ConnectorManifestRecord[];
  manifest_notes: string[];
};

export type ConnectorCsvPreviewRequest = {
  tenant_id: string;
  connector_id: string;
  file_name: string;
  csv_content: string;
};

export type ConnectorExternalDbPreviewRequest = {
  tenant_id: string;
  connector_id: string;
  connection_profile_id: string;
  schema_name: string;
  table_name: string;
  selected_columns: string[];
  sample_limit: number;
  credential_handle_id: string;
  metadata: Record<string, string>;
};

export type ConnectorConfigurationCreateRequest = {
  tenant_id: string;
  connector_id: string;
  display_name: string;
  sync_mode: string;
  created_by: string;
  configuration_payload: Record<string, string>;
  credential_ref_ids: string[];
  notes: string[];
};

export type ProposedOntologyEntity = {
  node_id: string;
  node_type: string;
  ontology_type: string;
  field_summary: Record<string, string>;
  evidence_refs: string[];
};

export type ConnectorAuditEventPreview = {
  event_type: string;
  scope: string;
  actor_id: string;
  result: string;
  evidence_refs: string[];
  payload_preview: Record<string, string>;
};

export type ConnectorCsvPreviewResult = {
  tenant_id: string;
  connector_id: string;
  file_name: string;
  preview_status: string;
  sync_mode: string;
  record_count: number;
  accepted_record_count: number;
  rejected_record_count: number;
  validation_issues: string[];
  proposed_entities: ProposedOntologyEntity[];
  audit_event_preview: ConnectorAuditEventPreview;
  preview_notes: string[];
};

export type ConnectorExternalDbColumnPreview = {
  source_column: string;
  target_field: string;
  ontology_target: string;
  data_type: string;
  nullable: boolean;
};

export type ConnectorExternalDbTablePreview = {
  schema_name: string;
  table_name: string;
  table_ref: string;
  record_count_estimate: string;
  sample_limit: number;
  columns: ConnectorExternalDbColumnPreview[];
  sample_rows: Record<string, string>[];
};

export type ConnectorExternalDbPreviewResult = {
  tenant_id: string;
  connector_id: string;
  connection_profile_id: string;
  source_type: string;
  preview_status: string;
  sync_mode: string;
  live_query_executed: boolean;
  validation_issues: string[];
  inspected_table: ConnectorExternalDbTablePreview;
  proposed_entities: ProposedOntologyEntity[];
  audit_event_preview: ConnectorAuditEventPreview;
  preview_notes: string[];
};

export type ConnectorTenantConfiguration = {
  tenant_id: string;
  connector_id: string;
  display_name: string;
  status: string;
  sync_mode: string;
  runtime_boundary: string;
  created_by: string;
  configuration_payload: Record<string, string>;
  credential_ref_ids: string[];
  notes: string[];
};

export type ManufacturingConnectorConfigurationRegistry = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  registry_status: PlatformStatus;
  metrics: {
    label: string;
    value: string;
    detail: string;
    status: PlatformStatus;
  }[];
  configurations: ConnectorTenantConfiguration[];
  configuration_notes: string[];
};

export type ConnectorCredentialRotation = {
  tenant_id: string;
  handle_id: string;
  rotated_by: string;
  rotated_at: string;
  evidence_ref: string;
  status: string;
  notes: string[];
};

export type ConnectorCredentialHandle = {
  tenant_id: string;
  connector_id: string;
  handle_id: string;
  display_name: string;
  status: string;
  secret_provider: string;
  secret_ref: string;
  purpose: string;
  rotation_interval_days: number;
  rotation_status: string;
  rotation_count: number;
  last_rotated_at: string | null;
  next_rotation_due_at: string | null;
  created_by: string;
  labels: Record<string, string>;
  notes: string[];
  last_rotation: ConnectorCredentialRotation | null;
};

export type ManufacturingConnectorCredentialHandleRegistry = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  registry_status: PlatformStatus;
  metrics: {
    label: string;
    value: string;
    detail: string;
    status: PlatformStatus;
  }[];
  handles: ConnectorCredentialHandle[];
  handle_notes: string[];
};

export type ConnectorCredentialLeaseRecord = {
  tenant_id: string;
  connector_id: string;
  handle_id: string;
  lease_id: string;
  status: string;
  lease_mode: string;
  runtime_boundary: string;
  requested_by: string;
  lease_purpose: string;
  secret_provider: string;
  secret_ref: string;
  vault_kms_policy: Record<string, string>;
  permission_decision: {
    allowed: boolean;
    reason: string;
  };
  lease_result: Record<string, string>;
  granted_at: string;
  expires_at: string;
  renewal_due_at: string;
  renewed_at: string | null;
  renewed_by: string | null;
  renewal_count: number;
  revoked_at: string | null;
  revoked_by: string | null;
  revocation_reason: string | null;
  audit_event_id: string | null;
  audit_event_type: string;
  notes: string[];
  created_at: string;
};

export type ManufacturingConnectorCredentialLeaseRegistry = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  registry_status: PlatformStatus;
  metrics: {
    label: string;
    value: string;
    detail: string;
    status: PlatformStatus;
  }[];
  leases: ConnectorCredentialLeaseRecord[];
  lease_notes: string[];
};

export type ConnectorRunRecord = {
  tenant_id: string;
  connector_id: string;
  run_id: string;
  status: string;
  execution_mode: string;
  runtime_boundary: string;
  requested_by: string;
  credential_handle_ids: string[];
  input_summary: Record<string, string>;
  result_summary: Record<string, unknown>;
  execution_result: ConnectorExecutionResult | null;
  schedule_result: ConnectorSyncScheduleResult | null;
  dispatch_result: ConnectorSyncDispatchResult | null;
  sync_execution_result: ConnectorSyncExecutionResult | null;
  audit_event_id: string | null;
  audit_event_type: string;
  notes: string[];
  created_at: string;
};

export type ConnectorExecutionResult = {
  adapter: string;
  status: string;
  external_sync_started: boolean;
  idempotency_key: string;
  result_summary: Record<string, string>;
  notes: string[];
};

export type ConnectorSyncScheduleResult = {
  adapter: string;
  status: string;
  schedule_ref: string;
  external_sync_started: boolean;
  idempotency_key: string;
  result_summary: Record<string, string>;
  notes: string[];
};

export type ConnectorSyncDispatchResult = {
  adapter: string;
  status: string;
  dispatch_ref: string;
  external_sync_started: boolean;
  idempotency_key: string;
  result_summary: Record<string, string>;
  notes: string[];
};

export type ConnectorSyncExecutionResult = {
  adapter: string;
  status: string;
  sync_ref: string;
  external_sync_started: boolean;
  idempotency_key: string;
  result_summary: Record<string, string>;
  notes: string[];
};

export type ManufacturingConnectorRunRegistry = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  registry_status: PlatformStatus;
  metrics: {
    label: string;
    value: string;
    detail: string;
    status: PlatformStatus;
  }[];
  runs: ConnectorRunRecord[];
  run_notes: string[];
};

export type ConnectorOntologyProposalRecord = {
  tenant_id: string;
  connector_id: string;
  proposal_id: string;
  source_run_id: string | null;
  source_file_name: string;
  mapping_profile: string;
  status: string;
  write_mode: string;
  graph_mutation_status: string;
  proposed_by: string;
  node_id: string;
  node_type: string;
  ontology_type: string;
  field_summary: Record<string, string>;
  evidence_refs: string[];
  promotion_id: string | null;
  policy_id: string | null;
  policy_set_id: string | null;
  policy_ids: string[] | null;
  policy_decision: ConnectorPromotionPolicyDecision | null;
  promoted_by: string | null;
  promoted_at: string | null;
  ontology_mutation: {
    status: string;
    adapter: string;
    mutation_ref: string | null;
    typeql: string | null;
    payload: Record<string, unknown>;
  } | null;
  audit_event_id: string | null;
  audit_event_type: string;
  notes: string[];
  created_at: string;
};

export type ConnectorPromotionPolicyDecision = {
  status: string;
  allowed: boolean;
  policy_id: string | null;
  policy_version: string | null;
  policy_set_id: string | null;
  policy_set_version: string | null;
  policy_ids: string[];
  policy_results: Record<string, unknown>[];
  enforcement_mode: string;
  reason: string;
  required_scopes: string[];
  matched_constraints: Record<string, string>;
};

export type ManufacturingConnectorOntologyProposalRegistry = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  registry_status: PlatformStatus;
  metrics: {
    label: string;
    value: string;
    detail: string;
    status: PlatformStatus;
  }[];
  proposals: ConnectorOntologyProposalRecord[];
  proposal_notes: string[];
};

export type ConnectorManualImportRecord = {
  tenant_id: string;
  connector_id: string;
  import_id: string;
  idempotency_key: string;
  status: string;
  import_mode: string;
  requested_by: string;
  owner_role: string;
  risk_level: string;
  approval_id: string;
  workflow_id: string;
  proposal_ids: string[];
  import_summary: Record<string, string>;
  controls: string[];
  graph_mutation_status: string;
  workflow_signal_status: string;
  decision: string | null;
  decision_actor_id: string | null;
  decision_note: string | null;
  decided_at: string | null;
  workflow_signal: {
    workflow_id: string;
    status: string;
    adapter: string;
    signal_name: string;
    payload: Record<string, unknown>;
  } | null;
  audit_event_id: string | null;
  audit_event_type: string;
  notes: string[];
  created_at: string;
  idempotent_replay: boolean;
};

export type ManufacturingConnectorManualImportRegistry = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  registry_status: PlatformStatus;
  metrics: {
    label: string;
    value: string;
    detail: string;
    status: PlatformStatus;
  }[];
  imports: ConnectorManualImportRecord[];
  import_notes: string[];
};

export type ConnectorPromotionPolicyRecord = {
  tenant_id: string;
  connector_id: string;
  policy_id: string;
  policy_version: string;
  status: string;
  enforcement_mode: string;
  created_by: string;
  required_authoring_scope: string;
  required_scopes: string[];
  required_manual_import_status: string;
  required_workflow_signal_status: string;
  allowed_risk_levels: string[];
  allowed_ontology_types: string[];
  review_window_hours: number;
  permission_decision: {
    allowed: boolean;
    reason: string;
  };
  audit_event_id: string | null;
  audit_event_type: string;
  revises_policy_id: string | null;
  replaced_by_policy_id: string | null;
  revision_idempotency_key: string | null;
  revision_approval_id: string | null;
  revision_decision: string | null;
  revision_workflow_signal_status: string | null;
  idempotent_replay: boolean;
  notes: string[];
  created_at: string;
};

export type ConnectorPromotionPolicyCreateRequest = {
  tenant_id: string;
  connector_id: string;
  policy_id: string;
  policy_version: string;
  status: string;
  enforcement_mode: string;
  created_by: string;
  actor_scopes: string[];
  required_scopes: string[];
  required_manual_import_status: string;
  required_workflow_signal_status: string;
  allowed_risk_levels: string[];
  allowed_ontology_types: string[];
  review_window_hours: number;
  notes: string[];
};

export type ConnectorPromotionPolicyEnableRequest = {
  tenant_id: string;
  policy_id: string;
  enabled_by: string;
  actor_scopes: string[];
  approval_id: string;
  approval_decision: string;
  workflow_signal_status: string;
  note: string | null;
};

export type ManufacturingConnectorPromotionPolicyRegistry = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  registry_status: PlatformStatus;
  metrics: {
    label: string;
    value: string;
    detail: string;
    status: PlatformStatus;
  }[];
  policies: ConnectorPromotionPolicyRecord[];
  policy_notes: string[];
};

export type ConnectorPromotionPolicyRevisionAdoptionRecord = {
  current_policy_id: string;
  revised_policy_id: string;
  revision_idempotency_key: string;
  adoption_approval_id: string | null;
  adoption_decision: string | null;
  adoption_workflow_signal_status: string | null;
  audit_event_id: string | null;
  audit_event_type: string | null;
};

export type ConnectorPromotionPolicySetRecord = {
  tenant_id: string;
  connector_id: string;
  policy_set_id: string;
  policy_set_version: string;
  status: string;
  activated_by: string;
  activation_scope: string;
  policy_ids: string[];
  permission_decision: {
    allowed: boolean;
    reason: string;
  };
  audit_event_id: string | null;
  audit_event_type: string;
  activation_reason: string;
  replaces_policy_set_id: string | null;
  replaced_by_policy_set_id: string | null;
  replacement_approval_id: string | null;
  replacement_decision: string | null;
  replacement_workflow_signal_status: string | null;
  replaced_at: string | null;
  rollback_to_policy_set_id: string | null;
  rollback_approval_id: string | null;
  rollback_decision: string | null;
  rollback_workflow_signal_status: string | null;
  policy_revision_adoptions: ConnectorPromotionPolicyRevisionAdoptionRecord[];
  notes: string[];
  created_at: string;
};

export type ManufacturingConnectorPromotionPolicySetRegistry = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  registry_status: PlatformStatus;
  metrics: {
    label: string;
    value: string;
    detail: string;
    status: PlatformStatus;
  }[];
  policy_sets: ConnectorPromotionPolicySetRecord[];
  policy_set_notes: string[];
};

export const defaultManufacturingConnectorRegistry: ManufacturingConnectorRegistry = {
  tenant_id: "tenant_demo_manufacturing",
  plant_name: "Ravenna Works",
  scenario: "Plant Operations Cockpit",
  registry_status: "watch",
  metrics: [
    {
      label: "Connector Manifests",
      value: "2",
      detail: "Public-safe connector manifests available for preview",
      status: "ready",
    },
    {
      label: "CSV Preview",
      value: "Ready",
      detail: "File connector can validate and map local CSV rows",
      status: "ready",
    },
    {
      label: "External DB Preview",
      value: "Metadata Only",
      detail: "Database connector preview uses profile ids and handles only",
      status: "ready",
    },
    {
      label: "Live Sync",
      value: "Blocked",
      detail: "No live connector mutation is enabled in this foundation slice",
      status: "watch",
    },
  ],
  connectors: [
    {
      connector_status: "watch",
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
          notes: [
            "Local CSV preview does not require stored credentials.",
            "Future connector runs must reference credential handles, not raw values.",
          ],
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
          {
            source_column: "asset_name",
            target_field: "display_name",
            ontology_target: "manufacturing_asset",
            data_type: "string",
            required: true,
            description: "Human-readable manufacturing asset name.",
          },
          {
            source_column: "domain",
            target_field: "domain",
            ontology_target: "manufacturing_asset",
            data_type: "string",
            required: true,
            description: "Operational domain such as Operations, Quality or Maintenance.",
          },
          {
            source_column: "station",
            target_field: "source_system_ref",
            ontology_target: "manufacturing_asset",
            data_type: "string",
            required: true,
            description: "Plant station, line or source-system reference.",
          },
          {
            source_column: "risk_level",
            target_field: "risk_level",
            ontology_target: "manufacturing_asset",
            data_type: "string",
            required: true,
            description: "Public-safe risk posture used for demo governance checks.",
          },
        ],
        mapping_notes: [
          "CSV preview maps rows to ontology entity proposals only.",
          "Manual import remains approval-gated and workflow-signaled before execution.",
          "Raw file content is never returned in API responses.",
        ],
      },
      runtime_policy: {
        allowed_operations: ["schema_validate", "preview_mapping", "dry_run_diff"],
        blocked_operations: ["live_write", "credential_capture", "external_egress"],
        egress_policy: "no-external-egress",
        max_file_size_mb: 5,
        row_limit: 500,
        payload_policy: "redacted-preview-only",
      },
      preview_sample: {
        file_name: "manufacturing-assets-demo.csv",
        record_count: 3,
        headers: ["asset_id", "asset_name", "domain", "station", "risk_level"],
        sample_rows: [
          {
            asset_id: "asset_line_2_packaging",
            asset_name: "Line 2 Packaging",
            domain: "Operations",
            station: "Line 2",
            risk_level: "high",
          },
          {
            asset_id: "asset_press_4",
            asset_name: "Press 4",
            domain: "Maintenance",
            station: "Press 4",
            risk_level: "medium",
          },
        ],
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
          notes: [
            "Database preview uses credential handles and profile ids only.",
            "Raw DSNs, SQL text and credential values are rejected.",
          ],
        },
        schema_fields: [
          {
            source_column: "order_id",
            target_field: "node_id",
            ontology_target: "production_order",
            data_type: "string",
            required: true,
            description: "Stable production order identifier from the source table.",
          },
          {
            source_column: "asset_id",
            target_field: "asset_ref",
            ontology_target: "production_order",
            data_type: "string",
            required: true,
            description: "Manufacturing asset reference linked by policy-aware import.",
          },
          {
            source_column: "work_center",
            target_field: "source_system_ref",
            ontology_target: "production_order",
            data_type: "string",
            required: true,
            description: "Operational work center or line reference.",
          },
          {
            source_column: "status",
            target_field: "operational_status",
            ontology_target: "production_order",
            data_type: "string",
            required: true,
            description: "Public-safe order status used for preview mapping.",
          },
          {
            source_column: "risk_level",
            target_field: "risk_level",
            ontology_target: "production_order",
            data_type: "string",
            required: true,
            description: "Governance risk posture used for import controls.",
          },
        ],
        mapping_notes: [
          "Database preview inspects declared metadata only; no live SQL is executed.",
          "Imports remain proposal-only until approval, workflow and policy gates pass.",
          "Connection details stay outside Axis as credential handles and profiles.",
        ],
      },
      runtime_policy: {
        allowed_operations: ["schema_validate", "metadata_preview", "dry_run_diff"],
        blocked_operations: [
          "live_query",
          "live_write",
          "credential_capture",
          "external_egress",
        ],
        egress_policy: "no-external-egress",
        max_file_size_mb: 5,
        row_limit: 100,
        payload_policy: "metadata-only-redacted-preview",
      },
      preview_sample: {
        file_name: "profile_postgres_ops_readonly:operations.production_orders",
        record_count: 2,
        headers: ["order_id", "asset_id", "work_center", "status", "risk_level"],
        sample_rows: [
          {
            order_id: "order_po_10045",
            asset_id: "asset_line_2_packaging",
            work_center: "Line 2",
            status: "blocked",
            risk_level: "high",
          },
          {
            order_id: "order_po_10046",
            asset_id: "asset_press_4",
            work_center: "Press 4",
            status: "scheduled",
            risk_level: "medium",
          },
        ],
      },
    },
  ],
  connector_notes: [
    "Connector manifests are public-safe and preview-only.",
    "The file/CSV connector maps rows to ontology proposals without writing data.",
    "The external DB connector previews declared metadata without live SQL.",
    "Credential retrieval, scheduled sync and production connector runs remain future work.",
  ],
};

export const defaultConnectorManifestRegistry: ManufacturingConnectorManifestRegistry = {
  tenant_id: "tenant_demo_manufacturing",
  plant_name: "Ravenna Works",
  scenario: "Plant Operations Cockpit",
  registry_status: "ready",
  metrics: [
    {
      label: "Persisted Manifests",
      value: "2",
      detail: "Tenant-scoped connector manifest records",
      status: "ready",
    },
    {
      label: "Raw Material",
      value: "Rejected",
      detail: "DSNs, SQL text and credential values are blocked",
      status: "ready",
    },
    {
      label: "Live Sync",
      value: "Not Enabled",
      detail: "Persisting a manifest does not start connector execution",
      status: "watch",
    },
  ],
  manifests: defaultManufacturingConnectorRegistry.connectors.map((connector, index) => ({
    tenant_id: "tenant_demo_manufacturing",
    manifest_id:
      index === 0
        ? "manifest_file_csv_manufacturing_assets"
        : "manifest_external_db_operational_mirror",
    connector_id: connector.manifest.connector_id,
    display_name: connector.manifest.display_name,
    connector_type: connector.manifest.connector_type,
    source_type: connector.manifest.source_type,
    version: connector.manifest.version,
    status: "registered_preview_only",
    runtime_boundary: connector.manifest.runtime_boundary,
    registered_by: "platform-connector-owner-role",
    manifest: connector.manifest,
    runtime_policy: connector.runtime_policy,
    preview_sample: connector.preview_sample,
    audit_event_id:
      index === 0
        ? "audit_connector_manifest_file_csv_20260622"
        : "audit_connector_manifest_external_db_20260622",
    audit_event_type: "connector.manifest.registered",
    notes: ["Manifest registration is metadata-only and does not enable live sync."],
    created_at: "2026-06-22T00:00:00Z",
  })),
  manifest_notes: [
    "Persisted connector manifests are tenant-scoped metadata records.",
    "Registration writes audit evidence but does not enable live sync.",
    "Raw connection strings, SQL text and credential values are rejected.",
  ],
};

export const defaultManufacturingConnectorPreview: ConnectorCsvPreviewResult = {
  tenant_id: "tenant_demo_manufacturing",
  connector_id: "file_csv_manufacturing_assets",
  file_name: "manufacturing-assets-demo.csv",
  preview_status: "ready",
  sync_mode: "preview_only",
  record_count: 2,
  accepted_record_count: 2,
  rejected_record_count: 0,
  validation_issues: [],
  proposed_entities: [
    {
      node_id: "asset_line_2_packaging",
      node_type: "asset",
      ontology_type: "manufacturing_asset",
      field_summary: {
        asset_name: "Line 2 Packaging",
        domain: "Operations",
        station: "Line 2",
        risk_level: "high",
      },
      evidence_refs: ["manufacturing-assets-demo.csv", "asset_line_2_packaging"],
    },
    {
      node_id: "asset_press_4",
      node_type: "asset",
      ontology_type: "manufacturing_asset",
      field_summary: {
        asset_name: "Press 4",
        domain: "Maintenance",
        station: "Press 4",
        risk_level: "medium",
      },
      evidence_refs: ["manufacturing-assets-demo.csv", "asset_press_4"],
    },
  ],
  audit_event_preview: {
    event_type: "connector.preview.generated",
    scope: "file_csv_manufacturing_assets",
    actor_id: "connector-preview-service",
    result: "ready",
    evidence_refs: ["manufacturing-assets-demo.csv", "file_csv_manufacturing_assets"],
    payload_preview: {
      file_name: "manufacturing-assets-demo.csv",
      record_count: "2",
      accepted_record_count: "2",
      rejected_record_count: "0",
    },
  },
  preview_notes: [
    "CSV content is parsed only for preview and is not persisted.",
    "Mapped rows become ontology proposals, not live graph mutations.",
    "Connector execution and scheduled sync remain outside preview boundaries.",
  ],
};

export const defaultExternalDbConnectorPreview: ConnectorExternalDbPreviewResult = {
  tenant_id: "tenant_demo_manufacturing",
  connector_id: "external_db_operational_mirror",
  connection_profile_id: "profile_postgres_ops_readonly",
  source_type: "database",
  preview_status: "ready",
  sync_mode: "schema_preview_only",
  live_query_executed: false,
  validation_issues: [],
  inspected_table: {
    schema_name: "operations",
    table_name: "production_orders",
    table_ref: "operations.production_orders",
    record_count_estimate: "not_queried",
    sample_limit: 2,
    columns: [
      {
        source_column: "order_id",
        target_field: "node_id",
        ontology_target: "production_order",
        data_type: "string",
        nullable: false,
      },
      {
        source_column: "asset_id",
        target_field: "asset_ref",
        ontology_target: "production_order",
        data_type: "string",
        nullable: false,
      },
      {
        source_column: "work_center",
        target_field: "source_system_ref",
        ontology_target: "production_order",
        data_type: "string",
        nullable: false,
      },
      {
        source_column: "status",
        target_field: "operational_status",
        ontology_target: "production_order",
        data_type: "string",
        nullable: false,
      },
      {
        source_column: "risk_level",
        target_field: "risk_level",
        ontology_target: "production_order",
        data_type: "string",
        nullable: false,
      },
    ],
    sample_rows: [
      {
        order_id: "order_po_10045",
        asset_id: "asset_line_2_packaging",
        work_center: "Line 2",
        status: "blocked",
        risk_level: "high",
      },
      {
        order_id: "order_po_10046",
        asset_id: "asset_press_4",
        work_center: "Press 4",
        status: "scheduled",
        risk_level: "medium",
      },
    ],
  },
  proposed_entities: [
    {
      node_id: "order_po_10045",
      node_type: "work_order",
      ontology_type: "production_order",
      field_summary: {
        asset_id: "asset_line_2_packaging",
        work_center: "Line 2",
        status: "blocked",
        risk_level: "high",
      },
      evidence_refs: [
        "profile_postgres_ops_readonly",
        "operations.production_orders",
        "order_po_10045",
      ],
    },
    {
      node_id: "order_po_10046",
      node_type: "work_order",
      ontology_type: "production_order",
      field_summary: {
        asset_id: "asset_press_4",
        work_center: "Press 4",
        status: "scheduled",
        risk_level: "medium",
      },
      evidence_refs: [
        "profile_postgres_ops_readonly",
        "operations.production_orders",
        "order_po_10046",
      ],
    },
  ],
  audit_event_preview: {
    event_type: "connector.external_db.previewed",
    scope: "external_db_operational_mirror",
    actor_id: "connector-preview-service",
    result: "ready",
    evidence_refs: [
      "profile_postgres_ops_readonly",
      "operations.production_orders",
      "cred_external_db_readonly",
    ],
    payload_preview: {
      connection_profile_id: "profile_postgres_ops_readonly",
      table_ref: "operations.production_orders",
      live_query_executed: "false",
      credential_handle_id: "cred_external_db_readonly",
    },
  },
  preview_notes: [
    "External DB preview is metadata-only and does not execute SQL.",
    "Connection details remain outside Axis behind profile ids and credential handles.",
    "Mapped rows become ontology proposals, not live graph mutations.",
  ],
};

export const defaultConnectorConfigurationRegistry: ManufacturingConnectorConfigurationRegistry = {
  tenant_id: "tenant_demo_manufacturing",
  plant_name: "Ravenna Works",
  scenario: "Plant Operations Cockpit",
  registry_status: "watch",
  metrics: [
    {
      label: "Configured Connectors",
      value: "1",
      detail: "Tenant-scoped preview connector configurations",
      status: "ready",
    },
    {
      label: "Credential Values",
      value: "Blocked",
      detail: "Configurations store handles and public-safe settings only",
      status: "watch",
    },
    {
      label: "Live Sync",
      value: "Disabled",
      detail: "Configuration is preview-only until connector run governance matures",
      status: "watch",
    },
  ],
  configurations: [
    {
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "file_csv_manufacturing_assets",
      display_name: "Manufacturing assets CSV intake",
      status: "configured_preview_only",
      sync_mode: "preview",
      runtime_boundary: "axis-connector-sandbox",
      created_by: "plant-operations-owner-role",
      configuration_payload: {
        file_name_pattern: "*.csv",
        mapping_profile: "manufacturing_asset_v1",
        row_limit: "500",
      },
      credential_ref_ids: [],
      notes: [
        "Preview-only tenant configuration.",
        "No raw credential values are stored.",
      ],
    },
  ],
  configuration_notes: [
    "Connector configurations are tenant-scoped and preview-only.",
    "Raw credential values are rejected; future work must use credential handles.",
    "Persisted connector runs, scheduled sync and audit writes remain future work.",
  ],
};

export const defaultConnectorCredentialHandleRegistry: ManufacturingConnectorCredentialHandleRegistry = {
  tenant_id: "tenant_demo_manufacturing",
  plant_name: "Ravenna Works",
  scenario: "Plant Operations Cockpit",
  registry_status: "ready",
  metrics: [
    {
      label: "Credential Handles",
      value: "1",
      detail: "External secret references stored as metadata only",
      status: "ready",
    },
    {
      label: "Rotation Due",
      value: "0",
      detail: "Handles needing rotation review",
      status: "ready",
    },
    {
      label: "Raw Values",
      value: "Never Stored",
      detail: "Axis stores references, not credential material",
      status: "ready",
    },
  ],
  handles: [
    {
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "file_csv_manufacturing_assets",
      handle_id: "cred_file_csv_readonly",
      display_name: "File CSV readonly vault reference",
      status: "active",
      secret_provider: "external_vault",
      secret_ref: "vault://axis/demo/connectors/file-csv-readonly",
      purpose: "preview_import_readonly",
      rotation_interval_days: 30,
      rotation_status: "healthy",
      rotation_count: 1,
      last_rotated_at: "2026-06-22T00:00:00Z",
      next_rotation_due_at: "2026-07-22T00:00:00Z",
      created_by: "plant-operations-owner-role",
      labels: {
        environment: "demo",
      },
      notes: ["Metadata-only handle; no raw credential value is stored."],
      last_rotation: {
        tenant_id: "tenant_demo_manufacturing",
        handle_id: "cred_file_csv_readonly",
        rotated_by: "security-operations-role",
        rotated_at: "2026-06-22T00:00:00Z",
        evidence_ref: "change-window-2026-06-22",
        status: "rotated",
        notes: ["Reference rotated in external vault; Axis stored metadata only."],
      },
    },
  ],
  handle_notes: [
    "Credential handles point to external secret managers or local dev refs.",
    "Rotation updates metadata and history without storing raw credential values.",
    "Connector run execution remains future work.",
  ],
};

export const defaultConnectorCredentialLeaseRegistry: ManufacturingConnectorCredentialLeaseRegistry = {
  tenant_id: "tenant_demo_manufacturing",
  plant_name: "Ravenna Works",
  scenario: "Plant Operations Cockpit",
  registry_status: "ready",
  metrics: [
    {
      label: "Credential Leases",
      value: "1",
      detail: "Vault/KMS lease records for connector execution",
      status: "ready",
    },
    {
      label: "Renewal Due",
      value: "0",
      detail: "Active leases at or past renewal window",
      status: "ready",
    },
    {
      label: "Secret Material",
      value: "Never Returned",
      detail: "Lease adapter returns refs and evidence only",
      status: "ready",
    },
  ],
  leases: [
    {
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "file_csv_manufacturing_assets",
      handle_id: "cred_file_csv_readonly",
      lease_id: "lease_file_csv_readonly_20260622",
      status: "active",
      lease_mode: "deferred_vault_kms_lease",
      runtime_boundary: "axis-credential-lease-broker",
      requested_by: "axis-connector-runtime-role",
      lease_purpose: "governed_dry_run",
      secret_provider: "external_vault",
      secret_ref: "vault://axis/demo/connectors/file-csv-readonly",
      vault_kms_policy: {
        provider_mode: "self_hosted_vault",
        lease_path: "axis/demo/connectors/file-csv-readonly",
        kms_key_ref: "kms://axis/demo/connectors",
      },
      permission_decision: {
        allowed: true,
        reason: "allowed",
      },
      lease_result: {
        adapter: "axis-deferred-vault-kms-lease-adapter",
        status: "lease_deferred",
        lease_id: "lease_file_csv_readonly_20260622",
        action: "request",
        external_secret_read: "false",
        secret_material_returned: "false",
        evidence_ref: "lease:lease_file_csv_readonly_20260622",
        provider_mode: "deferred",
        provider_lease_ref:
          "deferred-lease://tenant_demo_manufacturing/lease_file_csv_readonly_20260622",
      },
      granted_at: "2026-06-22T09:30:00Z",
      expires_at: "2026-06-22T09:45:00Z",
      renewal_due_at: "2026-06-22T09:40:00Z",
      renewed_at: null,
      renewed_by: null,
      renewal_count: 0,
      revoked_at: null,
      revoked_by: null,
      revocation_reason: null,
      audit_event_id: null,
      audit_event_type: "connector.credential_lease.requested",
      notes: [
        "Vault/KMS lease is deferred and returns metadata evidence only.",
        "Secret material is never returned to the console or API response.",
      ],
      created_at: "2026-06-22T09:30:00Z",
    },
  ],
  lease_notes: [
    "Credential leases are short-lived records for connector execution.",
    "The default adapter is deferred and never returns secret material.",
    "A self-hosted Vault/KMS lease adapter can be enabled without requiring managed services.",
    "Renewal and revocation write audit evidence before live sync is enabled.",
  ],
};

export const defaultConnectorRunRegistry: ManufacturingConnectorRunRegistry = {
  tenant_id: "tenant_demo_manufacturing",
  plant_name: "Ravenna Works",
  scenario: "Plant Operations Cockpit",
  registry_status: "ready",
  metrics: [
    {
      label: "Connector Runs",
      value: "4",
      detail: "Metadata-only connector run records",
      status: "ready",
    },
    {
      label: "Audit Writes",
      value: "4",
      detail: "Append-only audit events linked to run records",
      status: "ready",
    },
    {
      label: "Execution",
      value: "Deferred",
      detail: "Governed connector dry-runs stay behind the runtime adapter",
      status: "watch",
    },
  ],
  runs: [
    {
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "file_csv_manufacturing_assets",
      run_id: "run_file_csv_assets_governed_20260622",
      status: "execution_deferred",
      execution_mode: "governed_dry_run",
      runtime_boundary: "axis-connector-sandbox",
      requested_by: "plant-operations-owner-role",
      credential_handle_ids: ["cred_file_csv_readonly"],
      input_summary: {
        file_name: "manufacturing-assets-demo.csv",
        record_count: "2",
      },
      result_summary: {
        runtime_status: "deferred",
        external_sync_started: "false",
      },
      execution_result: {
        adapter: "axis-deferred-connector-execution-adapter",
        status: "execution_deferred",
        external_sync_started: false,
        idempotency_key:
          "tenant_demo_manufacturing:run_file_csv_assets_governed_20260622:execution",
        result_summary: {
          runtime_status: "deferred",
          external_sync_started: "false",
          connector_id: "file_csv_manufacturing_assets",
          execution_mode: "governed_dry_run",
        },
        notes: [
          "Connector execution is deferred by the Axis runtime adapter.",
          "No external sync, credential retrieval or graph mutation was started.",
        ],
      },
      schedule_result: null,
      dispatch_result: null,
      sync_execution_result: null,
      audit_event_id: "audit_connector_run_demo_20260622",
      audit_event_type: "connector.run.execution_deferred",
      notes: ["Governed dry-run stayed deferred behind the connector runtime adapter."],
      created_at: "2026-06-22T00:00:00Z",
    },
    {
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "file_csv_manufacturing_assets",
      run_id: "run_file_csv_assets_scheduled_20260622",
      status: "sync_execution_deferred",
      execution_mode: "scheduled_sync_plan",
      runtime_boundary: "axis-connector-sandbox",
      requested_by: "plant-operations-owner-role",
      credential_handle_ids: ["cred_file_csv_readonly"],
      input_summary: {
        source: "manufacturing-assets-demo.csv",
        record_count: "2",
      },
      result_summary: {
        runtime_status: "schedule_deferred",
        external_sync_started: "false",
        connector_id: "file_csv_manufacturing_assets",
        schedule_id: "schedule_file_csv_assets_hourly",
        schedule_cadence: "hourly",
        next_run_at: "2026-06-22T14:00:00Z",
        sync_schedule_result: {
          adapter: "axis-deferred-connector-sync-scheduler",
          status: "sync_schedule_deferred",
          schedule_ref: "deferred-sync://tenant_demo_manufacturing/schedule_file_csv_assets_hourly",
          external_sync_started: false,
          idempotency_key:
            "tenant_demo_manufacturing:run_file_csv_assets_scheduled_20260622:" +
            "schedule_file_csv_assets_hourly:sync-schedule",
          result_summary: {
            runtime_status: "schedule_deferred",
            external_sync_started: "false",
            connector_id: "file_csv_manufacturing_assets",
            schedule_id: "schedule_file_csv_assets_hourly",
            schedule_cadence: "hourly",
            next_run_at: "2026-06-22T14:00:00Z",
          },
          notes: [
            "Connector sync scheduling is deferred by the Axis runtime adapter.",
            "No external sync, credential retrieval or graph mutation was started.",
          ],
        },
        dispatch_id: "dispatch_file_csv_assets_hourly_20260622_1400",
        sync_dispatch_result: {
          adapter: "axis-deferred-connector-sync-dispatcher",
          status: "sync_dispatch_deferred",
          dispatch_ref:
            "deferred-sync-dispatch://tenant_demo_manufacturing/" +
            "run_file_csv_assets_scheduled_20260622/" +
            "dispatch_file_csv_assets_hourly_20260622_1400",
          external_sync_started: false,
          idempotency_key: "idem_dispatch_file_csv_assets_hourly_20260622_1400",
          result_summary: {
            runtime_status: "dispatch_deferred",
            external_sync_started: "false",
            connector_id: "file_csv_manufacturing_assets",
            schedule_id: "schedule_file_csv_assets_hourly",
            dispatch_id: "dispatch_file_csv_assets_hourly_20260622_1400",
          },
          notes: [
            "Connector sync dispatch is deferred by the Axis runtime adapter.",
            "No external sync, credential retrieval or graph mutation was started.",
          ],
        },
        sync_execution_id: "sync_exec_file_csv_assets_20260622_1400",
        sync_execution_result: {
          adapter: "axis-deferred-connector-sync-executor",
          status: "sync_execution_deferred",
          sync_ref:
            "deferred-sync-execution://tenant_demo_manufacturing/" +
            "run_file_csv_assets_scheduled_20260622/" +
            "sync_exec_file_csv_assets_20260622_1400",
          external_sync_started: false,
          idempotency_key: "idem_sync_exec_file_csv_assets_20260622_1400",
          result_summary: {
            runtime_status: "sync_execution_deferred",
            external_sync_started: "false",
            connector_id: "file_csv_manufacturing_assets",
            schedule_id: "schedule_file_csv_assets_hourly",
            dispatch_id: "dispatch_file_csv_assets_hourly_20260622_1400",
            execution_id: "sync_exec_file_csv_assets_20260622_1400",
          },
          notes: [
            "Connector sync execution is deferred by the Axis runtime adapter.",
            "No external sync, credential retrieval or graph mutation was started.",
          ],
        },
      },
      execution_result: null,
      schedule_result: {
        adapter: "axis-deferred-connector-sync-scheduler",
        status: "sync_schedule_deferred",
        schedule_ref: "deferred-sync://tenant_demo_manufacturing/schedule_file_csv_assets_hourly",
        external_sync_started: false,
        idempotency_key:
          "tenant_demo_manufacturing:run_file_csv_assets_scheduled_20260622:" +
          "schedule_file_csv_assets_hourly:sync-schedule",
        result_summary: {
          runtime_status: "schedule_deferred",
          external_sync_started: "false",
          connector_id: "file_csv_manufacturing_assets",
          schedule_id: "schedule_file_csv_assets_hourly",
          schedule_cadence: "hourly",
          next_run_at: "2026-06-22T14:00:00Z",
        },
        notes: [
          "Connector sync scheduling is deferred by the Axis runtime adapter.",
          "No external sync, credential retrieval or graph mutation was started.",
        ],
      },
      dispatch_result: {
        adapter: "axis-deferred-connector-sync-dispatcher",
        status: "sync_dispatch_deferred",
        dispatch_ref:
          "deferred-sync-dispatch://tenant_demo_manufacturing/" +
          "run_file_csv_assets_scheduled_20260622/" +
          "dispatch_file_csv_assets_hourly_20260622_1400",
        external_sync_started: false,
        idempotency_key: "idem_dispatch_file_csv_assets_hourly_20260622_1400",
        result_summary: {
          runtime_status: "dispatch_deferred",
          external_sync_started: "false",
          connector_id: "file_csv_manufacturing_assets",
          schedule_id: "schedule_file_csv_assets_hourly",
          dispatch_id: "dispatch_file_csv_assets_hourly_20260622_1400",
        },
        notes: [
          "Connector sync dispatch is deferred by the Axis runtime adapter.",
          "No external sync, credential retrieval or graph mutation was started.",
        ],
      },
      sync_execution_result: {
        adapter: "axis-deferred-connector-sync-executor",
        status: "sync_execution_deferred",
        sync_ref:
          "deferred-sync-execution://tenant_demo_manufacturing/" +
          "run_file_csv_assets_scheduled_20260622/" +
          "sync_exec_file_csv_assets_20260622_1400",
        external_sync_started: false,
        idempotency_key: "idem_sync_exec_file_csv_assets_20260622_1400",
        result_summary: {
          runtime_status: "sync_execution_deferred",
          external_sync_started: "false",
          connector_id: "file_csv_manufacturing_assets",
          schedule_id: "schedule_file_csv_assets_hourly",
          dispatch_id: "dispatch_file_csv_assets_hourly_20260622_1400",
          execution_id: "sync_exec_file_csv_assets_20260622_1400",
        },
        notes: [
          "Connector sync execution is deferred by the Axis runtime adapter.",
          "No external sync, credential retrieval or graph mutation was started.",
        ],
      },
      audit_event_id: "audit_connector_sync_execution_demo_20260622",
      audit_event_type: "connector.run.sync_execution_deferred",
      notes: ["Scheduled sync execution stayed deferred behind the runtime adapter."],
      created_at: "2026-06-22T00:05:00Z",
    },
    {
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "external_db_operational_mirror",
      run_id: "run_external_db_orders_scheduled_20260622",
      status: "sync_execution_completed",
      execution_mode: "scheduled_sync_plan",
      runtime_boundary: "axis-connector-sandbox",
      requested_by: "plant-operations-owner-role",
      credential_handle_ids: ["cred_external_db_readonly"],
      input_summary: {
        connection_profile_id: "profile_postgres_ops_readonly",
        schema_name: "operations",
        table_name: "production_orders",
        selected_columns: "order_id,asset_id,work_center,status,risk_level",
        record_count: "2",
      },
      result_summary: {
        runtime_status: "sync_execution_completed",
        external_sync_started: "false",
        connector_id: "external_db_operational_mirror",
        schedule_id: "schedule_file_csv_assets_hourly",
        schedule_cadence: "hourly",
        next_run_at: "2026-06-22T14:00:00Z",
        dispatch_id: "dispatch_external_db_orders_20260622_1400",
        sync_execution_id: "sync_exec_external_db_orders_20260622_1400",
        provider: "postgres",
        connection_profile_id: "profile_postgres_ops_readonly",
        schema_name: "operations",
        table_name: "production_orders",
        records_read: "2",
        records_accepted: "2",
        records_rejected: "0",
        external_query_started: "false",
        credential_material_returned: "false",
        graph_mutation_started: "false",
        source_mode: "external_db_profile",
      },
      execution_result: null,
      schedule_result: {
        adapter: "axis-deferred-connector-sync-scheduler",
        status: "sync_schedule_deferred",
        schedule_ref: "deferred-sync://tenant_demo_manufacturing/schedule_file_csv_assets_hourly",
        external_sync_started: false,
        idempotency_key:
          "tenant_demo_manufacturing:run_external_db_orders_scheduled_20260622:" +
          "schedule_file_csv_assets_hourly:sync-schedule",
        result_summary: {
          runtime_status: "schedule_deferred",
          external_sync_started: "false",
          connector_id: "external_db_operational_mirror",
          schedule_id: "schedule_file_csv_assets_hourly",
          schedule_cadence: "hourly",
          next_run_at: "2026-06-22T14:00:00Z",
        },
        notes: [
          "Connector sync scheduling is deferred by the Axis runtime adapter.",
          "No external sync, credential retrieval or graph mutation was started.",
        ],
      },
      dispatch_result: {
        adapter: "axis-deferred-connector-sync-dispatcher",
        status: "sync_dispatch_deferred",
        dispatch_ref:
          "deferred-sync-dispatch://tenant_demo_manufacturing/" +
          "run_external_db_orders_scheduled_20260622/" +
          "dispatch_external_db_orders_20260622_1400",
        external_sync_started: false,
        idempotency_key: "idem_dispatch_external_db_orders_20260622_1400",
        result_summary: {
          runtime_status: "dispatch_deferred",
          external_sync_started: "false",
          connector_id: "external_db_operational_mirror",
          schedule_id: "schedule_file_csv_assets_hourly",
          dispatch_id: "dispatch_external_db_orders_20260622_1400",
        },
        notes: [
          "Connector sync dispatch is deferred by the Axis runtime adapter.",
          "No external sync, credential retrieval or graph mutation was started.",
        ],
      },
      sync_execution_result: {
        adapter: "axis-postgres-external-db-sync-executor",
        status: "sync_execution_completed",
        sync_ref:
          "postgres-external-db-sync://tenant_demo_manufacturing/" +
          "profile_postgres_ops_readonly/" +
          "run_external_db_orders_scheduled_20260622/" +
          "sync_exec_external_db_orders_20260622_1400",
        external_sync_started: false,
        idempotency_key: "idem_sync_exec_external_db_orders_20260622_1400",
        result_summary: {
          runtime_status: "sync_execution_completed",
          external_sync_started: "false",
          connector_id: "external_db_operational_mirror",
          schedule_id: "schedule_file_csv_assets_hourly",
          dispatch_id: "dispatch_external_db_orders_20260622_1400",
          execution_id: "sync_exec_external_db_orders_20260622_1400",
          provider: "postgres",
          connection_profile_id: "profile_postgres_ops_readonly",
          schema_name: "operations",
          table_name: "production_orders",
          records_read: "2",
          records_accepted: "2",
          records_rejected: "0",
          external_query_started: "false",
          credential_material_returned: "false",
          graph_mutation_started: "false",
          source_mode: "external_db_profile",
        },
        notes: [
          "Postgres external DB sync executed through the profile adapter boundary.",
          "No raw connection string, credential material, external query or graph mutation was started.",
        ],
      },
      audit_event_id: "audit_external_db_sync_execution_demo_20260622",
      audit_event_type: "connector.run.sync_execution_completed",
      notes: ["External DB sync used the Postgres profile adapter boundary."],
      created_at: "2026-06-22T00:10:00Z",
    },
    {
      tenant_id: "tenant_demo_manufacturing",
      connector_id: "external_db_operational_mirror",
      run_id: "run_external_db_orders_live_preflight_passed_20260622",
      status: "sync_execution_preflight_passed",
      execution_mode: "scheduled_sync_plan",
      runtime_boundary: "axis-connector-sandbox",
      requested_by: "plant-operations-owner-role",
      credential_handle_ids: ["cred_external_db_readonly"],
      input_summary: {
        connection_profile_id: "profile_postgres_ops_readonly",
        schema_name: "operations",
        table_name: "production_orders",
        selected_columns: "order_id,asset_id,work_center,status,risk_level",
        record_count: "2",
        live_query_requested: "true",
        query_mode: "read_only_snapshot",
        egress_policy_id: "egress_policy_private_endpoint_ops",
        egress_boundary: "approved_private_endpoint",
        credential_access_mode: "lease_scoped_secret_ref",
      },
      result_summary: {
        runtime_status: "sync_execution_preflight_passed",
        external_sync_started: "false",
        connector_id: "external_db_operational_mirror",
        schedule_id: "schedule_file_csv_assets_hourly",
        schedule_cadence: "hourly",
        next_run_at: "2026-06-22T14:00:00Z",
        dispatch_id: "dispatch_external_db_orders_live_preflight_passed_20260622_1400",
        sync_execution_id: "sync_exec_external_db_orders_live_preflight_passed_20260622_1400",
        provider: "postgres",
        connection_profile_id: "profile_postgres_ops_readonly",
        schema_name: "operations",
        table_name: "production_orders",
        query_mode: "read_only_snapshot",
        egress_policy_id: "egress_policy_private_endpoint_ops",
        egress_boundary: "approved_private_endpoint",
        credential_access_mode: "lease_scoped_secret_ref",
        egress_policy_evidence_status: "validated",
        egress_policy_runtime_boundary: "axis-egress-policy-enforcer",
        egress_policy_result_status: "egress_policy_approved",
        egress_policy_ref:
          "self-hosted-egress-policy://tenant_demo_manufacturing/" +
          "egress_policy_private_endpoint_ops",
        egress_policy_scope: "external_db_operational_mirror:profile_postgres_ops_readonly",
        egress_policy_mode: "approved_private_endpoint",
        egress_policy_private_endpoint_ref:
          "private-endpoint://tenant_demo_manufacturing/operations-postgres-readonly",
        credential_lease_evidence_status: "validated",
        credential_lease_id: "lease_external_db_readonly_20260622",
        credential_lease_mode: "self_hosted_vault_kms_lease",
        credential_lease_runtime_boundary: "axis-credential-lease-broker",
        credential_lease_result_status: "lease_executed",
        credential_lease_ref:
          "self-hosted-vault-kms://tenant_demo_manufacturing/" +
          "lease_external_db_readonly_20260622",
        credential_lease_secret_material_returned: "false",
        secret_reference_evidence_status: "validated",
        secret_reference_runtime_boundary: "axis-secret-reference-resolver",
        secret_reference_result_status: "secret_reference_validated",
        secret_reference_scope: "external_db_operational_mirror:profile_postgres_ops_readonly",
        secret_reference_access_mode: "lease_scoped_secret_ref",
        secret_reference_lease_ref:
          "self-hosted-vault-kms://tenant_demo_manufacturing/" +
          "lease_external_db_readonly_20260622",
        secret_reference_material_returned: "false",
        records_read: "0",
        records_accepted: "0",
        records_rejected: "0",
        live_query_requested: "true",
        live_query_preflight_status: "passed",
        egress_policy_decision: "approved_private_endpoint",
        secret_retrieval_decision: "lease_scoped_reference_only",
        external_query_started: "false",
        credential_material_returned: "false",
        graph_mutation_started: "false",
        source_mode: "external_db_live_preflight",
      },
      execution_result: null,
      schedule_result: {
        adapter: "axis-deferred-connector-sync-scheduler",
        status: "sync_schedule_deferred",
        schedule_ref: "deferred-sync://tenant_demo_manufacturing/schedule_file_csv_assets_hourly",
        external_sync_started: false,
        idempotency_key:
          "tenant_demo_manufacturing:run_external_db_orders_live_preflight_passed_20260622:" +
          "schedule_file_csv_assets_hourly:sync-schedule",
        result_summary: {
          runtime_status: "schedule_deferred",
          external_sync_started: "false",
          connector_id: "external_db_operational_mirror",
          schedule_id: "schedule_file_csv_assets_hourly",
          schedule_cadence: "hourly",
          next_run_at: "2026-06-22T14:00:00Z",
        },
        notes: [
          "Connector sync scheduling is deferred by the Axis runtime adapter.",
          "No external sync, credential retrieval or graph mutation was started.",
        ],
      },
      dispatch_result: {
        adapter: "axis-deferred-connector-sync-dispatcher",
        status: "sync_dispatch_deferred",
        dispatch_ref:
          "deferred-sync-dispatch://tenant_demo_manufacturing/" +
          "run_external_db_orders_live_preflight_passed_20260622/" +
          "dispatch_external_db_orders_live_preflight_passed_20260622_1400",
        external_sync_started: false,
        idempotency_key: "idem_dispatch_external_db_orders_live_preflight_passed_20260622_1400",
        result_summary: {
          runtime_status: "dispatch_deferred",
          external_sync_started: "false",
          connector_id: "external_db_operational_mirror",
          schedule_id: "schedule_file_csv_assets_hourly",
          dispatch_id: "dispatch_external_db_orders_live_preflight_passed_20260622_1400",
        },
        notes: [
          "Connector sync dispatch is deferred by the Axis runtime adapter.",
          "No external sync, credential retrieval or graph mutation was started.",
        ],
      },
      sync_execution_result: {
        adapter: "axis-postgres-external-db-sync-executor",
        status: "sync_execution_preflight_passed",
        sync_ref:
          "postgres-external-db-preflight://tenant_demo_manufacturing/" +
          "profile_postgres_ops_readonly/" +
          "run_external_db_orders_live_preflight_passed_20260622/" +
          "sync_exec_external_db_orders_live_preflight_passed_20260622_1400",
        external_sync_started: false,
        idempotency_key: "idem_sync_exec_external_db_orders_live_preflight_passed_20260622_1400",
        result_summary: {
          runtime_status: "sync_execution_preflight_passed",
          external_sync_started: "false",
          connector_id: "external_db_operational_mirror",
          schedule_id: "schedule_file_csv_assets_hourly",
          dispatch_id: "dispatch_external_db_orders_live_preflight_passed_20260622_1400",
          execution_id: "sync_exec_external_db_orders_live_preflight_passed_20260622_1400",
          provider: "postgres",
          connection_profile_id: "profile_postgres_ops_readonly",
          schema_name: "operations",
          table_name: "production_orders",
          query_mode: "read_only_snapshot",
          egress_policy_id: "egress_policy_private_endpoint_ops",
          egress_boundary: "approved_private_endpoint",
          credential_access_mode: "lease_scoped_secret_ref",
          egress_policy_evidence_status: "validated",
          egress_policy_runtime_boundary: "axis-egress-policy-enforcer",
          egress_policy_result_status: "egress_policy_approved",
          egress_policy_ref:
            "self-hosted-egress-policy://tenant_demo_manufacturing/" +
            "egress_policy_private_endpoint_ops",
          egress_policy_scope: "external_db_operational_mirror:profile_postgres_ops_readonly",
          egress_policy_mode: "approved_private_endpoint",
          egress_policy_private_endpoint_ref:
            "private-endpoint://tenant_demo_manufacturing/operations-postgres-readonly",
          credential_lease_evidence_status: "validated",
          credential_lease_id: "lease_external_db_readonly_20260622",
          credential_lease_mode: "self_hosted_vault_kms_lease",
          credential_lease_runtime_boundary: "axis-credential-lease-broker",
          credential_lease_result_status: "lease_executed",
          credential_lease_ref:
            "self-hosted-vault-kms://tenant_demo_manufacturing/" +
            "lease_external_db_readonly_20260622",
          credential_lease_secret_material_returned: "false",
          secret_reference_evidence_status: "validated",
          secret_reference_runtime_boundary: "axis-secret-reference-resolver",
          secret_reference_result_status: "secret_reference_validated",
          secret_reference_scope:
            "external_db_operational_mirror:profile_postgres_ops_readonly",
          secret_reference_access_mode: "lease_scoped_secret_ref",
          secret_reference_lease_ref:
            "self-hosted-vault-kms://tenant_demo_manufacturing/" +
            "lease_external_db_readonly_20260622",
          secret_reference_material_returned: "false",
          records_read: "0",
          records_accepted: "0",
          records_rejected: "0",
          live_query_requested: "true",
          live_query_preflight_status: "passed",
          egress_policy_decision: "approved_private_endpoint",
          secret_retrieval_decision: "lease_scoped_reference_only",
          external_query_started: "false",
          credential_material_returned: "false",
          graph_mutation_started: "false",
          source_mode: "external_db_live_preflight",
        },
        notes: [
          "Postgres external DB live query preflight evaluated policy gates.",
          "No external query, raw connection string, credential material or graph mutation was started.",
        ],
      },
      audit_event_id: "audit_external_db_live_preflight_passed_demo_20260622",
      audit_event_type: "connector.run.sync_execution_preflight_passed",
      notes: ["External DB live query preflight passed without starting a query."],
      created_at: "2026-06-22T00:15:00Z",
    },
  ],
  run_notes: [
    "Connector run records are metadata-only evidence.",
    "Governed dry-runs write append-only audit evidence before live sync exists.",
    "Scheduled sync plans write audit evidence without starting external sync.",
    "Dispatch claims are idempotent and still do not start external sync.",
    "Sync execution attempts remain deferred unless the self-hosted runtime flag is enabled.",
    "External DB sync uses profile ids and redacted adapter evidence, not raw connection strings.",
    "External DB live query preflight can pass policy gates without starting a query.",
    "Raw payloads, file content and credential material are never stored.",
    "External sync and connector-backed production actions remain future work.",
  ],
};

export const defaultConnectorOntologyProposalRegistry: ManufacturingConnectorOntologyProposalRegistry =
  {
    tenant_id: "tenant_demo_manufacturing",
    plant_name: "Ravenna Works",
    scenario: "Plant Operations Cockpit",
    registry_status: "ready",
    metrics: [
      {
        label: "Ontology Proposals",
        value: "2",
        detail: "Connector preview proposals persisted for review",
        status: "ready",
      },
      {
        label: "Pending Review",
        value: "1",
        detail: "Proposals waiting for approval or import workflow",
        status: "watch",
      },
      {
        label: "Graph Mutations",
        value: "1",
        detail: "Connector proposals promoted through controlled graph mutation",
        status: "ready",
      },
    ],
    proposals: [
      {
        tenant_id: "tenant_demo_manufacturing",
        connector_id: "file_csv_manufacturing_assets",
        proposal_id: "proposal_asset_line_2_packaging",
        source_run_id: "run_file_csv_assets_governed_20260622",
        source_file_name: "manufacturing-assets-demo.csv",
        mapping_profile: "manufacturing_asset_v1",
        status: "promoted_to_graph",
        write_mode: "proposal_only",
        graph_mutation_status: "type_db_mutation_applied",
        proposed_by: "plant-operations-owner-role",
        node_id: "asset_line_2_packaging",
        node_type: "asset",
        ontology_type: "manufacturing_asset",
        field_summary: {
          asset_name: "Line 2 Packaging",
          domain: "Operations",
          station: "Line 2",
          risk_level: "high",
        },
        evidence_refs: ["manufacturing-assets-demo.csv", "asset_line_2_packaging"],
        promotion_id: "promote_asset_line_2_packaging_20260622",
        policy_id: "policy_connector_asset_promotion_v1",
        policy_set_id: "policy_set_connector_asset_required_20260622",
        policy_ids: ["policy_connector_asset_promotion_v1"],
        policy_decision: {
          status: "policy_set_enforced",
          allowed: true,
          policy_id: "policy_connector_asset_promotion_v1",
          policy_version: "2026-06-22",
          policy_set_id: "policy_set_connector_asset_required_20260622",
          policy_set_version: "2026-06-22.1",
          policy_ids: ["policy_connector_asset_promotion_v1"],
          policy_results: [
            {
              policy_id: "policy_connector_asset_promotion_v1",
              status: "policy_enforced",
              allowed: true,
              reason: "policy_constraints_satisfied",
            },
          ],
          enforcement_mode: "required",
          reason: "policy_set_constraints_satisfied",
          required_scopes: ["connectors:ontology:promote"],
          matched_constraints: {
            policy_set_status: "active",
            manual_import_status: "approval_approved",
            workflow_signal_status: "manual_import_signal_requested",
            risk_level: "high",
            ontology_type: "manufacturing_asset",
            selection_mode: "active_policy_set",
            policy_count: "1",
          },
        },
        promoted_by: "plant-operations-owner-role",
        promoted_at: "2026-06-22T00:00:00Z",
        ontology_mutation: {
          status: "type_db_mutation_applied",
          adapter: "axis-typedb-ontology-adapter",
          mutation_ref: "typedb://axis/asset_line_2_packaging",
          typeql: null,
          payload: {
            connector_id: "file_csv_manufacturing_assets",
            promotion_id: "promote_asset_line_2_packaging_20260622",
            proposal_id: "proposal_asset_line_2_packaging",
            manual_import_id: "import_assets_manual_20260622",
            node_id: "asset_line_2_packaging",
            field_summary_keys: ["asset_name", "domain", "risk_level", "station"],
          },
        },
        audit_event_id: "audit_connector_ontology_promotion_demo_20260622",
        audit_event_type: "connector.ontology_promotion.applied",
        notes: ["Proposal promoted after approval, workflow signal and audit evidence."],
        created_at: "2026-06-22T00:00:00Z",
      },
      {
        tenant_id: "tenant_demo_manufacturing",
        connector_id: "file_csv_manufacturing_assets",
        proposal_id: "proposal_asset_press_4",
        source_run_id: "run_file_csv_assets_governed_20260622",
        source_file_name: "manufacturing-assets-demo.csv",
        mapping_profile: "manufacturing_asset_v1",
        status: "proposed_from_preview",
        write_mode: "proposal_only",
        graph_mutation_status: "not_applied",
        proposed_by: "plant-operations-owner-role",
        node_id: "asset_press_4",
        node_type: "asset",
        ontology_type: "manufacturing_asset",
        field_summary: {
          asset_name: "Press 4",
          domain: "Maintenance",
          station: "Press 4",
          risk_level: "medium",
        },
        evidence_refs: ["manufacturing-assets-demo.csv", "asset_press_4"],
        promotion_id: null,
        policy_id: null,
        policy_set_id: null,
        policy_ids: null,
        policy_decision: null,
        promoted_by: null,
        promoted_at: null,
        ontology_mutation: null,
        audit_event_id: "audit_connector_ontology_proposals_demo_20260622",
        audit_event_type: "connector.ontology_proposals.recorded",
        notes: ["Proposal persisted for review; graph mutation is not applied."],
        created_at: "2026-06-22T00:00:00Z",
      },
    ],
    proposal_notes: [
      "Connector ontology proposals are persisted before any graph mutation.",
      "Graph mutation is applied only by the controlled promotion endpoint.",
      "Raw CSV content, payloads and credential material are never stored.",
      "Promotion to ontology graph requires approval, workflow evidence and audit writes.",
    ],
  };

export const defaultConnectorManualImportRegistry: ManufacturingConnectorManualImportRegistry =
  {
    tenant_id: "tenant_demo_manufacturing",
    plant_name: "Ravenna Works",
    scenario: "Plant Operations Cockpit",
    registry_status: "ready",
    metrics: [
      {
        label: "Manual Imports",
        value: "1",
        detail: "Approval-gated connector import requests",
        status: "ready",
      },
      {
        label: "Approval Required",
        value: "0",
        detail: "Manual imports waiting for human decision",
        status: "ready",
      },
      {
        label: "Workflow Signals",
        value: "1",
        detail: "Manual import decisions signaled to the workflow runtime",
        status: "ready",
      },
      {
        label: "Graph Mutations",
        value: "0",
        detail: "Manual import requests do not mutate the ontology graph",
        status: "ready",
      },
    ],
    imports: [
      {
        tenant_id: "tenant_demo_manufacturing",
        connector_id: "file_csv_manufacturing_assets",
        import_id: "import_assets_manual_20260622",
        idempotency_key: "manual-import-assets-20260622",
        status: "approval_approved",
        import_mode: "manual_import_request",
        requested_by: "plant-operations-owner-role",
        owner_role: "plant-operations-owner",
        risk_level: "high",
        approval_id: "appr_connector_import_assets_20260622",
        workflow_id: "wf_connector_manual_import_review",
        proposal_ids: ["proposal_asset_line_2_packaging"],
        import_summary: {
          proposal_count: "1",
          mapping_profile: "manufacturing_asset_v1",
        },
        controls: [
          "approval_required",
          "workflow_signal_required",
          "idempotency_enforced",
        ],
        graph_mutation_status: "not_applied",
        workflow_signal_status: "manual_import_signal_requested",
        decision: "approve",
        decision_actor_id: "plant-operations-owner-role",
        decision_note: "Approved import request; graph mutation remains gated.",
        decided_at: "2026-06-22T00:00:00Z",
        workflow_signal: {
          workflow_id: "wf_connector_manual_import_review",
          status: "manual_import_signal_requested",
          adapter: "axis-deferred-workflow-adapter",
          signal_name: "connector_manual_import_decided",
          payload: {
            connector_id: "file_csv_manufacturing_assets",
            import_id: "import_assets_manual_20260622",
            idempotency_key: "manual-import-assets-20260622",
            approval_id: "appr_connector_import_assets_20260622",
            import_mode: "manual_import_request",
            decision: "approve",
            approved: true,
            proposal_ids: ["proposal_asset_line_2_packaging"],
            proposal_count: 1,
            graph_mutation_status: "not_applied",
          },
        },
        audit_event_id: "audit_connector_manual_import_demo_20260622",
        audit_event_type: "connector.manual_import.decision_recorded",
        notes: ["Manual import request only; graph mutation is not applied."],
        created_at: "2026-06-22T00:00:00Z",
        idempotent_replay: false,
      },
    ],
    import_notes: [
      "Manual import requests are approval-gated metadata records.",
      "Workflow ids and signal status are recorded before any connector import can run.",
      "Idempotency keys prevent duplicate import requests and duplicate audit events.",
      "Graph mutation is only handled by the approved ontology promotion endpoint.",
    ],
  };

export const defaultConnectorPromotionPolicyRegistry: ManufacturingConnectorPromotionPolicyRegistry =
  {
    tenant_id: "tenant_demo_manufacturing",
    plant_name: "Ravenna Works",
    scenario: "Plant Operations Cockpit",
    registry_status: "ready",
    metrics: [
      {
        label: "Promotion Policies",
        value: "3",
        detail: "Connector proposal promotion policy versions",
        status: "ready",
      },
      {
        label: "Draft Policies",
        value: "1",
        detail: "Policies authored but not enabled",
        status: "watch",
      },
      {
        label: "Required Gates",
        value: "1",
        detail: "Policy enforced during connector proposal promotion",
        status: "ready",
      },
    ],
    policies: [
      {
        tenant_id: "tenant_demo_manufacturing",
        connector_id: "file_csv_manufacturing_assets",
        policy_id: "policy_connector_asset_promotion_draft_20260622",
        policy_version: "2026-06-22.0",
        status: "superseded",
        enforcement_mode: "advisory",
        created_by: "platform-governance-owner-role",
        required_authoring_scope: "connectors:promotion_policy:author",
        required_scopes: ["connectors:ontology:promote"],
        required_manual_import_status: "approval_approved",
        required_workflow_signal_status: "manual_import_signal_requested",
        allowed_risk_levels: ["high", "medium"],
        allowed_ontology_types: ["manufacturing_asset"],
        review_window_hours: 24,
        permission_decision: {
          allowed: true,
          reason: "allowed",
        },
        audit_event_id: "audit_connector_promotion_policy_draft_demo_20260622",
        audit_event_type: "connector.promotion_policy.authored",
        revises_policy_id: null,
        replaced_by_policy_id: "policy_connector_asset_promotion_draft_20260622_v2",
        revision_idempotency_key: null,
        revision_approval_id: null,
        revision_decision: null,
        revision_workflow_signal_status: null,
        idempotent_replay: false,
        notes: ["Superseded by an append-only draft revision."],
        created_at: "2026-06-22T00:00:00Z",
      },
      {
        tenant_id: "tenant_demo_manufacturing",
        connector_id: "file_csv_manufacturing_assets",
        policy_id: "policy_connector_asset_promotion_draft_20260622_v2",
        policy_version: "2026-06-22.0.2",
        status: "draft",
        enforcement_mode: "advisory",
        created_by: "platform-governance-owner-role",
        required_authoring_scope: "connectors:promotion_policy:revise",
        required_scopes: ["connectors:ontology:promote"],
        required_manual_import_status: "approval_approved",
        required_workflow_signal_status: "manual_import_signal_requested",
        allowed_risk_levels: ["high", "medium", "low"],
        allowed_ontology_types: ["manufacturing_asset"],
        review_window_hours: 48,
        permission_decision: {
          allowed: true,
          reason: "allowed",
        },
        audit_event_id: "audit_connector_promotion_policy_revision_demo_20260622",
        audit_event_type: "connector.promotion_policy.revised",
        revises_policy_id: "policy_connector_asset_promotion_draft_20260622",
        replaced_by_policy_id: null,
        revision_idempotency_key: "idem_policy_revision_asset_promotion_v2",
        revision_approval_id: "appr_policy_revision_asset_promotion_v2",
        revision_decision: "approve",
        revision_workflow_signal_status: "policy_revision_signal_recorded",
        idempotent_replay: false,
        notes: ["Draft revision widens risk coverage before enablement."],
        created_at: "2026-06-22T00:30:00Z",
      },
      {
        tenant_id: "tenant_demo_manufacturing",
        connector_id: "file_csv_manufacturing_assets",
        policy_id: "policy_connector_asset_promotion_v1",
        policy_version: "2026-06-22",
        status: "enabled",
        enforcement_mode: "required",
        created_by: "platform-governance-owner-role",
        required_authoring_scope: "connectors:promotion_policy:author",
        required_scopes: ["connectors:ontology:promote"],
        required_manual_import_status: "approval_approved",
        required_workflow_signal_status: "manual_import_signal_requested",
        allowed_risk_levels: ["high", "medium"],
        allowed_ontology_types: ["manufacturing_asset"],
        review_window_hours: 24,
        permission_decision: {
          allowed: true,
          reason: "allowed",
        },
        audit_event_id: "audit_connector_promotion_policy_enable_demo_20260622",
        audit_event_type: "connector.promotion_policy.enabled",
        revises_policy_id: null,
        replaced_by_policy_id: null,
        revision_idempotency_key: null,
        revision_approval_id: null,
        revision_decision: null,
        revision_workflow_signal_status: null,
        idempotent_replay: false,
        notes: [
          "Policy authored as draft before enablement.",
          "Required policy enabled after approval and workflow signal evidence.",
        ],
        created_at: "2026-06-22T00:00:00Z",
      },
    ],
    policy_notes: [
      "Promotion policies are governance metadata that can become required gates.",
      "Policy authoring records required scopes before enablement.",
      "Enablement requires approval and workflow signal evidence.",
      "Draft revisions are append-only and idempotent; enabled policies remain immutable.",
      "Enabled required policies are auto-selected before TypeDB mutation execution.",
    ],
  };

export const defaultConnectorPromotionPolicySetRegistry: ManufacturingConnectorPromotionPolicySetRegistry =
  {
    tenant_id: "tenant_demo_manufacturing",
    plant_name: "Ravenna Works",
    scenario: "Plant Operations Cockpit",
    registry_status: "ready",
    metrics: [
      {
        label: "Policy Sets",
        value: "3",
        detail: "Versioned connector promotion policy sets",
        status: "ready",
      },
      {
        label: "Active Sets",
        value: "1",
        detail: "Policy sets selected for automatic required gates",
        status: "ready",
      },
      {
        label: "Set Policies",
        value: "3",
        detail: "Required policy references inside versioned sets",
        status: "ready",
      },
    ],
    policy_sets: [
      {
        tenant_id: "tenant_demo_manufacturing",
        connector_id: "file_csv_manufacturing_assets",
        policy_set_id: "policy_set_connector_asset_required_20260622",
        policy_set_version: "2026-06-22.1",
        status: "superseded",
        activated_by: "platform-governance-owner-role",
        activation_scope: "connectors:promotion_policy_set:activate",
        policy_ids: ["policy_connector_asset_promotion_v1"],
        permission_decision: {
          allowed: true,
          reason: "allowed",
        },
        audit_event_id: "audit_connector_promotion_policy_set_demo_20260622",
        audit_event_type: "connector.promotion_policy_set.activated",
        activation_reason: "Activate required policy set for connector asset promotions.",
        replaces_policy_set_id: null,
        replaced_by_policy_set_id: "policy_set_connector_asset_required_20260622_v2",
        replacement_approval_id: "approval_policy_set_replace_20260622",
        replacement_decision: "approve",
        replacement_workflow_signal_status: "policy_set_replacement_signal_recorded",
        replaced_at: "2026-06-22T01:00:00Z",
        rollback_to_policy_set_id: null,
        rollback_approval_id: null,
        rollback_decision: null,
        rollback_workflow_signal_status: null,
        policy_revision_adoptions: [],
        notes: ["Superseded by a governed replacement policy set."],
        created_at: "2026-06-22T00:00:00Z",
      },
      {
        tenant_id: "tenant_demo_manufacturing",
        connector_id: "file_csv_manufacturing_assets",
        policy_set_id: "policy_set_connector_asset_required_20260622_v2",
        policy_set_version: "2026-06-22.2",
        status: "superseded",
        activated_by: "platform-governance-owner-role",
        activation_scope: "connectors:promotion_policy_set:activate",
        policy_ids: ["policy_connector_asset_promotion_v1"],
        permission_decision: {
          allowed: true,
          reason: "allowed",
        },
        audit_event_id: "audit_connector_promotion_policy_set_replace_demo_20260622",
        audit_event_type: "connector.promotion_policy_set.replaced",
        activation_reason: "Replace active set after governance review.",
        replaces_policy_set_id: "policy_set_connector_asset_required_20260622",
        replaced_by_policy_set_id: "policy_set_connector_asset_required_20260622_rollback",
        replacement_approval_id: "approval_policy_set_rollback_20260622",
        replacement_decision: "approve",
        replacement_workflow_signal_status: "policy_set_rollback_signal_recorded",
        replaced_at: "2026-06-22T02:00:00Z",
        rollback_to_policy_set_id: null,
        rollback_approval_id: null,
        rollback_decision: null,
        rollback_workflow_signal_status: null,
        policy_revision_adoptions: [],
        notes: ["Superseded by a governed rollback after review."],
        created_at: "2026-06-22T01:00:00Z",
      },
      {
        tenant_id: "tenant_demo_manufacturing",
        connector_id: "file_csv_manufacturing_assets",
        policy_set_id: "policy_set_connector_asset_required_20260622_rollback",
        policy_set_version: "2026-06-22.3",
        status: "active",
        activated_by: "platform-governance-owner-role",
        activation_scope: "connectors:promotion_policy_set:activate",
        policy_ids: ["policy_connector_asset_promotion_v1"],
        permission_decision: {
          allowed: true,
          reason: "allowed",
        },
        audit_event_id: "audit_connector_promotion_policy_set_rollback_demo_20260622",
        audit_event_type: "connector.promotion_policy_set.rolled_back",
        activation_reason: "Rollback active set after governance review.",
        replaces_policy_set_id: "policy_set_connector_asset_required_20260622_v2",
        replaced_by_policy_set_id: null,
        replacement_approval_id: null,
        replacement_decision: null,
        replacement_workflow_signal_status: null,
        replaced_at: null,
        rollback_to_policy_set_id: "policy_set_connector_asset_required_20260622",
        rollback_approval_id: "approval_policy_set_rollback_20260622",
        rollback_decision: "approve",
        rollback_workflow_signal_status: "policy_set_rollback_signal_recorded",
        policy_revision_adoptions: [],
        notes: ["Active rollback set restores the previous required gate with audit evidence."],
        created_at: "2026-06-22T02:00:00Z",
      },
    ],
    policy_set_notes: [
      "Policy sets version the active required gates for connector promotions.",
      "Activation requires policy-set scope and enabled required policy references.",
      "Replacing or rolling back an active set requires approval and workflow signal evidence.",
      "Replacement can atomically adopt approved draft policy revisions with adoption evidence.",
      "Promotion auto-selection uses the active set before TypeDB mutation execution.",
    ],
  };

export function buildDefaultCsvPreviewRequest(): ConnectorCsvPreviewRequest {
  return {
    tenant_id: "tenant_demo_manufacturing",
    connector_id: "file_csv_manufacturing_assets",
    file_name: "manufacturing-assets-demo.csv",
    csv_content:
      "asset_id,asset_name,domain,station,risk_level\n" +
      "asset_line_2_packaging,Line 2 Packaging,Operations,Line 2,high\n" +
      "asset_press_4,Press 4,Maintenance,Press 4,medium\n",
  };
}

export function buildDefaultExternalDbPreviewRequest(): ConnectorExternalDbPreviewRequest {
  return {
    tenant_id: "tenant_demo_manufacturing",
    connector_id: "external_db_operational_mirror",
    connection_profile_id: "profile_postgres_ops_readonly",
    schema_name: "operations",
    table_name: "production_orders",
    selected_columns: ["order_id", "asset_id", "work_center", "status", "risk_level"],
    sample_limit: 2,
    credential_handle_id: "cred_external_db_readonly",
    metadata: {},
  };
}

export function buildDefaultConnectorConfigurationRequest(): ConnectorConfigurationCreateRequest {
  return {
    tenant_id: "tenant_demo_manufacturing",
    connector_id: "file_csv_manufacturing_assets",
    display_name: "Manufacturing assets CSV intake",
    sync_mode: "preview",
    created_by: "plant-operations-owner-role",
    configuration_payload: {
      file_name_pattern: "*.csv",
      mapping_profile: "manufacturing_asset_v1",
    },
    credential_ref_ids: [],
    notes: ["Preview-only tenant configuration."],
  };
}

export function buildDefaultConnectorPromotionPolicyRequest(
  overrides: Partial<ConnectorPromotionPolicyCreateRequest> = {},
): ConnectorPromotionPolicyCreateRequest {
  return {
    tenant_id: "tenant_demo_manufacturing",
    connector_id: "file_csv_manufacturing_assets",
    policy_id: "policy_connector_asset_promotion_ui_v1",
    policy_version: "2026-06-22-ui",
    status: "draft",
    enforcement_mode: "advisory",
    created_by: "platform-governance-owner-role",
    actor_scopes: ["connectors:promotion_policy:author"],
    required_scopes: ["connectors:ontology:promote"],
    required_manual_import_status: "approval_approved",
    required_workflow_signal_status: "manual_import_signal_requested",
    allowed_risk_levels: ["high", "medium"],
    allowed_ontology_types: ["manufacturing_asset"],
    review_window_hours: 24,
    notes: ["Policy authored from connector console."],
    ...overrides,
  };
}

export function buildDefaultConnectorPromotionPolicyEnableRequest(
  overrides: Partial<ConnectorPromotionPolicyEnableRequest> = {},
): ConnectorPromotionPolicyEnableRequest {
  const policyId = overrides.policy_id ?? "policy_connector_asset_promotion_v1";
  const approvalIdSuffix = policyId.replace(/^policy_/, "");
  return {
    tenant_id: "tenant_demo_manufacturing",
    policy_id: policyId,
    enabled_by: "platform-governance-owner-role",
    actor_scopes: ["connectors:promotion_policy:enable"],
    approval_id: `appr_policy_enable_${approvalIdSuffix}`,
    approval_decision: "approve",
    workflow_signal_status: "policy_enable_signal_recorded",
    note: "Enable required policy after governance review.",
    ...overrides,
  };
}

export function recordLocalConnectorPromotionPolicy(
  registry: ManufacturingConnectorPromotionPolicyRegistry,
  request: ConnectorPromotionPolicyCreateRequest,
  record?: ConnectorPromotionPolicyRecord,
): ManufacturingConnectorPromotionPolicyRegistry {
  const authoredPolicy: ConnectorPromotionPolicyRecord = record ?? {
    tenant_id: request.tenant_id,
    connector_id: request.connector_id,
    policy_id: request.policy_id,
    policy_version: request.policy_version,
    status: request.status,
    enforcement_mode: request.enforcement_mode,
    created_by: request.created_by,
    required_authoring_scope: "connectors:promotion_policy:author",
    required_scopes: request.required_scopes,
    required_manual_import_status: request.required_manual_import_status,
    required_workflow_signal_status: request.required_workflow_signal_status,
    allowed_risk_levels: request.allowed_risk_levels,
    allowed_ontology_types: request.allowed_ontology_types,
    review_window_hours: request.review_window_hours,
    permission_decision: {
      allowed: true,
      reason: "local_preview",
    },
    audit_event_id: null,
    audit_event_type: "connector.promotion_policy.authored",
    revises_policy_id: null,
    replaced_by_policy_id: null,
    revision_idempotency_key: null,
    revision_approval_id: null,
    revision_decision: null,
    revision_workflow_signal_status: null,
    idempotent_replay: false,
    notes: request.notes,
    created_at: "2026-06-22T00:00:00Z",
  };
  const policies = [
    authoredPolicy,
    ...registry.policies.filter((policy) => policy.policy_id !== request.policy_id),
  ];
  const draftCount = policies.filter((policy) => policy.status === "draft").length;
  const requiredCount = policies.filter(
    (policy) => policy.status === "enabled" && policy.enforcement_mode === "required",
  ).length;

  return {
    ...registry,
    registry_status: "ready",
    metrics: [
      {
        label: "Promotion Policies",
        value: String(policies.length),
        detail: "Connector proposal promotion policies",
        status: policies.length > 0 ? "ready" : "watch",
      },
      {
        label: "Draft Policies",
        value: String(draftCount),
        detail: "Policies authored but not enabled",
        status: draftCount > 0 ? "watch" : "ready",
      },
      {
        label: "Required Gates",
        value: String(requiredCount),
        detail: "Enabled policies marked required for promotion",
        status: requiredCount > 0 ? "ready" : "watch",
      },
    ],
    policies,
  };
}

export function recordLocalConnectorPromotionPolicyEnable(
  registry: ManufacturingConnectorPromotionPolicyRegistry,
  request: ConnectorPromotionPolicyEnableRequest,
  record?: ConnectorPromotionPolicyRecord,
): ManufacturingConnectorPromotionPolicyRegistry {
  const policies = registry.policies.map((policy) => {
    if (policy.policy_id !== request.policy_id) {
      return policy;
    }

    return (
      record ?? {
        ...policy,
        status: "enabled",
        enforcement_mode: "required",
        permission_decision: {
          allowed: true,
          reason: "local_enable_preview",
        },
        audit_event_id: null,
        audit_event_type: "connector.promotion_policy.enabled",
        notes: [
          ...policy.notes,
          "Authoring audit event connector.promotion_policy.authored retained before enablement.",
          request.note ?? "Local enablement preview recorded with approval evidence.",
        ],
      }
    );
  });
  const draftCount = policies.filter((policy) => policy.status === "draft").length;
  const requiredCount = policies.filter(
    (policy) => policy.status === "enabled" && policy.enforcement_mode === "required",
  ).length;

  return {
    ...registry,
    registry_status: "ready",
    metrics: [
      {
        label: "Promotion Policies",
        value: String(policies.length),
        detail: "Connector proposal promotion policies",
        status: policies.length > 0 ? "ready" : "watch",
      },
      {
        label: "Draft Policies",
        value: String(draftCount),
        detail: "Policies authored but not enabled",
        status: draftCount > 0 ? "watch" : "ready",
      },
      {
        label: "Required Gates",
        value: String(requiredCount),
        detail: "Enabled policies marked required for promotion",
        status: requiredCount > 0 ? "ready" : "watch",
      },
    ],
    policies,
  };
}

export function findConnectorById(
  registry: ManufacturingConnectorRegistry,
  connectorId: string,
): ConnectorRegistryItem {
  return (
    registry.connectors.find((connector) => connector.manifest.connector_id === connectorId) ??
    registry.connectors[0]
  );
}

export function formatConnectorLabel(value: string): string {
  return value
    .split(/[._:-]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
