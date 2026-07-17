"use client";

import { useMemo, useState } from "react";
import { Bot, RadioTower } from "lucide-react";

import { AgentDetail } from "@/components/agents/agent-detail";
import { Card } from "@/components/ui/card";
import { Eyebrow } from "@/components/ui/eyebrow";
import { FilterBar, type FilterDef } from "@/components/ui/filter-bar";
import { Term } from "@/components/ui/glossary";
import { MasterDetail } from "@/components/ui/master-detail";
import { MetricStrip, type Metric } from "@/components/ui/metric-strip";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/states";
import {
  allAgentFilter,
  filterAgents,
  findAgentById,
  formatAgentLabel,
  type AgentFilters,
  type ManufacturingAgentRegistry,
} from "@/lib/agent-demo";
import { cn } from "@/lib/cn";
import {
  formatOverviewTimestamp,
  platformStatusClass,
  platformStatusLabel,
  type PlatformStatus,
} from "@/lib/platform-overview";
import { strings } from "@/lib/strings";
import { parseManufacturingAgentRegistry } from "@/lib/runtime-contracts/agents";
import { useAxisQuery } from "@/lib/use-axis-query";

const AGENTS_ENDPOINT = "/demo/manufacturing/agents";

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

const metricTones: Record<PlatformStatus, Metric["tone"]> = {
  ready: "ready",
  watch: "watch",
  action_required: "action",
};

/** Traffic-light tone for the list's status dot, derived from the agent status. */
function agentStatusToneClass(status: string): string {
  if (/(blocked|failed|disabled|suspended|retired)/.test(status)) {
    return "text-danger";
  }
  if (/(waiting|pending|proposal_ready|paused)/.test(status)) {
    return "text-warning";
  }
  return "text-positive";
}

function buildFilterDefs(registry: ManufacturingAgentRegistry): FilterDef[] {
  return [
    {
      id: "domain",
      label: "Domain",
      options: [
        { value: allAgentFilter, label: "All domains" },
        ...registry.filter_options.domains.map((domain) => ({ value: domain, label: domain })),
      ],
    },
    {
      id: "autonomy",
      label: "Autonomy",
      options: [
        { value: allAgentFilter, label: "All levels" },
        ...registry.filter_options.autonomy_levels.map((level) => ({
          value: level,
          label: level,
        })),
      ],
    },
    {
      id: "status",
      label: "Status",
      options: [
        { value: allAgentFilter, label: "All statuses" },
        ...registry.filter_options.statuses.map((status) => ({
          value: status,
          label: formatAgentLabel(status),
        })),
      ],
    },
  ];
}

const filterIdToKey: Record<string, keyof AgentFilters> = {
  domain: "domain",
  autonomy: "autonomyLevel",
  status: "status",
};

