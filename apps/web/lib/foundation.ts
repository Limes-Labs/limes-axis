export type FoundationStatus = "ready" | "guarded" | "planned";

/**
 * Limes Axis brand tokens (2026-07 redesign). Single source of truth for the
 * palette outside CSS — `app/globals.css` defines the same values as channel
 * custom properties and `lib/brand-system.test.ts` cross-checks the two.
 */
export const brandTokens = {
  /** Signal Blue — the only accent color. */
  signal: "#2f64ff",
  signalChannels: "47 100 255",
  /** Midnight Navy — ink on light, world background on dark. */
  navy: "#04122e",
  navyChannels: "4 18 46",
  /** Cloud White — light theme background. */
  cloud: "#f7f8fb",
  cloudChannels: "247 248 251",
  /** Mist Gray — hairlines and borders. */
  mist: "#d9dee8",
  mistChannels: "217 222 232",
  /** Slate Gray — muted copy. */
  slate: "#6e7a94",
  slateChannels: "110 122 148",
  /** Signal tints for fills and active states (light theme). */
  tint50: "#f3f6ff",
  tint100: "#eef3ff",
  tint200: "#dce6ff",
  /** Dark theme semantic channels — a navy world, not black. */
  dark: {
    bgChannels: "4 18 46",
    surfaceChannels: "9 26 58",
    inkChannels: "237 241 248",
    lineChannels: "34 52 88",
    mutedChannels: "158 172 200",
  },
} as const;

export type NavigationItem = {
  href: string;
  label: string;
  icon:
    | "gauge"
    | "network"
    | "workflow"
    | "bot"
    | "shield"
    | "scroll"
    | "receipt"
    | "cable"
    | "building"
    | "settings";
};

export type FoundationMetric = {
  label: string;
  value: string;
  detail: string;
  status: FoundationStatus;
};

export type OntologyPrimitive = {
  label: string;
  role: string;
  status: FoundationStatus;
};

export type WorkflowCheck = {
  label: string;
  runtime: string;
  status: FoundationStatus;
};

export type AutonomyLevel = {
  level: "L0" | "L1" | "L2" | "L3" | "L4";
  label: string;
  approval: string;
};

export type AuditEvent = {
  event: string;
  actor: string;
  scope: string;
  result: string;
};

export const navigationItems: NavigationItem[] = [
  { href: "/", label: "Operations", icon: "gauge" },
  { href: "/ontology", label: "Ontology", icon: "network" },
  { href: "/workflows", label: "Workflows", icon: "workflow" },
  { href: "/agents", label: "Agents", icon: "bot" },
  { href: "/model-routing", label: "Models", icon: "gauge" },
  { href: "/approvals", label: "Approvals", icon: "shield" },
  { href: "/policies", label: "Policies", icon: "scroll" },
  { href: "/audit", label: "Audit", icon: "receipt" },
  { href: "/simulation", label: "Simulation", icon: "workflow" },
  { href: "/connectors", label: "Connectors", icon: "cable" },
  { href: "/tenants", label: "Tenants", icon: "building" },
  { href: "/settings", label: "Settings", icon: "settings" },
];

export const foundationMetrics: FoundationMetric[] = [
  {
    label: "Runtime",
    value: "Self-hosted",
    detail: "Postgres, TypeDB, Temporal, MinIO, Keycloak",
    status: "ready",
  },
  {
    label: "Egress",
    value: "Closed",
    detail: "External providers blocked by default",
    status: "guarded",
  },
  {
    label: "Tenancy",
    value: "Tiered",
    detail: "SaaS, managed single-tenant, on-prem",
    status: "ready",
  },
  {
    label: "Expansion",
    value: "Mandatory",
    detail: "Cloud, Enterprise, SDK, connectors, deploy, docs",
    status: "planned",
  },
];

export const ontologyPrimitives: OntologyPrimitive[] = [
  { label: "Actor", role: "Human, agent, service account", status: "ready" },
  { label: "Organization", role: "Tenant and operating unit boundary", status: "ready" },
  { label: "Asset", role: "Physical or digital operational object", status: "ready" },
  { label: "Process", role: "Operational procedure or business flow", status: "ready" },
  { label: "Workflow", role: "Temporal-backed orchestration instance", status: "ready" },
  { label: "Operation", role: "Typed action with risk and approval metadata", status: "ready" },
  { label: "Policy", role: "Permission, approval, and governance rule", status: "guarded" },
  { label: "Audit Event", role: "Append-only operational evidence", status: "guarded" },
];

export const workflowChecks: WorkflowCheck[] = [
  { label: "Workflow runtime port", runtime: "Axis adapter boundary", status: "ready" },
  { label: "Temporal adapter", runtime: "Self-hosted namespace", status: "ready" },
  { label: "Approval workflow", runtime: "Signal-driven approval", status: "ready" },
  { label: "Worker deployment", runtime: "Container packaging track", status: "planned" },
];

export const autonomyLevels: AutonomyLevel[] = [
  { level: "L0", label: "Observe", approval: "No action execution" },
  { level: "L1", label: "Suggest", approval: "Human executes" },
  { level: "L2", label: "Draft", approval: "Human approves action payload" },
  { level: "L3", label: "Execute guarded", approval: "Policy and approval gate" },
  { level: "L4", label: "Autonomous bounded", approval: "Continuous policy enforcement" },
];

export const auditEvents: AuditEvent[] = [
  {
    event: "tenant.created",
    actor: "system:foundation",
    scope: "tenant_demo",
    result: "recorded",
  },
  {
    event: "operation.blocked",
    actor: "model-router",
    scope: "external-egress",
    result: "guarded",
  },
  {
    event: "approval.signaled",
    actor: "workflow-runtime",
    scope: "approval_workflow",
    result: "recorded",
  },
];

export function statusLabel(status: FoundationStatus): string {
  return status === "ready" ? "Ready" : status === "guarded" ? "Guarded" : "Planned";
}
