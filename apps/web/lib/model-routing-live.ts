import type { PlatformStatus } from "./platform-overview";

/**
 * Typed parsers for the live model-router read surfaces:
 *
 * - GET /platform/models/routing/telemetry — persisted invocations projected
 *   into the route-telemetry shape (route id = invocation id; tokens, cost,
 *   latency, egress decision and audit event id are recorded values).
 * - GET /platform/models/endpoints — metadata-only endpoint registry. The API
 *   returns a credential handle id (never credential material); the parser
 *   reduces it further to a presence flag so the console can only ever render
 *   "credential attached", not the handle reference itself.
 * - GET /platform/models/invocations — full invocation records (hash-based
 *   evidence; prompt and response bodies are never persisted).
 *
 * Parsing is strict: unexpected shapes raise ModelRoutingLiveParseError
 * instead of degrading into fabricated defaults.
 */

export const MODEL_INVOCATION_DEFERRED_STATUS = "model_invocation_deferred";

export const MODEL_ROUTING_EXECUTION_FLAG = "AXIS_MODEL_ROUTING_EXECUTION_ENABLED";

export const modelRoutingTelemetryPath = "/platform/models/routing/telemetry?limit=100";

export const modelEndpointsPath = "/platform/models/endpoints?limit=100";

export function modelInvocationsPath(pageSize = 50, cursor?: string | null): string {
  const params = new URLSearchParams({ page_size: String(pageSize) });
  if (cursor) {
    params.set("cursor", cursor);
  }
  return `/platform/models/invocations?${params.toString()}`;
}

export class ModelRoutingLiveParseError extends Error {
  readonly field: string;

  constructor(field: string, expected: string) {
    super(`Invalid model routing payload: ${field} is not ${expected}`);
    this.name = "ModelRoutingLiveParseError";
    this.field = field;
  }
}

function asRecord(value: unknown, field: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new ModelRoutingLiveParseError(field, "an object");
  }
  return value as Record<string, unknown>;
}

function asString(value: unknown, field: string): string {
  if (typeof value !== "string") {
    throw new ModelRoutingLiveParseError(field, "a string");
  }
  return value;
}

function asOptionalString(value: unknown, field: string): string | null {
  if (value === undefined || value === null) {
    return null;
  }
  return asString(value, field);
}

function asNumber(value: unknown, field: string): number {
  if (typeof value !== "number" || Number.isNaN(value)) {
    throw new ModelRoutingLiveParseError(field, "a number");
  }
  return value;
}

function asBoolean(value: unknown, field: string): boolean {
  if (typeof value !== "boolean") {
    throw new ModelRoutingLiveParseError(field, "a boolean");
  }
  return value;
}

function asStringArray(value: unknown, field: string): string[] {
  if (value === undefined || value === null) {
    return [];
  }
  if (!Array.isArray(value)) {
    throw new ModelRoutingLiveParseError(field, "an array of strings");
  }
  return value.map((entry, index) => asString(entry, `${field}[${index}]`));
}

const platformStatuses = new Set<PlatformStatus>(["ready", "watch", "action_required"]);

function asPlatformStatus(value: unknown, field: string): PlatformStatus {
  const status = asString(value, field);
  if (!platformStatuses.has(status as PlatformStatus)) {
    throw new ModelRoutingLiveParseError(field, "ready | watch | action_required");
  }
  return status as PlatformStatus;
}

export type LiveModelRoute = {
  route_id: string;
  agent_id: string;
  agent_name: string;
  domain: string;
  provider_id: string;
  provider_name: string;
  model: string;
  model_policy: string;
  data_boundary: string;
  external_egress_requested: boolean;
  external_egress_allowed: boolean;
  egress_decision: string;
  decision_reason: string;
  route_status: PlatformStatus;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_eur: number;
  latency_ms: number;
  audit_event_id: string;
  evidence_refs: string[];
};

export type LiveModelRoutingTelemetry = {
  tenant_id: string;
  route_count: number;
  routes: LiveModelRoute[];
  telemetry_notes: string[];
};

