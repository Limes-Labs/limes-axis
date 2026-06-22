export type FoundationStatus = "ready" | "guarded" | "planned";

export type NavigationItem = {
  href: string;
  label: string;
  icon: "gauge" | "network" | "workflow" | "bot" | "shield" | "receipt";
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
  { href: "/", label: "Overview", icon: "gauge" },
  { href: "/ontology", label: "Ontology", icon: "network" },
  { href: "/workflows", label: "Workflows", icon: "workflow" },
  { href: "/agents", label: "Agents", icon: "bot" },
  { href: "/model-routing", label: "Models", icon: "gauge" },
  { href: "/approvals", label: "Approvals", icon: "shield" },
  { href: "/audit", label: "Audit", icon: "receipt" },
  { href: "/simulation", label: "Simulation", icon: "workflow" },
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