export function AgentRegistry() {
  const { data: registry, source } = useAxisQuery<ManufacturingAgentRegistry>(AGENTS_ENDPOINT, {
    parse: parseManufacturingAgentRegistry,
  });
  const [filters, setFilters] = useState<AgentFilters>(defaultFilters);
  const [selectedAgentId, setSelectedAgentId] = useState("");

  const filteredAgents = useMemo(
    () => (registry ? filterAgents(registry, filters) : []),
    [registry, filters],
  );

  if (!registry) {
    if (source === "loading") {
      return (
        <div aria-label="Loading agent API" className="grid gap-4">
          <LoadingPanel layout="metrics" rows={3} />
          <MasterDetail
            detail={<LoadingPanel layout="detail" />}
            list={<LoadingPanel rows={4} />}
          />
        </div>
      );
    }

    return (
      <ErrorPanel
        detail={strings.agents.error.detail}
        endpoint={AGENTS_ENDPOINT}
        title={strings.agents.error.title}
      />
    );
  }

  if (registry.agents.length === 0) {
    return (
      <EmptyPanel
        detail={strings.agents.empty.detail}
        icon={Bot}
        title={strings.agents.empty.title}
      />
    );
  }

  // `findAgentById` falls back to the first agent, so a stale selection always
  // resolves to a real record; prefer the first *filtered* agent when the
  // selection is filtered out.
  const selectedAgent =
    filteredAgents.find((agent) => agent.agent_id === selectedAgentId)
    ?? filteredAgents[0]
    ?? findAgentById(registry, selectedAgentId);

  const metrics: Metric[] = registry.metrics.map((metric) => ({
    label: metric.label,
    value: metric.value,
    detail: metric.detail,
    tone: metricTones[metric.status],
  }));

  return (
    <div className="grid gap-4">
      <div
        aria-label="Agent source and registry status"
        className="flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-2"
      >
        <p className="m-0 min-w-0 text-sm break-words text-muted">
          {registry.plant_name} / {registry.scenario} / {registry.tenant_id}
        </p>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="status-pill signal-ready">
            <RadioTower size={15} />
            {sourceLabel(source)}
          </span>
          <span className={`status-pill ${platformStatusClass(registry.registry_status)}`}>
            <Bot size={15} />
            {platformStatusLabel(registry.registry_status)}
          </span>
          <span className="font-mono text-xs text-muted">
            {formatOverviewTimestamp(registry.as_of)}
          </span>
        </div>
      </div>

      {metrics.length > 0 ? <MetricStrip metrics={metrics} /> : null}

      <FilterBar
        filters={buildFilterDefs(registry)}
        values={{
          domain: filters.domain,
          autonomy: filters.autonomyLevel,
          status: filters.status,
        }}
        onChange={(id, value) => {
          const key = filterIdToKey[id];
          if (key) {
            setFilters((current) => ({ ...current, [key]: value }));
          }
        }}
        onReset={() => setFilters(defaultFilters)}
      />

      {filteredAgents.length === 0 ? (
        <EmptyPanel
          action={{
            label: strings.agents.noMatch.reset,
            onClick: () => setFilters(defaultFilters),
          }}
          detail={strings.agents.noMatch.detail}
          title={strings.agents.noMatch.title}
        />
      ) : (
        <MasterDetail
          detail={<AgentDetail agent={selectedAgent} />}
          list={
            <Card className="grid content-start gap-4">
              <div className="grid gap-1">
                <Eyebrow>{strings.agents.list.eyebrow}</Eyebrow>
                <h2 className="font-display m-0 text-xl text-ink">
                  {filteredAgents.length} visible
                </h2>
              </div>
              <div className="grid gap-2">
                {filteredAgents.map((agent) => {
                  const isSelected = agent.agent_id === selectedAgent.agent_id;

                  return (
                    <button
                      aria-pressed={isSelected}
                      className={cn(
                        "flex w-full cursor-pointer items-start justify-between gap-3 rounded-2xl border px-4 py-3 text-left transition-colors",
                        isSelected
                          ? "border-signal/60 bg-tint-100 dark:bg-signal/15"
                          : "border-line bg-transparent hover:border-signal/40 hover:bg-tint-50 dark:border-white/10 dark:hover:bg-white/5",
                      )}
                      key={agent.agent_id}
                      onClick={() => setSelectedAgentId(agent.agent_id)}
                      type="button"
                    >
                      <span className="grid min-w-0 gap-0.5">
                        <span className="text-sm font-medium text-ink">{agent.name}</span>
                        <span className="text-xs text-muted">{agent.domain}</span>
                        <span className="flex items-center gap-1.5 text-xs text-muted">
                          <span
                            aria-hidden="true"
                            className={cn("status-dot", agentStatusToneClass(agent.status))}
                          />
                          {formatAgentLabel(agent.status)}
                        </span>
                      </span>
                      <span className="status-pill signal-watch">
                        <Term k="autonomy_level">
                          {agent.policy_boundary.autonomy_level}
                        </Term>
                      </span>
                    </button>
                  );
                })}
              </div>
            </Card>
          }
        />
      )}

      {registry.registry_notes.length > 0 ? (
        <Card className="grid content-start gap-3">
          <Eyebrow>Registry Notes</Eyebrow>
          <div className="grid gap-2">
            {registry.registry_notes.map((note) => (
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
