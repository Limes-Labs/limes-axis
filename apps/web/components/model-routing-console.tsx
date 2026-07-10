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
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";

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
    <div className="grid min-w-0 gap-4">
      <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow m-0">Demo Model Router</p>
          <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{routing.plant_name}</h2>
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
            {routing.scenario} / {routing.tenant_id}
          </p>
        </div>
        <div className="flex min-w-0 flex-wrap items-center justify-end gap-2" aria-label="Model routing source and status">
          <span className="status-pill signal-ready">
            <RadioTower size={15} />
            {sourceLabel(source)}
          </span>
          <span className={`status-pill ${platformStatusClass(routing.routing_status)}`}>
            <Gauge size={15} />
            {platformStatusLabel(routing.routing_status)}
          </span>
          <span className="font-mono text-[13px] break-words">{formatOverviewTimestamp(routing.as_of)}</span>
        </div>
      </section>

      <div className="grid gap-3.5 sm:grid-cols-2 xl:grid-cols-4 [&>*]:min-w-0">
        {routing.metrics.map((metric) => (
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
          <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">Routing telemetry</h2>
        </div>
        <div className="grid w-full min-w-0 gap-2.5 sm:flex sm:w-auto sm:flex-wrap sm:items-end sm:justify-end">
          <Field label="Domain">
            <Select
              value={filters.domain}
              onChange={(event) => updateFilter("domain", event.target.value)}
            >
              <option value={allModelRoutingFilter}>All domains</option>
              {routing.filter_options.domains.map((domain) => (
                <option key={domain} value={domain}>
                  {domain}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Provider">
            <Select
              value={filters.provider}
              onChange={(event) => updateFilter("provider", event.target.value)}
            >
              <option value={allModelRoutingFilter}>All providers</option>
              {routing.filter_options.providers.map((provider) => (
                <option key={provider} value={provider}>
                  {provider}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Decision">
            <Select
              value={filters.decision}
              onChange={(event) => updateFilter("decision", event.target.value)}
            >
              <option value={allModelRoutingFilter}>All decisions</option>
              {routing.filter_options.egress_decisions.map((decision) => (
                <option key={decision} value={decision}>
                  {formatModelRoutingLabel(decision)}
                </option>
              ))}
            </Select>
          </Field>
          <button className="icon-button" onClick={resetFilters} title="Reset routing filters" type="button">
            <RotateCcw size={17} />
          </button>
        </div>
      </section>

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(330px,0.48fr)_minmax(0,1fr)] [&>*]:min-w-0">
        <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
          <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
            <div>
              <p className="eyebrow m-0">Routes</p>
              <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{filteredRoutes.length} visible</h2>
            </div>
            <span className="status-pill signal-ready">
              <Filter size={15} />
              {blockedRoutes} blocked
            </span>
          </div>
          <div className="grid">
            {filteredRoutes.map((route) => {
              const isSelected = route.route_id === selectedRoute.route_id;

              return (
                <button
                  aria-pressed={isSelected}
                  className={`grid w-full cursor-pointer grid-cols-[minmax(0,1fr)_auto] items-center gap-3.5 border-0 border-t border-line/60 bg-transparent px-2.5 py-3.5 text-left text-ink transition-colors first:border-t-0 hover:bg-ink/4 dark:border-white/10 dark:hover:bg-white/6${isSelected ? " bg-signal/10 shadow-[inset_2px_0_0_rgb(var(--signal))] dark:bg-signal/15" : ""}`}
                  key={route.route_id}
                  onClick={() => setSelectedRouteId(route.route_id)}
                  type="button"
                >
                  <span>
                    <span className="m-0 font-medium text-ink break-words">{route.agent_name}</span>
                    <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                      {route.domain} / {route.provider_id}
                    </span>
                    <span className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{route.model}</span>
                  </span>
                  <span className={`status-pill ${routeDecisionClass(route)}`}>
                    {formatModelRoutingLabel(route.egress_decision)}
                  </span>
                </button>
              );
            })}
          </div>
        </section>

        <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 grid gap-4">
          <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
            <div>
              <p className="eyebrow m-0">{selectedRoute.domain}</p>
              <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{selectedRoute.agent_name}</h2>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{selectedRoute.decision_reason}</p>
            </div>
            <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">
              <span className={`status-pill ${routeDecisionClass(selectedRoute)}`}>
                {formatModelRoutingLabel(selectedRoute.egress_decision)}
              </span>
              <span className={`status-pill ${platformStatusClass(selectedRoute.route_status)}`}>
                {platformStatusLabel(selectedRoute.route_status)}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3.5 border-y border-line/60 py-3.5 xl:grid-cols-4 dark:border-white/10 [&>*]:min-w-0">
            <div>
              <p className="eyebrow m-0">Provider</p>
              <p className="m-0 font-medium text-ink break-words">{selectedRoute.provider_name}</p>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{selectedRoute.provider_id}</p>
            </div>
            <div>
              <p className="eyebrow m-0">Model</p>
              <p className="m-0 font-medium text-ink break-words">{selectedRoute.model}</p>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{selectedRoute.prompt_classification}</p>
            </div>
            <div>
              <p className="eyebrow m-0">Estimated Cost</p>
              <p className="m-0 font-medium text-ink break-words">{formatEuroCost(selectedRoute.estimated_cost_eur)}</p>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{selectedRoute.cost_center}</p>
            </div>
            <div>
              <p className="eyebrow m-0">Latency</p>
              <p className="m-0 font-medium text-ink break-words">{selectedRoute.latency_ms} ms</p>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                {selectedRoute.input_tokens + selectedRoute.output_tokens} tokens
              </p>
            </div>
          </div>

          <div className="grid gap-4 border-y border-line/60 py-3.5 dark:border-white/10 lg:grid-cols-[minmax(0,0.7fr)_minmax(260px,1fr)] [&>*]:min-w-0">
            <div>
              <p className="eyebrow m-0">Policy</p>
              <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">{selectedRoute.model_policy}</h3>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                Requested external egress: {selectedRoute.external_egress_requested ? "yes" : "no"}
              </p>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                Allowed external egress: {selectedRoute.external_egress_allowed ? "yes" : "no"}
              </p>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">Boundary: {selectedRoute.data_boundary}</p>
            </div>
            <div>
              <p className="eyebrow m-0">Required Permissions</p>
              <div className="flex min-w-0 flex-wrap gap-2">
                {selectedRoute.required_permissions.map((permission) => (
                  <span className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted break-words transition-colors enabled:cursor-pointer aria-pressed:border-signal aria-pressed:bg-signal/10 aria-pressed:text-signal dark:border-white/15 dark:bg-white/5" key={permission}>
                    {permission}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-3 [&>*]:min-w-0">
            <div>
              <p className="eyebrow m-0">Observability Events</p>
              <ul className="mx-0 mt-2.5 mb-0 grid list-disc gap-2 pl-5 text-sm leading-snug text-muted">
                {selectedRoute.observability_events.map((event) => (
                  <li key={event}>{event}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="eyebrow m-0">Evidence</p>
              <ul className="mx-0 mt-2.5 mb-0 grid list-disc gap-2 pl-5 text-sm leading-snug text-muted">
                {selectedRoute.evidence_refs.map((evidence) => (
                  <li key={evidence}>{evidence}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="eyebrow m-0">Audit</p>
              <p className="m-0 font-medium text-ink break-words">{selectedRoute.audit_event_id}</p>
              <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
                Input {selectedRoute.input_tokens} / output {selectedRoute.output_tokens}
              </p>
            </div>
          </div>

          <div className="grid min-w-0 gap-3 border-t border-line/60 pt-3.5 dark:border-white/10">
            <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
              <div>
                <p className="eyebrow m-0">Provider Boundary</p>
                <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">{selectedProvider.display_name}</h3>
              </div>
              <span className={`status-pill ${routeDecisionClass(selectedRoute)}`}>
                {formatModelRoutingLabel(selectedProvider.status)}
              </span>
            </div>
            <div className="grid min-w-0 gap-2">
              <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5">
                <p className="eyebrow m-0">Type</p>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{selectedProvider.provider_type}</p>
              </div>
              <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5">
                <p className="eyebrow m-0">Hosting</p>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{selectedProvider.hosting_boundary}</p>
              </div>
              <div className="grid min-w-0 grid-cols-1 items-start gap-1 border-t border-line/60 pt-2 first:border-t-0 first:pt-0 dark:border-white/10 sm:grid-cols-[minmax(120px,0.35fr)_minmax(0,1fr)] sm:gap-2.5">
                <p className="eyebrow m-0">Cost Basis</p>
                <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">{selectedProvider.cost_basis}</p>
              </div>
            </div>
          </div>
        </section>
      </div>

      <div className="grid gap-4 lg:grid-cols-2 [&>*]:min-w-0">
        <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
          <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10">
            <div>
              <p className="eyebrow m-0">Budget Notes</p>
              <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">{formatEuroCost(estimatedCost)} estimated</h2>
            </div>
            <FileText size={18} />
          </div>
          <ul className="mx-0 mt-2.5 mb-0 grid list-disc gap-2 pl-5 text-sm leading-snug text-muted">
            {routing.budget_notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </section>

        <section className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
          <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 border-t border-line/60 py-3 first:border-t-0 dark:border-white/10">
            <div>
              <p className="eyebrow m-0">Observability Notes</p>
              <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">OpenTelemetry-first</h2>
            </div>
            <ShieldCheck size={18} />
          </div>
          <ul className="mx-0 mt-2.5 mb-0 grid list-disc gap-2 pl-5 text-sm leading-snug text-muted">
            {routing.observability_notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
