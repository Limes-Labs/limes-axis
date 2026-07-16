# Platform Usage Metering

Per-tenant quotas (see [`platform-tenants.md`](platform-tenants.md)) are
**instantaneous ceilings** — the most API requests per window, the most
concurrent sessions, the most rows a sync run may read. They answer "is this one
action allowed right now?" They keep no history. Usage metering is the missing
**cumulative accounting layer**: a per-tenant consumption ledger that records how
much of each metered surface a tenant actually consumed over time. Quotas gate;
metering accounts. Billing adapters remain a downstream concern; this ledger
supplies their auditable accounting input.

## Metrics

Seven typed metrics ship, each mapped to an existing enforcement choke point.
The metric key is an extensible, free-form column, so new metered surfaces add a
member to `TenantUsageMetric` without a schema change.

| Metric key            | Choke point                              | Quantity              |
| --------------------- | ---------------------------------------- | --------------------- |
| `api_request`         | rate-limit middleware (`rate_limit.py`)  | 1 per metered request |
| `connector_sync_rows` | governed live-sync run (`connector_runs.py`) | actual rows read  |
| `session_created`     | OIDC callback session creation (`main.py`) | 1 per session       |
| `model_invocations`   | governed model router (`model_invocations.py`) | 1 per completed attempt |
| `model_input_tokens`  | governed model router (`model_invocations.py`) | provider input tokens |
| `model_output_tokens` | governed model router (`model_invocations.py`) | provider output tokens |
| `agent_runs`          | governed agent execution (`agent_runs.py`) | 1 per executed run |

Metering only records for **tenant-resolved** activity. `api_request` reuses the
same verified bearer or persisted-cookie tenant resolution the rate limiter
uses. Without a tenant context metering is a no-op.

## Aggregation Semantics

Consumption is bucketed into epoch-aligned period windows
(`AXIS_USAGE_METERING_AGGREGATION_WINDOW_SECONDS`, default 86400 = UTC-day
buckets). Each
`(tenant_id, metric_key, period_window_seconds, period_start)` is one
running-total row in `tenant_usage_records`; deltas fold into it with an
**upsert-add**
(`INSERT ... ON CONFLICT DO UPDATE SET quantity = quantity + excluded.quantity`).
Including the window width prevents an hourly bucket at midnight from colliding
with a daily bucket at the same timestamp.

Every committed low-volume delta and every flushed request batch also has an
immutable row in `tenant_usage_events`. Its source identity
`(tenant_id, metric_key, source_type, source_id)` is unique. Inserting the event
and updating the rollup happen in one transaction: an identical retry is a
no-op, while reusing an identity with a different billing payload is an explicit
idempotency error.

Event dimensions remain in the journal. The period rollup is intentionally
non-dimensional; it cannot misrepresent a mixed bucket using whichever
provider, model, connector, or agent happened to arrive first.

### Accumulate-then-flush vs per-event insert

At API-request volume a row insert per request is far too heavy, so the two
paths differ deliberately:

- **`api_request` (hot path)** accumulates in a bounded, thread-safe in-process
  aggregator (`UsageAccumulator`). `record()` is an in-memory dict increment
  under a short-held lock — no I/O on the request path. A background flush loop
  in the API process drains the aggregator every
  `AXIS_USAGE_METERING_FLUSH_INTERVAL_SECONDS` and upsert-adds the batched
  counts; a final drain runs on clean shutdown. Every drained batch receives a
  stable source ID, so retrying after an ambiguous commit cannot count it twice.
- **Low-volume domain metrics** record a source-keyed journal event on the same
  transaction that persisted the session, connector execution, model
  invocation, or agent run.

### Correctness under concurrency

- **DB level.** Journal insert and upsert-add share one transaction. The
  source-identity constraint prevents replay duplication; the upsert-add is a
  single SQL statement under a row lock, so
  concurrent flushers, replicas and the synchronous recorders can all target the
  same bucket row without losing increments. `first_recorded_at` and
  `last_recorded_at` use minimum/maximum semantics, so out-of-order events cannot
  move the observed time range backwards.
