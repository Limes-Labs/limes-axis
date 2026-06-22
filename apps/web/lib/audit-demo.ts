import type { PlatformStatus } from "./platform-overview";

export type AuditLedgerEvent = {
  audit_event_id: string;
  occurred_at: string;
  tenant_id: string;
  actor_id: string;
  actor_type: string;
  event_type: string;
  category: string;
  domain: string;
  scope: string;
  result: string;
  severity: PlatformStatus;
  source: string;
  summary: string;
  permission_scope: string;
  data_classification: string;
  related_workflow_id: string | null;
  related_approval_id: string | null;
  related_agent_id: string | null;
  evidence_refs: string[];
  payload_preview: Record<string, string>;
};

export type AuditFilterOptions = {
  tenants: string[];
  event_types: string[];
  scopes: string[];
  actors: string[];
  categories: string[];
};

export type ManufacturingAuditExplorer = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  as_of: string;
  ledger_status: PlatformStatus;
  metrics: {
    label: string;
    value: string;
    detail: string;
    status: PlatformStatus;
  }[];
  filter_options: AuditFilterOptions;
  events: AuditLedgerEvent[];
  retention_notes: string[];
};

export type AuditRetentionPolicy = {
  policy_id: string;
  retention_days: number;
  retention_basis: string;
  disposal_action: string;
  legal_hold: boolean;
  export_requires_review: boolean;
  notes: string[];
};

export type AuditExportManifest = {
  export_id: string;
  generated_at: string;
  tenant_id: string;
  record_count: number;
  format: string;
  redaction_policy: string;
  retention_policy_id: string;
  checksum_sha256: string;
};

export type AuditExportBundle = {
  tenant_id: string;
  scenario: string;
  format: string;
  export_reason: string;
  filters: {
    tenant_id: string;
    event_type: string | null;
    actor_id: string | null;
    scope: string | null;
    limit: number;
  };
  retention_policy: AuditRetentionPolicy;
  manifest: AuditExportManifest;
  events: AuditLedgerEvent[];
  retention_notes: string[];
};

export type AuditFilters = {
  tenant: string;
  eventType: string;
  scope: string;
};

export const allAuditFilter = "all";

