"use client";

import { useEffect, useMemo, useState } from "react";
import { GitBranch, History, RadioTower, Route, TimerReset } from "lucide-react";

import { ApiRequiredState } from "@/components/api-required-state";
import { PlatformStatusPill } from "@/components/status-pill";
import { Card } from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import { Eyebrow } from "@/components/ui/eyebrow";
import { Skeleton } from "@/components/ui/skeleton";
import { axisFetchJson } from "@/lib/axis-api";
import { cn } from "@/lib/cn";
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

function DetailField({ label, title, detail, mono = false }: {
  label: string;
  title: string;
  detail: string;
  mono?: boolean;
}) {
  return (
    <div className="grid content-start gap-1">
      <Eyebrow>{label}</Eyebrow>
      <p className={cn("m-0 text-sm text-ink", mono && "font-mono break-words")}>{title}</p>
      <p className="m-0 text-xs text-muted">{detail}</p>
    </div>
  );
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
    if (source === "loading") {
      return (
        <div className="grid gap-5" aria-busy="true" aria-label="Loading workflow API">
          <Skeleton className="h-28" />
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Skeleton className="h-28" />
            <Skeleton className="h-28" />
            <Skeleton className="h-28" />
            <Skeleton className="h-28" />
          </div>
          <div className="grid gap-4 xl:grid-cols-[2fr_3fr]">
            <Skeleton className="h-96" />
            <Skeleton className="h-96" />
          </div>
        </div>
      );
    }

    return (
      <ApiRequiredState
        detail="Axis did not receive API-backed workflow records. Local fallback workflow records are disabled."
        endpoint="/demo/manufacturing/workflows/runs"
        title="Workflow API unavailable"
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
    <div className="grid gap-5">
      <Card className="flex flex-wrap items-start justify-between gap-4">
        <div className="grid gap-1">
          <Eyebrow>Demo Workflow Runtime</Eyebrow>
          <h2 className="font-display m-0 text-2xl text-ink">{workflowData.plant_name}</h2>
          <p className="m-0 text-sm text-muted">
            {workflowData.scenario} / {workflowData.tenant_id}
          </p>
        </div>
        <div
          className="flex flex-wrap items-center gap-2"
          aria-label="Workflow source and runtime status"
        >
          <span className="status-pill signal-ready">
            <RadioTower size={15} />
            {sourceLabel(source)}
          </span>
          <span className={`status-pill ${platformStatusClass(workflowData.runtime_status)}`}>
            <Route size={15} />
            {platformStatusLabel(workflowData.runtime_status)}
          </span>
          <span className="font-mono text-xs text-muted">
            {formatOverviewTimestamp(workflowData.as_of)}
          </span>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {workflowData.metrics.map((metric) => (
          <Card className="grid content-start gap-2 p-5" key={metric.label}>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <Eyebrow>{metric.label}</Eyebrow>
              <PlatformStatusPill status={metric.status} />
            </div>
            <p className="font-display m-0 text-3xl text-ink">{metric.value}</p>
            <div aria-hidden="true" className="rule-dotted" />
            <p className="m-0 text-xs text-muted">{metric.detail}</p>
          </Card>
        ))}
      </div>

      <div className="grid items-start gap-4 xl:grid-cols-[2fr_3fr]">
        <Card className="grid content-start gap-4">
          <div className="grid gap-1">
            <Eyebrow>Runs</Eyebrow>
            <h2 className="font-display m-0 text-xl text-ink">Workflow console</h2>
          </div>
          <div className="grid gap-2">
            {workflowData.workflow_runs.map((run) => {
              const isSelected = run.workflow_id === selectedWorkflow.workflow_id;

              return (
                <button
                  aria-pressed={isSelected}
                  className={cn(
                    "flex w-full items-start justify-between gap-3 rounded-2xl border px-4 py-3 text-left transition-colors",
                    isSelected
                      ? "border-signal/60 bg-tint-100 dark:bg-signal/15"
                      : "border-line bg-transparent hover:border-signal/40 hover:bg-tint-50 dark:border-white/10 dark:hover:bg-white/5",
                  )}
                  key={run.workflow_id}
                  onClick={() => setSelectedWorkflowId(run.workflow_id)}
                  type="button"
                >
                  <span className="grid min-w-0 gap-0.5">
                    <span className="text-sm font-medium text-ink">{run.name}</span>
                    <span className="text-xs text-muted">
                      {run.domain} / {formatWorkflowState(run.state)}
                    </span>
                    <span className="font-mono text-xs text-muted">ETA {run.eta}</span>
                  </span>
                  <PlatformStatusPill status={run.status} />
                </button>
              );
            })}
          </div>
        </Card>

        <Card className="grid content-start gap-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="grid max-w-xl gap-1">
              <Eyebrow>{selectedWorkflow.domain}</Eyebrow>
              <h2 className="font-display m-0 text-xl text-ink">{selectedWorkflow.name}</h2>
              <p className="m-0 text-sm text-muted">{selectedWorkflow.objective}</p>
            </div>
            <div className="flex flex-col items-end gap-2">
              <span className={`status-pill ${platformStatusClass(selectedWorkflow.status)}`}>
                {formatWorkflowState(selectedWorkflow.state)}
              </span>
              <span className="status-pill status-checking">{selectedWorkflow.current_step}</span>
            </div>
          </div>

          <div aria-hidden="true" className="rule-dotted" />

          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <DetailField
              detail={selectedWorkflow.adapter}
              label="Runtime"
              title={selectedWorkflow.runtime}
            />
            <DetailField
              detail={selectedWorkflow.autonomy_level}
              label="Owner"
              title={selectedWorkflow.owner_role}
            />
            <DetailField
              detail={`ETA ${selectedWorkflow.eta}`}
              label="Started"
              title={formatWorkflowTime(selectedWorkflow.started_at)}
            />
            <DetailField
              detail="Replay preview only"
              label="Audit Scope"
              mono
              title={selectedWorkflow.audit_scope}
            />
          </div>

          {selectedWorkflow.blocker ? (
            <div className="flex items-start gap-3 rounded-2xl border border-warning/40 bg-warning/8 p-4">
              <TimerReset className="mt-0.5 shrink-0 text-warning" size={18} />
              <div className="grid gap-0.5">
                <p className="m-0 text-sm font-medium text-ink">Current blocker</p>
                <p className="m-0 text-xs text-muted">{selectedWorkflow.blocker}</p>
              </div>
            </div>
          ) : null}

          <div className="grid gap-4 sm:grid-cols-3">
            <section className="grid content-start gap-2">
              <Eyebrow>Inputs</Eyebrow>
              <ul className="m-0 grid list-none gap-1.5 p-0 text-sm text-muted">
                {selectedWorkflow.inputs.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
            <section className="grid content-start gap-2">
              <Eyebrow>Proposed Outputs</Eyebrow>
              <ul className="m-0 grid list-none gap-1.5 p-0 text-sm text-muted">
                {selectedWorkflow.proposed_outputs.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
            <section className="grid content-start gap-2">
              <Eyebrow>Related Context</Eyebrow>
              <div className="flex flex-wrap gap-2">
                <span className="inline-flex items-center rounded-full border border-line px-3 py-1 font-mono text-xs text-muted dark:border-white/15">
                  {selectedWorkflow.related_risk}
                </span>
                {selectedWorkflow.related_assets.map((asset) => (
                  <span
                    className="inline-flex items-center rounded-full border border-line px-3 py-1 font-mono text-xs text-muted dark:border-white/15"
                    key={asset}
                  >
                    {asset}
                  </span>
                ))}
              </div>
            </section>
          </div>

          <div className="grid gap-4 rounded-2xl border border-line bg-tint-50 p-4 sm:grid-cols-2 dark:border-white/10 dark:bg-white/5">
            <div className="grid content-start gap-3">
              <Eyebrow>Pending Signals</Eyebrow>
              <div className="grid gap-3">
                {selectedWorkflow.pending_signals.map((signal) => (
                  <div className="flex flex-wrap items-start justify-between gap-2" key={signal.signal}>
                    <div className="grid min-w-0 gap-0.5">
                      <p className="m-0 font-mono text-sm break-words text-ink">{signal.signal}</p>
                      <p className="m-0 text-xs text-muted">
                        {signal.required_role}
                        {signal.approval_id ? ` / ${signal.approval_id}` : ""}
                      </p>
                    </div>
                    <span className="status-pill signal-action-required">{signal.status}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="grid content-start gap-2">
              <Eyebrow>Controls</Eyebrow>
              <div className="flex flex-wrap gap-2">
                {selectedWorkflow.controls.map((control) => (
                  <span
                    className="inline-flex items-center rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted dark:border-white/15 dark:bg-transparent"
                    key={control}
                  >
                    {control}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <section className="grid content-start gap-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="grid gap-1">
                <Eyebrow>History Preview</Eyebrow>
                <h3 className="font-display m-0 text-lg text-ink">Runtime timeline</h3>
              </div>
              <span className="status-pill signal-watch">
                <History size={15} />
                {waitingSignals} waiting
              </span>
            </div>
            <DataTable aria-label="Workflow runtime timeline" minWidth={560}>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Event</th>
                  <th>At / Actor / Result</th>
                  <th>Summary</th>
                </tr>
              </thead>
              <tbody>
                {selectedWorkflow.timeline.map((event, index) => (
                  <tr key={`${event.event}-${event.at}`}>
                    <td className="font-mono text-xs text-muted">{index + 1}</td>
                    <td>
                      <span className="inline-flex items-center gap-2 font-mono text-xs text-ink">
                        <GitBranch aria-label={event.result} className="text-signal" size={14} />
                        {event.event}
                      </span>
                    </td>
                    <td className="text-xs text-muted">
                      {formatWorkflowTime(event.at)} / {event.actor} / {event.result}
                    </td>
                    <td className="text-xs text-muted">{event.summary}</td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          </section>
        </Card>
      </div>

      <Card className="grid content-start gap-3">
        <Eyebrow>Runtime Notes</Eyebrow>
        <div className="grid gap-2">
          {workflowData.runtime_notes.map((note) => (
            <p className="m-0 text-sm text-muted" key={note}>
              {note}
            </p>
          ))}
        </div>
      </Card>
    </div>
  );
}
