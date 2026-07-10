import { describe, expect, it } from "vitest";

import {
  MODEL_INVOCATION_DEFERRED_STATUS,
  ModelRoutingLiveParseError,
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
} from "./model-routing-live";

const telemetryRouteFixture = {
  route_id: "3d1c2a3e-1111-4f2b-8a3c-9d8e7f6a5b4c",
  agent_id: "agent-runner-role",
  agent_name: "agent-runner-role",
  domain: "agent_proposal",
  provider_id: "local-vllm-endpoint",
  provider_name: "local-vllm-endpoint",
  model: "qwen2.5-7b-instruct",
  model_policy: "self_hosted",
  prompt_classification: "hash_only_no_body_persisted",
  data_boundary: "self_hosted",
  external_egress_requested: false,
  external_egress_allowed: false,
  egress_decision: "allowed_self_hosted",
  decision_reason: "routed",
  route_status: "ready",
  input_tokens: 812,
  output_tokens: 164,
  estimated_cost_eur: 0.0032,
  latency_ms: 640,
  cost_center: "platform-model-routing",
  required_permissions: ["models:invoke"],
  evidence_refs: ["model_invocation:3d1c2a3e-1111-4f2b-8a3c-9d8e7f6a5b4c"],
  audit_event_id: "audit-uuid-1",
  observability_events: ["model.invocation.recorded"],
};

const invocationFixture = {
  tenant_id: "tenant_demo_manufacturing",
  invocation_id: "3d1c2a3e-1111-4f2b-8a3c-9d8e7f6a5b4c",
  idempotency_key: "idem-1",
  status: "model_invocation_completed",
  task_type: "agent_proposal",
  model_id: "qwen2.5-7b-instruct",
  endpoint_id: "local-vllm-endpoint",
  provider_type: "openai_compatible",
  hosting_boundary: "self_hosted",
  egress_decision: "allowed_self_hosted",
  input_tokens: 812,
  output_tokens: 164,
  estimated_cost_eur: 0.0032,
  latency_ms: 640,
  cost_basis: "estimated_from_endpoint_rates",
  requested_by: "agent-runner-role",
  created_at: "2026-07-09T10:15:00Z",
  audit_event_id: "audit-uuid-1",
  error_code: null,
  idempotent_replay: false,
  prompt_sha256: "a".repeat(64),
  route_decision: { status: "routed", reason: "routed", task_type: "agent_proposal" },
  permission_decision: { allowed: true, reason: "scope_present" },
};

describe("model routing live paths", () => {
  it("targets the platform model routing read surfaces", () => {
    expect(modelRoutingTelemetryPath).toBe("/platform/models/routing/telemetry?limit=100");
    expect(modelEndpointsPath).toBe("/platform/models/endpoints?limit=100");
    expect(modelInvocationsPath()).toBe("/platform/models/invocations?page_size=50");
    expect(modelInvocationsPath(20, "cursor-token")).toBe(
      "/platform/models/invocations?page_size=20&cursor=cursor-token",
    );
  });
});

describe("parseModelRoutingTelemetry", () => {
  it("parses persisted telemetry routes with recorded values", () => {
    const telemetry = parseModelRoutingTelemetry({
      tenant_id: "tenant_demo_manufacturing",
      route_count: 1,
      routes: [telemetryRouteFixture],
      telemetry_notes: ["Routes project persisted model invocations."],
    });

    expect(telemetry.route_count).toBe(1);
    expect(telemetry.routes[0]).toMatchObject({
      route_id: telemetryRouteFixture.route_id,
      model: "qwen2.5-7b-instruct",
      egress_decision: "allowed_self_hosted",
      route_status: "ready",
      input_tokens: 812,
      output_tokens: 164,
      latency_ms: 640,
      audit_event_id: "audit-uuid-1",
    });
  });

  it("accepts an empty projection without fabricating routes", () => {
    const telemetry = parseModelRoutingTelemetry({
      tenant_id: "tenant_demo_manufacturing",
      route_count: 0,
      routes: [],
      telemetry_notes: [],
    });

    expect(telemetry.routes).toEqual([]);
    expect(telemetry.route_count).toBe(0);
  });

  it("rejects malformed telemetry instead of degrading silently", () => {
    expect(() => parseModelRoutingTelemetry(null)).toThrow(ModelRoutingLiveParseError);
    expect(() =>
      parseModelRoutingTelemetry({ tenant_id: "t", route_count: "1", routes: [] }),
    ).toThrow(ModelRoutingLiveParseError);
    expect(() =>
      parseModelRoutingTelemetry({
        tenant_id: "t",
        route_count: 1,
        routes: [{ ...telemetryRouteFixture, route_status: "online" }],
      }),
    ).toThrow(/route_status/);
  });
});