export const defaultManufacturingAuditExplorer: ManufacturingAuditExplorer = {
  tenant_id: "tenant_demo_manufacturing",
  plant_name: "Ravenna Works",
  scenario: "Plant Operations Cockpit",
  as_of: "2026-06-21T16:30:00+02:00",
  ledger_status: "watch",
  metrics: [
    {
      label: "Audit Events",
      value: "9",
      detail: "Synthetic public-safe events for the manufacturing demo",
      status: "ready",
    },
    {
      label: "Action Gates",
      value: "3",
      detail: "Approval and workflow signal events are visible",
      status: "action_required",
    },
    {
      label: "Policy Blocks",
      value: "1",
      detail: "External model egress block is recorded",
      status: "ready",
    },
    {
      label: "Replay",
      value: "Preview",
      detail: "Events are shaped for the replay simulation console",
      status: "watch",
    },
  ],
  filter_options: {
    tenants: ["tenant_demo_manufacturing"],
    event_types: [
      "agent.proposal.created",
      "ontology.relationship.read",
      "permission.check.evaluated",
      "policy.egress.blocked",
      "workflow.signal.awaiting",
      "workflow.started",
    ],
    scopes: [
      "agent_quality_risk",
      "approvals:supply:decide",
      "asset_line_2_packaging",
      "wf_maintenance_reschedule",
      "wf_quality_hold_review",
      "wf_supplier_delay_review",
    ],
    actors: [
      "axis-permission-engine",
      "axis-temporal-adapter",
      "maintenance-planner-agent",
      "model-router",
      "plant-operations-owner-role",
      "quality-risk-agent",
      "supply-risk-agent",
      "workflow-runtime",
    ],
    categories: ["agent", "ontology", "permission", "policy", "workflow"],
  },
  events: [
    {
      audit_event_id: "audit_20260621_140500_workflow_started",
      occurred_at: "2026-06-21T14:05:00+02:00",
      tenant_id: "tenant_demo_manufacturing",
      actor_id: "workflow-runtime",
      actor_type: "service",
      event_type: "workflow.started",
      category: "workflow",
      domain: "Supply",
      scope: "wf_supplier_delay_review",
      result: "started",
      severity: "ready",
      source: "Temporal",
      summary: "Supplier delay workflow created from the supply risk signal.",
      permission_scope: "workflows:read",
      data_classification: "public-demo",
      related_workflow_id: "wf_supplier_delay_review",
      related_approval_id: null,
      related_agent_id: null,
      evidence_refs: ["risk_supplier_delay", "asset_motors_batch"],
      payload_preview: {
        workflow_id: "wf_supplier_delay_review",
        runtime: "Temporal OSS",
        adapter: "axis-temporal-adapter",
      },
    },
    {
      audit_event_id: "audit_20260621_141200_agent_proposal",
      occurred_at: "2026-06-21T14:12:00+02:00",
      tenant_id: "tenant_demo_manufacturing",
      actor_id: "supply-risk-agent",
      actor_type: "agent",
      event_type: "agent.proposal.created",
      category: "agent",
      domain: "Supply",
      scope: "wf_supplier_delay_review",
      result: "approval_required",
      severity: "action_required",
      source: "Axis",
      summary: "L2 agent drafted an expedite supplier batch action payload.",
      permission_scope: "agents:read",
      data_classification: "public-demo",
      related_workflow_id: "wf_supplier_delay_review",
      related_approval_id: "appr_expedite_supplier_batch",
      related_agent_id: "agent_supply_risk",
      evidence_refs: ["appr_expedite_supplier_batch", "asset_line_2_packaging"],
      payload_preview: {
        action: "Expedite supplier batch",
        autonomy_level: "L2",
        risk_level: "high",
      },
    },
    {
      audit_event_id: "audit_20260621_141800_signal_awaiting",
      occurred_at: "2026-06-21T14:18:00+02:00",
      tenant_id: "tenant_demo_manufacturing",
      actor_id: "axis-temporal-adapter",
      actor_type: "service",
      event_type: "workflow.signal.awaiting",
      category: "workflow",
      domain: "Supply",
      scope: "wf_supplier_delay_review",
      result: "waiting_for_approval",
      severity: "action_required",
      source: "Axis Workflow Runtime",
      summary: "Workflow paused at the human approval gate.",
      permission_scope: "workflows:read",
      data_classification: "public-demo",
      related_workflow_id: "wf_supplier_delay_review",
      related_approval_id: "appr_expedite_supplier_batch",
      related_agent_id: null,
      evidence_refs: ["appr_expedite_supplier_batch"],
      payload_preview: {
        signal: "approval.decision",
        required_role: "plant-operations-owner",
        status: "waiting",
      },
    },
    {
      audit_event_id: "audit_20260621_133900_egress_blocked",
      occurred_at: "2026-06-21T13:39:00+02:00",
      tenant_id: "tenant_demo_manufacturing",
      actor_id: "model-router",
      actor_type: "service",
      event_type: "policy.egress.blocked",
      category: "policy",
      domain: "Security",
      scope: "agent_quality_risk",
      result: "blocked_by_default",
      severity: "ready",
      source: "Axis Policy",
      summary: "External model egress was blocked for quality evidence.",
      permission_scope: "security:read",
      data_classification: "public-demo",
      related_workflow_id: null,
      related_approval_id: null,
      related_agent_id: "agent_quality_risk",
      evidence_refs: ["policy_external_egress", "wf_quality_hold_review"],
      payload_preview: {
        model_policy: "no-external-egress",
        provider: "external",
        decision: "blocked",
      },
    },
    {
      audit_event_id: "audit_20260621_134400_quality_proposal",
      occurred_at: "2026-06-21T13:44:00+02:00",
      tenant_id: "tenant_demo_manufacturing",
      actor_id: "quality-risk-agent",
      actor_type: "agent",
      event_type: "agent.proposal.created",
      category: "agent",
      domain: "Quality",
      scope: "wf_quality_hold_review",
      result: "review_required",
      severity: "watch",
      source: "Axis",
      summary: "L2 agent drafted a quality hold proposal for Batch Q-1842.",
      permission_scope: "agents:read",
      data_classification: "public-demo",
      related_workflow_id: "wf_quality_hold_review",
      related_approval_id: "appr_quality_hold_batch",
      related_agent_id: "agent_quality_risk",
      evidence_refs: ["risk_quality_drift", "asset_batch_q_1842"],
      payload_preview: {
        action: "Place Batch Q-1842 on quality hold",
        autonomy_level: "L2",
        risk_level: "high",
      },
    },
    {
      audit_event_id: "audit_20260621_151800_maintenance_proposal",
      occurred_at: "2026-06-21T15:18:00+02:00",
      tenant_id: "tenant_demo_manufacturing",
      actor_id: "maintenance-planner-agent",
      actor_type: "agent",
      event_type: "agent.proposal.created",
      category: "agent",
      domain: "Maintenance",
      scope: "wf_maintenance_reschedule",
      result: "proposal_ready",
      severity: "watch",
      source: "Axis",
      summary: "L2 agent drafted the Press 4 maintenance schedule shift proposal.",
      permission_scope: "agents:read",
      data_classification: "public-demo",
      related_workflow_id: "wf_maintenance_reschedule",
      related_approval_id: "appr_shift_maintenance_window",
      related_agent_id: null,
      evidence_refs: ["risk_maintenance_window", "asset_press_4"],
      payload_preview: {
        action: "Shift Press 4 maintenance window",
        autonomy_level: "L2",
        risk_level: "medium",
      },
    },
    {
      audit_event_id: "audit_20260621_152500_maintenance_signal",
      occurred_at: "2026-06-21T15:25:00+02:00",
      tenant_id: "tenant_demo_manufacturing",
      actor_id: "axis-temporal-adapter",
      actor_type: "service",
      event_type: "workflow.signal.awaiting",
      category: "workflow",
      domain: "Maintenance",
      scope: "wf_maintenance_reschedule",
      result: "waiting_for_owner_review",
      severity: "watch",
      source: "Axis Workflow Runtime",
      summary: "Workflow paused before mutating the maintenance schedule.",
      permission_scope: "workflows:read",
      data_classification: "public-demo",
      related_workflow_id: "wf_maintenance_reschedule",
      related_approval_id: "appr_shift_maintenance_window",
      related_agent_id: null,
      evidence_refs: ["appr_shift_maintenance_window"],
      payload_preview: {
        signal: "maintenance.owner.review",
        required_role: "maintenance-owner",
        status: "waiting",
      },
    },
    {
      audit_event_id: "audit_20260621_153200_permission_check",
      occurred_at: "2026-06-21T15:32:00+02:00",
      tenant_id: "tenant_demo_manufacturing",
      actor_id: "axis-permission-engine",
      actor_type: "service",
      event_type: "permission.check.evaluated",
      category: "permission",
      domain: "Supply",
      scope: "approvals:supply:decide",
      result: "allowed_for_owner_role",
      severity: "ready",
      source: "Axis Permissions",
      summary: "Supply approval decision permission evaluated for the owner role.",
      permission_scope: "permissions:read",
      data_classification: "public-demo",
      related_workflow_id: null,
      related_approval_id: "appr_expedite_supplier_batch",
      related_agent_id: null,
      evidence_refs: ["plant-operations-owner", "appr_expedite_supplier_batch"],
      payload_preview: {
        role: "plant-operations-owner",
        permission: "approvals:supply:decide",
        decision: "allowed",
      },
    },
    {
      audit_event_id: "audit_20260621_154000_ontology_read",
      occurred_at: "2026-06-21T15:40:00+02:00",
      tenant_id: "tenant_demo_manufacturing",
      actor_id: "plant-operations-owner-role",
      actor_type: "role",
      event_type: "ontology.relationship.read",
      category: "ontology",
      domain: "Operations",
      scope: "asset_line_2_packaging",
      result: "allowed",
      severity: "ready",
      source: "TypeDB Boundary",
      summary: "Operations owner inspected supplier delay relationships for Line 2.",
      permission_scope: "operations:read",
      data_classification: "public-demo",
      related_workflow_id: "wf_supplier_delay_review",
      related_approval_id: null,
      related_agent_id: null,
      evidence_refs: ["asset_line_2_packaging", "risk_supplier_delay"],
      payload_preview: {
        node: "asset_line_2_packaging",
        relation: "impacts",
        decision: "allowed",
      },
    },
  ],
  retention_notes: [
    "This public audit explorer seed is read-only and synthetic.",
    "Payload previews are redacted and contain no customer data or credentials.",
    "Production audit events must be append-only and tenant-scoped.",
    "Export, retention policy enforcement and replay remain Platform work.",
  ],
};