export function parseModelRoutingTelemetry(input: unknown): LiveModelRoutingTelemetry {
  const payload = asRecord(input, "telemetry");
  const routesInput = payload.routes ?? [];
  if (!Array.isArray(routesInput)) {
    throw new ModelRoutingLiveParseError("telemetry.routes", "an array");
  }

  return {
    tenant_id: asString(payload.tenant_id, "telemetry.tenant_id"),
    route_count: asNumber(payload.route_count, "telemetry.route_count"),
    routes: routesInput.map((entry, index) => {
      const route = asRecord(entry, `telemetry.routes[${index}]`);
      const field = (name: string) => `telemetry.routes[${index}].${name}`;
      return {
        route_id: asString(route.route_id, field("route_id")),
        agent_id: asString(route.agent_id, field("agent_id")),
        agent_name: asString(route.agent_name, field("agent_name")),
        domain: asString(route.domain, field("domain")),
        provider_id: asString(route.provider_id, field("provider_id")),
        provider_name: asString(route.provider_name, field("provider_name")),
        model: asString(route.model, field("model")),
        model_policy: asString(route.model_policy, field("model_policy")),
        data_boundary: asString(route.data_boundary, field("data_boundary")),
        external_egress_requested: asBoolean(
          route.external_egress_requested,
          field("external_egress_requested"),
        ),
        external_egress_allowed: asBoolean(
          route.external_egress_allowed,
          field("external_egress_allowed"),
        ),
        egress_decision: asString(route.egress_decision, field("egress_decision")),
        decision_reason: asString(route.decision_reason, field("decision_reason")),
        route_status: asPlatformStatus(route.route_status, field("route_status")),
        input_tokens: asNumber(route.input_tokens, field("input_tokens")),
        output_tokens: asNumber(route.output_tokens, field("output_tokens")),
        estimated_cost_eur: asNumber(route.estimated_cost_eur, field("estimated_cost_eur")),
        latency_ms: asNumber(route.latency_ms, field("latency_ms")),
        audit_event_id: asString(route.audit_event_id, field("audit_event_id")),
        evidence_refs: asStringArray(route.evidence_refs, field("evidence_refs")),
      };
    }),
    telemetry_notes: asStringArray(payload.telemetry_notes, "telemetry.telemetry_notes"),
  };
}

export type LiveModelEndpoint = {
  endpoint_id: string;
  display_name: string;
  provider_type: string;
  hosting_boundary: string;
  default_model: string;
  task_types: string[];
  status: string;
  /**
   * Presence-only credential indicator. The handle reference returned by the
   * API is intentionally dropped during parsing so it can never render.
   */
  credential_attached: boolean;
  egress_policy_attached: boolean;
  created_by: string;
  created_at: string;
  notes: string[];
};

export type LiveModelEndpointRegistry = {
  tenant_id: string;
  endpoint_count: number;
  enabled_endpoint_count: number;
  endpoints: LiveModelEndpoint[];
  endpoint_notes: string[];
};

export function parseModelEndpointRegistry(input: unknown): LiveModelEndpointRegistry {
  const payload = asRecord(input, "endpoints");
  const endpointsInput = payload.endpoints ?? [];
  if (!Array.isArray(endpointsInput)) {
    throw new ModelRoutingLiveParseError("endpoints.endpoints", "an array");
  }

  return {
    tenant_id: asString(payload.tenant_id, "endpoints.tenant_id"),
    endpoint_count: asNumber(payload.endpoint_count, "endpoints.endpoint_count"),
    enabled_endpoint_count: asNumber(
      payload.enabled_endpoint_count,
      "endpoints.enabled_endpoint_count",
    ),
    endpoints: endpointsInput.map((entry, index) => {
      const endpoint = asRecord(entry, `endpoints.endpoints[${index}]`);
      const field = (name: string) => `endpoints.endpoints[${index}].${name}`;
      return {
        endpoint_id: asString(endpoint.endpoint_id, field("endpoint_id")),
        display_name: asString(endpoint.display_name, field("display_name")),
        provider_type: asString(endpoint.provider_type, field("provider_type")),
        hosting_boundary: asString(endpoint.hosting_boundary, field("hosting_boundary")),
        default_model: asString(endpoint.default_model, field("default_model")),
        task_types: asStringArray(endpoint.task_types, field("task_types")),
        status: asString(endpoint.status, field("status")),
        credential_attached:
          asOptionalString(endpoint.credential_handle_id, field("credential_handle_id"))
          !== null,
        egress_policy_attached:
          asOptionalString(endpoint.egress_policy_id, field("egress_policy_id")) !== null,
        created_by: asString(endpoint.created_by, field("created_by")),
        created_at: asString(endpoint.created_at, field("created_at")),
        notes: asStringArray(endpoint.notes, field("notes")),
      };
    }),
    endpoint_notes: asStringArray(payload.endpoint_notes, "endpoints.endpoint_notes"),
  };
}

