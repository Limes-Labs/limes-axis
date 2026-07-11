"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  ChevronDown,
  ChevronRight,
  History,
  RadioTower,
  Route,
  TimerReset,
  Workflow,
} from "lucide-react";

import { PlatformStatusPill } from "@/components/status-pill";
import { Card } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { DataTable } from "@/components/ui/data-table";
import { DetailGrid, KeyValueRow } from "@/components/ui/detail-grid";
import { Eyebrow } from "@/components/ui/eyebrow";
import { FilterBar, type FilterDef } from "@/components/ui/filter-bar";
import { Term } from "@/components/ui/glossary";
import { InspectDrawer } from "@/components/ui/inspect-drawer";
import { MasterDetail } from "@/components/ui/master-detail";
import { MetricStrip, type Metric } from "@/components/ui/metric-strip";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/states";
import { cn } from "@/lib/cn";
import {
  formatOverviewTimestamp,
  platformStatusClass,
  platformStatusLabel,
  type PlatformStatus,
} from "@/lib/platform-overview";
import { strings } from "@/lib/strings";
import { useAxisQuery } from "@/lib/use-axis-query";
import {
  allWorkflowFilter,
  filterWorkflows,
  formatWorkflowRelativeTime,
  formatWorkflowState,
  shouldUsePersistedWorkflowData,
  workflowBlockingApprovalId,
  workflowFilterOptions,
  workflowStatusLine,
  workflowTimelineTone,
  type ManufacturingWorkflowConsole,
  type WorkflowFilters,
  type WorkflowRun,
} from "@/lib/workflow-demo";

export const WORKFLOW_RUNS_ENDPOINT =
  "/demo/manufacturing/workflows/runs?tenant_id=tenant_demo_manufacturing&limit=100";
export const WORKFLOW_REFERENCE_ENDPOINT = "/demo/manufacturing/workflows";

type WorkflowSource = "loading" | "persisted" | "api" | "unavailable";

const defaultFilters: WorkflowFilters = {
  state: allWorkflowFilter,
  domain: allWorkflowFilter,
};

function sourceLabel(source: WorkflowSource): string {
  if (source === "persisted") {
    return "Persisted workflow runs";
  }

  if (source === "api") {
    return "API workflow records";
  }

  return source === "loading" ? "Loading workflow API" : "Workflow API unavailable";
}

const metricTones: Record<PlatformStatus, Metric["tone"]> = {
  ready: "ready",
  watch: "watch",
  action_required: "action",
};

const toneDotClass: Record<PlatformStatus, string> = {
  ready: "bg-positive",
  watch: "bg-warning",
  action_required: "bg-danger",
};

/** Traffic-light tone for the list's state dot, derived from the run status. */
function runStatusToneClass(status: PlatformStatus): string {
  if (status === "action_required") {
    return "text-danger";
  }
  return status === "watch" ? "text-warning" : "text-positive";
}

function buildFilterDefs(workflowData: ManufacturingWorkflowConsole): FilterDef[] {
  const options = workflowFilterOptions(workflowData);
  const copy = strings.workflows.filters;

  return [
    {
      id: "state",
      label: copy.state,
      options: [
        { value: allWorkflowFilter, label: copy.allStates },
        ...options.states.map((state) => ({ value: state, label: formatWorkflowState(state) })),
      ],
    },
    {
      id: "domain",
      label: copy.domain,
      options: [
        { value: allWorkflowFilter, label: copy.allDomains },
        ...options.domains.map((domain) => ({ value: domain, label: domain })),
      ],
    },
  ];
}

