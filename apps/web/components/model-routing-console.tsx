"use client";

import { useMemo, useState } from "react";
import { FileText, Filter, Gauge, RadioTower, RotateCcw, ShieldCheck } from "lucide-react";

import { ApiRequiredState } from "@/components/api-required-state";
import {
  allModelRoutingFilter,
  countBlockedModelRoutes,
  filterModelRoutes,
  findModelRouteById,
  formatEuroCost,
  formatModelRoutingLabel,
  sumEstimatedModelCost,
  type ManufacturingModelRouting,
  type ModelRoutingFilters,
  type ModelRouteTelemetry,
} from "@/lib/model-routing-demo";
import {
  formatOverviewTimestamp,
  platformStatusClass,
  platformStatusLabel,
} from "@/lib/platform-overview";
import { useAxisQuery } from "@/lib/use-axis-query";

const defaultFilters: ModelRoutingFilters = {
  domain: allModelRoutingFilter,
  provider: allModelRoutingFilter,
  decision: allModelRoutingFilter,
};

function sourceLabel(source: "loading" | "api" | "unavailable"): string {
  if (source === "api") {
    return "API routing telemetry";
  }

  return source === "loading" ? "Loading routing API" : "Routing API unavailable";
}

function routeDecisionClass(route: ModelRouteTelemetry): string {
  if (route.egress_decision === "blocked_by_default" || route.egress_decision === "local_allowed") {
    return "signal-ready";
  }

  return "signal-watch";
}

