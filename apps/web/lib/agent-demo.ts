import type { PlatformStatus } from "./platform-overview";

export type AgentActionProposal = {
  proposal_id: string;
  action: string;
  risk_level: "high" | "medium" | "low";
  status: string;
  approval_required: boolean;
  related_workflow_id: string | null;
  related_approval_id: string | null;
};

export type AgentPolicyBoundary = {
  autonomy_level: "L0" | "L1" | "L2" | "L3" | "L4";
  model_policy: string;
  external_egress_allowed: boolean;
  max_action_level: "L0" | "L1" | "L2" | "L3" | "L4";
  required_permissions: string[];
  guardrails: string[];
};

export type AgentRegistryEntry = {
  agent_id: string;
  name: string;
  domain: string;
  status: string;
  owner_role: string;
  purpose: string;
  policy_boundary: AgentPolicyBoundary;
  connected_systems: string[];
  data_access: string[];
  allowed_actions: string[];
  blocked_actions: string[];
  proposals: AgentActionProposal[];
  active_workflows: string[];
  pending_approvals: string[];
  last_audit_event: string;
  evidence_refs: string[];
};

export type AgentRegistryFilterOptions = {
  domains: string[];
  autonomy_levels: string[];
  statuses: string[];
  model_policies: string[];
};

export type ManufacturingAgentRegistry = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  as_of: string;
  registry_status: PlatformStatus;
  metrics: {
    label: string;
    value: string;
    detail: string;
    status: PlatformStatus;
  }[];
  filter_options: AgentRegistryFilterOptions;
  agents: AgentRegistryEntry[];
  registry_notes: string[];
};

export type AgentFilters = {
  domain: string;
  autonomyLevel: string;
  status: string;
};

export const allAgentFilter = "all";

