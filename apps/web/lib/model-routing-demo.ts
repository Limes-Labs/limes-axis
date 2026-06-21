import type { OverviewMetric, PlatformStatus } from "./platform-overview";

export type ModelProviderOption = {
  provider_id: string;
  display_name: string;
  provider_type: string;
  hosting_boundary: string;
  status: string;
  egress_mode: string;
  cost_basis: string;
  allowed_policies: string[];
  notes: string[];
};

export type ModelRouteTelemetry = {
  route_id: string;
  agent_id: string;
  agent_name: string;
  domain: string;
  provider_id: string;
  provider_name: string;
  model: string;
  model_policy: string;
  prompt_classification: string;
  data_boundary: string;
  external_egress_requested: boolean;
  external_egress_allowed: boolean;
  egress_decision: string;
  decision_reason: string;
  route_status: PlatformStatus;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_eur: number;
  latency_ms: number;
  cost_center: string;
  required_permissions: string[];
  evidence_refs: string[];
  audit_event_id: string;
  observability_events: string[];
};

export type ModelRoutingFilterOptions = {
  domains: string[];
  providers: string[];
  model_policies: string[];
  egress_decisions: string[];
  statuses: PlatformStatus[];
};

export type ManufacturingModelRouting = {
  tenant_id: string;
  plant_name: string;
  scenario: string;
  as_of: string;
  routing_status: PlatformStatus;
  metrics: OverviewMetric[];
  filter_options: ModelRoutingFilterOptions;
  provider_options: ModelProviderOption[];
  routes: ModelRouteTelemetry[];
  budget_notes: string[];
  observability_notes: string[];
};

export type ModelRoutingFilters = {
  domain: string;
  provider: string;
  decision: string;
};

export const allModelRoutingFilter = "all";