describe("parseModelEndpointRegistry", () => {
  const endpointFixture = {
    tenant_id: "tenant_demo_manufacturing",
    endpoint_id: "local-vllm-endpoint",
    display_name: "Local vLLM",
    provider_type: "openai_compatible",
    hosting_boundary: "self_hosted",
    base_url: "http://vllm.internal:8000",
    default_model: "qwen2.5-7b-instruct",
    task_types: ["agent_proposal", "summarization"],
    status: "enabled",
    credential_handle_id: "credential_handle_vllm",
    egress_policy_id: null,
    cost_input_per_1k: 0.0,
    cost_output_per_1k: 0.0,
    created_by: "platform-model-operator-role",
    audit_event_id: "audit-uuid-2",
    audit_event_type: "model.endpoint.registered",
    notes: [],
    created_at: "2026-07-08T08:00:00Z",
  };

  it("reduces the credential handle to a presence flag and drops the ref", () => {
    const registry = parseModelEndpointRegistry({
      tenant_id: "tenant_demo_manufacturing",
      endpoint_count: 1,
      enabled_endpoint_count: 1,
      endpoints: [endpointFixture],
      endpoint_notes: ["Model endpoints are metadata-only routing targets."],
    });

    const endpoint = registry.endpoints[0];
    expect(endpoint.credential_attached).toBe(true);
    expect(endpoint.egress_policy_attached).toBe(false);
    expect(JSON.stringify(registry)).not.toContain("credential_handle_vllm");
    expect(endpoint).toMatchObject({
      endpoint_id: "local-vllm-endpoint",
      hosting_boundary: "self_hosted",
      default_model: "qwen2.5-7b-instruct",
      status: "enabled",
      task_types: ["agent_proposal", "summarization"],
    });
  });

  it("marks endpoints without a credential handle as detached", () => {
    const registry = parseModelEndpointRegistry({
      tenant_id: "tenant_demo_manufacturing",
      endpoint_count: 1,
      enabled_endpoint_count: 0,
      endpoints: [{ ...endpointFixture, credential_handle_id: null, status: "disabled" }],
      endpoint_notes: [],
    });

    expect(registry.endpoints[0].credential_attached).toBe(false);
    expect(registry.enabled_endpoint_count).toBe(0);
  });

  it("rejects malformed endpoint payloads", () => {
    expect(() => parseModelEndpointRegistry([])).toThrow(ModelRoutingLiveParseError);
    expect(() =>
      parseModelEndpointRegistry({
        tenant_id: "t",
        endpoint_count: 1,
        enabled_endpoint_count: 1,
        endpoints: [{ ...endpointFixture, task_types: "agent_proposal" }],
      }),
    ).toThrow(/task_types/);
  });
});

describe("parseModelInvocationList", () => {
  it("parses invocation records including deferred flag-gated results", () => {
    const list = parseModelInvocationList({
      tenant_id: "tenant_demo_manufacturing",
      invocations: [
        invocationFixture,
        {
          ...invocationFixture,
          invocation_id: "9f8e7d6c-2222-4a1b-9c8d-7e6f5a4b3c2d",
          status: MODEL_INVOCATION_DEFERRED_STATUS,
          model_id: null,
          endpoint_id: "local-vllm-endpoint",
          input_tokens: 0,
          output_tokens: 0,
          estimated_cost_eur: 0,
          latency_ms: 0,
        },
      ],
      has_more: true,
      next_cursor: "cursor-token",
      invocation_notes: ["Invocations are listed newest-first."],
    });

    expect(list.invocations).toHaveLength(2);
    expect(list.has_more).toBe(true);
    expect(list.next_cursor).toBe("cursor-token");
    expect(list.invocations[0]).toMatchObject({
      invocation_id: invocationFixture.invocation_id,
      status: "model_invocation_completed",
      task_type: "agent_proposal",
      estimated_cost_eur: 0.0032,
      audit_event_id: "audit-uuid-1",
    });
    expect(countDeferredModelInvocations(list.invocations)).toBe(1);
    expect(sumLiveInvocationCost(list.invocations)).toBeCloseTo(0.0032);
  });

  it("accepts an empty list without fabricating rows", () => {
    const list = parseModelInvocationList({ tenant_id: "tenant_demo_manufacturing" });

    expect(list.invocations).toEqual([]);
    expect(list.has_more).toBe(false);
    expect(list.next_cursor).toBeNull();
  });

  it("rejects malformed invocation payloads", () => {
    expect(() => parseModelInvocationList(undefined)).toThrow(ModelRoutingLiveParseError);
    expect(() =>
      parseModelInvocationList({
        tenant_id: "t",
        invocations: [{ ...invocationFixture, invocation_id: 12 }],
      }),
    ).toThrow(/invocation_id/);
  });
});

describe("live status helpers", () => {
  it("classifies invocation statuses honestly", () => {
    expect(isDeferredModelInvocationStatus(MODEL_INVOCATION_DEFERRED_STATUS)).toBe(true);
    expect(isDeferredModelInvocationStatus("model_invocation_completed")).toBe(false);
    expect(liveInvocationStatusClass("model_invocation_completed")).toBe("signal-ready");
    expect(liveInvocationStatusClass(MODEL_INVOCATION_DEFERRED_STATUS)).toBe("signal-watch");
    expect(liveInvocationStatusClass("failed")).toBe("signal-action-required");
  });

  it("classifies endpoint statuses", () => {
    expect(liveEndpointStatusClass("enabled")).toBe("signal-ready");
    expect(liveEndpointStatusClass("disabled")).toBe("signal-action-required");
    expect(liveEndpointStatusClass("draft")).toBe("signal-watch");
  });

  it("keeps tiny recorded costs visible instead of rounding to zero", () => {
    expect(formatLiveEuroCost(0)).toBe("EUR 0.00");
    expect(formatLiveEuroCost(0.0032)).toBe("EUR 0.0032");
    expect(formatLiveEuroCost(0.01)).toBe("EUR 0.01");
    expect(formatLiveEuroCost(1.5)).toBe("EUR 1.50");
  });

  it("formats timestamps without inventing values", () => {
    expect(formatLiveTimestamp("not-a-date")).toBe("Not recorded");
    expect(formatLiveTimestamp("2026-07-09T10:15:00Z")).toMatch(/2026/);
  });
});
