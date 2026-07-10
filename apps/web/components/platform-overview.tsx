"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowRight,
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
import { AxisMark, AxisMarkGlyph } from "@/components/axis-mark";
import { ConsoleTopbar } from "@/components/console-topbar";
import { Reveal } from "@/components/reveal";
import { PlatformStatusPill } from "@/components/status-pill";
import { Card } from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import { Eyebrow } from "@/components/ui/eyebrow";
import { MetricSparkbar } from "@/components/ui/metric-sparkbar";
import { Skeleton } from "@/components/ui/skeleton";
import { axisFetchJson } from "@/lib/axis-api";
import { cn } from "@/lib/cn";
import { buildOidcAuthorizeUrl } from "@/lib/oidc-session";
import {
  countBlockedModelRoutes,
  formatEuroCost,
  formatModelRoutingLabel,
  sumEstimatedModelCost,
  type ManufacturingModelRouting,
  type ModelRouteTelemetry,
} from "@/lib/model-routing-demo";
import {
  buildOperationsArtifactRequest,
  getOperationsArtifactActionState,
  operationsArtifactHeadline,
  operationsArtifactRecordId,
  OPERATIONS_ARTIFACT_ACTIONS,
  type OperationsArtifactKind,
  type OperationsArtifactResponse,
} from "@/lib/operations-artifacts";
import {
  formatOverviewTimestamp,
  getDemoReadinessCounts,
  getDemoReadinessPriorityStatus,
  getOperationsSnapshotStatus,
  getPersistedArtifactCount,
  platformStatusClass,
  platformStatusLabel,
  sortDomainSnapshotsByOperationalPriority,
  type ManufacturingDemoReadinessReport,
  type ManufacturingDomainSnapshot,
  type IdentitySessionReadModel,
  type ManufacturingOverview,
  type ManufacturingOperationsSnapshot,
  type OverviewMetric,
  type PlatformStatus,
} from "@/lib/platform-overview";
import { useAxisQuery } from "@/lib/use-axis-query";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { useConsole } from "@/providers/console-provider";

type OverviewSource = "loading" | "api" | "unavailable";

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

function domainSnapshotStatus(domain: ManufacturingDomainSnapshot): PlatformStatus {
  if (domain.action_required_count > 0) {
    return "action_required";
  }

  return domain.watch_count > 0 ? "watch" : "ready";
}

function StatusDot({ status }: { status: PlatformStatus }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-block size-2 shrink-0 rounded-full",
        status === "ready" && "bg-positive",
        status === "watch" && "bg-warning",
        status === "action_required" && "bg-danger",
      )}
    />
  );
}

function PanelLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      className="mt-auto inline-flex items-center gap-1.5 pt-1 font-mono text-xs tracking-[0.12em] text-signal uppercase hover:underline"
      href={href}
    >
      {children}
      <ArrowRight aria-hidden="true" size={13} />
    </Link>
  );
}

function PanelHeader({
  eyebrow,
  title,
  aside,
}: {
  eyebrow: string;
  title?: string;
  aside?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="grid gap-1">
        <Eyebrow>{eyebrow}</Eyebrow>
        {title ? <h2 className="font-display m-0 text-lg text-ink">{title}</h2> : null}
      </div>
      {aside}
    </div>
  );
}

