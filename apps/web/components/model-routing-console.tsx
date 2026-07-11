"use client";

import { useMemo, useState } from "react";
import {
  Activity,
  Cable,
  FileText,
  Filter,
  Gauge,
  KeyRound,
  RadioTower,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";

import { buildAuditEventHref } from "@/lib/audit-demo";
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
  MODEL_ROUTING_EXECUTION_FLAG,
  countDeferredModelInvocations,
  formatLiveEuroCost,
  formatLiveTimestamp,
  isDeferredModelInvocationStatus,
  liveEndpointStatusClass,
  liveInvocationStatusClass,
  modelEndpointsPath,
  modelInvocationsPath,
  modelRoutingTelemetryPath,
  parseModelEndpointRegistry,
  parseModelInvocationList,
  parseModelRoutingTelemetry,
  sumLiveInvocationCost,
} from "@/lib/model-routing-live";
import {
  formatOverviewTimestamp,
  platformStatusClass,
  platformStatusLabel,
} from "@/lib/platform-overview";
import { strings } from "@/lib/strings";
import { useAxisQuery } from "@/lib/use-axis-query";
import { DataTable } from "@/components/ui/data-table";
import { Field } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyPanel, ErrorPanel, LoadingPanel } from "@/components/ui/states";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

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
  return (
    <Tabs className="grid min-w-0 gap-4" defaultValue="reference">
      <div
        className="flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-2"
        data-models-header-strip
      >
        <p className="m-0 min-w-0 text-sm leading-snug break-words text-muted">
          {strings.models.explainer}
        </p>
        <TabsList>
          <TabsTrigger value="reference">{strings.models.tabs.reference}</TabsTrigger>
          <TabsTrigger value="live">{strings.models.tabs.live}</TabsTrigger>
        </TabsList>
      </div>
      <TabsContent value="reference">
        <ReferenceModelRouting />
      </TabsContent>
      <TabsContent value="live">
        <LiveModelRouterSection />
      </TabsContent>
    </Tabs>
  );
}

