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

export type ConnectorEgressPolicyRecord = {
  tenant_id: string;
  connector_id: string;
  policy_id: string;
  display_name: string;
  status: string;
  connection_profile_id: string;
  egress_boundary: string;
  policy_mode: string;
  runtime_boundary: string;
  private_endpoint_ref: string;
  created_by: string;
  policy_document: Record<string, string>;
  evidence_refs: string[];
  audit_event_id: string | null;
  audit_event_type: string;
  notes: string[];
  created_at: string;
};

export type ManufacturingConnectorEgressPolicyRegistry = {
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
  policies: ConnectorEgressPolicyRecord[];
  policy_notes: string[];
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

export type ConnectorSyncCheckpointRecord = {
  tenant_id: string;
  connector_id: string;
  run_id: string;
  checkpoint_id: string;
  checkpoint_type: string;
  status: string;
  sequence: number;
  runtime_boundary: string;
  adapter: string;
  cursor: Record<string, unknown>;
  result_summary: Record<string, unknown>;
  evidence_refs: string[];
  audit_event_id: string | null;
  audit_event_type: string;
  notes: string[];
  created_at: string;
};

export type ManufacturingConnectorSyncCheckpointRegistry = {
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
  checkpoints: ConnectorSyncCheckpointRecord[];
  checkpoint_notes: string[];
};

const CONNECTOR_SYNC_CHECKPOINT_READ_SCOPE = "connectors:sync:checkpoint:read";

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

export function buildConnectorPromotionPolicyDraftRequest(
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

export function buildConnectorPromotionPolicyEnableRequest(
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

export function findConnectorById(
  registry: ManufacturingConnectorRegistry,
  connectorId: string,
): ConnectorRegistryItem {
  return (
    registry.connectors.find((connector) => connector.manifest.connector_id === connectorId) ??
    registry.connectors[0]
  );
}

export function filterConnectorSyncCheckpointsByConnector(
  registry: ManufacturingConnectorSyncCheckpointRegistry,
  connectorId: string,
): ConnectorSyncCheckpointRecord[] {
  return registry.checkpoints
    .filter((checkpoint) => checkpoint.connector_id === connectorId)
    .slice()
    .sort((left, right) => {
      if (left.sequence !== right.sequence) {
        return left.sequence - right.sequence;
      }

      const createdAtOrder = left.created_at.localeCompare(right.created_at);
      return createdAtOrder === 0
        ? left.checkpoint_id.localeCompare(right.checkpoint_id)
        : createdAtOrder;
    });
}

type ConnectorSyncCheckpointQueryPathOptions = {
  createdAfter?: string;
  createdBefore?: string;
};

export function buildConnectorSyncCheckpointQueryPath(
  tenantId: string,
  options: ConnectorSyncCheckpointQueryPathOptions = {},
): string {
  const params = new URLSearchParams({
    tenant_id: tenantId,
    actor_scopes: CONNECTOR_SYNC_CHECKPOINT_READ_SCOPE,
  });
  if (options.createdAfter) {
    params.set("created_after", options.createdAfter);
  }
  if (options.createdBefore) {
    params.set("created_before", options.createdBefore);
  }
  return `/demo/manufacturing/connectors/runs/checkpoints?${params.toString()}`;
}

export function formatConnectorLabel(value: string): string {
  return value
    .split(/[._:-]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
