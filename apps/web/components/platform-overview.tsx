"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, RadioTower, ShieldCheck } from "lucide-react";

import { ApiRequiredState } from "@/components/api-required-state";
import { ApiStatusPanel } from "@/components/api-status-panel";
import { getApiBaseUrl } from "@/lib/api-status";
import {
  formatOverviewTimestamp,
  platformStatusClass,
  platformStatusLabel,
  type ManufacturingOverview,
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
    return "API overview data";
  }

  return source === "loading" ? "Loading overview API" : "Overview API unavailable";
}

export function PlatformOverview() {
  const [overview, setOverview] = useState<ManufacturingOverview | null>(null);
  const [source, setSource] = useState<OverviewSource>("loading");
  const apiBaseUrl = getApiBaseUrl();

  useEffect(() => {
    const controller = new AbortController();

    async function fetchOverview() {
      try {
        const response = await fetch(`${apiBaseUrl}/demo/manufacturing/overview`, {
          signal: controller.signal,
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error(`Overview request failed with ${response.status}`);
        }

        setOverview((await response.json()) as ManufacturingOverview);
        setSource("api");
      } catch {
        if (!controller.signal.aborted) {
          setOverview(null);
          setSource("unavailable");
        }
      }
    }

    void fetchOverview();

    return () => controller.abort();
  }, [apiBaseUrl]);

  if (!overview) {
    return (
      <div className="stack">
        <ApiRequiredState
          detail="Axis did not receive API-backed overview records. Local fallback overview records are disabled."
          endpoint="/demo/manufacturing/overview"
          title={source === "loading" ? "Loading overview API" : "Overview API unavailable"}
        />
        <ApiStatusPanel />
      </div>
    );
  }

  return (
    <div className="stack">
      <section className="panel overview-context">
        <div>
          <p className="section-label">Demo Tenant</p>
          <h2 className="panel-title">{overview.plant_name}</h2>
          <p className="row-detail">
            {overview.scenario} / {overview.tenant_id}
          </p>
        </div>
        <div className="overview-meta" aria-label="Overview source and timestamp">
          <span className="status-pill signal-ready">
            <RadioTower size={15} />
            {sourceLabel(source)}
          </span>
          <span className="mono">{formatOverviewTimestamp(overview.as_of)}</span>
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

      <div className="two-column">
        <section className="panel">
          <p className="section-label">Risk Signals</p>
          <h2 className="panel-title">Decisions that need attention</h2>
          <div className="stack">
            {overview.risk_signals.map((signal) => (
              <div className="row" key={signal.title}>
                <div>
                  <p className="row-title">{signal.title}</p>
                  <p className="row-detail">
                    {signal.domain} / {signal.owner_role} / {signal.related_asset}
                  </p>
                  <p className="row-detail">{signal.evidence}</p>
                </div>
                <SignalPill status={signal.severity} />
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
              {overview.approvals.map((approval) => (
                <div className="row" key={approval.approval_id}>
                  <div>
                    <p className="row-title">{approval.action}</p>
                    <p className="row-detail">
                      {approval.requested_by} / {approval.owner_role}
                    </p>
                    <p className="row-detail">Due {approval.due}</p>
                  </div>
                  <span className="status-pill signal-action-required">{approval.risk_level}</span>
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
            {overview.workflows.map((workflow) => (
              <div className="row" key={workflow.workflow_id}>
                <div>
                  <p className="row-title">{workflow.name}</p>
                  <p className="row-detail">
                    {workflow.state} / {workflow.owner_role} / ETA {workflow.eta}
                  </p>
                  {workflow.blocker ? <p className="row-detail">{workflow.blocker}</p> : null}
                </div>
                <CheckCircle2 size={18} aria-label={workflow.state} />
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
          {overview.audit_events.map((item) => (
            <div className="row" key={`${item.event}-${item.scope}`}>
              <div>
                <p className="row-title mono">{item.event}</p>
                <p className="row-detail">
                  {item.actor} / {item.scope}
                </p>
              </div>
              <ShieldCheck size={18} aria-label={item.result} />
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
