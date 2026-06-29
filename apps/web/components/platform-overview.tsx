"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Bot,
  ClipboardCheck,
  FileCheck2,
  GitBranch,
  Play,
  RefreshCw,
  ShieldCheck,
  Workflow,
} from "lucide-react";

import { ApiRequiredState } from "@/components/api-required-state";
import { ConsoleTopbar } from "@/components/console-topbar";
import { axisFetchJson } from "@/lib/axis-api";
import {
  countBlockedModelRoutes,
  formatEuroCost,
  formatModelRoutingLabel,
  sumEstimatedModelCost,
  type ManufacturingModelRouting,
  type ModelRouteTelemetry,
} from "@/lib/model-routing-demo";
import {
  formatOverviewTimestamp,
  getDemoReadinessCounts,
  getDemoReadinessPriorityStatus,
  getOperationsSnapshotStatus,
  getPersistedArtifactCount,
  platformStatusClass,
  platformStatusLabel,
  sortDomainSnapshotsByOperationalPriority,
  type ManufacturingDemoReadinessCheck,
  type ManufacturingDemoReadinessReport,
  type ManufacturingDomainSnapshot,
  type ManufacturingOverview,
  type ManufacturingOperationsSnapshot,
  type OverviewMetric,
  type PlatformStatus,
} from "@/lib/platform-overview";
import { useConsole } from "@/providers/console-provider";

type OverviewSource = "loading" | "api" | "unavailable";

type HealthSignal = {
  label: string;
  status: PlatformStatus;
};

type StatusKpi = {
  label: string;
  value: string;
  detail: string;
  status: PlatformStatus;
  icon: typeof ShieldCheck;
};

function sourceLabel(source: OverviewSource): string {
  if (source === "api") {
    return "Live API";
  }

  return source === "loading" ? "Loading API" : "API unavailable";
}