export function ModelRoutingConsole() {
  const { data: routing, source } = useAxisQuery<ManufacturingModelRouting>(
    "/demo/manufacturing/model-routing",
  );
  const [filters, setFilters] = useState<ModelRoutingFilters>(defaultFilters);
  const [selectedRouteId, setSelectedRouteId] = useState("");

  const filteredRoutes = useMemo(
    () => (routing ? filterModelRoutes(routing, filters) : []),
    [routing, filters],
  );
  const effectiveSelectedRouteId = filteredRoutes.some(
    (route) => route.route_id === selectedRouteId,
  )
    ? selectedRouteId
    : (filteredRoutes[0]?.route_id ?? routing?.routes[0]?.route_id ?? "");

  const selectedRoute = useMemo(
    () =>
      routing && routing.routes.length > 0
        ? findModelRouteById(routing, effectiveSelectedRouteId)
        : null,
    [routing, effectiveSelectedRouteId],
  );
  const selectedProvider =
    routing && selectedRoute
      ? (routing.provider_options.find(
          (provider) => provider.provider_id === selectedRoute.provider_id,
        ) ?? routing.provider_options[0])
      : null;
  const blockedRoutes = routing ? countBlockedModelRoutes(routing) : 0;
  const estimatedCost = routing ? sumEstimatedModelCost(routing) : 0;

  function updateFilter(filterName: keyof ModelRoutingFilters, value: string) {
    setFilters((current) => ({
      ...current,
      [filterName]: value,
    }));
  }

  function resetFilters() {
    setFilters(defaultFilters);
  }

  if (!routing) {
    return (
      <ApiRequiredState
        detail="Axis did not receive API-backed model routing records. Local fallback routing records are disabled."
        endpoint="/demo/manufacturing/model-routing"
        title={source === "loading" ? "Loading routing API" : "Routing API unavailable"}
      />
    );
  }

  if (!selectedRoute || !selectedProvider) {
    return (
      <ApiRequiredState
        detail="The model routing API responded without route records for this tenant."
        endpoint="/demo/manufacturing/model-routing"
        title="Routing API returned no records"
      />
    );
  }

  return (
    <div className="console-stack">
      <section className="panel overview-context">
        <div>
          <p className="section-label">Demo Model Router</p>
          <h2 className="panel-title">{routing.plant_name}</h2>
          <p className="row-detail">
            {routing.scenario} / {routing.tenant_id}
          </p>
        </div>
        <div className="overview-meta" aria-label="Model routing source and status">
          <span className="status-pill signal-ready">
            <RadioTower size={15} />
            {sourceLabel(source)}
          </span>
          <span className={`status-pill ${platformStatusClass(routing.routing_status)}`}>
            <Gauge size={15} />
            {platformStatusLabel(routing.routing_status)}
          </span>
          <span className="mono">{formatOverviewTimestamp(routing.as_of)}</span>
        </div>
      </section>

      <div className="metric-grid">
        {routing.metrics.map((metric) => (
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

      <section className="panel model-filter-panel">
        <div>
          <p className="section-label">Filters</p>
          <h2 className="panel-title">Routing telemetry</h2>
        </div>
        <div className="model-filters">
          <label>
            <span className="metric-label">Domain</span>
            <select
              value={filters.domain}
              onChange={(event) => updateFilter("domain", event.target.value)}
            >
              <option value={allModelRoutingFilter}>All domains</option>
              {routing.filter_options.domains.map((domain) => (
                <option key={domain} value={domain}>
                  {domain}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="metric-label">Provider</span>
            <select
              value={filters.provider}
              onChange={(event) => updateFilter("provider", event.target.value)}
            >
              <option value={allModelRoutingFilter}>All providers</option>
              {routing.filter_options.providers.map((provider) => (
                <option key={provider} value={provider}>
                  {provider}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="metric-label">Decision</span>
            <select
              value={filters.decision}
              onChange={(event) => updateFilter("decision", event.target.value)}
            >
              <option value={allModelRoutingFilter}>All decisions</option>
              {routing.filter_options.egress_decisions.map((decision) => (
                <option key={decision} value={decision}>
                  {formatModelRoutingLabel(decision)}
                </option>
              ))}
            </select>
          </label>
          <button className="icon-button" onClick={resetFilters} title="Reset routing filters" type="button">
            <RotateCcw size={17} />
          </button>
        </div>
      </section>

      <div className="model-routing-layout">
        <section className="panel">
          <div className="model-list-header">
            <div>
              <p className="section-label">Routes</p>
              <h2 className="panel-title">{filteredRoutes.length} visible</h2>
            </div>
            <span className="status-pill signal-ready">
              <Filter size={15} />
              {blockedRoutes} blocked
            </span>
          </div>
          <div className="model-route-list">
            {filteredRoutes.map((route) => {
              const isSelected = route.route_id === selectedRoute.route_id;

              return (
                <button
                  aria-pressed={isSelected}
                  className={`model-route-list-item${isSelected ? " active" : ""}`}
                  key={route.route_id}
                  onClick={() => setSelectedRouteId(route.route_id)}
                  type="button"
                >
                  <span>
                    <span className="row-title">{route.agent_name}</span>
                    <span className="row-detail">
                      {route.domain} / {route.provider_id}
                    </span>
                    <span className="row-detail">{route.model}</span>
                  </span>
                  <span className={`status-pill ${routeDecisionClass(route)}`}>
                    {formatModelRoutingLabel(route.egress_decision)}
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="panel model-route-detail">
          <div className="model-route-detail-header">
            <div>
              <p className="section-label">{selectedRoute.domain}</p>
              <h2 className="panel-title">{selectedRoute.agent_name}</h2>
              <p className="row-detail">{selectedRoute.decision_reason}</p>
            </div>
            <div className="status-stack">
              <span className={`status-pill ${routeDecisionClass(selectedRoute)}`}>
                {formatModelRoutingLabel(selectedRoute.egress_decision)}
              </span>
              <span className={`status-pill ${platformStatusClass(selectedRoute.route_status)}`}>
                {platformStatusLabel(selectedRoute.route_status)}
              </span>
            </div>
          </div>

          <div className="model-route-detail-grid">
            <div>
              <p className="metric-label">Provider</p>
              <p className="row-title">{selectedRoute.provider_name}</p>
              <p className="row-detail">{selectedRoute.provider_id}</p>
            </div>
            <div>
              <p className="metric-label">Model</p>
              <p className="row-title">{selectedRoute.model}</p>
              <p className="row-detail">{selectedRoute.prompt_classification}</p>
            </div>
            <div>
              <p className="metric-label">Estimated Cost</p>
              <p className="row-title">{formatEuroCost(selectedRoute.estimated_cost_eur)}</p>
              <p className="row-detail">{selectedRoute.cost_center}</p>
            </div>
            <div>
              <p className="metric-label">Latency</p>
              <p className="row-title">{selectedRoute.latency_ms} ms</p>
              <p className="row-detail">
                {selectedRoute.input_tokens + selectedRoute.output_tokens} tokens
              </p>
            </div>
          </div>

          <div className="model-policy-band">
            <div>
              <p className="section-label">Policy</p>
              <h3 className="subsection-title">{selectedRoute.model_policy}</h3>
              <p className="row-detail">
                Requested external egress: {selectedRoute.external_egress_requested ? "yes" : "no"}
              </p>
              <p className="row-detail">
                Allowed external egress: {selectedRoute.external_egress_allowed ? "yes" : "no"}
              </p>
              <p className="row-detail">Boundary: {selectedRoute.data_boundary}</p>
            </div>
            <div>
              <p className="section-label">Required Permissions</p>
              <div className="tag-list">
                {selectedRoute.required_permissions.map((permission) => (
                  <span className="tag" key={permission}>
                    {permission}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="model-columns">
            <div>
              <p className="section-label">Observability Events</p>
              <ul className="clean-list">
                {selectedRoute.observability_events.map((event) => (
                  <li key={event}>{event}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="section-label">Evidence</p>
              <ul className="clean-list">
                {selectedRoute.evidence_refs.map((evidence) => (
                  <li key={evidence}>{evidence}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="section-label">Audit</p>
              <p className="row-title">{selectedRoute.audit_event_id}</p>
              <p className="row-detail">
                Input {selectedRoute.input_tokens} / output {selectedRoute.output_tokens}
              </p>
            </div>
          </div>

          <div className="model-provider-panel">
            <div className="model-provider-header">
              <div>
                <p className="section-label">Provider Boundary</p>
                <h3 className="subsection-title">{selectedProvider.display_name}</h3>
              </div>
              <span className={`status-pill ${routeDecisionClass(selectedRoute)}`}>
                {formatModelRoutingLabel(selectedProvider.status)}
              </span>
            </div>
            <div className="payload-grid">
              <div className="payload-row">
                <p className="metric-label">Type</p>
                <p className="row-detail">{selectedProvider.provider_type}</p>
              </div>
              <div className="payload-row">
                <p className="metric-label">Hosting</p>
                <p className="row-detail">{selectedProvider.hosting_boundary}</p>
              </div>
              <div className="payload-row">
                <p className="metric-label">Cost Basis</p>
                <p className="row-detail">{selectedProvider.cost_basis}</p>
              </div>
            </div>
          </div>
        </section>
      </div>

      <div className="model-note-grid">
        <section className="panel">
          <div className="row">
            <div>
              <p className="section-label">Budget Notes</p>
              <h2 className="panel-title">{formatEuroCost(estimatedCost)} estimated</h2>
            </div>
            <FileText size={18} />
          </div>
          <ul className="clean-list">
            {routing.budget_notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </section>

        <section className="panel">
          <div className="row">
            <div>
              <p className="section-label">Observability Notes</p>
              <h2 className="panel-title">OpenTelemetry-first</h2>
            </div>
            <ShieldCheck size={18} />
          </div>
          <ul className="clean-list">
            {routing.observability_notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
