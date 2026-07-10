# Platform Usage Metering

Per-tenant quotas (see [`platform-tenants.md`](platform-tenants.md)) are
**instantaneous ceilings** — the most API requests per window, the most
concurrent sessions, the most rows a sync run may read. They answer "is this one
action allowed right now?" They keep no history. Usage metering is the missing
**cumulative accounting layer**: a per-tenant consumption ledger that records how
much of each metered surface a tenant actually consumed over time. Quotas gate;
metering accounts. Billing is a future consumer of this ledger, not part of this
slice.

## Metrics

Three typed metrics ship, each mapped to an existing enforcement choke point.
The metric key is an extensible, free-form column, so new metered surfaces add a
member to `TenantUsageMetric` without a schema change.

| Metric key            | Choke point                              | Quantity              |
| --------------------- | ---------------------------------------- | --------------------- |
| `api_request`         | rate-limit middleware (`rate_limit.py`)  | 1 per metered request |
| `connector_sync_rows` | governed live-sync run (`connector_runs.py`) | actual rows read  |
| `session_created`     | OIDC callback session creation (`main.py`) | 1 per session       |

Metering only records for **tenant-resolved** activity. `api_request` reuses the
exact verified-cookie tenant resolution the rate limiter uses (bearer requests,
which the middleware does not resolve, are not metered). Without a tenant context
metering is a no-op, so there is no behavior change when the feature is off or
there is no tenant.

## Aggregation Semantics

Consumption is bucketed into epoch-aligned period windows
(`AXIS_USAGE_METERING_AGGREGATION_WINDOW_SECONDS`, default 86400 = UTC-day
buckets). Each `(tenant_id, metric_key, period_start)` is one running-total row in
`tenant_usage_records`; deltas fold into it with an **upsert-add**
(`INSERT ... ON CONFLICT DO UPDATE SET quantity = quantity + excluded.quantity`).
The unique constraint + composite index on `(tenant_id, metric_key, period_start)`
back both the upsert target and the aggregation reads.

### Accumulate-then-flush vs per-event insert

At API-request volume a row insert per request is far too heavy, so the two
paths differ deliberately:

- **`api_request` (hot path)** accumulates in a bounded, thread-safe in-process
  aggregator (`UsageAccumulator`). `record()` is an in-memory dict increment
  under a short-held lock — no I/O on the request path. A background flush loop
  in the API process drains the aggregator every
  `AXIS_USAGE_METERING_FLUSH_INTERVAL_SECONDS` and upsert-adds the batched
  counts; a final drain runs on clean shutdown.
- **`connector_sync_rows` and `session_created` (low volume)** record
  synchronously and durably on the same transaction that persisted the
  underlying event, so their consumption is never at risk across a crash window.

Both paths land on the same `add_tenant_usage` upsert-add.

### Correctness under concurrency

- **DB level.** The upsert-add is a single SQL statement under a row lock, so
  concurrent flushers, replicas and the synchronous recorders can all target the
  same bucket row without losing or double-counting deltas.
- **In-process aggregator.** `record` folds under a lock. `flush` calls `drain`,
  which atomically swaps out every pending bucket exactly once; the drained
  deltas are committed once. On a DB error the drained deltas are **restored**
  (added back under the lock, merged with any new increments) and re-raised, so a
  transient failure is retried on the next flush with **no loss and no double
  count**. When metering is disabled `record` is a no-op.

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

Migration `0049_tenant_usage_records` (down revision
`0048_session_device_metadata`) creates `tenant_usage_records`:
`id`, `tenant_id`, `metric_key`, `period_start`, `quantity` (bigint running
total), `dimensions` (JSONB, no sensitive data), `first_recorded_at`,
`last_recorded_at`, `created_at`, `updated_at`, with a unique constraint and a
composite index on `(tenant_id, metric_key, period_start)`.
