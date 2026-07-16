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

Every committed low-volume delta and every admitted request also has a row in
`tenant_usage_events` with immutable accounting payload and a mutable projection
marker. Its source identity
`(tenant_id, metric_key, source_type, source_id)` is unique. Inserting the event
and updating the rollup happen in one transaction for low-volume events. Request
events are journaled first and projected later; claiming the event and updating
the rollup still share one transaction. An identical retry is a no-op, while
reusing an identity with a different billing payload is an explicit idempotency
error.

Event dimensions remain in the journal. The period rollup is intentionally
non-dimensional; it cannot misrepresent a mixed bucket using whichever
provider, model, connector, or agent happened to arrive first.

### Durable admission and asynchronous projection

- **`api_request` (hot path)** writes one source-keyed journal event after
  authentication, tenant suspension checks and rate-limit admission, but before
  the application handler executes. A server-generated UUID is used as the
  source identity; client request IDs are never trusted for accounting. Handler
  4xx/5xx responses and crashes are still counted because the admitted request
  consumed platform capacity.
- **The projector** runs on every API replica. It atomically claims pending
  events in bounded batches, groups events by rollup key and applies one
  upsert-add per bucket. PostgreSQL replicas use `FOR UPDATE SKIP LOCKED`, so
  workers claim disjoint batches without a leader or duplicate projection.
- **Low-volume domain metrics** remain immediate: they write a source-keyed
  journal event and rollup in the same transaction that persists the session,
  connector execution, model invocation or agent run.

Requests are deliberately not metered when they are unauthenticated, belong to
a suspended tenant, fail rate-limit admission (`429`), fail a closed rate-limit
backend (`503`), use `OPTIONS`, or target health/OIDC session-control endpoints
(including refresh and logout).

### Correctness under concurrency

- **DB level.** The source-identity constraint prevents replay duplication. A
  projector transaction first marks only still-pending rows and receives their
  payloads through `UPDATE ... RETURNING`, then applies atomic upsert-adds. A
  rollback restores both the pending markers and the rollups. `first_recorded_at`
  and `last_recorded_at` use minimum/maximum semantics, so out-of-order events do
  not corrupt the observed range.
- **Admission retry.** The recorder reuses its server-generated event identity
  for an ambiguous-commit reconciliation read. It does not perform an internal
  write retry, avoiding retry storms; the client may retry the whole rejected
  request. PostgreSQL connect, pool, statement and lock waits are bounded. In
  `closed` mode, inability to establish a committed event returns a structured
  `503` before the handler runs. `open` mode is intended only for local or
  evaluation environments.
- **Rollout safety.** Migration `0053` marks every pre-existing journal event as
  projected because those events were already synchronously folded by older
  code. This prevents historical double counting during an upgrade.

Readiness exposes persistent projector failures and excessive oldest-event age.
Projection retries use bounded exponential backoff; committed journal events
remain recoverable across process crashes and restarts.

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

| Setting | Default | Meaning |
| --- | --- | --- |
| `AXIS_USAGE_METERING_ENABLED` | `false` | Master switch; off records nothing. |
| `AXIS_USAGE_METERING_FAILURE_MODE` | `open` | Admission DB failure policy; production requires `closed` when enabled. |
| `AXIS_USAGE_METERING_ADMISSION_STATEMENT_TIMEOUT_MS` | `1500` | PostgreSQL statement and lock budget for the admission transaction. |
| `AXIS_USAGE_METERING_FLUSH_INTERVAL_SECONDS` | `5.0` | Projector polling cadence. |
| `AXIS_USAGE_METERING_AGGREGATION_WINDOW_SECONDS` | `86400` | Period bucket width (60..86400 seconds). |
| `AXIS_USAGE_METERING_PROJECTION_BATCH_SIZE` | `500` | Maximum events claimed per transaction. |
| `AXIS_USAGE_METERING_PROJECTION_MAX_BATCHES_PER_TICK` | `10` | Work bound for one projector pass. |
| `AXIS_USAGE_METERING_PROJECTION_FAILURE_THRESHOLD` | `3` | Consecutive failures before readiness fails. |
| `AXIS_USAGE_METERING_PROJECTION_MAX_BACKLOG_AGE_SECONDS` | `60.0` | Oldest pending event age allowed by readiness. |
| `AXIS_USAGE_METERING_SHUTDOWN_TIMEOUT_SECONDS` | `10.0` | Maximum wait for an in-flight projector pass during shutdown. |

## Schema

Migration `0049_tenant_usage_records` creates the original rollup. Migration
`0052_tenant_usage_event_journal` adds `period_window_seconds` to its unique key
and creates `tenant_usage_events`. Migration `0053_usage_event_projection` adds
the nullable projection marker, safely backfills existing rows and creates a
partial pending-event index.

`tenant_usage_records` contains:
`id`, `tenant_id`, `metric_key`, `period_start`, `quantity` (bigint running
total), `period_window_seconds`, empty compatibility `dimensions`,
`first_recorded_at`, `last_recorded_at`, `created_at`, `updated_at`.

`tenant_usage_events` contains the immutable source identity, quantity, exact
dimensions, event and bucket timestamps, window width, journal timestamp and
nullable `projected_at` marker. The journal is sufficient to audit or rebuild
post-migration rollups; legacy rollup quantities remain valid but naturally have
no pre-0052 event rows.

High-volume deployments should define journal retention or time partitioning as
part of their capacity plan. Deleting projected rows is safe only after the
organization's billing audit and dispute-retention requirements are satisfied.
