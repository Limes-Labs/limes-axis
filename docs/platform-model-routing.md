# Platform Model Routing And Cost Observability

The model routing slice exposes the public-safe manufacturing demo view for
provider selection, egress decisions, token estimates, cost posture and audit
evidence.

It is read-only. The endpoint reads a persisted tenant-scoped bootstrap record
instead of a route-owned runtime seed. It does not call a live model provider,
does not send prompts outside the demo tenant boundary and does not enforce
production budgets yet.

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
- blocked external route visibility;
- local and approved-provider route examples;
- token and cost estimates;
- API response contracts;
- Playwright smoke coverage for API-required behavior.

Still Platform work:

- live provider adapters;
- provider-specific billing ingestion;
- tenant-scoped budget enforcement;
- persisted usage records;
- OpenTelemetry spans emitted by runtime code;
- policy-managed exception workflow for external model egress;
- audit ledger writes from live route decisions.
