import { z } from "zod";

import type {
  ConnectorCsvPreviewResult,
  ConnectorExternalDbPreviewResult,
  ConnectorRunRecord,
  ManufacturingConnectorCredentialHandleRegistry,
  ManufacturingConnectorCredentialLeaseRegistry,
  ManufacturingConnectorEgressPolicyRegistry,
  ManufacturingConnectorEvidenceInvariantReport,
  ManufacturingConnectorManifestRegistry,
  ManufacturingConnectorOntologyProposalRegistry,
  ManufacturingConnectorRegistry,
  ManufacturingConnectorRunRegistry,
} from "../connectors-demo";
import {
  nullableStringSchema,
  overviewMetricSchema,
  parseContract,
  platformStatusSchema,
  stringArraySchema,
} from "./shared";

const stringRecord = z.record(z.string(), z.string());
const unknownRecord = z.record(z.string(), z.unknown());
const connectorManifest = z.object({
  connector_id: z.string(),
  display_name: z.string(),
  connector_type: z.string(),
  version: z.string(),
  source_type: z.string(),
  sync_modes: stringArraySchema,
  runtime_boundary: z.string(),
  required_permissions: stringArraySchema,
  credential_requirements: z.object({
    storage: z.string(),
    required_secret_refs: stringArraySchema,
    notes: stringArraySchema,
  }),
  schema_fields: z.array(z.object({
    source_column: z.string(),
    target_field: z.string(),
    ontology_target: z.string(),
    data_type: z.string(),
    required: z.boolean(),
    description: z.string(),
  })),
  mapping_notes: stringArraySchema,
});
const connectorRuntimePolicy = z.object({
  allowed_operations: stringArraySchema,
  blocked_operations: stringArraySchema,
  egress_policy: z.string(),
  max_file_size_mb: z.number(),
  row_limit: z.number(),
  payload_policy: z.string(),
});
const connectorPreviewSample = z.object({
  file_name: z.string(),
  record_count: z.number(),
  headers: stringArraySchema,
  sample_rows: z.array(stringRecord),
});
const proposedOntologyEntity = z.object({
  node_id: z.string(),
  node_type: z.string(),
  ontology_type: z.string(),
  field_summary: stringRecord,
  evidence_refs: stringArraySchema,
});
const connectorAuditEventPreview = z.object({
  event_type: z.string(),
  scope: z.string(),
  actor_id: z.string(),
  result: z.string(),
  evidence_refs: stringArraySchema,
  payload_preview: stringRecord,
});
const connectorCsvPreviewResult = z.object({
  tenant_id: z.string(),
  connector_id: z.string(),
  file_name: z.string(),
  preview_status: z.string(),
  sync_mode: z.string(),
  record_count: z.number(),
  accepted_record_count: z.number(),
  rejected_record_count: z.number(),
  validation_issues: stringArraySchema,
  proposed_entities: z.array(proposedOntologyEntity),
  audit_event_preview: connectorAuditEventPreview,
  preview_notes: stringArraySchema,
});
const connectorExternalDbPreviewResult = z.object({
  tenant_id: z.string(),
  connector_id: z.string(),
  connection_profile_id: z.string(),
  source_type: z.string(),
  preview_status: z.string(),
  sync_mode: z.string(),
  live_query_executed: z.boolean(),
  validation_issues: stringArraySchema,
  inspected_table: z.object({
    schema_name: z.string(),
    table_name: z.string(),
    table_ref: z.string(),
    record_count_estimate: z.string(),
    sample_limit: z.number(),
    columns: z.array(z.object({
      source_column: z.string(),
      target_field: z.string(),
      ontology_target: z.string(),
      data_type: z.string(),
      nullable: z.boolean(),
    })),
    sample_rows: z.array(stringRecord),
  }),
  proposed_entities: z.array(proposedOntologyEntity),
  audit_event_preview: connectorAuditEventPreview,
  preview_notes: stringArraySchema,
});
const connectorRegistryHeader = {
  tenant_id: z.string(),
  plant_name: z.string(),
  scenario: z.string(),
  registry_status: platformStatusSchema,
  metrics: z.array(overviewMetricSchema),
};
const connectorRegistry = z.object({
  ...connectorRegistryHeader,
  connectors: z.array(z.object({
    manifest: connectorManifest,
    runtime_policy: connectorRuntimePolicy,
    preview_sample: connectorPreviewSample,
    connector_status: platformStatusSchema,
  })),
  connector_notes: stringArraySchema,
});
const connectorManifestRegistry = z.object({
  ...connectorRegistryHeader,
  manifests: z.array(z.object({
    tenant_id: z.string(),
    manifest_id: z.string(),
    connector_id: z.string(),
    display_name: z.string(),
    connector_type: z.string(),
    source_type: z.string(),
    version: z.string(),
    status: z.string(),
    runtime_boundary: z.string(),
    registered_by: z.string(),
    manifest: connectorManifest,
    runtime_policy: connectorRuntimePolicy,
    preview_sample: connectorPreviewSample,
    audit_event_id: nullableStringSchema,
    audit_event_type: z.string(),
    notes: stringArraySchema,
    created_at: z.string(),
  })),
  manifest_notes: stringArraySchema,
});
const credentialRotation = z.object({
  tenant_id: z.string(),
  handle_id: z.string(),
  rotated_by: z.string(),
  rotated_at: z.string(),
  evidence_ref: z.string(),
  status: z.string(),
  notes: stringArraySchema,
});
const connectorCredentialHandleRegistry = z.object({
  ...connectorRegistryHeader,
  handles: z.array(z.object({
    tenant_id: z.string(),
    connector_id: z.string(),
    handle_id: z.string(),
    display_name: z.string(),
    status: z.string(),
    secret_provider: z.string(),
    secret_ref: z.string(),
    purpose: z.string(),
    rotation_interval_days: z.number(),
    rotation_status: z.string(),
    rotation_count: z.number(),
    last_rotated_at: nullableStringSchema,
    next_rotation_due_at: nullableStringSchema,
    created_by: z.string(),
    labels: stringRecord,
    notes: stringArraySchema,
    last_rotation: credentialRotation.nullable(),
  })),
  handle_notes: stringArraySchema,
});
const permissionDecision = z.object({ allowed: z.boolean(),
  reason: z.string() });
