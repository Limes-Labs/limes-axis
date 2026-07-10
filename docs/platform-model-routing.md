# Platform Model Routing And Cost Observability

The model routing surface has two parts: the read-only reference telemetry
view described below, and a flag-gated execution slice.

The execution slice registers tenant-scoped model endpoints through
`GET/POST /platform/models/endpoints` (openai-compatible providers;
`self_hosted`, `approved_private_endpoint` and `external` hosting boundaries;
scope `platform:model:endpoint:admin`) and runs governed invocations through
`POST /platform/models/invocations` (scope `models:invoke`), with routing
telemetry at `GET /platform/models/routing/telemetry`. Execution requires
`AXIS_MODEL_ROUTING_EXECUTION_ENABLED=true` (default `false`; disabled
invocations record an honest deferred status). Invocation records are
metadata-only — token counts, latency, status and audit evidence; prompt text
is excerpted only up to `AXIS_MODEL_INVOCATION_PROMPT_EXCERPT_CHARS` (default
`0`) — and feed per-tenant usage metering. Non-self-hosted egress stays
separately blocked while `AXIS_EXTERNAL_MODEL_EGRESS_ENABLED=false`.

The reference telemetry view is read-only. The endpoint reads a persisted
tenant-scoped bootstrap record instead of a route-owned runtime seed. It does
not call a live model provider, does not send prompts outside the demo tenant
boundary and does not enforce production budgets yet.

The API module no longer defines a model routing runtime seed factory. Contract
tests validate the Alembic bootstrap payload directly against the public API
schema.

## API

```text
GET /demo/manufacturing/model-routing
```

The endpoint reads the active `demo_reference_records` row for
`surface=model-routing` and `reference_id=manufacturing-model-routing`, then
returns:

- tenant, plant, scenario and timestamp metadata;
- top-level metrics for route decisions, blocked egress, estimated spend and
  agent coverage;
- provider options with hosting boundary, egress mode, cost basis and allowed
  policies;
- route telemetry for each demo agent;
- model policy, prompt classification, token estimates and cost estimates;
- decision reason, required permissions, evidence references and audit event ID;
- budget and observability notes.

Missing persisted reference records return 404. Invalid or tenant-mismatched
payloads return 422.

## Console

The `/model-routing` page shows:

- route telemetry filters for domain, provider and egress decision;
- selected route detail with provider, model, token count, latency and
  estimated cost;
- policy posture for external egress requested/allowed;
- required permissions, evidence refs and observability event names;
- provider boundary metadata;
- budget and OpenTelemetry-first observability notes.

## Current Scope

Delivered:

- read-only reference route telemetry;
- persisted bootstrap record for the reference route telemetry;
- runtime seed factory removed from the API module;
- blocked external route visibility;
- local and approved-provider route examples;
- token and cost estimates;
- API response contracts;
- Playwright smoke coverage for API-required behavior;
- flag-gated model endpoint registration and governed invocations
  (`AXIS_MODEL_ROUTING_EXECUTION_ENABLED`, off by default) with the
  openai-compatible provider adapter;
- metadata-only persisted invocation records with audit ledger evidence and
  per-tenant usage metering;
- model-routed agent proposals through the governed agent run slice.

Still Platform work:

- additional provider adapters beyond openai-compatible endpoints;
- provider-specific billing ingestion;
- tenant-scoped budget enforcement;
- policy-managed exception workflow for external model egress.
