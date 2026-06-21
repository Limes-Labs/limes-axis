import type { PlatformStatus } from "./platform-overview";

export type ActionRiskLevel = "low" | "medium" | "high" | "critical";
export type ApprovalMode = "not_required" | "required" | "conditional";

export type ActionJsonSchema = {
  type: string;
  required?: string[];
  properties?: Record<string, { type: string; items?: { type: string } }>;
};

export type ActionDefinition = {
  action_id: string;
  display_name: string;
  domain: string;
  risk_level: ActionRiskLevel;
  approval_mode: ApprovalMode;
  input_schema: ActionJsonSchema;
  output_schema: ActionJsonSchema;
  required_permissions: string[];
};

export type ActionRegistryPolicy = {
  approval_role: string;
  autonomy_ceiling: "L0" | "L1" | "L2" | "L3" | "L4";
  execution_mode: string;
  runtime_adapter: string;
  audit_event_type: string;
  model_egress_policy: string;
  idempotency_required: boolean;
  dry_run_supported: boolean;
};

export type ActionRegistryEntry = {
  definition: ActionDefinition;
  description: string;
  owner_role: string;
  status: string;
  side_effects: string;
  policy: ActionRegistryPolicy;
  connected_agents: string[];
  workflow_bindings: string[];
  approval_refs: string[];
  guardrails: string[];
  validation_checks: string[];
  blocked_conditions: string[];
  sample_input: Record<string, string>;
  sample_output: Record<string, string>;
};

export type ActionRegistryFilterOptions = {
  domains: string[];
  risk_levels: ActionRiskLevel[];
  approval_modes: ApprovalMode[];
  statuses: string[];
};

export type ManufacturingActionRegistry = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  as_of: string;
  registry_status: PlatformStatus;
  schema_version: string;
  metrics: {
    label: string;
    value: string;
    detail: string;
    status: PlatformStatus;
  }[];
  filter_options: ActionRegistryFilterOptions;
  actions: ActionRegistryEntry[];
  registry_notes: string[];
};

export type ActionRunRequest = {
  actor_id: string;
  actor_scopes: string[];
  idempotency_key?: string;
  payload: Record<string, unknown>;
};

export type ActionRunPersistenceResult = {
  tenant_id: string;
  action_run_id: string;
  action_id: string;
  idempotency_key: string;
  status: string;
  execution_mode: string;
  requested_by: string;
  approval_required: boolean;
  approval_id?: string | null;
  workflow_id?: string | null;
  persisted: boolean;
  idempotent_replay: boolean;
  permission_decision: {
    allowed: boolean;
    reason: string;
  };
  audit_event_id?: string | null;
  audit_event_type?: string | null;
};

export type ActionFilters = {
  domain: string;
  riskLevel: string;
  approvalMode: string;
  status: string;
};

export const allActionFilter = "all";