export const defaultAuditExportBundle: AuditExportBundle = {
  tenant_id: defaultManufacturingAuditExplorer.tenant_id,
  scenario: defaultManufacturingAuditExplorer.scenario,
  format: "json",
  export_reason: "standalone-console-fallback",
  filters: {
    tenant_id: defaultManufacturingAuditExplorer.tenant_id,
    event_type: null,
    actor_id: null,
    scope: null,
    limit: 100,
  },
  retention_policy: {
    policy_id: "axis-demo-audit-standard",
    retention_days: 365,
    retention_basis: "tenant-scoped operational audit ledger",
    disposal_action: "review_then_delete",
    legal_hold: false,
    export_requires_review: true,
    notes: [
      "Demo exports are payload-preview-only and require governance review before sharing.",
      "Retention controls are represented as policy metadata in this slice.",
      "Deletion enforcement, legal hold workflow and immutable storage hardening remain future work.",
    ],
  },
  manifest: {
    export_id: "audit-export-local-seed",
    generated_at: defaultManufacturingAuditExplorer.as_of,
    tenant_id: defaultManufacturingAuditExplorer.tenant_id,
    record_count: defaultManufacturingAuditExplorer.events.length,
    format: "json",
    redaction_policy: "payload-preview-only",
    retention_policy_id: "axis-demo-audit-standard",
    checksum_sha256: "0".repeat(64),
  },
  events: defaultManufacturingAuditExplorer.events,
  retention_notes: [
    "Export bundle is tenant-scoped before optional filters are applied.",
    "Events include ledger metadata and redacted payload previews only.",
    "Retention policy is advisory metadata until enforcement is implemented.",
  ],
};

export function filterAuditEvents(
  explorer: ManufacturingAuditExplorer,
  filters: AuditFilters,
): AuditLedgerEvent[] {
  return explorer.events.filter((event) => {
    const tenantMatches = filters.tenant === allAuditFilter || event.tenant_id === filters.tenant;
    const eventMatches =
      filters.eventType === allAuditFilter || event.event_type === filters.eventType;
    const scopeMatches = filters.scope === allAuditFilter || event.scope === filters.scope;

    return tenantMatches && eventMatches && scopeMatches;
  });
}

export function findAuditEventById(
  explorer: ManufacturingAuditExplorer,
  auditEventId: string,
): AuditLedgerEvent {
  return (
    explorer.events.find((event) => event.audit_event_id === auditEventId) ?? explorer.events[0]
  );
}

export function formatAuditLabel(value: string): string {
  return value
    .split(/[._:]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