export type LiveModelInvocation = {
  invocation_id: string;
  status: string;
  task_type: string;
  model_id: string | null;
  endpoint_id: string | null;
  provider_type: string | null;
  hosting_boundary: string | null;
  egress_decision: string;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_eur: number;
  latency_ms: number;
  cost_basis: string;
  requested_by: string;
  created_at: string;
  audit_event_id: string | null;
  error_code: string | null;
  idempotent_replay: boolean;
};

export type LiveModelInvocationList = {
  tenant_id: string;
  invocations: LiveModelInvocation[];
  has_more: boolean;
  next_cursor: string | null;
  invocation_notes: string[];
};

export function parseModelInvocation(input: unknown, field = "invocation"): LiveModelInvocation {
  const invocation = asRecord(input, field);
  const at = (name: string) => `${field}.${name}`;
  return {
    invocation_id: asString(invocation.invocation_id, at("invocation_id")),
    status: asString(invocation.status, at("status")),
    task_type: asString(invocation.task_type, at("task_type")),
    model_id: asOptionalString(invocation.model_id, at("model_id")),
    endpoint_id: asOptionalString(invocation.endpoint_id, at("endpoint_id")),
    provider_type: asOptionalString(invocation.provider_type, at("provider_type")),
    hosting_boundary: asOptionalString(invocation.hosting_boundary, at("hosting_boundary")),
    egress_decision: asString(invocation.egress_decision, at("egress_decision")),
    input_tokens: asNumber(invocation.input_tokens ?? 0, at("input_tokens")),
    output_tokens: asNumber(invocation.output_tokens ?? 0, at("output_tokens")),
    estimated_cost_eur: asNumber(invocation.estimated_cost_eur ?? 0, at("estimated_cost_eur")),
    latency_ms: asNumber(invocation.latency_ms ?? 0, at("latency_ms")),
    cost_basis: asString(
      invocation.cost_basis ?? "estimated_from_endpoint_rates",
      at("cost_basis"),
    ),
    requested_by: asString(invocation.requested_by, at("requested_by")),
    created_at: asString(invocation.created_at, at("created_at")),
    audit_event_id: asOptionalString(invocation.audit_event_id, at("audit_event_id")),
    error_code: asOptionalString(invocation.error_code, at("error_code")),
    idempotent_replay: invocation.idempotent_replay === true,
  };
}

export function parseModelInvocationList(input: unknown): LiveModelInvocationList {
  const payload = asRecord(input, "invocations");
  const invocationsInput = payload.invocations ?? [];
  if (!Array.isArray(invocationsInput)) {
    throw new ModelRoutingLiveParseError("invocations.invocations", "an array");
  }

  return {
    tenant_id: asString(payload.tenant_id, "invocations.tenant_id"),
    invocations: invocationsInput.map((entry, index) =>
      parseModelInvocation(entry, `invocations.invocations[${index}]`),
    ),
    has_more: payload.has_more === true,
    next_cursor: asOptionalString(payload.next_cursor, "invocations.next_cursor"),
    invocation_notes: asStringArray(payload.invocation_notes, "invocations.invocation_notes"),
  };
}

export function isDeferredModelInvocationStatus(status: string): boolean {
  return status === MODEL_INVOCATION_DEFERRED_STATUS;
}

export function countDeferredModelInvocations(invocations: LiveModelInvocation[]): number {
  return invocations.filter((invocation) =>
    isDeferredModelInvocationStatus(invocation.status),
  ).length;
}

export function liveInvocationStatusClass(status: string): string {
  if (status === "model_invocation_completed" || status === "completed") {
    return "signal-ready";
  }
  if (isDeferredModelInvocationStatus(status) || status === "requested") {
    return "signal-watch";
  }
  return "signal-action-required";
}

export function liveEndpointStatusClass(status: string): string {
  if (status === "enabled") {
    return "signal-ready";
  }
  if (status === "disabled") {
    return "signal-action-required";
  }
  return "signal-watch";
}

export function sumLiveInvocationCost(invocations: LiveModelInvocation[]): number {
  return invocations.reduce((total, invocation) => total + invocation.estimated_cost_eur, 0);
}

/**
 * Live invocation costs are tiny per-call estimates; keep four decimals so a
 * recorded EUR 0.0032 never rounds down to a fabricated-looking EUR 0.00.
 */
export function formatLiveEuroCost(value: number): string {
  const rounded = Number(value.toFixed(4));
  return `EUR ${rounded.toFixed(Number.isInteger(rounded * 100) ? 2 : 4)}`;
}

export function formatLiveTimestamp(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "Not recorded";
  }
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}
