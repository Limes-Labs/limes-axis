"use client";

import { useMemo, useState } from "react";
import { Bot, Filter, RadioTower, RotateCcw, ShieldCheck } from "lucide-react";

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
  formatOverviewTimestamp,
  platformStatusClass,
  platformStatusLabel,
} from "@/lib/platform-overview";
import { useAxisQuery } from "@/lib/use-axis-query";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";

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
      <ApiRequiredState
        detail="Axis did not receive API-backed agent records. Local fallback agent records are disabled."
        endpoint="/demo/manufacturing/agents"
        title={source === "loading" ? "Loading agent API" : "Agent API unavailable"}
      />
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