export const defaultManufacturingAgentRegistry: ManufacturingAgentRegistry = {
  tenant_id: "tenant_demo_manufacturing",
  plant_name: "Ravenna Works",
  scenario: "Plant Operations Cockpit",
  as_of: "2026-06-21T16:30:00+02:00",
  registry_status: "watch",
  metrics: [
    {
      label: "Registered Agents",
      value: "4",
      detail: "Governed L1-L2 agents in the manufacturing demo tenant",
      status: "ready",
    },
    {
      label: "Pending Proposals",
      value: "4",
      detail: "One brief proposal and three action proposals under owner review",
      status: "watch",
    },
    {
      label: "Approval Gates",
      value: "3",
      detail: "High and medium risk agent proposals require human owners",
      status: "action_required",
    },
    {
      label: "External Egress",
      value: "0 allowed",
      detail: "All demo agents remain inside the tenant boundary",
      status: "ready",
    },
  ],
  filter_options: {
    domains: ["Maintenance", "Operations", "Quality", "Supply"],
    autonomy_levels: ["L1", "L2"],
    statuses: ["drafting_actions", "proposal_ready", "recommending", "waiting_for_approval"],
    model_policies: ["local-or-approved-provider", "no-external-egress"],
  },
  agents: [
    {
      agent_id: "agent_daily_brief",
      name: "Daily Brief Agent",
      domain: "Operations",
      status: "recommending",
      owner_role: "plant-operations-owner",
      purpose: "Summarize plant risks, pending workflow gates and audit evidence for owners.",
      policy_boundary: {
        autonomy_level: "L1",
        model_policy: "local-or-approved-provider",
        external_egress_allowed: false,
        max_action_level: "L1",
        required_permissions: ["agents:read", "audit:read", "workflows:read"],
        guardrails: [
          "Summaries only; no action payload execution.",
          "No external model egress unless tenant policy explicitly allows it.",
          "Must cite workflow, approval or audit evidence for operational claims.",
        ],
      },
      connected_systems: ["Axis Audit", "Temporal", "TypeDB Boundary"],
      data_access: [
        "workflow summaries",
        "approval queue summaries",
        "audit event summaries",
        "ontology relationship summaries",
      ],
      allowed_actions: [
        "Generate daily plant brief",
        "Rank open governance gates",
        "Prepare owner-facing evidence summary",
      ],
      blocked_actions: [
        "Execute workflow signal",
        "Approve action payload",
        "Read unrestricted source-system records",
      ],
      proposals: [
        {
          proposal_id: "proposal_daily_brief_20260621",
          action: "Generate daily plant brief",
          risk_level: "low",
          status: "ready_for_owner_review",
          approval_required: false,
          related_workflow_id: "wf_supplier_delay_review",
          related_approval_id: null,
        },
      ],
      active_workflows: ["wf_supplier_delay_review", "wf_quality_hold_review"],
      pending_approvals: [],
      last_audit_event: "audit_20260621_154000_ontology_read",
      evidence_refs: ["wf_supplier_delay_review", "audit_20260621_154000_ontology_read"],
    },
    {
      agent_id: "agent_supply_risk",
      name: "Supply Risk Agent",
      domain: "Supply",
      status: "waiting_for_approval",
      owner_role: "plant-operations-owner",
      purpose: "Detect supplier delay risk and draft governed supply actions.",
      policy_boundary: {
        autonomy_level: "L2",
        model_policy: "no-external-egress",
        external_egress_allowed: false,
        max_action_level: "L2",
        required_permissions: ["agents:read", "supply:read", "approvals:supply:request"],
        guardrails: [
          "Can draft action payloads, but cannot execute supplier changes.",
          "High-risk supply actions require plant operations owner approval.",
          "Must keep supplier and production context inside tenant boundary.",
        ],
      },
      connected_systems: ["Supplier Portal", "MES", "ERP", "Axis Audit"],
      data_access: [
        "inbound shipment status",
        "Line 2 packaging schedule",
        "rush order priority flag",
        "supply approval history",
      ],
      allowed_actions: [
        "Draft expedite supplier batch action",
        "Prepare supplier delay evidence",
        "Request supply owner approval",
      ],
      blocked_actions: ["Book priority freight", "Mutate supplier order", "Signal workflow completion"],
      proposals: [
        {
          proposal_id: "proposal_expedite_supplier_batch",
          action: "Expedite supplier batch",
          risk_level: "high",
          status: "approval_required",
          approval_required: true,
          related_workflow_id: "wf_supplier_delay_review",
          related_approval_id: "appr_expedite_supplier_batch",
        },
      ],
      active_workflows: ["wf_supplier_delay_review"],
      pending_approvals: ["appr_expedite_supplier_batch"],
      last_audit_event: "audit_20260621_141200_agent_proposal",
      evidence_refs: [
        "risk_supplier_delay",
        "asset_motors_batch",
        "audit_20260621_141200_agent_proposal",
      ],
    },
    {
      agent_id: "agent_quality_risk",
      name: "Quality Risk Agent",
      domain: "Quality",
      status: "drafting_actions",
      owner_role: "quality-owner",
      purpose: "Review quality drift evidence and draft quality hold recommendations.",
      policy_boundary: {
        autonomy_level: "L2",
        model_policy: "no-external-egress",
        external_egress_allowed: false,
        max_action_level: "L2",
        required_permissions: ["agents:read", "quality:read", "approvals:quality:request"],
        guardrails: [
          "Can draft quality hold recommendations, but cannot release or hold batches.",
          "Quality evidence must stay inside approved tenant systems.",
          "External model egress is blocked by default for quality evidence.",
        ],
      },
      connected_systems: ["QMS", "MES", "ERP", "Axis Audit"],
      data_access: [
        "sample inspection variance",
        "batch genealogy",
        "customer order priority",
        "quality proposal audit trail",
      ],
      allowed_actions: [
        "Draft quality hold proposal",
        "Prepare evidence for quality owner",
        "Request quality owner review",
      ],
      blocked_actions: [
        "Release batch",
        "Place batch on hold without approval",
        "Use external model provider for quality data",
      ],
      proposals: [
        {
          proposal_id: "proposal_quality_hold_batch_q_1842",
          action: "Place Batch Q-1842 on quality hold",
          risk_level: "high",
          status: "review_required",
          approval_required: true,
          related_workflow_id: "wf_quality_hold_review",
          related_approval_id: "appr_quality_hold_batch",
        },
      ],
      active_workflows: ["wf_quality_hold_review"],
      pending_approvals: ["appr_quality_hold_batch"],
      last_audit_event: "audit_20260621_134400_quality_proposal",
      evidence_refs: [
        "risk_quality_drift",
        "asset_batch_q_1842",
        "audit_20260621_133900_egress_blocked",
      ],
    },
    {
      agent_id: "agent_maintenance_planner",
      name: "Maintenance Planner Agent",
      domain: "Maintenance",
      status: "proposal_ready",
      owner_role: "maintenance-owner",
      purpose: "Draft maintenance schedule changes while preserving service-window policy.",
      policy_boundary: {
        autonomy_level: "L2",
        model_policy: "local-or-approved-provider",
        external_egress_allowed: false,
        max_action_level: "L2",
        required_permissions: [
          "agents:read",
          "maintenance:read",
          "approvals:maintenance:request",
        ],
        guardrails: [
          "Can draft schedule shifts, but cannot mutate CMMS state.",
          "Service-window policy must be checked before owner review.",
          "Schedule changes require maintenance owner approval.",
        ],
      },
      connected_systems: ["CMMS", "MES", "ERP", "Axis Audit"],
      data_access: [
        "Press 4 maintenance window",
        "rush order schedule",
        "service interval tolerance",
        "maintenance proposal audit trail",
      ],
      allowed_actions: [
        "Draft maintenance reschedule proposal",
        "Prepare service-window evidence",
        "Request maintenance owner review",
      ],
      blocked_actions: [
        "Mutate CMMS schedule",
        "Delay maintenance beyond policy",
        "Close workflow without owner signal",
      ],
      proposals: [
        {
          proposal_id: "proposal_shift_press_4_maintenance",
          action: "Shift Press 4 maintenance window",
          risk_level: "medium",
          status: "proposal_ready",
          approval_required: true,
          related_workflow_id: "wf_maintenance_reschedule",
          related_approval_id: "appr_shift_maintenance_window",
        },
      ],
      active_workflows: ["wf_maintenance_reschedule"],
      pending_approvals: ["appr_shift_maintenance_window"],
      last_audit_event: "audit_20260621_151800_maintenance_proposal",
      evidence_refs: [
        "risk_maintenance_window",
        "asset_press_4",
        "audit_20260621_151800_maintenance_proposal",
      ],
    },
  ],
  registry_notes: [
    "This public agent registry seed is read-only and synthetic.",
    "Agents can draft or recommend inside their autonomy level, but cannot mutate systems.",
    "External model egress is disabled unless tenant policy explicitly enables it.",
    "A production action registry, runtime execution and persisted agent state remain Platform work.",
  ],
};

export function filterAgents(
  registry: ManufacturingAgentRegistry,
  filters: AgentFilters,
): AgentRegistryEntry[] {
  return registry.agents.filter((agent) => {
    const domainMatches = filters.domain === allAgentFilter || agent.domain === filters.domain;
    const autonomyMatches =
      filters.autonomyLevel === allAgentFilter ||
      agent.policy_boundary.autonomy_level === filters.autonomyLevel;
    const statusMatches = filters.status === allAgentFilter || agent.status === filters.status;

    return domainMatches && autonomyMatches && statusMatches;
  });
}

export function findAgentById(
  registry: ManufacturingAgentRegistry,
  agentId: string,
): AgentRegistryEntry {
  return registry.agents.find((agent) => agent.agent_id === agentId) ?? registry.agents[0];
}

export function countPendingAgentProposals(registry: ManufacturingAgentRegistry): number {
  return registry.agents.reduce((total, agent) => total + agent.proposals.length, 0);
}

export function formatAgentLabel(value: string): string {
  return value
    .split(/[._:-]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