export const defaultManufacturingActionRegistry: ManufacturingActionRegistry = {
  tenant_id: "tenant_demo_manufacturing",
  plant_name: "Ravenna Works",
  scenario: "Plant Operations Cockpit",
  as_of: "2026-06-21T16:30:00+02:00",
  registry_status: "watch",
  schema_version: "2026-06-21",
  metrics: [
    {
      label: "Registered Actions",
      value: "4",
      detail: "Typed action definitions for the manufacturing demo tenant",
      status: "ready",
    },
    {
      label: "Approval Required",
      value: "3",
      detail: "High and conditional actions are routed to owner review",
      status: "action_required",
    },
    {
      label: "Runtime Execution",
      value: "0 live",
      detail: "Public demo remains preview and dry-run only",
      status: "watch",
    },
    {
      label: "External Egress",
      value: "0 allowed",
      detail: "Action payloads stay inside the tenant boundary",
      status: "ready",
    },
  ],
  filter_options: {
    domains: ["Maintenance", "Operations", "Quality", "Supply"],
    risk_levels: ["high", "low", "medium"],
    approval_modes: ["conditional", "not_required", "required"],
    statuses: [
      "approval_required",
      "available_for_preview",
      "conditional_approval_required",
      "review_required",
    ],
  },
  actions: [
    {
      definition: {
        action_id: "generate_daily_plant_brief",
        display_name: "Generate daily plant brief",
        domain: "Operations",
        risk_level: "low",
        approval_mode: "not_required",
        input_schema: {
          type: "object",
          required: ["tenant_id", "scope", "evidence_refs"],
          properties: {
            tenant_id: { type: "string" },
            scope: { type: "string" },
            evidence_refs: { type: "array", items: { type: "string" } },
          },
        },
        output_schema: {
          type: "object",
          required: ["brief_id", "summary", "cited_evidence"],
          properties: {
            brief_id: { type: "string" },
            summary: { type: "string" },
            cited_evidence: { type: "array", items: { type: "string" } },
          },
        },
        required_permissions: ["briefs:generate", "audit:read", "workflows:read"],
      },
      description: "Build a read-only daily plant brief from workflow, approval and audit evidence.",
      owner_role: "plant-operations-owner",
      status: "available_for_preview",
      side_effects: "No external mutation; produces owner-facing summary only.",
      policy: {
        approval_role: "plant-operations-owner",
        autonomy_ceiling: "L1",
        execution_mode: "preview_only",
        runtime_adapter: "axis-action-preview",
        audit_event_type: "action.preview.generated",
        model_egress_policy: "local-or-approved-provider",
        idempotency_required: false,
        dry_run_supported: true,
      },
      connected_agents: ["agent_daily_brief"],
      workflow_bindings: ["wf_supplier_delay_review", "wf_quality_hold_review"],
      approval_refs: [],
      guardrails: [
        "Must cite existing workflow, approval or audit evidence.",
        "Cannot approve or signal workflow state.",
        "External model egress remains blocked unless tenant policy allows it.",
      ],
      validation_checks: [
        "tenant_id matches request context",
        "evidence_refs exist in accessible audit scope",
        "scope is limited to plant operations cockpit",
      ],
      blocked_conditions: [
        "missing evidence references",
        "cross-tenant evidence requested",
        "unapproved external model route",
      ],
      sample_input: {
        tenant_id: "tenant_demo_manufacturing",
        scope: "daily_operations",
        evidence_refs: "wf_supplier_delay_review,audit_20260621_154000_ontology_read",
      },
      sample_output: {
        brief_id: "brief_20260621_demo",
        summary: "Three governed operational risks require owner review.",
        cited_evidence: "wf_supplier_delay_review,audit_20260621_154000_ontology_read",
      },
    },
    {
      definition: {
        action_id: "request_supplier_expedite",
        display_name: "Request supplier expedite",
        domain: "Supply",
        risk_level: "high",
        approval_mode: "required",
        input_schema: {
          type: "object",
          required: ["supplier_batch_id", "target_arrival", "reason", "cost_ceiling_eur"],
          properties: {
            supplier_batch_id: { type: "string" },
            target_arrival: { type: "string" },
            reason: { type: "string" },
            cost_ceiling_eur: { type: "string" },
          },
        },
        output_schema: {
          type: "object",
          required: ["request_id", "approval_id", "audit_event_id"],
          properties: {
            request_id: { type: "string" },
            approval_id: { type: "string" },
            audit_event_id: { type: "string" },
          },
        },
        required_permissions: ["supply:read", "approvals:supply:request"],
      },
      description: "Prepare an expedite request for delayed inbound material.",
      owner_role: "plant-operations-owner",
      status: "approval_required",
      side_effects: "Would request supplier action after owner approval; demo is dry-run only.",
      policy: {
        approval_role: "plant-operations-owner",
        autonomy_ceiling: "L2",
        execution_mode: "approval_gated_dry_run",
        runtime_adapter: "axis-temporal-adapter",
        audit_event_type: "action.proposal.created",
        model_egress_policy: "no-external-egress",
        idempotency_required: true,
        dry_run_supported: true,
      },
      connected_agents: ["agent_supply_risk"],
      workflow_bindings: ["wf_supplier_delay_review"],
      approval_refs: ["appr_expedite_supplier_batch"],
      guardrails: [
        "High-risk supply action must enter approval inbox before execution.",
        "Agent can draft payload but cannot book priority freight.",
        "Cost ceiling and target arrival must be visible to the owner.",
      ],
      validation_checks: [
        "supplier_batch_id maps to accessible supplier risk evidence",
        "cost_ceiling_eur is present",
        "approval role matches plant operations owner",
        "idempotency key exists before runtime signal",
      ],
      blocked_conditions: [
        "missing approval",
        "external freight booking requested directly",
        "supplier batch outside tenant scope",
      ],
      sample_input: {
        supplier_batch_id: "asset_motors_batch",
        target_arrival: "2026-06-22T08:00:00+02:00",
        reason: "Line 2 packaging risk",
        cost_ceiling_eur: "1200",
      },
      sample_output: {
        request_id: "act_supplier_expedite_preview",
        approval_id: "appr_expedite_supplier_batch",
        audit_event_id: "audit_20260621_141200_agent_proposal",
      },
    },
    {
      definition: {
        action_id: "place_quality_hold",
        display_name: "Place quality hold",
        domain: "Quality",
        risk_level: "high",
        approval_mode: "required",
        input_schema: {
          type: "object",
          required: ["batch_id", "hold_reason", "evidence_refs"],
          properties: {
            batch_id: { type: "string" },
            hold_reason: { type: "string" },
            evidence_refs: { type: "array", items: { type: "string" } },
          },
        },
        output_schema: {
          type: "object",
          required: ["hold_request_id", "approval_id", "audit_event_id"],
          properties: {
            hold_request_id: { type: "string" },
            approval_id: { type: "string" },
            audit_event_id: { type: "string" },
          },
        },
        required_permissions: ["quality:read", "approvals:quality:request"],
      },
      description: "Draft a quality hold proposal for owner review.",
      owner_role: "quality-owner",
      status: "review_required",
      side_effects: "Would hold a production batch only after quality owner approval.",
      policy: {
        approval_role: "quality-owner",
        autonomy_ceiling: "L2",
        execution_mode: "approval_gated_dry_run",
        runtime_adapter: "axis-temporal-adapter",
        audit_event_type: "action.proposal.created",
        model_egress_policy: "no-external-egress",
        idempotency_required: true,
        dry_run_supported: true,
      },
      connected_agents: ["agent_quality_risk"],
      workflow_bindings: ["wf_quality_hold_review"],
      approval_refs: ["appr_quality_hold_batch"],
      guardrails: [
        "Quality evidence must remain inside tenant systems.",
        "Agent cannot release or hold a batch without owner decision.",
        "Proposal must include batch genealogy evidence.",
      ],
      validation_checks: [
        "batch_id maps to accessible quality risk evidence",
        "evidence_refs include audit event and risk node",
        "approval role matches quality owner",
      ],
      blocked_conditions: [
        "missing batch genealogy",
        "owner approval absent",
        "external model route requested for quality data",
      ],
      sample_input: {
        batch_id: "asset_batch_q_1842",
        hold_reason: "Inspection variance crossed watch threshold",
        evidence_refs: "risk_quality_drift,audit_20260621_134400_quality_proposal",
      },
      sample_output: {
        hold_request_id: "act_quality_hold_preview",
        approval_id: "appr_quality_hold_batch",
        audit_event_id: "audit_20260621_134400_quality_proposal",
      },
    },
    {
      definition: {
        action_id: "shift_maintenance_window",
        display_name: "Shift maintenance window",
        domain: "Maintenance",
        risk_level: "medium",
        approval_mode: "conditional",
        input_schema: {
          type: "object",
          required: ["asset_id", "current_window", "proposed_window", "policy_check_id"],
          properties: {
            asset_id: { type: "string" },
            current_window: { type: "string" },
            proposed_window: { type: "string" },
            policy_check_id: { type: "string" },
          },
        },
        output_schema: {
          type: "object",
          required: ["proposal_id", "approval_id", "audit_event_id"],
          properties: {
            proposal_id: { type: "string" },
            approval_id: { type: "string" },
            audit_event_id: { type: "string" },
          },
        },
        required_permissions: ["maintenance:read", "approvals:maintenance:request"],
      },
      description: "Draft a service-window-safe maintenance reschedule proposal.",
      owner_role: "maintenance-owner",
      status: "conditional_approval_required",
      side_effects: "Would update CMMS schedule only after policy and owner gates.",
      policy: {
        approval_role: "maintenance-owner",
        autonomy_ceiling: "L2",
        execution_mode: "conditional_approval_dry_run",
        runtime_adapter: "axis-temporal-adapter",
        audit_event_type: "action.proposal.created",
        model_egress_policy: "local-or-approved-provider",
        idempotency_required: true,
        dry_run_supported: true,
      },
      connected_agents: ["agent_maintenance_planner"],
      workflow_bindings: ["wf_maintenance_reschedule"],
      approval_refs: ["appr_shift_maintenance_window"],
      guardrails: [
        "Service-window policy must pass before owner review.",
        "Agent cannot mutate CMMS schedule directly.",
        "Schedule shift must preserve maintenance interval tolerance.",
      ],
      validation_checks: [
        "asset_id maps to accessible maintenance risk evidence",
        "policy_check_id is present",
        "proposed_window stays inside allowed service tolerance",
      ],
      blocked_conditions: [
        "service-window policy failed",
        "maintenance owner approval absent",
        "CMMS mutation requested before workflow signal",
      ],
      sample_input: {
        asset_id: "asset_press_4",
        current_window: "2026-06-22T09:00:00+02:00",
        proposed_window: "2026-06-22T13:00:00+02:00",
        policy_check_id: "service-window-policy",
      },
      sample_output: {
        proposal_id: "act_maintenance_shift_preview",
        approval_id: "appr_shift_maintenance_window",
        audit_event_id: "audit_20260621_151800_maintenance_proposal",
      },
    },
  ],
  registry_notes: [
    "This public action registry seed is synthetic and safe for dry-run requests.",
    "Actions are typed and policy-gated, but live runtime execution is not enabled.",
    "High-risk actions require owner approval before any production signal.",
    "Action run requests can be persisted with idempotency and append-only audit.",
  ],
};