const connectorCredentialLeaseRegistry = z.object({
  ...connectorRegistryHeader,
  leases: z.array(z.object({
    tenant_id: z.string(),
    connector_id: z.string(),
    handle_id: z.string(),
    lease_id: z.string(),
    status: z.string(),
    lease_mode: z.string(),
    runtime_boundary: z.string(),
    requested_by: z.string(),
    lease_purpose: z.string(),
    secret_provider: z.string(),
    secret_ref: z.string(),
    vault_kms_policy: stringRecord,
    permission_decision: permissionDecision,
    lease_result: stringRecord,
    granted_at: z.string(),
    expires_at: z.string(),
    renewal_due_at: z.string(),
    renewed_at: nullableStringSchema,
    renewed_by: nullableStringSchema,
    renewal_count: z.number(),
    revoked_at: nullableStringSchema,
    revoked_by: nullableStringSchema,
    revocation_reason: nullableStringSchema,
    audit_event_id: nullableStringSchema,
    audit_event_type: z.string(),
    notes: stringArraySchema,
    created_at: z.string(),
  })),
  lease_evidence_invariants: z.array(z.object({
    lease_id: z.string(),
    audit_event_id: nullableStringSchema,
    reason: z.string(),
    detail: z.string(),
  })),
  lease_notes: stringArraySchema,
});
const connectorEgressPolicyRegistry = z.object({
  ...connectorRegistryHeader,
  policies: z.array(z.object({
    tenant_id: z.string(),
    connector_id: z.string(),
    policy_id: z.string(),
    display_name: z.string(),
    status: z.string(),
    connection_profile_id: z.string(),
    egress_boundary: z.string(),
    policy_mode: z.string(),
    runtime_boundary: z.string(),
    private_endpoint_ref: z.string(),
    created_by: z.string(),
    policy_document: stringRecord,
    evidence_refs: stringArraySchema,
    audit_event_id: nullableStringSchema,
    audit_event_type: z.string(),
    notes: stringArraySchema,
    created_at: z.string(),
  })),
  policy_evidence_invariants: z.array(z.object({
    policy_id: z.string(),
    audit_event_id: nullableStringSchema,
    reason: z.string(),
    detail: z.string(),
  })),
  policy_notes: stringArraySchema,
});
const connectorRunResult = z.object({
  adapter: z.string(),
  status: z.string(),
  external_sync_started: z.boolean(),
  idempotency_key: z.string(),
  result_summary: stringRecord,
  notes: stringArraySchema,
});
const connectorRunRecord = z.object({
  tenant_id: z.string(),
  connector_id: z.string(),
  run_id: z.string(),
  status: z.string(),
  execution_mode: z.string(),
  runtime_boundary: z.string(),
  requested_by: z.string(),
  credential_handle_ids: stringArraySchema,
  input_summary: stringRecord,
  result_summary: unknownRecord,
  execution_result: connectorRunResult.nullable(),
  schedule_result: connectorRunResult.extend({ schedule_ref: z.string() }).nullable(),
  dispatch_result: connectorRunResult.extend({ dispatch_ref: z.string() }).nullable(),
  sync_execution_result: connectorRunResult.extend({ sync_ref: z.string() }).nullable(),
  audit_event_id: nullableStringSchema,
  audit_event_type: z.string(),
  notes: stringArraySchema,
  created_at: z.string(),
});
const connectorRunRegistry = z.object({
  ...connectorRegistryHeader,
  runs: z.array(connectorRunRecord),
  run_notes: stringArraySchema,
});
const connectorEvidenceInvariantReport = z.object({
  ...connectorRegistryHeader,
  invariant_counts: z.object({
    checkpoint: z.number(),
    checkpoint_claim: z.number(),
    credential_lease: z.number(),
    egress_policy: z.number(),
  }),
  invariants: z.array(z.object({
    evidence_type: z.enum(["checkpoint", "checkpoint_claim", "credential_lease", "egress_policy"]),
    subject_id: z.string(),
    parent_id: nullableStringSchema,
    audit_event_id: nullableStringSchema,
    reason: z.string(),
    detail: z.string(),
  })),
  report_notes: stringArraySchema,
});
const connectorPromotionDecision = z.object({
  status: z.string(),
  allowed: z.boolean(),
  policy_id: nullableStringSchema,
  policy_version: nullableStringSchema,
  policy_set_id: nullableStringSchema,
  policy_set_version: nullableStringSchema,
  policy_ids: stringArraySchema,
  policy_results: z.array(unknownRecord),
  enforcement_mode: z.string(),
  reason: z.string(),
  required_scopes: stringArraySchema,
  matched_constraints: stringRecord,
});
const connectorOntologyProposalRegistry = z.object({
  ...connectorRegistryHeader,
  proposals: z.array(z.object({
    tenant_id: z.string(),
    connector_id: z.string(),
    proposal_id: z.string(),
    source_run_id: nullableStringSchema,
    source_file_name: z.string(),
    mapping_profile: z.string(),
    status: z.string(),
    write_mode: z.string(),
    graph_mutation_status: z.string(),
    proposed_by: z.string(),
    node_id: z.string(),
    node_type: z.string(),
    ontology_type: z.string(),
    field_summary: stringRecord,
    evidence_refs: stringArraySchema,
    promotion_id: nullableStringSchema,
    policy_id: nullableStringSchema,
    policy_set_id: nullableStringSchema,
    policy_ids: stringArraySchema.nullable(),
    policy_decision: connectorPromotionDecision.nullable(),
    promoted_by: nullableStringSchema,
    promoted_at: nullableStringSchema,
    ontology_mutation: z.object({
      status: z.string(),
      adapter: z.string(),
      mutation_ref: nullableStringSchema,
      typeql: nullableStringSchema,
      payload: unknownRecord,
    }).nullable(),
    audit_event_id: nullableStringSchema,
    audit_event_type: z.string(),
    notes: stringArraySchema,
    created_at: z.string(),
  })),
  proposal_notes: stringArraySchema,
});