function ReferenceModelRouting() {
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
    if (source === "loading") {
      return <LoadingPanel layout="detail" />;
    }

    return (
      <ErrorPanel
        detail={strings.models.reference.error.detail}
        endpoint="/demo/manufacturing/model-routing"
        title={strings.models.reference.error.title}
      />
    );
  }

  if (!selectedRoute || !selectedProvider) {
    return (
      <ErrorPanel
        detail={strings.models.reference.noRecords.detail}
        endpoint="/demo/manufacturing/model-routing"
        title={strings.models.reference.noRecords.title}
      />
    );
  }

  return (
    <div className="grid min-w-0 gap-4">
      <div
        aria-label="Model routing source and status"
        className="flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-2"
      >
        <p className="m-0 min-w-0 text-sm leading-snug break-words text-muted">
          {routing.plant_name} / {routing.scenario} / {routing.tenant_id}
        </p>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="status-pill signal-watch" data-source-badge="reference">
            <FileText size={15} />
            Reference
          </span>
          <span className="status-pill signal-ready">
            <RadioTower size={15} />
            {sourceLabel(source)}
          </span>
          <span className={`status-pill ${platformStatusClass(routing.routing_status)}`}>
            <Gauge size={15} />
            {platformStatusLabel(routing.routing_status)}
          </span>
          <span className="font-mono text-[13px] break-words text-muted">{formatOverviewTimestamp(routing.as_of)}</span>
        </div>
      </div>

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

type ParsedQueryState<T> = {
  data: T | null;
  isLoading: boolean;
};

function useParsedAxisQuery<T>(path: string, parse: (input: unknown) => T): ParsedQueryState<T> {
  const { data, isLoading } = useAxisQuery<unknown>(path);

  const parsed = useMemo(() => {
    if (data === null || data === undefined) {
      return null;
    }
    try {
      return parse(data);
    } catch {
      // A malformed payload is treated exactly like an unavailable API:
      // the console never renders partially-fabricated records.
      return null;
    }
  }, [data, parse]);

  return { data: parsed, isLoading };
}

function LiveSourceBadge() {
  return (
    <span className="status-pill signal-ready" data-source-badge="live">
      <Activity size={15} />
      Live executed
    </span>
  );
}

function LivePanelSkeleton() {
  return (
    <div className="grid gap-2.5" aria-label="Loading live model router data">
      <Skeleton className="h-9 w-full" />
      <Skeleton className="h-9 w-full" />
      <Skeleton className="h-9 w-2/3" />
    </div>
  );
}

function endpointChip(label: string): string {
  return label;
}

/**
 * Live model-router surfaces backed by persisted execution records:
 * routing telemetry, real invocation rows and the metadata-only endpoint
 * registry. Nothing here is seeded — every row is a recorded invocation.
 */
function LiveModelRouterSection() {
  const telemetry = useParsedAxisQuery(modelRoutingTelemetryPath, parseModelRoutingTelemetry);
  const invocations = useParsedAxisQuery(modelInvocationsPath(), parseModelInvocationList);
  const endpoints = useParsedAxisQuery(modelEndpointsPath, parseModelEndpointRegistry);

  const deferredCount = invocations.data
    ? countDeferredModelInvocations(invocations.data.invocations)
    : 0;
  const liveCost = invocations.data
    ? sumLiveInvocationCost(invocations.data.invocations)
    : 0;

  return (
    <section className="grid min-w-0 gap-4" data-live-model-router>
      <div className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow m-0">Live Model Router</p>
          <h2 className="font-display mx-0 mt-1 mb-4 text-xl text-ink">Executed invocations</h2>
          <p className="mx-0 mt-1 mb-0 text-sm leading-snug text-muted break-words">
            Persisted invocation records from the platform model router. Token counts, latency,
            cost estimates and egress decisions are recorded values, never reference data.
          </p>
        </div>
        <div
          className="flex min-w-0 flex-wrap items-center justify-end gap-2"
          aria-label="Live model router source and status"
        >
          <LiveSourceBadge />
          {telemetry.data ? (
            <span className="status-pill signal-ready">
              <Gauge size={15} />
              {telemetry.data.route_count} recorded
            </span>
          ) : null}
          {deferredCount > 0 ? (
            <span className="status-pill signal-watch">
              {deferredCount} deferred (flag-gated)
            </span>
          ) : null}
        </div>
      </div>

      <div className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 grid gap-4">
        <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
          <div>
            <p className="eyebrow m-0">Live Invocations</p>
            <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">
              {invocations.data
                ? `${invocations.data.invocations.length} recorded${invocations.data.has_more ? "+" : ""}`
                : "Awaiting invocation API"}
            </h3>
          </div>
          {invocations.data && invocations.data.invocations.length > 0 ? (
            <span className="status-pill signal-ready">
              {formatLiveEuroCost(liveCost)} estimated
            </span>
          ) : null}
        </div>

        {invocations.isLoading ? (
          <LivePanelSkeleton />
        ) : !invocations.data ? (
          <ErrorPanel
            detail={strings.models.live.invocationsError.detail}
            endpoint="/platform/models/invocations"
            title={strings.models.live.invocationsError.title}
          />
        ) : invocations.data.invocations.length === 0 ? (
          <EmptyPanel
            detail={`No live model invocations are recorded for this tenant. Model routing execution is deferred by default until ${MODEL_ROUTING_EXECUTION_FLAG} is enabled on the API; deferred requests perform zero provider calls and Axis never fabricates rows.`}
            title="No invocations recorded yet"
          />
        ) : (
          <DataTable data-testid="live-invocations-table" minWidth={980}>
            <thead>
              <tr>
                <th>Model</th>
                <th>Endpoint</th>
                <th>Task</th>
                <th>Status</th>
                <th>Tokens in / out</th>
                <th>Est. cost</th>
                <th>Latency</th>
                <th>Egress</th>
                <th>Recorded</th>
                <th>Audit</th>
              </tr>
            </thead>
            <tbody>
              {invocations.data.invocations.map((invocation) => (
                <tr data-invocation-id={invocation.invocation_id} key={invocation.invocation_id}>
                  <td className="font-mono text-[13px] text-ink">
                    {invocation.model_id ?? "unrouted"}
                  </td>
                  <td className="font-mono text-[13px]">{invocation.endpoint_id ?? "unrouted"}</td>
                  <td>{invocation.task_type}</td>
                  <td>
                    <span className={`status-pill ${liveInvocationStatusClass(invocation.status)}`}>
                      {formatModelRoutingLabel(
                        isDeferredModelInvocationStatus(invocation.status)
                          ? "deferred"
                          : invocation.status.replace("model_invocation_", ""),
                      )}
                    </span>
                  </td>
                  <td className="font-mono text-[13px]">
                    {invocation.input_tokens} / {invocation.output_tokens}
                  </td>
                  <td className="font-mono text-[13px]">
                    {formatLiveEuroCost(invocation.estimated_cost_eur)}
                  </td>
                  <td className="font-mono text-[13px]">{invocation.latency_ms} ms</td>
                  <td>{formatModelRoutingLabel(invocation.egress_decision)}</td>
                  <td className="font-mono text-[13px]">
                    {formatLiveTimestamp(invocation.created_at)}
                  </td>
                  <td>
                    {invocation.audit_event_id ? (
                      <a
                        className="font-mono text-[13px] text-signal underline-offset-2 hover:underline"
                        href={buildAuditEventHref(invocation.audit_event_id)}
                      >
                        Open audit
                      </a>
                    ) : (
                      <span className="font-mono text-[13px] text-muted">pending</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        )}

        {invocations.data && invocations.data.invocation_notes.length > 0 ? (
          <ul className="mx-0 mt-0 mb-0 grid list-disc gap-1.5 pl-5 text-xs leading-relaxed text-muted">
            {invocations.data.invocation_notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        ) : null}
      </div>

      <div className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5 grid gap-4">
        <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
          <div>
            <p className="eyebrow m-0">Endpoint Registry</p>
            <h3 className="font-display mx-0 mt-1 mb-0 text-lg text-ink">
              {endpoints.data
                ? `${endpoints.data.enabled_endpoint_count} of ${endpoints.data.endpoint_count} enabled`
                : "Awaiting endpoint API"}
            </h3>
          </div>
          <span className="status-pill signal-ready">
            <Cable size={15} />
            Metadata only
          </span>
        </div>

        {endpoints.isLoading ? (
          <LivePanelSkeleton />
        ) : !endpoints.data ? (
          <ErrorPanel
            detail={strings.models.live.endpointsError.detail}
            endpoint="/platform/models/endpoints"
            title={strings.models.live.endpointsError.title}
          />
        ) : endpoints.data.endpoints.length === 0 ? (
          <EmptyPanel
            detail="This tenant has no registered model endpoints. Register an endpoint through POST /platform/models/endpoints to enable deterministic, fail-closed routing."
            title="No model endpoints registered"
          />
        ) : (
          <div className="grid gap-3.5 sm:grid-cols-2 xl:grid-cols-3 [&>*]:min-w-0">
            {endpoints.data.endpoints.map((endpoint) => (
              <article
                className="min-w-0 rounded-3xl border border-line bg-surface p-4 dark:border-white/10 dark:bg-white/5 grid content-start gap-3"
                data-endpoint-id={endpoint.endpoint_id}
                key={endpoint.endpoint_id}
              >
                <div className="flex min-w-0 flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="m-0 font-medium text-ink break-words">{endpoint.display_name}</p>
                    <p className="mx-0 mt-1 mb-0 font-mono text-xs text-muted break-words">
                      {endpoint.endpoint_id}
                    </p>
                  </div>
                  <span className={`status-pill ${liveEndpointStatusClass(endpoint.status)}`}>
                    {formatModelRoutingLabel(endpoint.status)}
                  </span>
                </div>
                <div className="flex min-w-0 flex-wrap gap-2">
                  <span className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full border border-signal/40 bg-signal/10 px-3 py-1 font-mono text-xs text-signal break-words">
                    {endpointChip(endpoint.hosting_boundary)}
                  </span>
                  <span className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted break-words dark:border-white/15 dark:bg-white/5">
                    {endpointChip(endpoint.provider_type)}
                  </span>
                </div>
                <div>
                  <p className="eyebrow m-0">Default Model</p>
                  <p className="mx-0 mt-1 mb-0 font-mono text-[13px] text-ink break-words">
                    {endpoint.default_model}
                  </p>
                </div>
                <div>
                  <p className="eyebrow m-0">Task Types</p>
                  <div className="mt-1.5 flex min-w-0 flex-wrap gap-2">
                    {endpoint.task_types.map((taskType) => (
                      <span
                        className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 font-mono text-xs text-muted break-words dark:border-white/15 dark:bg-white/5"
                        key={taskType}
                      >
                        {taskType}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex min-w-0 flex-wrap items-center gap-3 border-t border-line/60 pt-3 dark:border-white/10">
                  <span
                    className={`inline-flex items-center gap-1.5 text-xs ${
                      endpoint.credential_attached ? "text-ink" : "text-muted"
                    }`}
                  >
                    <KeyRound size={14} />
                    {endpoint.credential_attached ? "Credential attached" : "No credential handle"}
                  </span>
                  <span
                    className={`inline-flex items-center gap-1.5 text-xs ${
                      endpoint.egress_policy_attached ? "text-ink" : "text-muted"
                    }`}
                  >
                    <ShieldCheck size={14} />
                    {endpoint.egress_policy_attached ? "Egress policy attached" : "No egress policy"}
                  </span>
                </div>
              </article>
            ))}
          </div>
        )}

        {endpoints.data && endpoints.data.endpoint_notes.length > 0 ? (
          <ul className="mx-0 mt-0 mb-0 grid list-disc gap-1.5 pl-5 text-xs leading-relaxed text-muted">
            {endpoints.data.endpoint_notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        ) : null}
      </div>

      {telemetry.data && telemetry.data.telemetry_notes.length > 0 ? (
        <div className="min-w-0 rounded-3xl border border-line bg-surface p-5 dark:border-white/10 dark:bg-white/5">
          <p className="eyebrow m-0">Telemetry Notes</p>
          <ul className="mx-0 mt-2.5 mb-0 grid list-disc gap-2 pl-5 text-sm leading-snug text-muted">
            {telemetry.data.telemetry_notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