function normalizeLabel(value: string): string {
  return value
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

function compactPolicyLabel(value: string): string {
  return normalizeLabel(value)
    .replace("Local Or Approved Provider", "Local approved")
    .replace("No External Egress", "No external egress");
}

function compactWorkflowName(value: string): string {
  return normalizeLabel(value).replace(" Review", "").replace(" Reschedule", "");
}

function compactAgentStatus(value: string): string {
  return normalizeLabel(value)
    .replace("Drafting Actions", "Drafting")
    .replace("Waiting For Approval", "Waiting review");
}

function compactConnectorEvent(value: string): string {
  return normalizeLabel(value.replace("connector.", ""))
    .replace("Evidence Invariant Snapshots Exported", "Evidence export")
    .replace("Evidence Invariant Snapshots Read", "Snapshot read")
    .replace("Evidence Invariants Read", "Evidence read")
    .replace("Run Sync Checkpoint Claims Read", "Checkpoint claims")
    .replace("Run Sync Checkpoints Read", "Sync checkpoints")
    .replace("Credential Leases Read", "Credential leases")
    .replace("Egress Policies Read", "Egress policies");
}

function shortTime(value: string): string {
  return new Intl.DateTimeFormat("en", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function metricByLabel(overview: ManufacturingOverview, label: string): OverviewMetric | null {
  return overview.metrics.find((metric) => metric.label === label) ?? null;
}

function readinessCheckById(
  report: ManufacturingDemoReadinessReport,
  checkId: string,
): ManufacturingDemoReadinessCheck | null {
  return report.checks.find((check) => check.check_id === checkId) ?? null;
}

function statusScore(status: PlatformStatus): number {
  if (status === "ready") {
    return 0.92;
  }

  return status === "watch" ? 0.68 : 0.46;
}

function radarPoint(index: number, total: number, status: PlatformStatus): string {
  const center = 54;
  const radius = 41 * statusScore(status);
  const angle = -Math.PI / 2 + (Math.PI * 2 * index) / total;

  return `${(center + Math.cos(angle) * radius).toFixed(1)},${(
    center + Math.sin(angle) * radius
  ).toFixed(1)}`;
}

function connectionEvents(snapshot: ManufacturingOperationsSnapshot): number {
  return snapshot.recent_audit_events.filter((event) => event.event_type.startsWith("connector."))
    .length;
}

function routeDecisionClass(route: ModelRouteTelemetry): string {
  return route.route_status === "ready" && !route.external_egress_allowed
    ? "signal-ready"
    : platformStatusClass(route.route_status);
}

function StatusPill({ status }: { status: PlatformStatus }) {
  return <span className={`status-pill ${platformStatusClass(status)}`}>{platformStatusLabel(status)}</span>;
}

function StatusDot({ status }: { status: PlatformStatus }) {
  return <span aria-hidden="true" className={`status-dot ${platformStatusClass(status)}`} />;
}

function TopKpis({
  demoReadiness,
  overview,
  operationsSnapshot,
}: {
  demoReadiness: ManufacturingDemoReadinessReport;
  overview: ManufacturingOverview;
  operationsSnapshot: ManufacturingOperationsSnapshot;
}) {
  const workflowMetric = metricByLabel(overview, "Workflow Load");
  const approvalsMetric = metricByLabel(overview, "Approvals");
  const agentsMetric = metricByLabel(overview, "Agents");
  const auditMetric = metricByLabel(overview, "Audit");
  const snapshotStatus = getOperationsSnapshotStatus(operationsSnapshot);
  const systemStatus =
    snapshotStatus === "action_required" || demoReadiness.readiness_status === "action_required"
      ? "watch"
      : demoReadiness.readiness_status;

  const kpis: StatusKpi[] = [
    {
      label: "System status",
      value: systemStatus === "ready" ? "Operational" : "Operational watch",
      detail:
        systemStatus === "ready"
          ? "All required demo evidence is present"
          : "Production hardening limits remain explicit",
      status: systemStatus,
      icon: ShieldCheck,
    },
    {
      label: "Workflows",
      value: workflowMetric?.value ?? `${overview.workflows.length} tracked`,
      detail: workflowMetric?.detail ?? "Workflow records from the API",
      status: workflowMetric?.status ?? "watch",
      icon: Workflow,
    },
    {
      label: "Approvals",
      value: approvalsMetric?.value ?? `${overview.approvals.length} pending`,
      detail: approvalsMetric?.detail ?? "Human decision gates from the API",
      status: approvalsMetric?.status ?? "watch",
      icon: ClipboardCheck,
    },
    {
      label: "Agents",
      value: agentsMetric?.value ?? `${overview.agents.length} governed`,
      detail: agentsMetric?.detail ?? "Governed autonomy records",
      status: agentsMetric?.status ?? "ready",
      icon: Bot,
    },
    {
      label: "Audit events",
      value: auditMetric?.value ?? `${operationsSnapshot.recent_audit_events.length} recent`,
      detail: auditMetric?.detail ?? "Append-only evidence stream",
      status: auditMetric?.status ?? "ready",
      icon: FileCheck2,
    },
  ];

  return (
    <div className="ops-kpi-grid" aria-label="Operations status metrics">
      {kpis.map((kpi) => {
        const Icon = kpi.icon;

        return (
          <article className="ops-kpi-card" key={kpi.label}>
            <Icon size={32} strokeWidth={1.5} />
            <div>
              <p className="section-label">{kpi.label}</p>
              <p className={`ops-kpi-value ${platformStatusClass(kpi.status)}`}>{kpi.value}</p>
              <p className="row-detail">{kpi.detail}</p>
            </div>
          </article>
        );
      })}
    </div>
  );
}

function OntologyMap({ domains }: { domains: ManufacturingDomainSnapshot[] }) {
  const sortedDomains = sortDomainSnapshotsByOperationalPriority(domains).slice(0, 6);

  return (
    <section className="ops-panel ops-ontology-card">
      <div className="ops-panel-header">
        <div>
          <p className="section-label">Operational ontology</p>
          <h2 className="ops-panel-title">Domain graph</h2>
        </div>
      </div>
      <div className="ontology-map" aria-label="Operational ontology graph">
        <div className="ontology-center">Axis</div>
        {sortedDomains.map((domain, index) => (
          <div className={`ontology-node ontology-node-${index + 1}`} key={domain.domain}>
            <span className="ontology-node-dot" />
            {domain.domain}
          </div>
        ))}
        <div className="ontology-legend" aria-label="Ontology legend">
          <span>
            <span className="legend-dot entity" /> Entity
          </span>
          <span>
            <span className="legend-line" /> Relation
          </span>
          <span>
            <span className="legend-dot attribute" /> Attribute
          </span>
        </div>
      </div>
      <Link className="ops-panel-link" href="/ontology">
        Explore ontology
        <span aria-hidden="true">-&gt;</span>
      </Link>
    </section>
  );
}

function WorkflowOrchestration({ overview }: { overview: ManufacturingOverview }) {
  return (
    <section className="ops-panel ops-workflow-card">
      <div className="ops-panel-header">
        <div>
          <p className="section-label">Workflow orchestration</p>
          <h2 className="ops-panel-title">Human-gated flow</h2>
        </div>
      </div>
      <div className="workflow-pipeline" aria-label="Workflow pipeline">
        {overview.workflows.slice(0, 3).map((workflow, index) => (
          <div className="pipeline-step" key={workflow.workflow_id}>
            <span className="pipeline-step-index mono">{index + 1}</span>
            <div>
              <p className="row-title">{compactWorkflowName(workflow.name)}</p>
              <p className="row-detail">{normalizeLabel(workflow.state)}</p>
            </div>
          </div>
        ))}
        <div className="pipeline-step pipeline-step-approval">
          <ShieldCheck size={17} />
          <div>
            <p className="row-title">Approval gate</p>
            <p className="row-detail">{overview.approvals.length} requests</p>
          </div>
        </div>
      </div>
      <div className="ops-panel-metrics">
        <span>
          <strong>{overview.workflows.length}</strong>
          active executions
        </span>
        <span>
          <strong>{overview.approvals.length}</strong>
          pending review
        </span>
      </div>
      <Link className="ops-panel-link" href="/workflows">
        Open workflows
        <span aria-hidden="true">-&gt;</span>
      </Link>
    </section>
  );
}

function AgentControl({ overview }: { overview: ManufacturingOverview }) {
  return (
    <section className="ops-panel">
      <div className="ops-panel-header">
        <div>
          <p className="section-label">Agent control</p>
          <h2 className="ops-panel-title">Governed autonomy</h2>
        </div>
        <span className="section-label">Status</span>
      </div>
      <div className="ops-list">
        {overview.agents.map((agent) => (
          <div className="ops-list-row" key={agent.agent_id}>
            <Bot size={18} />
            <div>
              <p className="row-title">{agent.name}</p>
              <p className="row-detail ops-agent-policy">
                {agent.autonomy_level} / {compactPolicyLabel(agent.model_policy)}
              </p>
            </div>
            <span className={`ops-live-status ${agent.status.includes("waiting") ? "signal-watch" : "signal-ready"}`}>
              {compactAgentStatus(agent.status)}
              <StatusDot status={agent.status.includes("waiting") ? "watch" : "ready"} />
            </span>
          </div>
        ))}
      </div>
      <Link className="ops-panel-link" href="/agents">
        Manage agents
        <span aria-hidden="true">-&gt;</span>
      </Link>
    </section>
  );
}

function ConnectorEvidence({ snapshot }: { snapshot: ManufacturingOperationsSnapshot }) {
  const connectorEvents = snapshot.recent_audit_events
    .filter((event) => event.event_type.startsWith("connector."))
    .slice(0, 5);

  return (
    <section className="ops-panel">
      <p className="section-label">Connectors</p>
      <h2 className="ops-panel-title">Evidence stream</h2>
      <div className="ops-table" role="table" aria-label="Connector evidence events">
        <div className="ops-table-row ops-table-head" role="row">
          <span>Name</span>
          <span>Type</span>
          <span>Status</span>
          <span>Last sync</span>
        </div>
        {connectorEvents.map((event) => (
          <div className="ops-table-row" role="row" key={`${event.event_type}-${event.created_at}`}>
            <span>{compactConnectorEvent(event.event_type)}</span>
            <span>Audit</span>
            <span className="signal-ready">Recorded</span>
            <span className="mono">{shortTime(event.created_at)}</span>
          </div>
        ))}
      </div>
      <Link className="ops-panel-link" href="/connectors">
        Manage connectors
        <span aria-hidden="true">-&gt;</span>
      </Link>
    </section>
  );
}

function ApprovalQueue({ overview }: { overview: ManufacturingOverview }) {
  return (
    <section className="ops-panel">
      <p className="section-label">Approvals</p>
      <h2 className="ops-panel-title">Pending decisions</h2>
      <div className="ops-table" role="table" aria-label="Approval requests">
        <div className="ops-table-row ops-table-head" role="row">
          <span>Request</span>
          <span>Requested by</span>
          <span>Type</span>
          <span>Due</span>
        </div>
        {overview.approvals.map((approval) => (
          <div className="ops-table-row" role="row" key={approval.approval_id}>
            <span>{approval.action}</span>
            <span>{normalizeLabel(approval.requested_by)}</span>
            <span>{normalizeLabel(approval.risk_level)}</span>
            <span>{approval.due}</span>
          </div>
        ))}
      </div>
      <Link className="ops-panel-link" href="/approvals">
        Review approvals
        <span aria-hidden="true">-&gt;</span>
      </Link>
    </section>
  );
}

function AuditObservability({ snapshot }: { snapshot: ManufacturingOperationsSnapshot }) {
  const events = snapshot.recent_audit_events.slice(0, 8).reverse();
  const points = events
    .map((event, index) => {
      const payloadWeight = Object.values(event.payload_refs).filter(Boolean).length;
      const x = 18 + index * 38;
      const y = 78 - Math.min(58, 12 + payloadWeight * 12 + index * 3);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <section className="ops-panel">
      <p className="section-label">Audit observability</p>
      <h2 className="ops-panel-title">Recent evidence</h2>
      <svg className="audit-chart" viewBox="0 0 300 96" role="img" aria-label="Recent audit evidence chart">
        <defs>
          <pattern id="audit-grid" width="20" height="16" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 16" fill="none" stroke="rgba(220,226,234,.10)" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="300" height="96" fill="url(#audit-grid)" />
        <polyline points={points} fill="none" stroke="var(--signal-blue)" strokeWidth="2" />
        {points.split(" ").map((point) => {
          const [cx, cy] = point.split(",");

          return <circle cx={cx} cy={cy} fill="var(--signal-blue)" key={point} r="3" />;
        })}
      </svg>
      <div className="ops-panel-metrics">
        <span>
          <strong>{snapshot.recent_audit_events.length}</strong>
          recent events
        </span>
        <span>
          <strong>{getPersistedArtifactCount(snapshot)}</strong>
          governed artifacts
        </span>
        <span>
          <strong>{connectionEvents(snapshot)}</strong>
          connector events
        </span>
      </div>
      <Link className="ops-panel-link" href="/audit">
        Open audit
        <span aria-hidden="true">-&gt;</span>
      </Link>
    </section>
  );
}

function SystemHealth({
  demoReadiness,
  modelRouting,
  operationsSnapshot,
  overview,
}: {
  demoReadiness: ManufacturingDemoReadinessReport;
  modelRouting: ManufacturingModelRouting;
  operationsSnapshot: ManufacturingOperationsSnapshot;
  overview: ManufacturingOverview;
}) {
  const workflowMetric = metricByLabel(overview, "Workflow Load");
  const agentsMetric = metricByLabel(overview, "Agents");
  const healthSignals: HealthSignal[] = [
    {
      label: "Policies",
      status: readinessCheckById(demoReadiness, "human_approval_gates")?.status ?? "watch",
    },
    { label: "Security", status: getDemoReadinessPriorityStatus(demoReadiness) },
    { label: "Data", status: operationsSnapshot.metrics.every((metric) => metric.status === "ready") ? "ready" : "watch" },
    { label: "Workflows", status: workflowMetric?.status ?? "watch" },
    { label: "Agents", status: agentsMetric?.status ?? "ready" },
    { label: "Connectors", status: connectionEvents(operationsSnapshot) > 0 ? "ready" : "watch" },
  ];
  const polygon = healthSignals
    .map((signal, index) => radarPoint(index, healthSignals.length, signal.status))
    .join(" ");
  const baseline = healthSignals
    .map((_, index) => radarPoint(index, healthSignals.length, "watch"))
    .join(" ");

  return (
    <section className="ops-panel side-panel">
      <h2 className="section-label">System health</h2>
      <svg className="radar-chart" viewBox="0 0 108 108" role="img" aria-label="System health radar">
        {[18, 30, 42].map((radius) => (
          <circle cx="54" cy="54" fill="none" key={radius} r={radius} stroke="rgba(220,226,234,.14)" />
        ))}
        {healthSignals.map((signal, index) => {
          const point = radarPoint(index, healthSignals.length, "ready");
          const [x, y] = point.split(",");

          return (
            <line
              key={signal.label}
              x1="54"
              y1="54"
              x2={x}
              y2={y}
              stroke="rgba(220,226,234,.12)"
            />
          );
        })}
        <polygon points={baseline} fill="none" stroke="rgba(220,226,234,.35)" strokeDasharray="2 3" />
        <polygon points={polygon} fill="rgba(62,107,255,.18)" stroke="var(--signal-blue)" strokeWidth="2" />
      </svg>
      <div className="radar-labels">
        {healthSignals.map((signal) => (
          <span key={signal.label}>
            <StatusDot status={signal.status} />
            {signal.label}
          </span>
        ))}
      </div>
      <p className="row-detail">
        Routing posture: {platformStatusLabel(modelRouting.routing_status)} /{" "}
        {countBlockedModelRoutes(modelRouting)} blocked route
      </p>
    </section>
  );
}

function RiskSignals({ overview }: { overview: ManufacturingOverview }) {
  return (
    <section className="ops-panel side-panel">
      <div className="ops-panel-header">
        <p className="section-label">Risk signals</p>
        <Link className="side-link" href="/audit">
          View all
        </Link>
      </div>
      <div className="side-list">
        {overview.risk_signals.map((signal) => (
          <div className="side-list-row" key={signal.title}>
            <AlertTriangle
              className={platformStatusClass(signal.severity)}
              size={21}
              strokeWidth={1.8}
            />
            <div>
              <p className="row-title">{signal.title}</p>
              <p className="row-detail">{signal.evidence}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function RecentActivity({ snapshot }: { snapshot: ManufacturingOperationsSnapshot }) {
  return (
    <section className="ops-panel side-panel">
      <div className="ops-panel-header">
        <p className="section-label">Recent activity</p>
        <Link className="side-link" href="/audit">
          View all
        </Link>
      </div>
      <div className="side-list">
        {snapshot.recent_audit_events.slice(0, 5).map((event) => (
          <div className="activity-row" key={`${event.event_type}-${event.created_at}`}>
            <StatusDot status="ready" />
            <div>
              <p className="row-title">{normalizeLabel(event.event_type)}</p>
              <p className="row-detail">{normalizeLabel(event.actor_id)}</p>
            </div>
            <span className="mono">{shortTime(event.created_at)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function QuickActions() {
  const actions = [
    { label: "New workflow", href: "/workflows", icon: GitBranch },
    { label: "Deploy agent", href: "/agents", icon: Bot },
    { label: "Create policy", href: "/approvals", icon: ShieldCheck },
    { label: "Run simulation", href: "/simulation", icon: Play },
  ];

  return (
    <section className="ops-panel side-panel">
      <p className="section-label">Quick actions</p>
      <div className="quick-action-grid">
        {actions.map((action) => {
          const Icon = action.icon;

          return (
            <Link className="quick-action" href={action.href} key={action.label}>
              <Icon size={17} />
              {action.label}
            </Link>
          );
        })}
      </div>
    </section>
  );
}

function ModelRoutingStrip({ routing }: { routing: ManufacturingModelRouting }) {
  const primaryRoute = routing.routes[0];
  const blockedRoutes = countBlockedModelRoutes(routing);
  const totalCost = sumEstimatedModelCost(routing);

  return (
    <section className="ops-panel model-strip">
      <div className="ops-panel-header">
        <div>
          <p className="section-label">Model routing</p>
          <h2 className="ops-panel-title">Persisted routing posture</h2>
        </div>
        <Link className="side-link" href="/model-routing">
          View routing
        </Link>
      </div>
      <div className="model-strip-flow" aria-label="Model routing decision flow">
        <div className="model-strip-node">
          <p className="section-label">Request</p>
          <p className="row-title">{primaryRoute.prompt_classification}</p>
          <p className="row-detail">Source: {primaryRoute.agent_name}</p>
        </div>
        <div className="model-flow-arrow" aria-hidden="true">
          -&gt;
        </div>
        <div className="model-strip-node">
          <p className="section-label">Routing decision</p>
          <p className="row-title">{primaryRoute.model}</p>
          <p className="row-detail">{primaryRoute.data_boundary}</p>
        </div>
        <div className="model-flow-arrow" aria-hidden="true">
          -&gt;
        </div>
        <div className="model-strip-node">
          <p className="section-label">Execution</p>
          <p className={`row-title ${routeDecisionClass(primaryRoute)}`}>
            {formatModelRoutingLabel(primaryRoute.egress_decision)}
          </p>
          <p className="row-detail">Latency: {primaryRoute.latency_ms} ms</p>
        </div>
        <div className="model-flow-arrow" aria-hidden="true">
          -&gt;
        </div>
        <div className="model-strip-node model-strip-node-compact">
          <p className="section-label">Response</p>
          <p className="row-title">{formatEuroCost(totalCost)}</p>
          <p className="row-detail">{blockedRoutes} blocked route</p>
        </div>
      </div>
    </section>
  );
}

export function PlatformOverview() {
  const [overview, setOverview] = useState<ManufacturingOverview | null>(null);
  const [operationsSnapshot, setOperationsSnapshot] =
    useState<ManufacturingOperationsSnapshot | null>(null);
  const [demoReadiness, setDemoReadiness] = useState<ManufacturingDemoReadinessReport | null>(
    null,
  );
  const [modelRouting, setModelRouting] = useState<ManufacturingModelRouting | null>(null);
  const [source, setSource] = useState<OverviewSource>("loading");
  const { refreshNonce, triggerRefresh } = useConsole();

  useEffect(() => {
    const controller = new AbortController();

    async function fetchOverview() {
      setSource("loading");

      try {
        const [
          overviewPayload,
          operationsSnapshotPayload,
          demoReadinessPayload,
          modelRoutingPayload,
        ] = await Promise.all([
          axisFetchJson<ManufacturingOverview>("/demo/manufacturing/overview", {
            signal: controller.signal,
          }),
          axisFetchJson<ManufacturingOperationsSnapshot>(
            "/demo/manufacturing/operations/snapshot",
            { signal: controller.signal },
          ),
          axisFetchJson<ManufacturingDemoReadinessReport>("/demo/manufacturing/demo-readiness", {
            signal: controller.signal,
          }),
          axisFetchJson<ManufacturingModelRouting>("/demo/manufacturing/model-routing", {
            signal: controller.signal,
          }),
        ]);

        setOverview(overviewPayload);
        setOperationsSnapshot(operationsSnapshotPayload);
        setDemoReadiness(demoReadinessPayload);
        setModelRouting(modelRoutingPayload);
        setSource("api");
      } catch {
        if (!controller.signal.aborted) {
          setOverview(null);
          setOperationsSnapshot(null);
          setDemoReadiness(null);
          setModelRouting(null);
          setSource("unavailable");
        }
      }
    }

    void fetchOverview();

    return () => controller.abort();
  }, [refreshNonce]);

  const readinessCounts = useMemo(
    () =>
      demoReadiness
        ? getDemoReadinessCounts(demoReadiness)
        : { action_required: 0, ready: 0, watch: 0 },
    [demoReadiness],
  );

  if (!overview || !operationsSnapshot || !demoReadiness || !modelRouting) {
    return (
      <div className="ops-console">
        <ConsoleTopbar
          evidenceLabel={source === "api" ? "Evidence present" : "Evidence required"}
          sourceLabel={
            source === "api"
              ? "Live API"
              : source === "loading"
                ? "Loading API"
                : "API unavailable"
          }
        />
        <div className="ops-loading-shell">
          <ApiRequiredState
            detail="Axis did not receive API-backed overview, operations snapshot, demo-readiness and model-routing records. Local fallback overview records are disabled."
            endpoint="/demo/manufacturing/overview + /demo/manufacturing/operations/snapshot + /demo/manufacturing/demo-readiness + /demo/manufacturing/model-routing"
            title={source === "loading" ? "Loading operations API" : "Operations API unavailable"}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="ops-console">
      <ConsoleTopbar
        evidenceLabel={source === "api" ? "Evidence present" : "Evidence required"}
        sourceLabel={source === "api" ? "Live API" : sourceLabel(source)}
      />
      <section className="ops-page-header">
        <div>
          <h1 className="ops-page-title">Operations</h1>
          <p className="ops-page-subtitle">
            {overview.plant_name} / {overview.scenario} / {formatOverviewTimestamp(operationsSnapshot.as_of)}
          </p>
        </div>
        <div className="ops-controls" aria-label="Operations controls">
          <span className="control-chip">Demo tenant</span>
          <span className="control-chip">Latest evidence</span>
          <button
            className="ops-icon-button"
            type="button"
            aria-label="Refresh state"
            title="Refresh state"
            onClick={triggerRefresh}
          >
            <RefreshCw size={17} />
          </button>
        </div>
      </section>

      <div className="ops-dashboard-grid">
        <main className="ops-dashboard-main" aria-label="Operations dashboard">
          <TopKpis
            demoReadiness={demoReadiness}
            operationsSnapshot={operationsSnapshot}
            overview={overview}
          />

          <div className="ops-main-grid">
            <OntologyMap domains={operationsSnapshot.domain_snapshots} />
            <WorkflowOrchestration overview={overview} />
            <AgentControl overview={overview} />
            <ConnectorEvidence snapshot={operationsSnapshot} />
            <ApprovalQueue overview={overview} />
            <AuditObservability snapshot={operationsSnapshot} />
          </div>

          <ModelRoutingStrip routing={modelRouting} />

          <section className="ops-panel readiness-panel" id="readiness">
            <div className="ops-panel-header">
              <div>
                <p className="section-label">Demo readiness</p>
                <h2 className="ops-panel-title">Feedback environment</h2>
              </div>
              <StatusPill status={getDemoReadinessPriorityStatus(demoReadiness)} />
            </div>
            <p className="row-detail">{demoReadiness.summary}</p>
            <div className="readiness-counts">
              <span>
                <strong>{readinessCounts.ready}</strong>
                ready
              </span>
              <span>
                <strong>{readinessCounts.watch}</strong>
                watch
              </span>
              <span>
                <strong>{readinessCounts.action_required}</strong>
                action required
              </span>
            </div>
            <div className="readiness-track-grid">
              {demoReadiness.tracks.map((track) => (
                <div className="readiness-track" key={track.name}>
                  <div>
                    <p className="row-title">{track.name}</p>
                    <p className="row-detail">{track.detail}</p>
                  </div>
                  <StatusPill status={track.status} />
                </div>
              ))}
            </div>
          </section>
        </main>

        <aside className="ops-right-rail" aria-label="Operations side rail">
          <SystemHealth
            demoReadiness={demoReadiness}
            modelRouting={modelRouting}
            operationsSnapshot={operationsSnapshot}
            overview={overview}
          />
          <RiskSignals overview={overview} />
          <RecentActivity snapshot={operationsSnapshot} />
          <QuickActions />
        </aside>
      </div>
    </div>
  );
}
