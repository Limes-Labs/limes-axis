"use client";

import { useEffect, useState } from "react";
import {
  Database,
  FileCheck2,
  GitBranch,
  RadioTower,
  ShieldCheck,
} from "lucide-react";

import { ApiRequiredState } from "@/components/api-required-state";
import { ApiStatusPanel } from "@/components/api-status-panel";
import { getApiBaseUrl } from "@/lib/api-status";
import {
  formatOverviewTimestamp,
  getOperationsSnapshotStatus,
  getPersistedArtifactCount,
  platformStatusClass,
  platformStatusLabel,
  sortDomainSnapshotsByOperationalPriority,
  type ManufacturingOverview,
  type ManufacturingOperationsSnapshot,
  type PlatformStatus,
} from "@/lib/platform-overview";

type OverviewSource = "loading" | "api" | "unavailable";

function SignalPill({ status }: { status: PlatformStatus }) {
  return (
    <span className={`status-pill ${platformStatusClass(status)}`}>
      {platformStatusLabel(status)}
    </span>
  );
}

function sourceLabel(source: OverviewSource): string {
  if (source === "api") {
    return "API-backed control plane";
  }

  return source === "loading" ? "Loading overview API" : "Overview API unavailable";
}

function statusFromRiskLevel(value: string): PlatformStatus {
  if (value === "high" || value === "critical") {
    return "action_required";
  }

  return value === "low" ? "ready" : "watch";
}

function statusFromRecordStatus(value: string): PlatformStatus {
  if (value === "action_required" || value === "pending") {
    return "action_required";
  }

  return value === "generated" || value === "ready" || value === "approved" ? "ready" : "watch";
}

