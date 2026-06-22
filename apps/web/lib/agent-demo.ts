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
