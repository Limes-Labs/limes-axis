"use client";

import { useEffect, useMemo, useState } from "react";
import { Bot, Filter, RadioTower, RotateCcw, ShieldCheck } from "lucide-react";

import { getApiBaseUrl } from "@/lib/api-status";
import {
  allAgentFilter,
  countPendingAgentProposals,
  defaultManufacturingAgentRegistry,
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

type AgentSource = "loading" | "api" | "fallback";

const defaultFilters: AgentFilters = {
  domain: allAgentFilter,
  autonomyLevel: allAgentFilter,
  status: allAgentFilter,
};

function sourceLabel(source: AgentSource): string {
  if (source === "api") {
    return "Live agent seed";
  }

  return source === "loading" ? "Loading agent seed" : "Fallback agent seed";
}

export function AgentRegistry() {
  const [registry, setRegistry] = useState<ManufacturingAgentRegistry>(
    defaultManufacturingAgentRegistry,
  );
  const [source, setSource] = useState<AgentSource>("loading");
  const [filters, setFilters] = useState<AgentFilters>(defaultFilters);
  const [selectedAgentId, setSelectedAgentId] = useState(
    defaultManufacturingAgentRegistry.agents[0].agent_id,
  );
  const apiBaseUrl = getApiBaseUrl();

  useEffect(() => {
    const controller = new AbortController();

    async function fetchAgents() {
      try {
        const response = await fetch(`${apiBaseUrl}/demo/manufacturing/agents`, {
          signal: controller.signal,
          cache: "no-store",
        });

        if (!response.ok) {
          throw new Error(`Agent registry request failed with ${response.status}`);
        }

        const nextRegistry = (await response.json()) as ManufacturingAgentRegistry;
        setRegistry(nextRegistry);
        setSelectedAgentId(nextRegistry.agents[0].agent_id);
        setSource("api");
      } catch {
        if (!controller.signal.aborted) {
          setRegistry(defaultManufacturingAgentRegistry);
          setSelectedAgentId(defaultManufacturingAgentRegistry.agents[0].agent_id);
          setSource("fallback");
        }
      }
    }

    void fetchAgents();

    return () => controller.abort();
  }, [apiBaseUrl]);

  const filteredAgents = useMemo(() => filterAgents(registry, filters), [registry, filters]);
  const effectiveSelectedAgentId = filteredAgents.some((agent) => agent.agent_id === selectedAgentId)
    ? selectedAgentId
    : (filteredAgents[0]?.agent_id ?? registry.agents[0].agent_id);

  const selectedAgent = useMemo(
    () => findAgentById(registry, effectiveSelectedAgentId),
    [registry, effectiveSelectedAgentId],
  );
  const proposalCount = countPendingAgentProposals(registry);

  function updateFilter(filterName: keyof AgentFilters, value: string) {
    setFilters((current) => ({
      ...current,
      [filterName]: value,
    }));
  }

  function resetFilters() {
    setFilters(defaultFilters);
  }

  return (
    <div className="stack">
      <section className="panel overview-context">
        <div>
          <p className="section-label">Demo Agent Registry</p>
          <h2 className="panel-title">{registry.plant_name}</h2>
          <p className="row-detail">
            {registry.scenario} / {registry.tenant_id}
          </p>
        </div>
        <div className="overview-meta" aria-label="Agent source and registry status">
          <span className="status-pill signal-ready">
            <RadioTower size={15} />
            {sourceLabel(source)}
          </span>
          <span className={`status-pill ${platformStatusClass(registry.registry_status)}`}>
            <Bot size={15} />
            {platformStatusLabel(registry.registry_status)}
          </span>
          <span className="mono">{formatOverviewTimestamp(registry.as_of)}</span>
        </div>
      </section>

      <div className="metric-grid">
        {registry.metrics.map((metric) => (
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

      <section className="panel agent-filter-panel">
        <div>
          <p className="section-label">Filters</p>
          <h2 className="panel-title">Agent registry</h2>
        </div>
        <div className="agent-filters">
          <label>
            <span className="metric-label">Domain</span>
            <select value={filters.domain} onChange={(event) => updateFilter("domain", event.target.value)}>
              <option value={allAgentFilter}>All domains</option>
              {registry.filter_options.domains.map((domain) => (
                <option key={domain} value={domain}>
                  {domain}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="metric-label">Autonomy</span>
            <select
              value={filters.autonomyLevel}
              onChange={(event) => updateFilter("autonomyLevel", event.target.value)}
            >
              <option value={allAgentFilter}>All levels</option>
              {registry.filter_options.autonomy_levels.map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="metric-label">Status</span>
            <select value={filters.status} onChange={(event) => updateFilter("status", event.target.value)}>
              <option value={allAgentFilter}>All statuses</option>
              {registry.filter_options.statuses.map((status) => (
                <option key={status} value={status}>
                  {formatAgentLabel(status)}
                </option>
              ))}
            </select>
          </label>
          <button className="icon-button" onClick={resetFilters} title="Reset filters" type="button">
            <RotateCcw size={17} />
          </button>
        </div>
      </section>

      <div className="agent-layout">
        <section className="panel">
          <div className="agent-list-header">
            <div>
              <p className="section-label">Agents</p>
              <h2 className="panel-title">{filteredAgents.length} visible</h2>
            </div>
            <span className="status-pill signal-watch">
              <Filter size={15} />
              {proposalCount} proposals
            </span>
          </div>
          <div className="agent-list">
            {filteredAgents.map((agent) => {
              const isSelected = agent.agent_id === selectedAgent.agent_id;

              return (
                <button
                  aria-pressed={isSelected}
                  className={`agent-list-item${isSelected ? " active" : ""}`}
                  key={agent.agent_id}
                  onClick={() => setSelectedAgentId(agent.agent_id)}
                  type="button"
                >
                  <span>
                    <span className="row-title">{agent.name}</span>
                    <span className="row-detail">
                      {agent.domain} / {agent.owner_role}
                    </span>
                    <span className="row-detail">{formatAgentLabel(agent.status)}</span>
                  </span>
                  <span className="status-pill signal-watch">
                    {agent.policy_boundary.autonomy_level}
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="panel agent-detail">
          <div className="agent-detail-header">
            <div>
              <p className="section-label">{selectedAgent.domain}</p>
              <h2 className="panel-title">{selectedAgent.name}</h2>
              <p className="row-detail">{selectedAgent.purpose}</p>
            </div>
            <div className="status-stack">
              <span className="status-pill signal-watch">
                {selectedAgent.policy_boundary.autonomy_level}
              </span>
              <span className="status-pill status-checking">
                {formatAgentLabel(selectedAgent.status)}
              </span>
            </div>
          </div>

          <div className="agent-detail-grid">
            <div>
              <p className="metric-label">Owner</p>
              <p className="row-title">{selectedAgent.owner_role}</p>
              <p className="row-detail">{selectedAgent.agent_id}</p>
            </div>
            <div>
              <p className="metric-label">Model Policy</p>
              <p className="row-title">{selectedAgent.policy_boundary.model_policy}</p>
              <p className="row-detail">
                Egress {selectedAgent.policy_boundary.external_egress_allowed ? "allowed" : "blocked"}
              </p>
            </div>
            <div>
              <p className="metric-label">Max Action</p>
              <p className="row-title">{selectedAgent.policy_boundary.max_action_level}</p>
              <p className="row-detail">Policy boundary</p>
            </div>
            <div>
              <p className="metric-label">Last Audit</p>
              <p className="row-title mono">{selectedAgent.last_audit_event}</p>
              <p className="row-detail">Evidence-linked</p>
            </div>
          </div>

          <div className="agent-columns">
            <section>
              <p className="section-label">Connected Systems</p>
              <div className="tag-list">
                {selectedAgent.connected_systems.map((system) => (
                  <span className="tag" key={system}>
                    {system}
                  </span>
                ))}
              </div>
            </section>
            <section>
              <p className="section-label">Data Access</p>
              <ul className="clean-list">
                {selectedAgent.data_access.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
            <section>
              <p className="section-label">Evidence</p>
              <div className="tag-list">
                {selectedAgent.evidence_refs.map((item) => (
                  <span className="tag" key={item}>
                    {item}
                  </span>
                ))}
              </div>
            </section>
          </div>

          <div className="agent-policy-band">
            <section>
              <p className="section-label">Required Permissions</p>
              <div className="tag-list">
                {selectedAgent.policy_boundary.required_permissions.map((permission) => (
                  <span className="tag" key={permission}>
                    {permission}
                  </span>
                ))}
              </div>
            </section>
            <section>
              <p className="section-label">Guardrails</p>
              <ul className="clean-list">
                {selectedAgent.policy_boundary.guardrails.map((guardrail) => (
                  <li key={guardrail}>{guardrail}</li>
                ))}
              </ul>
            </section>
          </div>

          <div className="agent-columns">
            <section>
              <p className="section-label">Allowed Actions</p>
              <ul className="clean-list">
                {selectedAgent.allowed_actions.map((action) => (
                  <li key={action}>{action}</li>
                ))}
              </ul>
            </section>
            <section>
              <p className="section-label">Blocked Actions</p>
              <ul className="clean-list">
                {selectedAgent.blocked_actions.map((action) => (
                  <li key={action}>{action}</li>
                ))}
              </ul>
            </section>
            <section>
              <p className="section-label">Workflow Links</p>
              <div className="tag-list">
                {selectedAgent.active_workflows.map((workflow) => (
                  <span className="tag" key={workflow}>
                    {workflow}
                  </span>
                ))}
                {selectedAgent.pending_approvals.map((approval) => (
                  <span className="tag" key={approval}>
                    {approval}
                  </span>
                ))}
              </div>
            </section>
          </div>

          <section className="agent-proposals">
            <div className="agent-proposals-header">
              <div>
                <p className="section-label">Proposals</p>
                <h3 className="subsection-title">Read-only action proposals</h3>
              </div>
              <ShieldCheck size={18} />
            </div>
            <div className="stack">
              {selectedAgent.proposals.map((proposal) => (
                <div className="row" key={proposal.proposal_id}>
                  <div>
                    <p className="row-title">{proposal.action}</p>
                    <p className="row-detail">
                      {proposal.proposal_id} / {proposal.status}
                    </p>
                    <p className="row-detail">
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

      <section className="panel">
        <p className="section-label">Registry Notes</p>
        <div className="stack">
          {registry.registry_notes.map((note) => (
            <p className="row-detail" key={note}>
              {note}
            </p>
          ))}
        </div>
      </section>
    </div>
  );
}