export function PlatformOverview() {
  const [overview, setOverview] = useState<ManufacturingOverview | null>(null);
  const [operationsSnapshot, setOperationsSnapshot] =
    useState<ManufacturingOperationsSnapshot | null>(null);
  const [source, setSource] = useState<OverviewSource>("loading");
  const apiBaseUrl = getApiBaseUrl();

  useEffect(() => {
    const controller = new AbortController();

    async function fetchOverview() {
      try {
        const [overviewResponse, operationsSnapshotResponse] = await Promise.all([
          fetch(`${apiBaseUrl}/demo/manufacturing/overview`, {
            signal: controller.signal,
            cache: "no-store",
          }),
          fetch(`${apiBaseUrl}/demo/manufacturing/operations/snapshot`, {
            signal: controller.signal,
            cache: "no-store",
          }),
        ]);

        if (!overviewResponse.ok) {
          throw new Error(`Overview request failed with ${overviewResponse.status}`);
        }

        if (!operationsSnapshotResponse.ok) {
          throw new Error(
            `Operations snapshot request failed with ${operationsSnapshotResponse.status}`,
          );
        }

        const [overviewPayload, operationsSnapshotPayload] = await Promise.all([
          overviewResponse.json(),
          operationsSnapshotResponse.json(),
        ]);

        setOverview(overviewPayload as ManufacturingOverview);
        setOperationsSnapshot(operationsSnapshotPayload as ManufacturingOperationsSnapshot);
        setSource("api");
      } catch {
        if (!controller.signal.aborted) {
          setOverview(null);
          setOperationsSnapshot(null);
          setSource("unavailable");
        }
      }
    }

    void fetchOverview();

    return () => controller.abort();
  }, [apiBaseUrl]);

  if (!overview || !operationsSnapshot) {
    return (
      <div className="stack">
        <ApiRequiredState
          detail="Axis did not receive API-backed overview and operations snapshot records. Local fallback overview records are disabled."
          endpoint="/demo/manufacturing/overview + /demo/manufacturing/operations/snapshot"
          title={source === "loading" ? "Loading overview API" : "Overview API unavailable"}
        />
        <ApiStatusPanel />
      </div>
    );
  }

  const prioritizedDomains = sortDomainSnapshotsByOperationalPriority(
    operationsSnapshot.domain_snapshots,
  );
  const snapshotStatus = getOperationsSnapshotStatus(operationsSnapshot);
  const persistedArtifactCount = getPersistedArtifactCount(operationsSnapshot);

  return (
    <div className="stack">
      <section className="operations-hero">
        <div className="operations-hero-main">
          <p className="section-label">Demo Tenant</p>
          <h2 className="operations-hero-title">{overview.plant_name}</h2>
          <p className="operations-hero-copy">
            {overview.scenario} is running on tenant-scoped API records. The overview now composes
            persisted operations, generated briefs, risk scenarios, workflow state, approval gates
            and audit evidence.
          </p>
          <div className="overview-meta" aria-label="Overview source and timestamp">
            <span className="status-pill signal-ready">
              <RadioTower size={15} />
              {sourceLabel(source)}
            </span>
            <span className={`status-pill ${platformStatusClass(snapshotStatus)}`}>
              <Database size={15} />
              Operations snapshot
            </span>
            <span className="mono">{formatOverviewTimestamp(operationsSnapshot.as_of)}</span>
          </div>
        </div>
        <div className="operations-hero-ledger" aria-label="Operations snapshot summary">
          <div>
            <p className="metric-label">Operational Domains</p>
            <p className="metric-value">{operationsSnapshot.domain_snapshots.length}</p>
            <p className="metric-detail">Persisted domain rollups</p>
          </div>
          <div>
            <p className="metric-label">Generated Artifacts</p>
            <p className="metric-value">{persistedArtifactCount}</p>
            <p className="metric-detail">Briefs and risk scenarios</p>
          </div>
          <div>
            <p className="metric-label">Pending Gates</p>
            <p className="metric-value">{operationsSnapshot.pending_approvals.length}</p>
            <p className="metric-detail">Human decisions required</p>
          </div>
        </div>
      </section>

      <div className="metric-grid">
        {overview.metrics.map((metric) => (
          <article className="metric-card" key={metric.label}>
            <div className="row">
              <p className="metric-label">{metric.label}</p>
              <SignalPill status={metric.status} />
            </div>
            <p className="metric-value">{metric.value}</p>
            <p className="metric-detail">{metric.detail}</p>
          </article>
        ))}
      </div>

      <section className="panel">
        <div className="section-heading-row">
          <div>
            <p className="section-label">Operations Snapshot</p>
            <h2 className="panel-title">Persisted plant state</h2>
          </div>
          <span className={`status-pill ${platformStatusClass(snapshotStatus)}`}>
            {platformStatusLabel(snapshotStatus)}
          </span>
        </div>
        <div className="domain-snapshot-grid">
          {prioritizedDomains.map((domain) => (
            <article className="domain-snapshot" key={domain.domain}>
              <div className="domain-snapshot-topline">
                <p className="row-title">{domain.domain}</p>
                <span
                  className={`status-pill ${platformStatusClass(
                    statusFromRiskLevel(domain.highest_risk_level),
                  )}`}
                >
                  {domain.highest_risk_level}
                </span>
              </div>
              <div className="domain-snapshot-counts">
                <span>
                  <strong>{domain.record_count}</strong>
                  records
                </span>
                <span>
                  <strong>{domain.action_required_count}</strong>
                  actions
                </span>
                <span>
                  <strong>{domain.watch_count}</strong>
                  watch
                </span>
              </div>
              <p className="row-detail">{domain.owner_roles.join(", ")}</p>
              <p className="row-detail mono">{domain.evidence_refs[0] ?? "No evidence ref"}</p>
            </article>
          ))}
        </div>
      </section>

      <div className="two-column">
        <section className="panel">
          <p className="section-label">Generated Evidence</p>
          <h2 className="panel-title">Briefs and risk scenarios</h2>
          <div className="stack">
            {operationsSnapshot.latest_daily_briefs.map((brief) => (
              <div className="row" key={brief.brief_id}>
                <div>
                  <p className="row-title">{brief.brief_id}</p>
                  <p className="row-detail">
                    {brief.brief_date} / {brief.requested_by} / {brief.source_record_count} sources
                  </p>
                  <p className="row-detail mono">{brief.audit_event_type}</p>
                </div>
                <span
                  className={`status-pill ${platformStatusClass(
                    statusFromRecordStatus(brief.status),
                  )}`}
                >
                  <FileCheck2 size={15} />
                  {brief.status}
                </span>
              </div>
            ))}
            {operationsSnapshot.risk_scenarios.map((scenario) => (
              <div className="row" key={scenario.scenario_id}>
                <div>
                  <p className="row-title">{scenario.scenario_id}</p>
                  <p className="row-detail">
                    {scenario.domain} / {scenario.owner_role} / {scenario.source_record_count} sources
                  </p>
                  <p className="row-detail mono">{scenario.audit_event_type}</p>
                </div>
                <span
                  className={`status-pill ${platformStatusClass(
                    statusFromRiskLevel(scenario.risk_level),
                  )}`}
                >
                  {scenario.risk_level}
                </span>
              </div>
            ))}
          </div>
        </section>

        <div className="stack">
          <ApiStatusPanel />
          <section className="panel">
            <p className="section-label">Approval Queue</p>
            <h2 className="panel-title">Human gates</h2>
            <div className="stack">
              {operationsSnapshot.pending_approvals.map((approval) => (
                <div className="row" key={approval.approval_id}>
                  <div>
                    <p className="row-title">{approval.action_id}</p>
                    <p className="row-detail">
                      {approval.requested_by} / {approval.owner_role}
                    </p>
                    <p className="row-detail">{approval.workflow_id ?? "No workflow binding"}</p>
                  </div>
                  <span
                    className={`status-pill ${platformStatusClass(
                      statusFromRiskLevel(approval.risk_level),
                    )}`}
                  >
                    {approval.status}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>

      <div className="two-column">
        <section className="panel">
          <p className="section-label">Workflow Console</p>
          <h2 className="panel-title">Active operational flows</h2>
          <div className="stack">
            {operationsSnapshot.active_workflows.map((workflow) => (
              <div className="row" key={workflow.workflow_id}>
                <div>
                  <p className="row-title">{workflow.name}</p>
                  <p className="row-detail">
                    {workflow.domain} / {workflow.state} / {workflow.owner_role}
                  </p>
                  {workflow.blocker ? <p className="row-detail">{workflow.blocker}</p> : null}
                </div>
                <span
                  className={`status-pill ${platformStatusClass(
                    statusFromRecordStatus(workflow.status),
                  )}`}
                >
                  <GitBranch size={15} />
                  {workflow.autonomy_level}
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="panel">
          <p className="section-label">Agent Registry</p>
          <h2 className="panel-title">Governed autonomy</h2>
          <div className="stack">
            {overview.agents.map((agent) => (
              <div className="row" key={agent.agent_id}>
                <div>
                  <p className="row-title">{agent.name}</p>
                  <p className="row-detail">
                    {agent.autonomy_level} / {agent.status} / {agent.model_policy}
                  </p>
                </div>
                <span className="status-pill signal-watch">{agent.proposals_pending} pending</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="panel">
        <p className="section-label">Recent Evidence</p>
        <h2 className="panel-title">Audit trail</h2>
        <div className="stack">
          {operationsSnapshot.recent_audit_events.map((item) => (
            <div className="row" key={`${item.event_type}-${item.created_at}`}>
              <div>
                <p className="row-title mono">{item.event_type}</p>
                <p className="row-detail">
                  {item.actor_id} / {formatOverviewTimestamp(item.created_at)}
                </p>
                <p className="row-detail mono">{Object.values(item.payload_refs).join(" / ")}</p>
              </div>
              <ShieldCheck size={18} aria-label={item.event_type} />
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
