"use client";

import { useEffect, useMemo, useState } from "react";
import { Activity, Bot, Filter, History, RadioTower, RotateCcw, ShieldCheck } from "lucide-react";

import { ApiRequiredState } from "@/components/api-required-state";
import {
  allAgentFilter,
  countPendingAgentProposals,
  filterAgents,
  findAgentById,
  formatAgentLabel,
  type AgentFilters,
  type ManufacturingAgentRegistry,
} from "@/lib/agent-demo";
import {
  AGENT_RUN_EXECUTION_FLAG,
  agentRunStatusClass,
  agentRunStatusLabel,
  agentRunsPath,
  buildAgentRunRail,
  buildApprovalActionRunHref,
  isDeferredAgentRunStatus,
  modelInvocationDetailPath,
  parseAgentRunList,
  type AgentRunRailState,
  type AgentRunRecord,
} from "@/lib/agent-runs-live";
import { buildAuditEventHref } from "@/lib/audit-demo";
import { axisFetchJson } from "@/lib/axis-api";
import { cn } from "@/lib/cn";
import { formatModelRoutingLabel } from "@/lib/model-routing-demo";
import {
  formatLiveEuroCost,
  formatLiveTimestamp,
  parseModelInvocation,
  type LiveModelInvocation,
} from "@/lib/model-routing-live";
import {
  formatOverviewTimestamp,
  platformStatusClass,
  platformStatusLabel,
} from "@/lib/platform-overview";
import { useAxisQuery } from "@/lib/use-axis-query";
import { useOidcConsoleSession } from "@/lib/use-oidc-session";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";

const defaultFilters: AgentFilters = {
  domain: allAgentFilter,
  autonomyLevel: allAgentFilter,
  status: allAgentFilter,
};

function sourceLabel(source: "loading" | "api" | "unavailable"): string {
  if (source === "api") {
    return "API agent registry";
  }

  return source === "loading" ? "Loading agent API" : "Agent API unavailable";
}