export const defaultManufacturingModelRouting: ManufacturingModelRouting = {
  tenant_id: "tenant_demo_manufacturing",
  plant_name: "Ravenna Works",
  scenario: "Plant Operations Cockpit",
  as_of: "2026-06-21T16:30:00+02:00",
  routing_status: "watch",
  metrics: [
    {
      label: "Route Decisions",
      value: "4",
      detail: "Synthetic route decisions observed for governed demo agents",
      status: "ready",
    },
    {
      label: "External Egress",
      value: "1 blocked",
      detail: "No public demo route sends operational data outside the tenant boundary",
      status: "ready",
    },
    {
      label: "Estimated Spend",
      value: "EUR 0.76",
      detail: "Synthetic token-cost estimate for the visible demo routes",
      status: "watch",
    },
    {
      label: "Coverage",
      value: "4 agents",
      detail: "Every registered demo agent has a visible routing posture",
      status: "ready",
    },
  ],
  filter_options: {
    domains: ["Maintenance", "Operations", "Quality", "Supply"],
    providers: ["eu-approved-provider", "external-general-llm", "local-vllm"],
    model_policies: ["local-or-approved-provider", "no-external-egress"],
    egress_decisions: ["approved_private_endpoint", "blocked_by_default", "local_allowed"],
    statuses: ["ready", "watch"],
  },
  provider_options: [
    {
      provider_id: "local-vllm",
      display_name: "Local vLLM Gateway",
      provider_type: "self-hosted",
      hosting_boundary: "tenant-private-runtime",
      status: "available",
      egress_mode: "no-external-egress",
      cost_basis: "infrastructure-metered",
      allowed_policies: ["local-or-approved-provider", "no-external-egress"],
      notes: [
        "Default route for sensitive operational prompts.",
        "Runs inside the tenant-controlled runtime boundary.",
      ],
    },
    {
      provider_id: "eu-approved-provider",
      display_name: "EU Approved Provider",
      provider_type: "managed-private-endpoint",
      hosting_boundary: "eu-region-approved-boundary",
      status: "policy_gated",
      egress_mode: "approved-private-endpoint",
      cost_basis: "token-metered",
      allowed_policies: ["local-or-approved-provider"],
      notes: [
        "Allowed only when tenant policy enables the approved endpoint.",
        "No public internet model route is implied by this demo seed.",
      ],
    },
    {
      provider_id: "external-general-llm",
      display_name: "External General LLM",
      provider_type: "external",
      hosting_boundary: "outside-tenant-boundary",
      status: "blocked_by_default",
      egress_mode: "external-egress",
      cost_basis: "not-executed",
      allowed_policies: ["explicit-exception-required"],
      notes: [
        "Shown to make blocked egress observable.",
        "The public demo never sends prompt or operational data to this route.",
      ],
    },
  ],
  routes: [
    {
      route_id: "route_daily_brief_local",
      agent_id: "agent_daily_brief",
      agent_name: "Daily Brief Agent",
      domain: "Operations",
      provider_id: "local-vllm",
      provider_name: "Local vLLM Gateway",
      model: "axis-local-brief-7b",
      model_policy: "local-or-approved-provider",
      prompt_classification: "operational-summary",
      data_boundary: "tenant-private-runtime",
      external_egress_requested: false,
      external_egress_allowed: false,
      egress_decision: "local_allowed",
      decision_reason: "Local provider satisfies the tenant model policy.",
      route_status: "ready",
      input_tokens: 1860,
      output_tokens: 420,
      estimated_cost_eur: 0.18,
      latency_ms: 840,
      cost_center: "plant-operations",
      required_permissions: ["agents:read", "audit:read", "workflows:read"],
      evidence_refs: ["wf_supplier_delay_review", "audit_20260621_154000_ontology_read"],
      audit_event_id: "audit_20260621_model_route_daily_brief",
      observability_events: [
        "model.route.selected",
        "model.tokens.estimated",
        "model.cost.estimated",
      ],
    },
    {
      route_id: "route_supply_risk_local",
      agent_id: "agent_supply_risk",
      agent_name: "Supply Risk Agent",
      domain: "Supply",
      provider_id: "local-vllm",
      provider_name: "Local vLLM Gateway",
      model: "axis-local-risk-13b",
      model_policy: "no-external-egress",
      prompt_classification: "supplier-risk-evidence",
      data_boundary: "tenant-private-runtime",
      external_egress_requested: false,
      external_egress_allowed: false,
      egress_decision: "local_allowed",
      decision_reason: "Supply evidence remains inside the tenant boundary.",
      route_status: "ready",
      input_tokens: 2440,
      output_tokens: 610,
      estimated_cost_eur: 0.27,
      latency_ms: 1160,
      cost_center: "supply",
      required_permissions: ["agents:read", "supply:read"],
      evidence_refs: ["risk_supplier_delay", "asset_motors_batch"],
      audit_event_id: "audit_20260621_model_route_supply_risk",
      observability_events: [
        "model.route.selected",
        "model.policy.evaluated",
        "model.cost.estimated",
      ],
    },
    {
      route_id: "route_quality_external_blocked",
      agent_id: "agent_quality_risk",
      agent_name: "Quality Risk Agent",
      domain: "Quality",
      provider_id: "external-general-llm",
      provider_name: "External General LLM",
      model: "external-quality-general",
      model_policy: "no-external-egress",
      prompt_classification: "quality-evidence",
      data_boundary: "outside-tenant-boundary",
      external_egress_requested: true,
      external_egress_allowed: false,
      egress_decision: "blocked_by_default",
      decision_reason: "Tenant policy blocks external model egress for quality evidence.",
      route_status: "ready",
      input_tokens: 0,
      output_tokens: 0,
      estimated_cost_eur: 0,
      latency_ms: 18,
      cost_center: "quality",
      required_permissions: ["agents:read", "quality:read", "security:read"],
      evidence_refs: ["policy_external_egress", "audit_20260621_133900_egress_blocked"],
      audit_event_id: "audit_20260621_133900_egress_blocked",
      observability_events: [
        "model.policy.evaluated",
        "model.egress.blocked",
        "audit.event.recorded",
      ],
    },
    {
      route_id: "route_maintenance_approved_private",
      agent_id: "agent_maintenance_planner",
      agent_name: "Maintenance Planner Agent",
      domain: "Maintenance",
      provider_id: "eu-approved-provider",
      provider_name: "EU Approved Provider",
      model: "eu-operation-copilot",
      model_policy: "local-or-approved-provider",
      prompt_classification: "maintenance-schedule-summary",
      data_boundary: "eu-region-approved-boundary",
      external_egress_requested: false,
      external_egress_allowed: false,
      egress_decision: "approved_private_endpoint",
      decision_reason: "Tenant policy allows this approved private endpoint path.",
      route_status: "watch",
      input_tokens: 1980,
      output_tokens: 530,
      estimated_cost_eur: 0.31,
      latency_ms: 920,
      cost_center: "maintenance",
      required_permissions: ["agents:read", "maintenance:read"],
      evidence_refs: ["risk_maintenance_window", "asset_press_4"],
      audit_event_id: "audit_20260621_model_route_maintenance",
      observability_events: [
        "model.route.selected",
        "model.provider.policy_gated",
        "model.cost.estimated",
      ],
    },
  ],
  budget_notes: [
    "Cost values are synthetic observability estimates, not product pricing.",
    "Production budgets must be tenant-scoped and enforced before route execution.",
    "Blocked routes keep token and cost counters at zero because no prompt is sent.",
    "Provider-specific billing adapters remain Platform work.",
  ],
  observability_notes: [
    "The seed models route selection, policy evaluation, token estimates and audit refs.",
    "OpenTelemetry spans, persisted usage records and live provider meters remain Platform work.",
    "External model egress is blocked by default unless tenant policy explicitly enables it.",
  ],
};

export function formatModelRoutingLabel(value: string): string {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replaceAll(":", " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

export function filterModelRoutes(
  routing: ManufacturingModelRouting,
  filters: ModelRoutingFilters,
): ModelRouteTelemetry[] {
  return routing.routes.filter((route) => {
    const domainMatches =
      filters.domain === allModelRoutingFilter || route.domain === filters.domain;
    const providerMatches =
      filters.provider === allModelRoutingFilter || route.provider_id === filters.provider;
    const decisionMatches =
      filters.decision === allModelRoutingFilter || route.egress_decision === filters.decision;

    return domainMatches && providerMatches && decisionMatches;
  });
}

export function findModelRouteById(
  routing: ManufacturingModelRouting,
  routeId: string,
): ModelRouteTelemetry {
  return routing.routes.find((route) => route.route_id === routeId) ?? routing.routes[0];
}

export function countBlockedModelRoutes(routing: ManufacturingModelRouting): number {
  return routing.routes.filter((route) => route.egress_decision === "blocked_by_default").length;
}

export function sumEstimatedModelCost(routing: ManufacturingModelRouting): number {
  return routing.routes.reduce((total, route) => total + route.estimated_cost_eur, 0);
}

export function formatEuroCost(value: number): string {
  return `EUR ${value.toFixed(2)}`;
}