export function filterActions(
  registry: ManufacturingActionRegistry,
  filters: ActionFilters,
): ActionRegistryEntry[] {
  return registry.actions.filter((action) => {
    const domainMatches =
      filters.domain === allActionFilter || action.definition.domain === filters.domain;
    const riskMatches =
      filters.riskLevel === allActionFilter ||
      action.definition.risk_level === filters.riskLevel;
    const approvalMatches =
      filters.approvalMode === allActionFilter ||
      action.definition.approval_mode === filters.approvalMode;
    const statusMatches = filters.status === allActionFilter || action.status === filters.status;

    return domainMatches && riskMatches && approvalMatches && statusMatches;
  });
}

export function findActionById(
  registry: ManufacturingActionRegistry,
  actionId: string,
): ActionRegistryEntry {
  return (
    registry.actions.find((action) => action.definition.action_id === actionId) ??
    registry.actions[0]
  );
}

export function countApprovalGatedActions(registry: ManufacturingActionRegistry): number {
  return registry.actions.filter((action) => action.definition.approval_mode !== "not_required")
    .length;
}

export function formatActionLabel(value: string): string {
  return value
    .split(/[._:-]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function formatSchemaFields(schema: ActionJsonSchema): string[] {
  return Object.entries(schema.properties ?? {}).map(([name, definition]) => {
    const type =
      definition.type === "array" && definition.items
        ? `${definition.items.type}[]`
        : definition.type;
    const required = schema.required?.includes(name) ? "required" : "optional";

    return `${name}: ${type} (${required})`;
  });
}

export function buildActionRunIdempotencyKey(
  registry: ManufacturingActionRegistry,
  action: ActionRegistryEntry,
): string {
  const approvalOrPreview = action.approval_refs[0] ?? "preview";

  return `${registry.tenant_id}:${action.definition.action_id}:${approvalOrPreview}`;
}

export function buildTypedActionPayload(action: ActionRegistryEntry): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(action.sample_input).map(([field, value]) => {
      const fieldSchema = action.definition.input_schema.properties?.[field];
      if (fieldSchema?.type === "array") {
        return [
          field,
          value
            .split(",")
            .map((item) => item.trim())
            .filter(Boolean),
        ];
      }

      return [field, value];
    }),
  );
}

export function buildActionRunRequest(
  registry: ManufacturingActionRegistry,
  action: ActionRegistryEntry,
): ActionRunRequest {
  return {
    actor_id: action.connected_agents[0] ?? action.owner_role,
    actor_scopes: action.definition.required_permissions,
    idempotency_key: buildActionRunIdempotencyKey(registry, action),
    payload: buildTypedActionPayload(action),
  };
}