function formatWorkflowTime(value: string): string {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

/**
 * Prominent banner for a blocked run. Links to /approvals and names the
 * blocking approval when the record's pending signals carry its id.
 */
function BlockerBanner({ workflow }: { workflow: WorkflowRun }) {
  const approvalId = workflowBlockingApprovalId(workflow);
  const copy = strings.workflows.blocker;

  return (
    <div
      aria-label="Current blocker"
      className="flex items-start gap-3 rounded-2xl border border-warning/50 bg-warning/10 p-4"
      role="status"
    >
      <TimerReset aria-hidden="true" className="mt-0.5 shrink-0 text-warning" size={18} />
      <div className="grid min-w-0 gap-1">
        <p className="m-0 text-sm font-semibold text-ink">{copy.title}</p>
        <p className="m-0 text-sm text-muted">{workflow.blocker}</p>
        <Link
          className="mt-1 inline-flex flex-wrap items-center gap-1.5 text-sm font-medium text-signal underline-offset-2 hover:underline"
          href="/approvals"
        >
          {approvalId ? (
            <>
              {copy.linkNamed}
              <span className="font-mono text-xs">{approvalId}</span>
            </>
          ) : (
            copy.linkGeneric
          )}
          <ArrowRight aria-hidden="true" size={14} />
        </Link>
      </div>
    </div>
  );
}

/** The visual centerpiece: the recorded runtime history with tone dots. */
function RuntimeTimeline({ workflow }: { workflow: WorkflowRun }) {
  const copy = strings.workflows.timeline;
  const waitingSignals = workflow.pending_signals.filter(
    (signal) => signal.status === "waiting",
  ).length;

  return (
    <section className="grid content-start gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="grid gap-1">
          <Eyebrow>{copy.eyebrow}</Eyebrow>
          <h3 className="font-display m-0 text-lg text-ink">{copy.title}</h3>
        </div>
        <span className="status-pill signal-watch">
          <History size={15} />
          {waitingSignals} {copy.waiting}
        </span>
      </div>
      <DataTable aria-label="Workflow runtime timeline" minWidth={560}>
        <thead>
          <tr>
            <th>{copy.columns.step}</th>
            <th>{copy.columns.result}</th>
            <th>{copy.columns.when}</th>
            <th>{copy.columns.summary}</th>
          </tr>
        </thead>
        <tbody>
          {workflow.timeline.map((event) => (
            <tr key={`${event.event}-${event.at}`}>
              <td>
                <span className="grid min-w-0 gap-0.5">
                  <span className="inline-flex items-center gap-2 font-mono text-xs text-ink">
                    <span
                      aria-hidden="true"
                      className={cn(
                        "inline-block size-2 shrink-0 rounded-full",
                        toneDotClass[workflowTimelineTone(event)],
                      )}
                    />
                    {event.event}
                  </span>
                  <span className="pl-4 text-xs text-muted">{event.actor}</span>
                </span>
              </td>
              <td className="text-xs text-muted">{event.result}</td>
              <td>
                <span
                  className="font-mono text-xs whitespace-nowrap text-muted"
                  title={formatWorkflowTime(event.at)}
                >
                  {formatWorkflowRelativeTime(event.at)}
                </span>
              </td>
              <td className="text-xs text-muted">{event.summary}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
    </section>
  );
}

function CollapsibleSection({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const Chevron = open ? ChevronDown : ChevronRight;

  return (
    <Collapsible onOpenChange={setOpen} open={open}>
      <CollapsibleTrigger className="flex cursor-pointer items-center gap-1.5 bg-transparent p-0">
        <Chevron aria-hidden="true" className="text-muted" size={14} />
        <span className="eyebrow">{label}</span>
      </CollapsibleTrigger>
      <CollapsibleContent className="pt-2 pl-5.5">{children}</CollapsibleContent>
    </Collapsible>
  );
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="m-0 grid list-none gap-1.5 p-0 text-sm text-muted">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function ChipList({ items }: { items: string[] }) {
  return (
    <div className="flex min-w-0 flex-wrap gap-2">
      {items.map((item) => (
        <span
          className="inline-flex max-w-full min-w-0 items-center rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs break-words text-muted dark:border-white/15 dark:bg-transparent"
          key={item}
        >
          {item}
        </span>
      ))}
    </div>
  );
}

function PendingSignals({ workflow }: { workflow: WorkflowRun }) {
  const copy = strings.workflows.detail;

  if (workflow.pending_signals.length === 0) {
    return <span className="text-muted">{copy.noSignals}</span>;
  }

  return (
    <div className="grid min-w-0 gap-2.5">
      {workflow.pending_signals.map((signal) => (
        <div className="flex flex-wrap items-start justify-between gap-2" key={signal.signal}>
          <span className="grid min-w-0 gap-0.5">
            <span className="font-mono text-xs break-words text-ink">{signal.signal}</span>
            <span className="text-xs text-muted">
              {signal.required_role}
              {signal.approval_id ? ` / ${signal.approval_id}` : ""}
            </span>
          </span>
          <span className="status-pill signal-action-required">{signal.status}</span>
        </div>
      ))}
    </div>
  );
}

/**
 * Workflow detail pane: plain-language status, blocker banner, the runtime
 * timeline as the centerpiece, collapsed record sections, and the raw record
 * behind an Inspect drawer.
 */
function WorkflowDetail({ workflow }: { workflow: WorkflowRun }) {
  const copy = strings.workflows;

  return (
    <Card className="grid content-start gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid max-w-xl gap-1">
          <Eyebrow>{workflow.domain}</Eyebrow>
          <h2 className="font-display m-0 text-xl text-ink">{workflow.name}</h2>
          <p className="m-0 text-sm text-muted">{workflow.objective}</p>
          <p className="m-0 text-sm text-ink">{workflowStatusLine(workflow)}</p>
        </div>
        <span className={`status-pill ${platformStatusClass(workflow.status)}`}>
          {formatWorkflowState(workflow.state)}
        </span>
      </div>

      {workflow.blocker ? <BlockerBanner workflow={workflow} /> : null}

      <RuntimeTimeline workflow={workflow} />

      <div className="grid gap-3">
        <CollapsibleSection label={copy.sections.inputs}>
          <BulletList items={workflow.inputs} />
        </CollapsibleSection>
        <CollapsibleSection label={copy.sections.outputs}>
          <BulletList items={workflow.proposed_outputs} />
        </CollapsibleSection>
        <CollapsibleSection label={copy.sections.context}>
          <ChipList items={[workflow.related_risk, ...workflow.related_assets]} />
        </CollapsibleSection>
      </div>

      <div aria-hidden="true" className="rule-dotted" />

      <DetailGrid>
        <KeyValueRow label={copy.detail.runtime}>
          {workflow.runtime}
          <span className="block font-mono text-xs text-muted">{workflow.adapter}</span>
        </KeyValueRow>
        <KeyValueRow label={copy.detail.owner}>
          {workflow.owner_role} / <Term k="autonomy_level">{workflow.autonomy_level}</Term>
        </KeyValueRow>
        <KeyValueRow label={copy.detail.started}>
          {formatWorkflowTime(workflow.started_at)}
        </KeyValueRow>
        <KeyValueRow label={copy.detail.expected}>{workflow.eta}</KeyValueRow>
        <KeyValueRow label={copy.detail.auditScope} mono>
          {workflow.audit_scope}
        </KeyValueRow>
        <KeyValueRow label={copy.detail.replay}>
          <Term k="replay">
            {workflow.replay_ready ? copy.detail.replayReady : copy.detail.replayNotReady}
          </Term>
        </KeyValueRow>
        <KeyValueRow label={copy.detail.signals}>
          <PendingSignals workflow={workflow} />
        </KeyValueRow>
        <KeyValueRow label={copy.detail.controls}>
          <ChipList items={workflow.controls} />
        </KeyValueRow>
      </DetailGrid>

      <InspectDrawer
        record={workflow}
        title={workflow.name}
        trigger={
          <button
            className="inline-flex w-fit cursor-pointer items-center font-mono text-xs text-muted transition-colors duration-200 hover:text-signal"
            type="button"
          >
            {copy.inspect}
          </button>
        }
      />
    </Card>
  );
}

export function WorkflowConsole() {
  const persisted = useAxisQuery<ManufacturingWorkflowConsole>(WORKFLOW_RUNS_ENDPOINT);
  const usePersisted = persisted.data !== null && shouldUsePersistedWorkflowData(persisted.data);
  // The persisted-runs endpoint wins whenever it has records; the reference
  // registry is only consulted when the API answered with zero persisted runs.
  const referenceEnabled = persisted.source === "api" && persisted.data !== null && !usePersisted;
  const reference = useAxisQuery<ManufacturingWorkflowConsole>(WORKFLOW_REFERENCE_ENDPOINT, {
    enabled: referenceEnabled,
  });

  const [filters, setFilters] = useState<WorkflowFilters>(defaultFilters);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState("");

  let workflowData: ManufacturingWorkflowConsole | null = null;
  let source: WorkflowSource = "loading";
  if (usePersisted) {
    workflowData = persisted.data;
    source = "persisted";
  } else if (referenceEnabled && reference.source === "api") {
    workflowData = reference.data;
    source = "api";
  } else if (
    persisted.source === "unavailable"
    || (referenceEnabled && reference.source === "unavailable")
  ) {
    source = "unavailable";
  }

  const filteredWorkflows = useMemo(
    () => (workflowData ? filterWorkflows(workflowData, filters) : []),
    [workflowData, filters],
  );

  if (!workflowData) {
    if (source === "loading") {
      return (
        <div aria-label="Loading workflow API" className="grid gap-4">
          <LoadingPanel layout="metrics" rows={4} />
          <MasterDetail
            detail={<LoadingPanel layout="detail" />}
            list={<LoadingPanel rows={4} />}
          />
        </div>
      );
    }

    return (
      <ErrorPanel
        detail={strings.workflows.error.detail}
        endpoint={WORKFLOW_RUNS_ENDPOINT}
        title={strings.workflows.error.title}
      />
    );
  }

  if (workflowData.workflow_runs.length === 0) {
    return (
      <EmptyPanel
        detail={strings.workflows.empty.detail}
        icon={Workflow}
        title={strings.workflows.empty.title}
      />
    );
  }

  const selectedWorkflow =
    filteredWorkflows.find((run) => run.workflow_id === selectedWorkflowId)
    ?? filteredWorkflows[0];

  const metrics: Metric[] = workflowData.metrics.map((metric) => ({
    label: metric.label,
    value: metric.value,
    detail: metric.detail,
    tone: metricTones[metric.status],
  }));

  return (
    <div className="grid gap-4">
      <div
        aria-label="Workflow source and runtime status"
        className="flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-2"
      >
        <p className="m-0 min-w-0 text-sm break-words text-muted">
          {workflowData.plant_name} / {workflowData.scenario} / {workflowData.tenant_id}
        </p>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
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
      </div>

      {metrics.length > 0 ? <MetricStrip metrics={metrics} /> : null}

      <FilterBar
        filters={buildFilterDefs(workflowData)}
        values={{ state: filters.state, domain: filters.domain }}
        onChange={(id, value) => {
          if (id === "state" || id === "domain") {
            setFilters((current) => ({ ...current, [id]: value }));
          }
        }}
        onReset={() => setFilters(defaultFilters)}
      />

      {filteredWorkflows.length === 0 || !selectedWorkflow ? (
        <EmptyPanel
          action={{
            label: strings.workflows.noMatch.reset,
            onClick: () => setFilters(defaultFilters),
          }}
          detail={strings.workflows.noMatch.detail}
          title={strings.workflows.noMatch.title}
        />
      ) : (
        <MasterDetail
          detail={<WorkflowDetail workflow={selectedWorkflow} />}
          list={
            <Card className="grid content-start gap-4">
              <div className="grid gap-1">
                <Eyebrow>{strings.workflows.list.eyebrow}</Eyebrow>
                <h2 className="font-display m-0 text-xl text-ink">
                  {filteredWorkflows.length} visible
                </h2>
              </div>
              <div className="grid gap-2">
                {filteredWorkflows.map((run) => {
                  const isSelected = run.workflow_id === selectedWorkflow.workflow_id;

                  return (
                    <button
                      aria-pressed={isSelected}
                      className={cn(
                        "flex w-full cursor-pointer items-start justify-between gap-3 rounded-2xl border px-4 py-3 text-left transition-colors",
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
                        <span className="text-xs text-muted">{run.domain}</span>
                        <span className="flex items-center gap-1.5 text-xs text-muted">
                          <span
                            aria-hidden="true"
                            className={cn("status-dot", runStatusToneClass(run.status))}
                          />
                          {formatWorkflowState(run.state)}
                        </span>
                      </span>
                      <PlatformStatusPill status={run.status} />
                    </button>
                  );
                })}
              </div>
            </Card>
          }
        />
      )}

      {workflowData.runtime_notes.length > 0 ? (
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
      ) : null}
    </div>
  );
}