export function AgentRegistry() {
  const { data: registry, source } = useAxisQuery<ManufacturingAgentRegistry>(
    "/demo/manufacturing/agents",
  );
  const [filters, setFilters] = useState<AgentFilters>(defaultFilters);
  const [selectedAgentId, setSelectedAgentId] = useState("");

  const filteredAgents = useMemo(
    () => (registry ? filterAgents(registry, filters) : []),
    [registry, filters],
  );
  const effectiveSelectedAgentId =
    registry && filteredAgents.some((agent) => agent.agent_id === selectedAgentId)
      ? selectedAgentId
      : (filteredAgents[0]?.agent_id ?? registry?.agents[0]?.agent_id ?? "");

  const selectedAgent = useMemo(
    () =>
      registry && registry.agents.length > 0
        ? findAgentById(registry, effectiveSelectedAgentId)
        : null,
    [registry, effectiveSelectedAgentId],
  );
  const proposalCount = registry ? countPendingAgentProposals(registry) : 0;

  function updateFilter(filterName: keyof AgentFilters, value: string) {
    setFilters((current) => ({
      ...current,
      [filterName]: value,
    }));
  }

  function resetFilters() {
    setFilters(defaultFilters);
  }

  if (!registry) {
    return (
      <div className="grid min-w-0 gap-4">
        <ApiRequiredState
          detail="Axis did not receive API-backed agent records. Local fallback agent records are disabled."
          endpoint="/demo/manufacturing/agents"
          title={source === "loading" ? "Loading agent API" : "Agent API unavailable"}
        />
        <ApiRequiredState
          detail="Live agent run records need the agent registry API first. Run timelines are never fabricated."
          endpoint="/demo/manufacturing/agents/{agent_id}/runs"
          title="Agent runs API unavailable"
        />
      </div>
    );
  }

  if (!selectedAgent) {
    return (
      <ApiRequiredState
        detail="The agent API responded without registry records for this tenant."
        endpoint="/demo/manufacturing/agents"
        title="Agent API returned no records"
      />
    );
  }

  return (
    <div className="grid min-w-0 gap-4">
      <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow m-0">Demo Agent Registry</p>
          <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{registry.plant_name}</h2>
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
            {registry.scenario} / {registry.tenant_id}
          </p>
        </div>
        <div className="flex min-w-0 flex-wrap items-center justify-end gap-2" aria-label="Agent source and registry status">
          <span className="status-pill signal-ready">
            <RadioTower size={15} />
            {sourceLabel(source)}
          </span>
          <span className={`status-pill ${platformStatusClass(registry.registry_status)}`}>
            <Bot size={15} />
            {platformStatusLabel(registry.registry_status)}
          </span>
          <span className="font-mono text-[13px] break-words">{formatOverviewTimestamp(registry.as_of)}</span>
        </div>
      </section>

      <div className="grid gap-3.5 sm:grid-cols-2 xl:grid-cols-4 [&>*]:min-w-0">
        {registry.metrics.map((metric) => (
          <article className="min-w-0 rounded-3xl border border-line bg-surface p-4 dark:border-white/10 dark:bg-white/5 min-h-[120px]" key={metric.label}>
            <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10">
              <p className="eyebrow m-0">{metric.label}</p>
              <span className={`status-pill ${platformStatusClass(metric.status)}`}>
                {platformStatusLabel(metric.status)}
              </span>
            </div>
            <p className="font-display mx-0 mt-4 mb-2 text-3xl text-ink">{metric.value}</p>
            <p className="m-0 text-xs leading-relaxed text-muted break-words">{metric.detail}</p>
          </article>
        ))}
      </div>

      <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow m-0">Filters</p>
          <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">Agent registry</h2>
        </div>
        <div className="grid w-full min-w-0 gap-2.5 sm:flex sm:w-auto sm:flex-wrap sm:items-end sm:justify-end">
          <Field label="Domain">
            <Select value={filters.domain} onChange={(event) => updateFilter("domain", event.target.value)}>
              <option value={allAgentFilter}>All domains</option>
              {registry.filter_options.domains.map((domain) => (
                <option key={domain} value={domain}>
                  {domain}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Autonomy">
            <Select
              value={filters.autonomyLevel}
              onChange={(event) => updateFilter("autonomyLevel", event.target.value)}
            >
              <option value={allAgentFilter}>All levels</option>
              {registry.filter_options.autonomy_levels.map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Status">
            <Select value={filters.status} onChange={(event) => updateFilter("status", event.target.value)}>
              <option value={allAgentFilter}>All statuses</option>
              {registry.filter_options.statuses.map((status) => (
                <option key={status} value={status}>
                  {formatAgentLabel(status)}
                </option>
              ))}
            </Select>
          </Field>
          <button className="icon-button" onClick={resetFilters} title="Reset filters" type="button">
            <RotateCcw size={17} />
          </button>
        </div>
      </section>

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(310px,0.46fr)_minmax(0,1fr)] [&>*]:min-w-0">
        <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
          <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
            <div>
              <p className="eyebrow m-0">Agents</p>
              <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{filteredAgents.length} visible</h2>
            </div>
            <span className="status-pill signal-watch">
              <Filter size={15} />
              {proposalCount} proposals
            </span>
          </div>
          <div className="grid">
            {filteredAgents.map((agent) => {
              const isSelected = agent.agent_id === selectedAgent.agent_id;

              return (
                <button
                  aria-pressed={isSelected}
                  className={`grid w-full cursor-pointer grid-cols-[minmax(0,1fr)_auto] items-center gap-3.5 border-0 border-t border-line/60 bg-transparent px-2.5 py-3.5 text-left text-ink transition-colors first:border-t-0 hover:bg-ink/4 dark:border-white/10 dark:hover:bg-white/6${isSelected ? " bg-signal/10 shadow-[inset_2px_0_0_rgb(var(--signal))] dark:bg-signal/15" : ""}`}
                  key={agent.agent_id}
                  onClick={() => setSelectedAgentId(agent.agent_id)}
                  type="button"
                >
                  <span>
                    <span className="m-0 font-medium text-ink break-words">{agent.name}</span>
                    <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                      {agent.domain} / {agent.owner_role}
                    </span>
                    <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{formatAgentLabel(agent.status)}</span>
                  </span>
                  <span className="status-pill signal-watch">
                    {agent.policy_boundary.autonomy_level}
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 grid gap-4">
          <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
            <div>
              <p className="eyebrow m-0">{selectedAgent.domain}</p>
              <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{selectedAgent.name}</h2>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{selectedAgent.purpose}</p>
            </div>
            <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">
              <span className="status-pill signal-watch">
                {selectedAgent.policy_boundary.autonomy_level}
              </span>
              <span className="status-pill status-checking">
                {formatAgentLabel(selectedAgent.status)}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3.5 border-y border-line/60 py-3.5 xl:grid-cols-4 dark:border-white/10 [&>*]:min-w-0">
            <div>
              <p className="eyebrow m-0">Owner</p>
              <p className="m-0 font-medium text-ink break-words">{selectedAgent.owner_role}</p>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{selectedAgent.agent_id}</p>
            </div>
            <div>
              <p className="eyebrow m-0">Model Policy</p>
              <p className="m-0 font-medium text-ink break-words">{selectedAgent.policy_boundary.model_policy}</p>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                Egress {selectedAgent.policy_boundary.external_egress_allowed ? "allowed" : "blocked"}
              </p>
            </div>
            <div>
              <p className="eyebrow m-0">Max Action</p>
              <p className="m-0 font-medium text-ink break-words">{selectedAgent.policy_boundary.max_action_level}</p>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">Policy boundary</p>
            </div>
            <div>
              <p className="eyebrow m-0">Last Audit</p>
              <p className="m-0 font-medium text-ink break-words font-mono text-[13px]">{selectedAgent.last_audit_event}</p>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">Evidence-linked</p>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-3 [&>*]:min-w-0">
            <section>
              <p className="eyebrow m-0">Connected Systems</p>
              <div className="flex min-w-0 flex-wrap gap-2">
                {selectedAgent.connected_systems.map((system) => (
                  <span className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted break-words transition-colors enabled:cursor-pointer aria-pressed:border-signal aria-pressed:bg-signal/10 aria-pressed:text-signal dark:border-white/15 dark:bg-white/5" key={system}>
                    {system}
                  </span>
                ))}
              </div>
            </section>
            <section>
              <p className="eyebrow m-0">Data Access</p>
              <ul className="mx-0 mt-2.5 mb-0 grid list-disc gap-2 pl-5 text-sm leading-snug text-muted">
                {selectedAgent.data_access.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
            <section>
              <p className="eyebrow m-0">Evidence</p>
              <div className="flex min-w-0 flex-wrap gap-2">
                {selectedAgent.evidence_refs.map((item) => (
                  <span className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted break-words transition-colors enabled:cursor-pointer aria-pressed:border-signal aria-pressed:bg-signal/10 aria-pressed:text-signal dark:border-white/15 dark:bg-white/5" key={item}>
                    {item}
                  </span>
                ))}
              </div>
            </section>
          </div>

          <div className="grid gap-4 border-y border-line/60 py-3.5 dark:border-white/10 lg:grid-cols-[minmax(0,0.7fr)_minmax(260px,1fr)] [&>*]:min-w-0">
            <section>
              <p className="eyebrow m-0">Required Permissions</p>
              <div className="flex min-w-0 flex-wrap gap-2">
                {selectedAgent.policy_boundary.required_permissions.map((permission) => (
                  <span className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted break-words transition-colors enabled:cursor-pointer aria-pressed:border-signal aria-pressed:bg-signal/10 aria-pressed:text-signal dark:border-white/15 dark:bg-white/5" key={permission}>
                    {permission}
                  </span>
                ))}
              </div>
            </section>
            <section>
              <p className="eyebrow m-0">Guardrails</p>
              <ul className="mx-0 mt-2.5 mb-0 grid list-disc gap-2 pl-5 text-sm leading-snug text-muted">
                {selectedAgent.policy_boundary.guardrails.map((guardrail) => (
                  <li key={guardrail}>{guardrail}</li>
                ))}
              </ul>
            </section>
          </div>

          <div className="grid gap-4 lg:grid-cols-3 [&>*]:min-w-0">
            <section>
              <p className="eyebrow m-0">Allowed Actions</p>
              <ul className="mx-0 mt-2.5 mb-0 grid list-disc gap-2 pl-5 text-sm leading-snug text-muted">
                {selectedAgent.allowed_actions.map((action) => (
                  <li key={action}>{action}</li>
                ))}
              </ul>
            </section>
            <section>
              <p className="eyebrow m-0">Blocked Actions</p>
              <ul className="mx-0 mt-2.5 mb-0 grid list-disc gap-2 pl-5 text-sm leading-snug text-muted">
                {selectedAgent.blocked_actions.map((action) => (
                  <li key={action}>{action}</li>
                ))}
              </ul>
            </section>
            <section>
              <p className="eyebrow m-0">Workflow Links</p>
              <div className="flex min-w-0 flex-wrap gap-2">
                {selectedAgent.active_workflows.map((workflow) => (
                  <span className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted break-words transition-colors enabled:cursor-pointer aria-pressed:border-signal aria-pressed:bg-signal/10 aria-pressed:text-signal dark:border-white/15 dark:bg-white/5" key={workflow}>
                    {workflow}
                  </span>
                ))}
                {selectedAgent.pending_approvals.map((approval) => (
                  <span className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted break-words transition-colors enabled:cursor-pointer aria-pressed:border-signal aria-pressed:bg-signal/10 aria-pressed:text-signal dark:border-white/15 dark:bg-white/5" key={approval}>
                    {approval}
                  </span>
                ))}
              </div>
            </section>
          </div>

          <section className="grid min-w-0 gap-3 border-t border-line/60 pt-3.5 dark:border-white/10">
            <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
              <div>
                <p className="eyebrow m-0">Proposals</p>
                <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">Read-only action proposals</h3>
              </div>
              <ShieldCheck size={18} />
            </div>
            <div className="grid min-w-0 gap-2.5">
              {selectedAgent.proposals.map((proposal) => (
                <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10" key={proposal.proposal_id}>
                  <div>
                    <p className="m-0 font-medium text-ink break-words">{proposal.action}</p>
                    <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                      {proposal.proposal_id} / {proposal.status}
                    </p>
                    <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                      {proposal.related_workflow_id}
                      {proposal.related_approval_id ? ` / ${proposal.related_approval_id}` : ""}
                    </p>
                  </div>
                  <span
                    className={`status-pill ${
                      proposal.approval_required ? "signal-action-required" : "signal-ready"
                    }`}
                  >
                    {proposal.risk_level}
                  </span>
                </div>
              ))}
            </div>
          </section>

          <AgentRunsPanel agentId={selectedAgent.agent_id} agentName={selectedAgent.name} />
        </section>
      </div>

      <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
        <p className="eyebrow m-0">Registry Notes</p>
        <div className="grid min-w-0 gap-2.5">
          {registry.registry_notes.map((note) => (
            <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words" key={note}>
              {note}
            </p>
          ))}
        </div>
      </section>
    </div>
  );
}

function RunRailMarker({ state }: { state: AgentRunRailState }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-block size-2.5 shrink-0 rotate-45",
        state === "done" && "bg-signal",
        state === "current" && "border-2 border-signal bg-transparent",
        state === "failed" && "border-2 border-[rgb(var(--signal-action-required,220_38_38))] bg-transparent",
        state === "pending" && "border border-mist bg-transparent dark:border-white/25",
      )}
      style={
        state === "current"
          ? { animation: "tick-pulse 1.6s ease-in-out infinite" }
          : undefined
      }
    />
  );
}

/**
 * Step timeline projected from the persisted agent_run_steps records onto
 * the fixed context_read → model call → proposal rail, mirroring the
 * approval inbox decision rail treatment.
 */
function AgentRunRail({ run }: { run: AgentRunRecord }) {
  const stages = buildAgentRunRail(run);

  return (
    <div className="grid gap-2" aria-label="Agent run step timeline">
      <div className="flex items-center gap-2">
        {stages.map((stage, index) => (
          <div
            className={cn("flex items-center gap-2", index > 0 && "min-w-0 flex-1")}
            key={stage.step_type}
          >
            {index > 0 ? <div className="rule-dotted relative h-px min-w-6 flex-1" /> : null}
            <RunRailMarker state={stage.state} />
          </div>
        ))}
      </div>
      <div className="grid grid-cols-3 gap-2">
        {stages.map((stage) => (
          <div className="grid min-w-0 gap-0.5" key={stage.step_type}>
            <p
              className={cn(
                "m-0 font-mono text-[10.5px] tracking-[0.14em] uppercase",
                stage.state === "pending" ? "text-muted" : "text-signal",
              )}
            >
              {stage.label}
            </p>
            <p className="m-0 truncate text-xs text-muted" title={stage.detail}>
              {stage.detail}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

type LinkedInvocationsState = {
  invocations: LiveModelInvocation[];
  failedIds: string[];
  isLoading: boolean;
};

type LinkedInvocationsResult = {
  /** The id-list key the result was resolved for; stale results are ignored. */
  key: string;
  invocations: LiveModelInvocation[];
  failedIds: string[];
};

/** Resolve the run's linked model invocation records from the platform
 * router; failures are reported per id instead of being masked. */
function useLinkedModelInvocations(invocationIds: string[]): LinkedInvocationsState {
  const { session } = useOidcConsoleSession();
  const [result, setResult] = useState<LinkedInvocationsResult | null>(null);
  const idsKey = invocationIds.join(",");

  useEffect(() => {
    if (idsKey === "") {
      return;
    }

    const controller = new AbortController();
    const ids = idsKey.split(",");

    async function load() {
      const invocations: LiveModelInvocation[] = [];
      const failedIds: string[] = [];

      await Promise.all(
        ids.map(async (invocationId) => {
          try {
            const payload = await axisFetchJson<unknown>(
              modelInvocationDetailPath(invocationId),
              { session, signal: controller.signal },
            );
            invocations.push(parseModelInvocation(payload));
          } catch {
            failedIds.push(invocationId);
          }
        }),
      );

      if (!controller.signal.aborted) {
        setResult({ key: idsKey, invocations, failedIds });
      }
    }

    void load();

    return () => controller.abort();
  }, [idsKey, session]);

  const resolved = result !== null && result.key === idsKey ? result : null;

  return {
    invocations: resolved?.invocations ?? [],
    failedIds: resolved?.failedIds ?? [],
    isLoading: idsKey !== "" && resolved === null,
  };
}

function AgentRunDetail({ run }: { run: AgentRunRecord }) {
  const linked = useLinkedModelInvocations(run.model_invocation_ids);

  return (
    <div className="grid min-w-0 gap-3 border-t border-line/60 pt-3 dark:border-white/10" data-run-detail={run.run_id}>
      <AgentRunRail run={run} />

      {run.error_reason ? (
        <p className="m-0 font-mono text-xs break-words text-muted">
          Error reason: {run.error_reason}
        </p>
      ) : null}

      <div>
        <p className="eyebrow m-0">Linked Model Invocations</p>
        {run.model_invocation_ids.length === 0 ? (
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted">
            No model invocations are linked to this run.
          </p>
        ) : linked.isLoading ? (
          <Skeleton className="mt-2 h-9 w-full" />
        ) : (
          <div className="mt-1 grid min-w-0 gap-2">
            {linked.invocations.map((invocation) => (
              <div
                className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-t border-line/60 py-2 first:border-t-0 dark:border-white/10"
                key={invocation.invocation_id}
              >
                <div>
                  <p className="m-0 font-mono text-[13px] text-ink break-words">
                    {invocation.model_id ?? "unrouted"} / {invocation.endpoint_id ?? "unrouted"}
                  </p>
                  <p className="mx-0 mt-0.5 mb-0 text-xs leading-snug text-muted break-words">
                    {invocation.input_tokens} in / {invocation.output_tokens} out tokens /{" "}
                    {formatLiveEuroCost(invocation.estimated_cost_eur)} / {invocation.latency_ms} ms /{" "}
                    {formatModelRoutingLabel(invocation.egress_decision)}
                  </p>
                </div>
                {invocation.audit_event_id ? (
                  <a
                    className="font-mono text-xs text-signal underline-offset-2 hover:underline"
                    href={buildAuditEventHref(invocation.audit_event_id)}
                  >
                    Open audit
                  </a>
                ) : (
                  <span className="font-mono text-xs text-muted">audit pending</span>
                )}
              </div>
            ))}
            {linked.failedIds.map((invocationId) => (
              <p className="m-0 font-mono text-xs break-words text-muted" key={invocationId}>
                Invocation {invocationId} detail unavailable (/platform/models/invocations).
              </p>
            ))}
          </div>
        )}
      </div>

      <div className="flex min-w-0 flex-wrap items-center gap-3">
        {run.proposed_action_run_id ? (
          <a
            className="font-mono text-xs text-signal underline-offset-2 hover:underline"
            href={buildApprovalActionRunHref(run.proposed_action_run_id)}
          >
            Open proposed action run in approvals
          </a>
        ) : (
          <span className="font-mono text-xs text-muted">
            No action run was created by this run.
          </span>
        )}
        {run.audit_event_id ? (
          <a
            className="font-mono text-xs text-signal underline-offset-2 hover:underline"
            href={buildAuditEventHref(run.audit_event_id)}
          >
            Open run audit event
          </a>
        ) : null}
      </div>

      {run.notes.length > 0 ? (
        <ul className="mx-0 mt-0 mb-0 grid list-disc gap-1.5 pl-5 text-xs leading-relaxed text-muted">
          {run.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/**
 * Per-agent expandable panel over the persisted agent run records. The run
 * list loads only when expanded and renders exclusively API-backed rows —
 * empty and unavailable states stay honest.
 */
function AgentRunsPanel({ agentId, agentName }: { agentId: string; agentName: string }) {
  const [expanded, setExpanded] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState("");
  const runsQuery = useAxisQuery<unknown>(agentRunsPath(agentId), { enabled: expanded });

  const runList = useMemo(() => {
    if (!expanded || runsQuery.data === null || runsQuery.data === undefined) {
      return null;
    }
    try {
      return parseAgentRunList(runsQuery.data);
    } catch {
      return null;
    }
  }, [expanded, runsQuery.data]);

  const selectedRun =
    runList?.runs.find((run) => run.run_id === selectedRunId) ?? runList?.runs[0] ?? null;
  const deferredCount = runList
    ? runList.runs.filter((run) => isDeferredAgentRunStatus(run.status)).length
    : 0;

  return (
    <section
      className="grid min-w-0 gap-3 border-t border-line/60 pt-3.5 dark:border-white/10"
      data-agent-runs-panel={agentId}
    >
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow m-0">Runs</p>
          <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">
            Live executed runs
          </h3>
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
            Persisted run records for {agentName}; steps, model links and proposals are recorded
            values.
          </p>
        </div>
        <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">
          <span className="status-pill signal-ready" data-source-badge="live">
            <Activity size={15} />
            Live executed
          </span>
          <button
            className="icon-button"
            aria-expanded={expanded}
            onClick={() => setExpanded((current) => !current)}
            title={expanded ? "Hide agent runs" : "Show agent runs"}
            type="button"
          >
            <History size={17} />
          </button>
        </div>
      </div>

      {!expanded ? null : runsQuery.isLoading ? (
        <div className="grid gap-2.5" aria-label="Loading agent runs">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-2/3" />
        </div>
      ) : !runList ? (
        <ApiRequiredState
          detail="Axis did not receive persisted run records for this agent. Run timelines are never fabricated."
          endpoint={`/demo/manufacturing/agents/${agentId}/runs`}
          title="Agent runs API unavailable"
        />
      ) : runList.runs.length === 0 ? (
        <section
          className="min-w-0 rounded-2xl border border-dashed border-slate/45 bg-surface/55 p-4.5 dark:border-white/20 dark:bg-white/4"
          data-agent-runs-empty
        >
          <p className="eyebrow m-0">Flag-Gated</p>
          <h4 className="font-display mx-0 mt-2 mb-1.5 text-xl text-ink">
            No runs recorded — execution flag-gated
          </h4>
          <p className="m-0 max-w-2xl text-sm leading-snug text-muted">
            No runs are recorded for this agent. Agent run execution is deferred by default until{" "}
            {AGENT_RUN_EXECUTION_FLAG} is enabled on the API; Axis never fabricates run rows.
          </p>
        </section>
      ) : (
        <div className="grid min-w-0 gap-3">
          {deferredCount > 0 ? (
            <p className="m-0 font-mono text-xs text-muted">
              {deferredCount} deferred run{deferredCount === 1 ? "" : "s"} — model routing
              execution is flag-gated; deferred runs end honestly without a proposal.
            </p>
          ) : null}
          <div className="grid min-w-0">
            {runList.runs.map((run) => {
              const isSelected = selectedRun !== null && run.run_id === selectedRun.run_id;

              return (
                <button
                  aria-pressed={isSelected}
                  className={cn(
                    "grid w-full cursor-pointer grid-cols-[minmax(0,1fr)_auto] items-center gap-3.5 border-0 border-t border-line/60 bg-transparent px-2.5 py-3 text-left text-ink transition-colors first:border-t-0 hover:bg-ink/4 dark:border-white/10 dark:hover:bg-white/6",
                    isSelected
                      && "bg-signal/10 shadow-[inset_2px_0_0_rgb(var(--signal))] dark:bg-signal/15",
                  )}
                  data-run-id={run.run_id}
                  key={run.run_id}
                  onClick={() => setSelectedRunId(run.run_id)}
                  type="button"
                >
                  <span>
                    <span className="m-0 font-mono text-[13px] text-ink break-words">
                      {run.run_id}
                    </span>
                    <span className="mx-0 mt-1 mb-0 block text-sm leading-snug text-muted break-words">
                      {run.autonomy_level} / started {formatLiveTimestamp(run.created_at)} by{" "}
                      {run.requested_by}
                    </span>
                  </span>
                  <span className="flex min-w-0 flex-wrap items-center justify-end gap-2">
                    {run.mode === "dry_run" ? (
                      <span className="status-pill signal-watch">Dry run</span>
                    ) : null}
                    <span className={`status-pill ${agentRunStatusClass(run.status)}`}>
                      {agentRunStatusLabel(run.status)}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>

          {selectedRun ? <AgentRunDetail run={selectedRun} /> : null}

          {runList.run_notes.length > 0 ? (
            <ul className="mx-0 mt-0 mb-0 grid list-disc gap-1.5 pl-5 text-xs leading-relaxed text-muted">
              {runList.run_notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          ) : null}
        </div>
      )}
    </section>
  );
}