export function parseManufacturingConnectorRegistry(
  value: unknown,
): ManufacturingConnectorRegistry {
  return parseContract(connectorRegistry, value);
}

export function parseManufacturingConnectorManifestRegistry(
  value: unknown,
): ManufacturingConnectorManifestRegistry {
  return parseContract(connectorManifestRegistry, value);
}

export function parseManufacturingConnectorCredentialHandleRegistry(
  value: unknown,
): ManufacturingConnectorCredentialHandleRegistry {
  return parseContract(connectorCredentialHandleRegistry, value);
}

export function parseManufacturingConnectorCredentialLeaseRegistry(
  value: unknown,
): ManufacturingConnectorCredentialLeaseRegistry {
  return parseContract(connectorCredentialLeaseRegistry, value);
}

export function parseManufacturingConnectorEgressPolicyRegistry(
  value: unknown,
): ManufacturingConnectorEgressPolicyRegistry {
  return parseContract(connectorEgressPolicyRegistry, value);
}

export function parseManufacturingConnectorRunRegistry(
  value: unknown,
): ManufacturingConnectorRunRegistry {
  return parseContract(connectorRunRegistry, value);
}

export function parseManufacturingConnectorEvidenceInvariantReport(
  value: unknown,
): ManufacturingConnectorEvidenceInvariantReport {
  return parseContract(connectorEvidenceInvariantReport, value);
}

export function parseManufacturingConnectorOntologyProposalRegistry(
  value: unknown,
): ManufacturingConnectorOntologyProposalRegistry {
  return parseContract(connectorOntologyProposalRegistry, value);
}

export function parseConnectorCsvPreviewResult(value: unknown): ConnectorCsvPreviewResult {
  return parseContract(connectorCsvPreviewResult, value);
}

export function parseConnectorExternalDbPreviewResult(
  value: unknown,
): ConnectorExternalDbPreviewResult {
  return parseContract(connectorExternalDbPreviewResult, value);
}

export function parseConnectorRunRecord(value: unknown): ConnectorRunRecord {
  return parseContract(connectorRunRecord, value);
}