- **In-process aggregator.** `record` folds under a lock. `flush` calls `drain`,
  which atomically assigns identities to pending buckets. On a DB error the
  exact batches are restored without merging them into newer traffic, preserving
  retry identity. When metering is disabled `record` is a no-op.

The remaining boundary is explicit: an API process can still lose request
increments held only in memory if it suffers a hard crash before a flush.
Exactly-once retries are covered after a batch identity exists; billing-grade
durability for each admitted request requires a later durable admission/event
ingress. Low-volume domain metrics do not have this volatile window.

The flush loop is observable: it logs flushed volume at debug and logs (without
losing deltas) on failure.

## Read API

`GET /platform/tenants/{tenant_id}/usage` returns aggregated consumption per
metric over a queryable window. Query parameters:

- `last_days` (1..366, default 7) — window ending now, or
- `from` / `to` (ISO datetimes) — explicit window; `to` is exclusive.

The response is a summary plus a per-period breakdown:

```jsonc
{
  "tenant_id": "tenant_acme_manufacturing",
  "window_start": "2026-07-03T00:00:00Z",
  "window_end": "2026-07-10T12:00:00Z",
  "period_window_seconds": 86400,
  "metric_totals": [
    { "metric_key": "api_request", "quantity": 15 },
    { "metric_key": "session_created", "quantity": 2 }
  ],
  "periods": [
    { "period_start": "2026-07-08T00:00:00Z", "metric_key": "api_request", "quantity": 5 },
    { "period_start": "2026-07-09T00:00:00Z", "metric_key": "api_request", "quantity": 10 },
    { "period_start": "2026-07-09T00:00:00Z", "metric_key": "session_created", "quantity": 2 }
  ],
  "usage_notes": ["..."]
}
```

`window_start` is floored to its period bucket so a partial leading bucket is
included whole. An unknown tenant returns 404; an inverted window returns 422.

### Authorization

The read follows the same cross-tenant operator convention as the rest of the
platform-tenant surface: it requires the `platform:tenant:operator` scope plus a
dedicated `platform:tenant:usage` scope (billing-adjacent reads are kept
separable from the general tenant read scope). The operator authenticates under
their own tenant and reads any tenant's consumption; the usual principal-tenant
match is deliberately absent. The demo-mode caveat applies as everywhere: in
unauthenticated local demo mode the scope gate is not evaluated.

The usage read is a read and is not separately audited, matching the read
conventions on the rest of the platform-tenant surface.

## Console Surface

The tenant detail page (`/tenants/[tenantId]`) renders a read-only usage panel
below the lifecycle actions: one card per metric with the cumulative total over
the last 7 days and how many period buckets contributed. It reuses the tenant
console idioms — `axisFetch`, the loading / API-unavailable / tenant-not-found
states — and adds no dependencies.

## Configuration

| Setting                                          | Default | Meaning                                  |
| ------------------------------------------------ | ------- | ---------------------------------------- |
| `AXIS_USAGE_METERING_ENABLED`                    | `false` | Master switch; off records nothing.      |
| `AXIS_USAGE_METERING_FLUSH_INTERVAL_SECONDS`     | `5.0`   | Aggregator drain cadence (API process).  |
| `AXIS_USAGE_METERING_AGGREGATION_WINDOW_SECONDS` | `86400` | Period bucket width (60..86400 seconds). |

## Schema

Migration `0049_tenant_usage_records` creates the original rollup. Migration
`0052_tenant_usage_event_journal` adds `period_window_seconds` to its unique key
and creates `tenant_usage_events`.

`tenant_usage_records` contains:
`id`, `tenant_id`, `metric_key`, `period_start`, `quantity` (bigint running
total), `period_window_seconds`, empty compatibility `dimensions`,
`first_recorded_at`, `last_recorded_at`, `created_at`, `updated_at`.

`tenant_usage_events` contains the immutable source identity, quantity, exact
dimensions, event and bucket timestamps, window width, and journal timestamp.
The journal is sufficient to audit or rebuild post-migration rollups; legacy
rollup quantities remain valid but naturally have no pre-0052 event rows.
