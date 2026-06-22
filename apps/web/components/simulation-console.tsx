"use client";

import { useEffect, useMemo, useState } from "react";
import { FileText, GitBranch, History, RadioTower, ShieldCheck } from "lucide-react";

import { getApiBaseUrl } from "@/lib/api-status";
import {
  countChangedPolicySetDiffs,
  countChangedPolicyResults,
  defaultManufacturingReplaySimulation,
  findReplayArtifactById,
  formatSimulationLabel,
  shouldUsePersistedReplayData,
  type ManufacturingReplaySimulation,
} from "@/lib/simulation-demo";
import {
  formatOverviewTimestamp,
  platformStatusClass,
  platformStatusLabel,
} from "@/lib/platform-overview";

type SimulationSource = "loading" | "persisted" | "fallback";

function sourceLabel(source: SimulationSource): string {
  if (source === "persisted") {
    return "Persisted replay artifacts";
  }

  return source === "loading" ? "Loading replay artifacts" : "Fallback replay seed";
}

function formatReplayTime(value: string): string {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function SimulationConsole() {
  const [simulationData, setSimulationData] = useState<ManufacturingReplaySimulation>(
    defaultManufacturingReplaySimulation,
  );
  const [source, setSource] = useState<SimulationSource>("loading");
  const [selectedArtifactId, setSelectedArtifactId] = useState(
    defaultManufacturingReplaySimulation.artifacts[0].artifact_id,
  );
  const apiBaseUrl = getApiBaseUrl();

  useEffect(() => {
    const controller = new AbortController();

    async function fetchReplaySimulation(): Promise<ManufacturingReplaySimulation> {
      const response = await fetch(
        `${apiBaseUrl}/demo/manufacturing/simulation/replay?tenant_id=tenant_demo_manufacturing&limit=20`,
        {
          signal: controller.signal,
          cache: "no-store",
        },
      );

      if (!response.ok) {
        throw new Error(`Replay simulation request failed with ${response.status}`);
      }

      return (await response.json()) as ManufacturingReplaySimulation;
    }

    async function loadReplaySimulation() {
      try {
        const data = await fetchReplaySimulation();
        if (shouldUsePersistedReplayData(data)) {
          setSimulationData(data);
          setSelectedArtifactId(data.artifacts[0].artifact_id);
          setSource("persisted");
          return;
        }

        setSimulationData(defaultManufacturingReplaySimulation);
        setSelectedArtifactId(defaultManufacturingReplaySimulation.artifacts[0].artifact_id);
        setSource("fallback");
      } catch {
        if (!controller.signal.aborted) {
          setSimulationData(defaultManufacturingReplaySimulation);
          setSelectedArtifactId(defaultManufacturingReplaySimulation.artifacts[0].artifact_id);
          setSource("fallback");
        }
      }
    }

    void loadReplaySimulation();

    return () => controller.abort();
  }, [apiBaseUrl]);

  const selectedArtifact = useMemo(
    () => findReplayArtifactById(simulationData, selectedArtifactId),
    [simulationData, selectedArtifactId],
  );
  const changedPolicies = countChangedPolicyResults(simulationData);
  const changedPolicySetDiffs = countChangedPolicySetDiffs(simulationData);
  const primaryPolicy = selectedArtifact.policy_results[0];
  const primaryPolicySetDiff = (selectedArtifact.policy_set_diffs ?? [])[0];
  const persistedOutputs = simulationData.persisted_outputs ?? [];

  return (
    <div className="stack">
      <section className="panel overview-context">
        <div>
          <p className="section-label">Replay Foundation</p>
          <h2 className="panel-title">{simulationData.plant_name}</h2>
          <p className="row-detail">
            {simulationData.scenario} / {simulationData.tenant_id}
          </p>
        </div>
        <div className="overview-meta" aria-label="Simulation source and status">
          <span className="status-pill signal-ready">
            <RadioTower size={15} />
            {sourceLabel(source)}
          </span>
          <span className={`status-pill ${platformStatusClass(simulationData.simulation_status)}`}>
            <ShieldCheck size={15} />
            {platformStatusLabel(simulationData.simulation_status)}
          </span>
          <span className="mono">{formatOverviewTimestamp(simulationData.as_of)}</span>
        </div>
      </section>

      <div className="metric-grid">
        {simulationData.metrics.map((metric) => (
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

      <div className="simulation-layout">
        <section className="panel">
          <div className="audit-list-header">
            <div>
              <p className="section-label">Artifacts</p>
              <h2 className="panel-title">{simulationData.artifacts.length} replay previews</h2>
            </div>
            <span className="status-pill signal-watch">
              <GitBranch size={15} />
              {changedPolicies + changedPolicySetDiffs} changed
            </span>
          </div>

          <div className="workflow-list">
            {simulationData.artifacts.map((artifact) => {
              const isSelected = artifact.artifact_id === selectedArtifact.artifact_id;

              return (
                <button
                  aria-pressed={isSelected}
                  className={`workflow-list-item${isSelected ? " active" : ""}`}
                  key={artifact.artifact_id}
                  onClick={() => setSelectedArtifactId(artifact.artifact_id)}
                  type="button"
                >
                  <span>
                    <span className="row-title">{artifact.workflow_name}</span>
                    <span className="row-detail mono">{artifact.workflow_id}</span>
                    <span className="row-detail">
                      {artifact.timeline_event_count + artifact.audit_event_count} evidence events
                    </span>
                  </span>
                  <span className="status-pill signal-watch">
                    {formatSimulationLabel(artifact.determinism_status)}
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="panel simulation-detail">
          <div className="workflow-detail-header">
            <div>
              <p className="section-label">{selectedArtifact.replay_mode}</p>
              <h2 className="panel-title">{selectedArtifact.workflow_name}</h2>
              <p className="row-detail mono">{selectedArtifact.artifact_id}</p>
            </div>
            <div className="status-stack">
              <span className="status-pill signal-watch">
                {formatSimulationLabel(selectedArtifact.determinism_status)}
              </span>
              <span className="status-pill status-checking">{selectedArtifact.audit_scope}</span>
            </div>
          </div>

          <div className="simulation-detail-grid">
            <div>
              <p className="metric-label">Timeline</p>
              <p className="row-title">{selectedArtifact.timeline_event_count}</p>
              <p className="row-detail">workflow history events</p>
            </div>
            <div>
              <p className="metric-label">Audit</p>
              <p className="row-title">{selectedArtifact.audit_event_count}</p>
              <p className="row-detail">ledger events</p>
            </div>
            <div>
              <p className="metric-label">Policy</p>
              <p className="row-title mono">{primaryPolicy.policy_id}</p>
              <p className="row-detail">{primaryPolicy.simulated_decision}</p>
            </div>
            <div>
              <p className="metric-label">Replay Ready</p>
              <p className="row-title">{selectedArtifact.replay_ready ? "Yes" : "No"}</p>
              <p className="row-detail">preview foundation</p>
            </div>
          </div>

          <section className="simulation-policy-band">
            <div>
              <p className="section-label">Policy Simulation</p>
              <h3 className="subsection-title">{primaryPolicy.policy_name}</h3>
              <p className="row-detail">{primaryPolicy.summary}</p>
            </div>
            <div className="payload-grid">
              <div className="payload-row">
                <span className="metric-label">Baseline</span>
                <span className="mono">{primaryPolicy.baseline_decision}</span>
              </div>
              <div className="payload-row">
                <span className="metric-label">Simulated</span>
                <span className="mono">{primaryPolicy.simulated_decision}</span>
              </div>
              <div className="payload-row">
                <span className="metric-label">Outcome Change</span>
                <span className="mono">{primaryPolicy.changed_outcome ? "yes" : "no"}</span>
              </div>
            </div>
          </section>

          {primaryPolicySetDiff ? (
            <section className="simulation-policy-band">
              <div>
                <p className="section-label">Policy Set Diff</p>
                <h3 className="subsection-title">{primaryPolicySetDiff.connector_id}</h3>
                <p className="row-detail">{primaryPolicySetDiff.summary}</p>
              </div>
              <div className="payload-grid">
                <div className="payload-row">
                  <span className="metric-label">Baseline Set</span>
                  <span className="mono">
                    {primaryPolicySetDiff.baseline_policy_set_id} /{" "}
                    {primaryPolicySetDiff.baseline_policy_set_version}
                  </span>
                </div>
                <div className="payload-row">
                  <span className="metric-label">Candidate Set</span>
                  <span className="mono">
                    {primaryPolicySetDiff.candidate_policy_set_id} /{" "}
                    {primaryPolicySetDiff.candidate_policy_set_version}
                  </span>
                </div>
                <div className="payload-row">
                  <span className="metric-label">Diff Status</span>
                  <span className="mono">{primaryPolicySetDiff.diff_status}</span>
                </div>
                <div className="payload-row">
                  <span className="metric-label">Audit Event</span>
                  <span className="mono">{primaryPolicySetDiff.audit_event_type}</span>
                </div>
                <div className="payload-row">
                  <span className="metric-label">Changed Policies</span>
                  <span className="mono">{primaryPolicySetDiff.changed_policy_ids.join(", ")}</span>
                </div>
              </div>
            </section>
          ) : null}

          <div className="workflow-columns">
            <section>
              <p className="section-label">Evidence</p>
              <div className="tag-list">
                {selectedArtifact.evidence_refs.slice(0, 10).map((ref) => (
                  <span className="tag" key={ref}>
                    {ref}
                  </span>
                ))}
              </div>
            </section>
            <section>
              <p className="section-label">Audit Event Types</p>
              <div className="tag-list">
                {selectedArtifact.audit_events.slice(0, 8).map((event) => (
                  <span className="tag" key={event.audit_event_id}>
                    {event.event_type}
                  </span>
                ))}
              </div>
            </section>
            <section>
              <p className="section-label">Mode</p>
              <div className="tag-list">
                <span className="tag">{selectedArtifact.replay_mode}</span>
                <span className="tag">{selectedArtifact.determinism_status}</span>
              </div>
            </section>
          </div>

          <section className="workflow-history">
            <div className="workflow-history-header">
              <div>
                <p className="section-label">Replay Trace</p>
                <h3 className="subsection-title">Timeline evidence</h3>
              </div>
              <span className="status-pill signal-ready">
                <History size={15} />
                {selectedArtifact.timeline.length} events
              </span>
            </div>
            <div className="timeline">
              {selectedArtifact.timeline.map((event, index) => (
                <div className="timeline-item" key={`${event.event}-${event.at}`}>
                  <div className="timeline-index">{index + 1}</div>
                  <div className="row">
                    <div>
                      <p className="row-title mono">{event.event}</p>
                      <p className="row-detail">
                        {formatReplayTime(event.at)} / {event.actor} / {event.result}
                      </p>
                      <p className="row-detail">{event.summary}</p>
                    </div>
                    <FileText size={18} aria-label={event.result} />
                  </div>
                </div>
              ))}
            </div>
          </section>
        </section>
      </div>

      <section className="panel">
        <div className="audit-list-header">
          <div>
            <p className="section-label">Persisted Outputs</p>
            <h2 className="panel-title">{persistedOutputs.length} governed output</h2>
          </div>
          <span className="status-pill signal-ready">
            <FileText size={15} />
            audit-backed
          </span>
        </div>
        <div className="payload-grid">
          {persistedOutputs.length ? (
            persistedOutputs.map((output) => (
              <div className="payload-row" key={output.simulation_output_id}>
                <span>
                  <span className="metric-label">{output.simulation_output_id}</span>
                  <span className="row-detail mono">{output.audit_event_type}</span>
                </span>
                <span className="mono">{output.output_hash.slice(0, 12)}</span>
              </div>
            ))
          ) : (
            <div className="payload-row">
              <span className="metric-label">No persisted output</span>
              <span className="mono">preview-only</span>
            </div>
          )}
        </div>
        {persistedOutputs.map((output) => (
          <div className="simulation-detail-grid" key={`${output.simulation_output_id}-detail`}>
            <div>
              <p className="metric-label">Workflow</p>
              <p className="row-title">{output.workflow_id}</p>
              <p className="row-detail mono">{output.artifact_id}</p>
            </div>
            <div>
              <p className="metric-label">Retention</p>
              <p className="row-title">{output.retention_window_days} days</p>
              <p className="row-detail">{output.status}</p>
            </div>
            <div>
              <p className="metric-label">Requested By</p>
              <p className="row-title">{output.requested_by}</p>
              <p className="row-detail">{output.permission_decision.reason}</p>
            </div>
            <div>
              <p className="metric-label">Audit</p>
              <p className="row-title">{output.audit_event_id ?? "pending"}</p>
              <p className="row-detail">{output.required_scope}</p>
            </div>
          </div>
        ))}
      </section>

      <section className="panel">
        <p className="section-label">Simulation Notes</p>
        <div className="stack">
          {simulationData.simulation_notes.map((note) => (
            <p className="row-detail" key={note}>
              {note}
            </p>
          ))}
        </div>
      </section>
    </div>
  );
}
