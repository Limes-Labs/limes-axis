"use client";

import { useEffect, useMemo, useState } from "react";
import { GitBranch, History, RadioTower, Route, TimerReset } from "lucide-react";

import { ApiRequiredState } from "@/components/api-required-state";
import { axisFetchJson } from "@/lib/axis-api";
import {
  countWaitingWorkflowSignals,
  findWorkflowById,
  formatWorkflowState,
  shouldUsePersistedWorkflowData,
  type ManufacturingWorkflowConsole,
} from "@/lib/workflow-demo";
import {
  formatOverviewTimestamp,
  platformStatusClass,
  platformStatusLabel,
} from "@/lib/platform-overview";
import { useConsole } from "@/providers/console-provider";

type WorkflowSource = "loading" | "persisted" | "api" | "unavailable";

function sourceLabel(source: WorkflowSource): string {
  if (source === "persisted") {
    return "Persisted workflow runs";
  }

  if (source === "api") {
    return "API workflow records";
  }

  return source === "loading" ? "Loading workflow API" : "Workflow API unavailable";
}

function formatWorkflowTime(value: string): string {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function WorkflowConsole() {
  const [workflowData, setWorkflowData] = useState<ManufacturingWorkflowConsole | null>(null);
  const [source, setSource] = useState<WorkflowSource>("loading");
  const [selectedWorkflowId, setSelectedWorkflowId] = useState("");
  const { refreshNonce } = useConsole();

  useEffect(() => {
    const controller = new AbortController();

    async function fetchWorkflows() {
      setSource("loading");

      try {
        const persistedWorkflowData = await axisFetchJson<ManufacturingWorkflowConsole>(
          "/demo/manufacturing/workflows/runs?tenant_id=tenant_demo_manufacturing&limit=100",
          { signal: controller.signal },
        );
        if (shouldUsePersistedWorkflowData(persistedWorkflowData)) {
          setWorkflowData(persistedWorkflowData);
          setSelectedWorkflowId(persistedWorkflowData.workflow_runs[0]?.workflow_id ?? "");
          setSource("persisted");
          return;
        }

        const referenceWorkflowData = await axisFetchJson<ManufacturingWorkflowConsole>(
          "/demo/manufacturing/workflows",
          { signal: controller.signal },
        );
        setWorkflowData(referenceWorkflowData);
        setSelectedWorkflowId(referenceWorkflowData.workflow_runs[0]?.workflow_id ?? "");
        setSource("api");
      } catch {
        if (!controller.signal.aborted) {
          setWorkflowData(null);
          setSelectedWorkflowId("");
          setSource("unavailable");
        }
      }
    }

    void fetchWorkflows();

    return () => controller.abort();
  }, [refreshNonce]);

  const selectedWorkflow = useMemo(
    () =>
      workflowData && workflowData.workflow_runs.length > 0
        ? findWorkflowById(workflowData, selectedWorkflowId)
        : null,
    [workflowData, selectedWorkflowId],
  );
  const waitingSignals = workflowData ? countWaitingWorkflowSignals(workflowData) : 0;

  if (!workflowData) {
    return (
      <ApiRequiredState
        detail="Axis did not receive API-backed workflow records. Local fallback workflow records are disabled."
        endpoint="/demo/manufacturing/workflows/runs"
        title={source === "loading" ? "Loading workflow API" : "Workflow API unavailable"}
      />
    );
  }

  if (!selectedWorkflow) {
    return (
      <ApiRequiredState
        detail="The workflow API responded without runtime records for this tenant."
        endpoint="/demo/manufacturing/workflows/runs"
        title="Workflow API returned no records"
      />
    );
  }

  return (
    <div className="console-stack">
      <section className="panel overview-context">
        <div>
          <p className="section-label">Demo Workflow Runtime</p>
          <h2 className="panel-title">{workflowData.plant_name}</h2>
          <p className="row-detail">
            {workflowData.scenario} / {workflowData.tenant_id}
          </p>
        </div>
        <div className="overview-meta" aria-label="Workflow source and runtime status">
          <span className="status-pill signal-ready">
            <RadioTower size={15} />
            {sourceLabel(source)}
          </span>
          <span className={`status-pill ${platformStatusClass(workflowData.runtime_status)}`}>
            <Route size={15} />
            {platformStatusLabel(workflowData.runtime_status)}
          </span>
          <span className="mono">{formatOverviewTimestamp(workflowData.as_of)}</span>
        </div>
      </section>

      <div className="metric-grid">
        {workflowData.metrics.map((metric) => (
          <article className="metric-card compact-card" key={metric.label}>
            <div className="row">
              <p className="metric-label">{metric.label}</p>
              <span className={`status-pill ${platformStatusClass(metric.status)}`}>
                {platformStatusLabel(metric.status)}
              </span>
            </div>
            <p className="metric-value">{metric.value}</p>
            <p className="metric-detail">{metric.detail}</p>
          </article>
        ))}
      </div>

      <div className="workflow-layout">
        <section className="panel">
          <p className="section-label">Runs</p>
          <h2 className="panel-title">Workflow console</h2>
          <div className="workflow-list">
            {workflowData.workflow_runs.map((run) => {
              const isSelected = run.workflow_id === selectedWorkflow.workflow_id;

              return (
                <button
                  aria-pressed={isSelected}
                  className={`workflow-list-item${isSelected ? " active" : ""}`}
                  key={run.workflow_id}
                  onClick={() => setSelectedWorkflowId(run.workflow_id)}
                  type="button"
                >
                  <span>
                    <span className="row-title">{run.name}</span>
                    <span className="row-detail">
                      {run.domain} / {formatWorkflowState(run.state)}
                    </span>
                    <span className="row-detail">ETA {run.eta}</span>
                  </span>
                  <span className={`status-pill ${platformStatusClass(run.status)}`}>
                    {platformStatusLabel(run.status)}
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="panel workflow-detail">
          <div className="workflow-detail-header">
            <div>
              <p className="section-label">{selectedWorkflow.domain}</p>
              <h2 className="panel-title">{selectedWorkflow.name}</h2>
              <p className="row-detail">{selectedWorkflow.objective}</p>
            </div>
            <div className="status-stack">
              <span className={`status-pill ${platformStatusClass(selectedWorkflow.status)}`}>
                {formatWorkflowState(selectedWorkflow.state)}
              </span>
              <span className="status-pill status-checking">{selectedWorkflow.current_step}</span>
            </div>
          </div>

          <div className="workflow-detail-grid">
            <div>
              <p className="metric-label">Runtime</p>
              <p className="row-title">{selectedWorkflow.runtime}</p>
              <p className="row-detail">{selectedWorkflow.adapter}</p>
            </div>
            <div>
              <p className="metric-label">Owner</p>
              <p className="row-title">{selectedWorkflow.owner_role}</p>
              <p className="row-detail">{selectedWorkflow.autonomy_level}</p>
            </div>
            <div>
              <p className="metric-label">Started</p>
              <p className="row-title">{formatWorkflowTime(selectedWorkflow.started_at)}</p>
              <p className="row-detail">ETA {selectedWorkflow.eta}</p>
            </div>
            <div>
              <p className="metric-label">Audit Scope</p>
              <p className="row-title mono">{selectedWorkflow.audit_scope}</p>
              <p className="row-detail">Replay preview only</p>
            </div>
          </div>

          {selectedWorkflow.blocker ? (
            <div className="workflow-blocker">
              <TimerReset size={18} />
              <div>
                <p className="row-title">Current blocker</p>
                <p className="row-detail">{selectedWorkflow.blocker}</p>
              </div>
            </div>
          ) : null}

          <div className="workflow-columns">
            <section>
              <p className="section-label">Inputs</p>
              <ul className="clean-list">
                {selectedWorkflow.inputs.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
            <section>
              <p className="section-label">Proposed Outputs</p>
              <ul className="clean-list">
                {selectedWorkflow.proposed_outputs.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
            <section>
              <p className="section-label">Related Context</p>
              <div className="tag-list">
                <span className="tag">{selectedWorkflow.related_risk}</span>
                {selectedWorkflow.related_assets.map((asset) => (
                  <span className="tag" key={asset}>
                    {asset}
                  </span>
                ))}
              </div>
            </section>
          </div>

          <div className="workflow-signal-band">
            <div>
              <p className="section-label">Pending Signals</p>
              <div className="stack">
                {selectedWorkflow.pending_signals.map((signal) => (
                  <div className="row" key={signal.signal}>
                    <div>
                      <p className="row-title mono">{signal.signal}</p>
                      <p className="row-detail">
                        {signal.required_role}
                        {signal.approval_id ? ` / ${signal.approval_id}` : ""}
                      </p>
                    </div>
                    <span className="status-pill signal-action-required">{signal.status}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <p className="section-label">Controls</p>
              <div className="tag-list">
                {selectedWorkflow.controls.map((control) => (
                  <span className="tag" key={control}>
                    {control}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <section className="workflow-history">
            <div className="workflow-history-header">
              <div>
                <p className="section-label">History Preview</p>
                <h3 className="subsection-title">Runtime timeline</h3>
              </div>
              <span className="status-pill signal-watch">
                <History size={15} />
                {waitingSignals} waiting
              </span>
            </div>
            <div className="timeline">
              {selectedWorkflow.timeline.map((event, index) => (
                <div className="timeline-item" key={`${event.event}-${event.at}`}>
                  <div className="timeline-index">{index + 1}</div>
                  <div className="row">
                    <div>
                      <p className="row-title mono">{event.event}</p>
                      <p className="row-detail">
                        {formatWorkflowTime(event.at)} / {event.actor} / {event.result}
                      </p>
                      <p className="row-detail">{event.summary}</p>
                    </div>
                    <GitBranch size={18} aria-label={event.result} />
                  </div>
                </div>
              ))}
            </div>
          </section>
        </section>
      </div>

      <section className="panel">
        <p className="section-label">Runtime Notes</p>
        <div className="stack">
          {workflowData.runtime_notes.map((note) => (
            <p className="row-detail" key={note}>
              {note}
            </p>
          ))}
        </div>
      </section>
    </div>
  );
}