function OverviewHero({
  overview,
  operationsSnapshot,
  onRefresh,
}: {
  overview: ManufacturingOverview;
  operationsSnapshot: ManufacturingOperationsSnapshot;
  onRefresh: () => void;
}) {
  return (
    <section className="relative overflow-hidden rounded-3xl border border-navy bg-navy px-6 py-8 text-white sm:px-10 sm:py-10 dark:border-white/10">
      {/* Signal glow + static dot grid, same treatment in both themes. */}
      <div
        aria-hidden="true"
        className="absolute inset-0"
        style={{
          backgroundImage:
            "radial-gradient(ellipse 80% 90% at 50% 110%, rgb(47 100 255 / 0.35) 0%, rgb(47 100 255 / 0.08) 45%, transparent 70%), radial-gradient(rgb(255 255 255 / 0.05) 1px, transparent 1px)",
          backgroundSize: "auto, 22px 22px",
        }}
      />
      <div className="relative z-10 grid gap-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <AxisMark className="h-9 w-9 text-white" />
            <Eyebrow className="text-signal">
              {overview.plant_name} / Governed operations
            </Eyebrow>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-white/20 px-3 py-1 font-mono text-[11px] tracking-[0.12em] text-white/80 uppercase">
              Latest evidence
            </span>
            <button
              aria-label="Refresh state"
              className="inline-flex size-8 items-center justify-center rounded-full border border-white/20 text-white/80 transition-colors hover:border-signal hover:text-white"
              onClick={onRefresh}
              title="Refresh state"
              type="button"
            >
              <RefreshCw size={15} />
            </button>
          </div>
        </div>

        <div className="grid gap-3">
          <h1 className="font-display m-0 max-w-3xl text-4xl text-white sm:text-5xl">
            <span className="text-signal">Operations</span> {overview.scenario}
          </h1>
          <p className="ops-page-subtitle m-0! max-w-2xl text-[15px]! text-white/70!">
            {overview.plant_name} / {overview.scenario} /{" "}
            {formatOverviewTimestamp(operationsSnapshot.as_of)}
          </p>
        </div>

        <div className="flex flex-wrap gap-x-8 gap-y-3">
          {[
            { label: "Workflows", value: overview.workflows.length },
            { label: "Approvals pending", value: overview.approvals.length },
            { label: "Agents governed", value: overview.agents.length },
            { label: "Audit events", value: operationsSnapshot.recent_audit_events.length },
          ].map((fact) => (
            <div className="grid gap-0.5" key={fact.label}>
              <span className="font-display text-2xl text-white">{fact.value}</span>
              <span className="font-mono text-[10.5px] tracking-[0.14em] text-white/60 uppercase">
                {fact.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
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
    <Reveal>
      <div
        aria-label="Operations status metrics"
        className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5"
      >
        {kpis.map((kpi) => {
          const Icon = kpi.icon;

          return (
            <Card className="grid content-start gap-2 p-5" data-kpi-card key={kpi.label}>
              <div className="flex items-start justify-between gap-2">
                <Icon className="text-signal" size={22} strokeWidth={1.6} />
                <StatusDot status={kpi.status} />
              </div>
              <Eyebrow>{kpi.label}</Eyebrow>
              <p className="font-display m-0 text-xl break-words text-ink">{kpi.value}</p>
              <div aria-hidden="true" className="rule-dotted" />
              <p className="m-0 text-xs text-muted">{kpi.detail}</p>
            </Card>
          );
        })}
      </div>
    </Reveal>
  );
}

function DomainSnapshots({ snapshot }: { snapshot: ManufacturingOperationsSnapshot }) {
  const domains = sortDomainSnapshotsByOperationalPriority(snapshot.domain_snapshots);

  return (
    <Reveal>
      <section className="grid gap-4" aria-label="Domain snapshots">
        <PanelHeader eyebrow="Domain snapshots" title="Operational domains" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <Card className="grid content-start gap-3 p-5">
            <Eyebrow>Records by domain</Eyebrow>
            <MetricSparkbar
              caption="Record counts per operational domain from the operations snapshot"
              points={domains.map((domain) => ({
                label: domain.domain,
                value: domain.record_count,
              }))}
            />
            <p className="m-0 text-xs text-muted">
              {domains.reduce((total, domain) => total + domain.record_count, 0)} records across{" "}
              {domains.length} domains
            </p>
          </Card>
          {domains.map((domain) => (
            <Card className="grid content-start gap-3 p-5" key={domain.domain}>
              <div className="flex items-start justify-between gap-2">
                <Eyebrow>{domain.domain}</Eyebrow>
                <PlatformStatusPill status={domainSnapshotStatus(domain)} />
              </div>
              <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                <span className="font-display text-2xl text-ink">{domain.record_count}</span>
                <span className="font-mono text-[10.5px] tracking-[0.14em] text-muted uppercase">
                  records
                </span>
              </div>
              <div aria-hidden="true" className="rule-dotted" />
              <div className="grid grid-cols-3 gap-2 text-xs text-muted">
                <span>
                  <strong className="block text-sm text-ink">{domain.action_required_count}</strong>
                  action
                </span>
                <span>
                  <strong className="block text-sm text-ink">{domain.watch_count}</strong>
                  watch
                </span>
                <span>
                  <strong className="block text-sm text-ink">{domain.workflow_ids.length}</strong>
                  workflows
                </span>
              </div>
              <p className="m-0 font-mono text-[11px] text-muted">
                risk: {domain.highest_risk_level} / {domain.owner_roles.join(", ")}
              </p>
            </Card>
          ))}
        </div>
      </section>
    </Reveal>
  );
}

function OperationsArtifactPanel({
  identitySession,
  identitySessionUnavailable,
  onArtifactCommitted,
  operationsSnapshot,
  session,
}: {
  identitySession: IdentitySessionReadModel | null;
  identitySessionUnavailable: boolean;
  onArtifactCommitted: () => void;
  operationsSnapshot: ManufacturingOperationsSnapshot;
  session: ReturnType<typeof useOidcConsoleSession>["session"];
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { apiBaseUrl } = useConsole();
  const [pendingKind, setPendingKind] = useState<OperationsArtifactKind | null>(null);
  const [artifact, setArtifact] = useState<{
    actionLabel: string;
    response: OperationsArtifactResponse;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sessionStatus = identitySession?.authenticated ? "ready" : "watch";
  const sessionLabel = identitySession?.authenticated
    ? "API-verified actor"
    : identitySessionUnavailable
      ? "Identity API required"
      : "OIDC session required";
  const returnTo = `${pathname}${searchParams.toString() ? `?${searchParams.toString()}` : ""}`;
  const signInUrl = buildOidcAuthorizeUrl(apiBaseUrl, returnTo);

  async function submitArtifact(kind: OperationsArtifactKind) {
    setPendingKind(kind);
    setError(null);

    try {
      const request = buildOperationsArtifactRequest({
        kind,
        identitySession,
        snapshot: operationsSnapshot,
      });
      const response = await axisFetchJson<OperationsArtifactResponse>(request.endpoint, {
        method: "POST",
        session,
        body: request.body,
      });

      setArtifact({
        actionLabel: request.action.label,
        response,
      });
      onArtifactCommitted();
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Axis could not persist the operations artifact.",
      );
    } finally {
      setPendingKind(null);
    }
  }

  return (
    <Card className="grid content-start gap-4">
      <PanelHeader
        aside={
          <span className={`status-pill ${platformStatusClass(sessionStatus)}`}>
            {sessionLabel}
          </span>
        }
        eyebrow="Operations artifact runtime"
        title="Generate governed evidence"
      />
      <p className="m-0 max-w-3xl text-sm text-muted">
        Each action calls the live Axis API, persists a tenant-scoped artifact, writes audit
        evidence and refreshes the operations snapshot. No browser-local data is generated.
      </p>

      {!identitySession?.authenticated ? (
        <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-signal/30 bg-tint-50 p-4 dark:bg-signal/10">
          <ShieldCheck className="shrink-0 text-signal" size={18} />
          <div className="grid min-w-0 flex-1 gap-0.5">
            <p className="m-0 text-sm font-medium text-ink">
              Browser SSO required for artifact generation
            </p>
            <p className="m-0 text-xs text-muted">
              Sign in with the API-owned OIDC session before creating daily briefs or risk
              scenarios.
            </p>
          </div>
          <a
            className="inline-flex items-center gap-2 rounded-full bg-navy px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-signal dark:bg-signal dark:hover:bg-white dark:hover:text-navy"
            href={signInUrl}
          >
            Sign in with SSO
          </a>
        </div>
      ) : null}

      <div className="grid gap-3 md:grid-cols-3">
        {OPERATIONS_ARTIFACT_ACTIONS.map((action) => {
          const state = getOperationsArtifactActionState(action.kind, identitySession);
          const pending = pendingKind === action.kind;

          return (
            <button
              aria-describedby={`${action.kind}-artifact-state`}
              className="flex items-start gap-3 rounded-2xl border border-line bg-transparent p-4 text-left transition-colors enabled:hover:border-signal/50 enabled:hover:bg-tint-50 disabled:cursor-not-allowed disabled:opacity-55 dark:border-white/10 dark:enabled:hover:bg-white/5"
              disabled={!state.canRun || Boolean(pendingKind)}
              key={action.kind}
              onClick={() => void submitArtifact(action.kind)}
              title={state.reason ?? action.description}
              type="button"
            >
              <span className="mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-tint-100 text-signal dark:bg-signal/15">
                {action.kind === "daily_brief" ? (
                  <FileCheck2 size={16} />
                ) : action.kind === "supplier_delay" ? (
                  <AlertTriangle size={16} />
                ) : (
                  <ShieldCheck size={16} />
                )}
              </span>
              <span className="grid min-w-0 gap-1">
                <strong className="text-sm font-medium text-ink">
                  {pending ? "Persisting..." : action.label}
                </strong>
                <small className="text-xs text-muted" id={`${action.kind}-artifact-state`}>
                  {state.reason ?? action.description}
                </small>
              </span>
            </button>
          );
        })}
      </div>

      {artifact ? (
        <div
          className="flex flex-wrap items-start gap-3 rounded-2xl border border-positive/35 bg-positive/8 p-4"
          role="status"
        >
          <StatusDot status="ready" />
          <div className="grid min-w-0 flex-1 gap-1">
            <p className="m-0 font-mono text-sm break-words text-ink">
              {artifact.actionLabel} / {operationsArtifactRecordId(artifact.response)}
            </p>
            <p className="m-0 text-xs text-muted">
              {operationsArtifactHeadline(artifact.response)}
            </p>
            <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11px] text-muted">
              <span>{artifact.response.idempotent_replay ? "Idempotent replay" : "Created"}</span>
              <span>{artifact.response.source_record_ids.length} source records</span>
              <span>{artifact.response.audit_event_type}</span>
            </div>
          </div>
          {artifact.response.audit_event_id ? (
            <Link
              className="font-mono text-xs tracking-[0.12em] text-signal uppercase hover:underline"
              href="/audit"
            >
              Open audit
            </Link>
          ) : null}
        </div>
      ) : null}

      {error ? (
        <p className="m-0 text-sm text-danger" role="status">
          {error}
        </p>
      ) : null}
    </Card>
  );
}

function OntologyMap({ domains }: { domains: ManufacturingDomainSnapshot[] }) {
  const sortedDomains = sortDomainSnapshotsByOperationalPriority(domains).slice(0, 6);
  const width = 300;
  const height = 190;
  const cx = width / 2;
  const cy = height / 2;
  const radius = 72;

  return (
    <Card className="flex flex-col gap-3">
      <PanelHeader eyebrow="Operational ontology" title="Domain graph" />
      <svg
        aria-label="Operational ontology graph"
        className="h-auto w-full"
        role="img"
        viewBox={`0 0 ${width} ${height}`}
      >
        {sortedDomains.map((domain, index) => {
          const angle = -Math.PI / 2 + (Math.PI * 2 * index) / Math.max(1, sortedDomains.length);
          const x = cx + Math.cos(angle) * radius;
          const y = cy + Math.sin(angle) * radius * 0.72;

          return (
            <g key={domain.domain}>
              <line
                stroke="rgb(var(--signal))"
                strokeOpacity={0.35}
                x1={cx}
                x2={x}
                y1={cy}
                y2={y}
              />
              <rect
                fill="rgb(var(--ink))"
                height={7}
                transform={`rotate(45 ${x} ${y})`}
                width={7}
                x={x - 3.5}
                y={y - 3.5}
              />
              <text
                className="font-mono"
                fill="rgb(var(--muted))"
                fontSize={9.5}
                textAnchor="middle"
                x={x}
                y={y + (Math.sin(angle) >= 0 ? 16 : -10)}
              >
                {domain.domain}
              </text>
            </g>
          );
        })}
        <AxisMarkGlyph cx={cx} cy={cy} r={16} rayColor="rgb(var(--ink))" />
      </svg>
      <PanelLink href="/ontology">Explore ontology</PanelLink>
    </Card>
  );
}

function WorkflowOrchestration({ overview }: { overview: ManufacturingOverview }) {
  return (
    <Card className="flex flex-col gap-3">
      <PanelHeader eyebrow="Workflow orchestration" title="Human-gated flow" />
      <div className="grid gap-0" aria-label="Workflow pipeline">
        {overview.workflows.slice(0, 3).map((workflow, index) => (
          <div className="grid gap-3 py-2.5 first:pt-0" key={workflow.workflow_id}>
            {index > 0 ? <div aria-hidden="true" className="rule-dotted -mt-2.5 mb-1" /> : null}
            <div className="flex items-center gap-3">
              <span className="inline-flex size-6 shrink-0 items-center justify-center rounded-full border border-signal/40 font-mono text-xs text-signal">
                {index + 1}
              </span>
              <div className="grid min-w-0 gap-0.5">
                <p className="m-0 text-sm font-medium text-ink">
                  {compactWorkflowName(workflow.name)}
                </p>
                <p className="m-0 text-xs text-muted">{normalizeLabel(workflow.state)}</p>
              </div>
            </div>
          </div>
        ))}
        <div aria-hidden="true" className="rule-dotted mb-1" />
        <div className="flex items-center gap-3 rounded-xl bg-tint-50 px-3 py-2.5 dark:bg-signal/10">
          <ShieldCheck className="shrink-0 text-signal" size={17} />
          <div className="grid gap-0.5">
            <p className="m-0 text-sm font-medium text-ink">Approval gate</p>
            <p className="m-0 text-xs text-muted">{overview.approvals.length} requests</p>
          </div>
        </div>
      </div>
      <div className="flex gap-6 text-xs text-muted">
        <span>
          <strong className="mr-1 font-display text-base text-ink">
            {overview.workflows.length}
          </strong>
          active executions
        </span>
        <span>
          <strong className="mr-1 font-display text-base text-ink">
            {overview.approvals.length}
          </strong>
          pending review
        </span>
      </div>
      <PanelLink href="/workflows">Open workflows</PanelLink>
    </Card>
  );
}

function AgentControl({ overview }: { overview: ManufacturingOverview }) {
  return (
    <Card className="flex flex-col gap-3">
      <PanelHeader eyebrow="Agent control" title="Governed autonomy" />
      <div className="grid gap-3">
        {overview.agents.map((agent) => {
          const waiting = agent.status.includes("waiting");

          return (
            <div className="flex items-center gap-3" key={agent.agent_id}>
              <Bot className="shrink-0 text-signal" size={18} />
              <div className="grid min-w-0 flex-1 gap-0.5">
                <p className="m-0 text-sm font-medium text-ink">{agent.name}</p>
                <p className="m-0 font-mono text-[11px] text-muted">
                  {agent.autonomy_level} / {compactPolicyLabel(agent.model_policy)}
                </p>
              </div>
              <span className="inline-flex items-center gap-2 text-xs whitespace-nowrap text-muted">
                {compactAgentStatus(agent.status)}
                <StatusDot status={waiting ? "watch" : "ready"} />
              </span>
            </div>
          );
        })}
      </div>
      <PanelLink href="/agents">Manage agents</PanelLink>
    </Card>
  );
}

function ConnectorEvidence({ snapshot }: { snapshot: ManufacturingOperationsSnapshot }) {
  const connectorEvents = snapshot.recent_audit_events
    .filter((event) => event.event_type.startsWith("connector."))
    .slice(0, 5);

  return (
    <Card className="flex flex-col gap-3">
      <PanelHeader eyebrow="Connectors" title="Evidence stream" />
      <DataTable aria-label="Connector evidence events" minWidth={0}>
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Status</th>
            <th>Last sync</th>
          </tr>
        </thead>
        <tbody>
          {connectorEvents.map((event) => (
            <tr key={`${event.event_type}-${event.created_at}`}>
              <td className="text-xs">{compactConnectorEvent(event.event_type)}</td>
              <td className="text-xs text-muted">Audit</td>
              <td className="text-xs text-positive">Recorded</td>
              <td className="font-mono text-xs text-muted">{shortTime(event.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <PanelLink href="/connectors">Manage connectors</PanelLink>
    </Card>
  );
}

function ApprovalQueue({ overview }: { overview: ManufacturingOverview }) {
  return (
    <Card className="flex flex-col gap-3">
      <PanelHeader eyebrow="Approvals" title="Pending decisions" />
      <DataTable aria-label="Approval requests" minWidth={0}>
        <thead>
          <tr>
            <th>Request</th>
            <th>Requested by</th>
            <th>Type</th>
            <th>Due</th>
          </tr>
        </thead>
        <tbody>
          {overview.approvals.map((approval) => (
            <tr key={approval.approval_id}>
              <td className="text-xs">{approval.action}</td>
              <td className="text-xs text-muted">{normalizeLabel(approval.requested_by)}</td>
              <td className="text-xs text-muted">{normalizeLabel(approval.risk_level)}</td>
              <td className="font-mono text-xs text-muted">{approval.due}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
      <PanelLink href="/approvals">Review approvals</PanelLink>
    </Card>
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
    <Card className="flex flex-col gap-3">
      <PanelHeader eyebrow="Audit observability" title="Recent evidence" />
      <Reveal>
        <svg
          aria-label="Recent audit evidence chart"
          className="h-auto w-full"
          role="img"
          viewBox="0 0 300 96"
        >
          <defs>
            <pattern height="16" id="audit-grid" patternUnits="userSpaceOnUse" width="20">
              <path
                d="M 20 0 L 0 0 0 16"
                fill="none"
                stroke="rgb(var(--line) / 0.5)"
                strokeWidth="1"
              />
            </pattern>
          </defs>
          <rect fill="url(#audit-grid)" height="96" width="300" />
          <polyline
            className="draw-path"
            fill="none"
            points={points}
            stroke="rgb(var(--signal))"
            strokeWidth="2"
          />
          {points.split(" ").map((point) => {
            const [pointX, pointY] = point.split(",");

            return <circle cx={pointX} cy={pointY} fill="rgb(var(--signal))" key={point} r="3" />;
          })}
        </svg>
      </Reveal>
      <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs text-muted">
        <span>
          <strong className="mr-1 font-display text-base text-ink">
            {snapshot.recent_audit_events.length}
          </strong>
          recent events
        </span>
        <span>
          <strong className="mr-1 font-display text-base text-ink">
            {getPersistedArtifactCount(snapshot)}
          </strong>
          governed artifacts
        </span>
        <span>
          <strong className="mr-1 font-display text-base text-ink">
            {connectionEvents(snapshot)}
          </strong>
          connector events
        </span>
      </div>
      <PanelLink href="/audit">Open audit</PanelLink>
    </Card>
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
  const healthSignals: { label: string; status: PlatformStatus }[] = [
    {
      label: "Policies",
      status:
        demoReadiness.checks.find((check) => check.check_id === "human_approval_gates")?.status ??
        "watch",
    },
    { label: "Security", status: getDemoReadinessPriorityStatus(demoReadiness) },
    {
      label: "Data",
      status: operationsSnapshot.metrics.every((metric) => metric.status === "ready")
        ? "ready"
        : "watch",
    },
    { label: "Workflows", status: workflowMetric?.status ?? "watch" },
    { label: "Agents", status: agentsMetric?.status ?? "ready" },
    {
      label: "Connectors",
      status: connectionEvents(operationsSnapshot) > 0 ? "ready" : "watch",
    },
  ];
  const polygon = healthSignals
    .map((signal, index) => radarPoint(index, healthSignals.length, signal.status))
    .join(" ");
  const baseline = healthSignals
    .map((_, index) => radarPoint(index, healthSignals.length, "watch"))
    .join(" ");

  return (
    <Card className="grid content-start gap-3">
      <h2 className="eyebrow m-0 text-[11px] font-medium">System health</h2>
      <svg
        aria-label="System health radar"
        className="mx-auto h-auto w-full max-w-52"
        role="img"
        viewBox="0 0 108 108"
      >
        {[18, 30, 42].map((radius) => (
          <circle
            cx="54"
            cy="54"
            fill="none"
            key={radius}
            r={radius}
            stroke="rgb(var(--line) / 0.7)"
          />
        ))}
        {healthSignals.map((signal, index) => {
          const point = radarPoint(index, healthSignals.length, "ready");
          const [x, y] = point.split(",");

          return (
            <line key={signal.label} stroke="rgb(var(--line) / 0.6)" x1="54" x2={x} y1="54" y2={y} />
          );
        })}
        <polygon
          fill="none"
          points={baseline}
          stroke="rgb(var(--muted) / 0.5)"
          strokeDasharray="2 3"
        />
        <polygon
          fill="rgb(var(--signal) / 0.16)"
          points={polygon}
          stroke="rgb(var(--signal))"
          strokeWidth="2"
        />
      </svg>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
        {healthSignals.map((signal) => (
          <span className="inline-flex items-center gap-2 text-xs text-muted" key={signal.label}>
            <StatusDot status={signal.status} />
            {signal.label}
          </span>
        ))}
      </div>
      <div aria-hidden="true" className="rule-dotted" />
      <p className="m-0 text-xs text-muted">
        Routing posture: {platformStatusLabel(modelRouting.routing_status)} /{" "}
        {countBlockedModelRoutes(modelRouting)} blocked route
      </p>
    </Card>
  );
}

function RiskSignals({ overview }: { overview: ManufacturingOverview }) {
  return (
    <Card className="grid content-start gap-3">
      <PanelHeader
        aside={
          <Link
            className="font-mono text-xs tracking-[0.12em] text-signal uppercase hover:underline"
            href="/audit"
          >
            View all
          </Link>
        }
        eyebrow="Risk signals"
      />
      <div className="grid gap-3">
        {overview.risk_signals.map((signal) => (
          <div className="flex items-start gap-3" key={signal.title}>
            <AlertTriangle
              className={cn(
                "mt-0.5 shrink-0",
                signal.severity === "ready" && "text-positive",
                signal.severity === "watch" && "text-warning",
                signal.severity === "action_required" && "text-danger",
              )}
              size={18}
              strokeWidth={1.8}
            />
            <div className="grid gap-0.5">
              <p className="m-0 text-sm font-medium text-ink">{signal.title}</p>
              <p className="m-0 text-xs text-muted">{signal.evidence}</p>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function RecentActivity({ snapshot }: { snapshot: ManufacturingOperationsSnapshot }) {
  return (
    <Card className="grid content-start gap-3">
      <PanelHeader
        aside={
          <Link
            className="font-mono text-xs tracking-[0.12em] text-signal uppercase hover:underline"
            href="/audit"
          >
            View all
          </Link>
        }
        eyebrow="Recent activity"
      />
      <div className="grid gap-3">
        {snapshot.recent_audit_events.slice(0, 5).map((event) => (
          <div className="flex items-start gap-3" key={`${event.event_type}-${event.created_at}`}>
            <span className="mt-1.5">
              <StatusDot status="ready" />
            </span>
            <div className="grid min-w-0 flex-1 gap-0.5">
              <p className="m-0 text-sm font-medium break-words text-ink">
                {normalizeLabel(event.event_type)}
              </p>
              <p className="m-0 text-xs text-muted">{normalizeLabel(event.actor_id)}</p>
            </div>
            <span className="font-mono text-xs whitespace-nowrap text-muted">
              {shortTime(event.created_at)}
            </span>
          </div>
        ))}
      </div>
    </Card>
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
    <Card className="grid content-start gap-3">
      <Eyebrow>Quick actions</Eyebrow>
      <div className="grid grid-cols-2 gap-2">
        {actions.map((action) => {
          const Icon = action.icon;

          return (
            <Link
              className="inline-flex items-center gap-2 rounded-xl border border-line px-3 py-2.5 text-xs font-medium text-ink transition-colors hover:border-signal/50 hover:text-signal dark:border-white/10"
              href={action.href}
              key={action.label}
            >
              <Icon className="shrink-0" size={15} />
              {action.label}
            </Link>
          );
        })}
      </div>
    </Card>
  );
}

function ModelRoutingStrip({ routing }: { routing: ManufacturingModelRouting }) {
  const primaryRoute = routing.routes[0];
  const blockedRoutes = countBlockedModelRoutes(routing);
  const totalCost = sumEstimatedModelCost(routing);
  const stages = [
    {
      label: "Request",
      title: primaryRoute.prompt_classification,
      detail: `Source: ${primaryRoute.agent_name}`,
      titleClass: "",
    },
    {
      label: "Routing decision",
      title: primaryRoute.model,
      detail: primaryRoute.data_boundary,
      titleClass: "",
    },
    {
      label: "Execution",
      title: formatModelRoutingLabel(primaryRoute.egress_decision),
      detail: `Latency: ${primaryRoute.latency_ms} ms`,
      titleClass:
        routeDecisionClass(primaryRoute) === "signal-ready" ? "text-positive" : "text-warning",
    },
    {
      label: "Response",
      title: formatEuroCost(totalCost),
      detail: `${blockedRoutes} blocked route`,
      titleClass: "",
    },
  ];

  return (
    <Card className="grid content-start gap-4">
      <PanelHeader
        aside={
          <Link
            className="font-mono text-xs tracking-[0.12em] text-signal uppercase hover:underline"
            href="/model-routing"
          >
            View routing
          </Link>
        }
        eyebrow="Model routing"
        title="Persisted routing posture"
      />
      <div
        aria-label="Model routing decision flow"
        className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"
      >
        {stages.map((stage, index) => (
          <div
            className="relative grid content-start gap-1 rounded-2xl border border-line p-4 dark:border-white/10"
            key={stage.label}
          >
            <Eyebrow>{stage.label}</Eyebrow>
            <p className={cn("m-0 text-sm font-medium break-words text-ink", stage.titleClass)}>
              {stage.title}
            </p>
            <p className="m-0 text-xs text-muted">{stage.detail}</p>
            {index < stages.length - 1 ? (
              <ArrowRight
                aria-hidden="true"
                className="absolute top-1/2 -right-2.5 hidden -translate-y-1/2 text-signal xl:block"
                size={15}
              />
            ) : null}
          </div>
        ))}
      </div>
    </Card>
  );
}

function ReadinessPanel({ demoReadiness }: { demoReadiness: ManufacturingDemoReadinessReport }) {
  const readinessCounts = getDemoReadinessCounts(demoReadiness);

  return (
    <Card className="grid content-start gap-4" id="readiness">
      <PanelHeader
        aside={<PlatformStatusPill status={getDemoReadinessPriorityStatus(demoReadiness)} />}
        eyebrow="Demo readiness"
        title="Feedback environment"
      />
      <p className="m-0 max-w-3xl text-sm text-muted">{demoReadiness.summary}</p>
      <Reveal>
        <div className="grid gap-4 sm:grid-cols-[220px_1fr]">
          <div className="grid content-start gap-2">
            <MetricSparkbar
              caption="Demo readiness check counts: ready, watch, action required"
              points={[
                { label: "ready", value: readinessCounts.ready },
                { label: "watch", value: readinessCounts.watch },
                { label: "action required", value: readinessCounts.action_required },
              ]}
            />
            <div className="grid grid-cols-3 gap-2 text-[11px] tracking-[0.1em] text-muted uppercase">
              <span>
                <strong className="block font-display text-lg tracking-normal text-ink">
                  {readinessCounts.ready}
                </strong>
                ready
              </span>
              <span>
                <strong className="block font-display text-lg tracking-normal text-ink">
                  {readinessCounts.watch}
                </strong>
                watch
              </span>
              <span>
                <strong className="block font-display text-lg tracking-normal text-ink">
                  {readinessCounts.action_required}
                </strong>
                action required
              </span>
            </div>
          </div>
          <div className="grid content-start gap-2 sm:grid-cols-2">
            {demoReadiness.tracks.map((track) => (
              <div
                className="flex items-start justify-between gap-3 rounded-2xl border border-line p-3.5 dark:border-white/10"
                key={track.name}
              >
                <div className="grid min-w-0 gap-0.5">
                  <p className="m-0 text-sm font-medium text-ink">{track.name}</p>
                  <p className="m-0 text-xs text-muted">{track.detail}</p>
                </div>
                <PlatformStatusPill status={track.status} />
              </div>
            ))}
          </div>
        </div>
      </Reveal>
    </Card>
  );
}

function OverviewSkeleton() {
  return (
    <div className="grid gap-5 px-6 py-6" aria-busy="true" aria-label="Loading operations API">
      <Skeleton className="h-64 rounded-3xl" />
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
        <Skeleton className="h-36" />
        <Skeleton className="h-36" />
        <Skeleton className="h-36" />
        <Skeleton className="h-36" />
        <Skeleton className="h-36" />
      </div>
      <Skeleton className="h-72" />
    </div>
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
  const { session } = useOidcConsoleSession();
  const { data: identitySession, isUnavailable: identitySessionUnavailable } =
    useAxisQuery<IdentitySessionReadModel>("/identity/session");

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
            session,
            signal: controller.signal,
          }),
          axisFetchJson<ManufacturingOperationsSnapshot>(
            "/demo/manufacturing/operations/snapshot",
            { session, signal: controller.signal },
          ),
          axisFetchJson<ManufacturingDemoReadinessReport>("/demo/manufacturing/demo-readiness", {
            session,
            signal: controller.signal,
          }),
          axisFetchJson<ManufacturingModelRouting>("/demo/manufacturing/model-routing", {
            session,
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
  }, [refreshNonce, session]);

  if (!overview || !operationsSnapshot || !demoReadiness || !modelRouting) {
    return (
      <div className="ops-console grid min-h-screen content-start gap-3 px-4 pb-5 sm:px-6">
        <ConsoleTopbar
          evidenceLabel={source === "api" ? "Evidence present" : "Evidence required"}
          sourceLabel={sourceLabel(source)}
        />
        {source === "loading" ? (
          <OverviewSkeleton />
        ) : (
          <div className="mx-auto grid min-h-[60vh] w-full max-w-3xl content-center px-6 py-6">
            <ApiRequiredState
              detail="Axis did not receive API-backed overview, operations snapshot, demo-readiness and model-routing records. Local fallback overview records are disabled."
              endpoint="/demo/manufacturing/overview + /demo/manufacturing/operations/snapshot + /demo/manufacturing/demo-readiness + /demo/manufacturing/model-routing"
              title="Operations API unavailable"
            />
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="ops-console grid min-h-screen content-start gap-3 px-4 pb-5 sm:px-6">
      <ConsoleTopbar
        evidenceLabel={source === "api" ? "Evidence present" : "Evidence required"}
        sourceLabel={sourceLabel(source)}
      />

      <div className="ops-dashboard-grid grid grid-cols-1 gap-5 px-5 py-6 min-[1400px]:grid-cols-[minmax(0,1fr)_320px] sm:px-6">
        <main aria-label="Operations dashboard" className="ops-dashboard-main grid min-w-0 gap-5">
          <OverviewHero
            onRefresh={triggerRefresh}
            operationsSnapshot={operationsSnapshot}
            overview={overview}
          />

          <TopKpis
            demoReadiness={demoReadiness}
            operationsSnapshot={operationsSnapshot}
            overview={overview}
          />

          <OperationsArtifactPanel
            identitySession={identitySession}
            identitySessionUnavailable={identitySessionUnavailable}
            onArtifactCommitted={triggerRefresh}
            operationsSnapshot={operationsSnapshot}
            session={session}
          />

          <DomainSnapshots snapshot={operationsSnapshot} />

          <Reveal>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <OntologyMap domains={operationsSnapshot.domain_snapshots} />
              <WorkflowOrchestration overview={overview} />
              <AgentControl overview={overview} />
              <ConnectorEvidence snapshot={operationsSnapshot} />
              <ApprovalQueue overview={overview} />
              <AuditObservability snapshot={operationsSnapshot} />
            </div>
          </Reveal>

          <ModelRoutingStrip routing={modelRouting} />

          <ReadinessPanel demoReadiness={demoReadiness} />
        </main>

        <aside aria-label="Operations side rail" className="ops-right-rail grid min-w-0 content-start gap-4">
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
