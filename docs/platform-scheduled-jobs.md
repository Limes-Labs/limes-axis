# Platform Scheduled Jobs

The scheduled-jobs slice adds periodic background maintenance to the platform.
Before it, all maintenance was request-driven or lazy: audit retention deletion
only ran on an explicit `POST`, orphaned `refreshing` sessions were only
recovered when the same cookie was presented again, expired sessions lingered at
rest until re-presented, and tenant state was only ever reconciled through the
in-process TTL cache. This slice runs three maintenance jobs on Temporal
Schedules so the work happens on a cadence, unattended.

The jobs run in the Temporal worker (`services/worker`), not the API process.

## Architecture

The worker owns a SQLAlchemy session factory built from the shared
`axis_api.config.Settings` (`axis_api.db.create_session_factory`) — the same
configuration and persistence layer the API uses. The worker depends on the API
package through a local path source (`tool.uv.sources` in
`services/worker/pyproject.toml`), mirroring how `packages/sdk-python` depends on
the API. This means the jobs reuse the API's persistence methods and services
directly and never duplicate business logic:

- audit retention reuses `axis_api.audit_queries.execute_audit_retention_deletion`
  (the same function the retention endpoint calls);
- the session sweep reuses the request-path revoke primitives
  (`AxisPersistenceRepository.revoke_oidc_browser_session` plus the
  `identity.oidc_session.revoked` audit event), so a swept session is
  indistinguishable from one recovered lazily on presentation;
- tenant reconciliation reuses the tenant/quota persistence readers and the
  documented lifecycle/quota enums.

The reusable job functions live in `axis_api.maintenance_jobs`. They operate on
an `AxisPersistenceRepository` bound to a caller-provided session, so they are
driven by the worker against Postgres in production and unit-tested directly
against an in-memory SQLite session with no live Temporal.

```text
Temporal Schedule (interval)
  -> Scheduled Workflow (axis_worker.workflows.maintenance_workflows)
    -> DB-owning Activity (axis_worker.maintenance_activities)
      -> Reusable job function (axis_api.maintenance_jobs)
        -> Existing persistence / service functions (axis_api.*)
```

## Jobs

Each job is tenant-scoped where applicable, idempotent, audited (a job-run
evidence event with counts and no sensitive payloads), observable (a structured
`JobRunResult` carrying items scanned/affected and a duration) and fail-closed
(a per-item failure is recorded in `errors` and surfaced as
`status="partial_failure"`, never silently swallowed).

### 1. Audit retention deletion — `axis-audit-retention-deletion`

Sweeps audit retention deletion across every tenant by calling
`execute_audit_retention_deletion` per tenant with the scheduled actor holding
the `audit:retention:delete` scope. Legal holds and dry-run behavior are honored
by the reused function. Idempotent: once eligible rows are deleted, the next run
finds no further candidates. Defaults to **dry-run** so it counts without
deleting until an operator opts into physical deletion.

Summary evidence: `platform.scheduled_job.audit_retention.completed`.

### 2. Orphaned / expired session sweep — `axis-orphaned-session-sweep`

Revokes browser sessions that the request path only handles lazily:

- **orphaned `refreshing`**: rows whose `updated_at` is older than the refresh
  claim staleness window (`AXIS_OIDC_REFRESH_CLAIM_STALENESS_SECONDS`) — the
  refreshing process crashed between claim and completion;
- **expired `active`**: rows past their sliding `expires_at`, past their
  `absolute_expires_at`, or idle beyond the idle timeout
  (`AXIS_OIDC_SESSION_IDLE_TIMEOUT_SECONDS`).

Both are revoked through the shared revoke path with a distinct audit reason
(`refresh_claim_orphaned_sweep` / `session_expired_sweep`). Fresh sessions are
preserved. Idempotent: revoked rows leave the candidate set, so a re-run is a
no-op.

Summary evidence: `platform.scheduled_job.session_sweep.completed`.

### 3. Tenant state reconciliation — `axis-tenant-state-reconciliation`

A real consistency pass (not a no-op). For every tenant it:

- validates the lifecycle status against the documented enum
  (`active`/`suspended`/`pending_deletion`);
- validates every quota row's key against `TenantQuotaKey` and its value for
  non-negativity;
- fail-closed remediation: a suspended or pending-deletion tenant must not retain
  usable sessions, so lingering `active` browser sessions are revoked through the
  shared revoke path (reason `tenant_state_reconciliation_sweep`).

Every tenant with a finding or remediation records per-tenant evidence; a summary
event records aggregate counts. Idempotent: a clean tenant produces no findings
and no revocations on re-run.

Summary evidence: `platform.scheduled_job.tenant_reconciliation.completed`.

## Schedules, overlap and idempotency

Schedules use the modern Temporal Python SDK Schedule API (the repo pins
`temporalio` 1.29). Each job maps to one Schedule with an interval read from
`Settings`. The overlap policy is `SKIP`: a slow run never overlaps its
successor. Combined with each job being individually idempotent, repeated and
overlapping invocations are safe.

`axis_worker.schedules.register_maintenance_schedules` reconciles the schedules
on worker startup. It is create-or-update idempotent: the first run creates each
Schedule, subsequent runs update the existing Schedule in place (interval,
overlap, paused state) without creating duplicates. The Temporal client is used
behind a narrow `ScheduleClientPort` protocol so tests drive a thin in-memory
fake and never require a live Temporal.

## Configuration

All flags default so that existing deployments and the default test suite are
unaffected (`AXIS_SCHEDULED_JOBS_ENABLED=false`).

| Setting | Default | Meaning |
| --- | --- | --- |
| `AXIS_SCHEDULED_JOBS_ENABLED` | `false` | Master enable flag. When false, schedules are still reconciled but registered **paused**. |
| `AXIS_SCHEDULED_AUDIT_RETENTION_INTERVAL_SECONDS` | `86400` | Audit retention sweep interval. |
| `AXIS_SCHEDULED_AUDIT_RETENTION_DAYS` | `365` | Retention window passed to the reused deletion function. |
| `AXIS_SCHEDULED_AUDIT_RETENTION_DRY_RUN` | `true` | Count only; set false to physically delete. |
| `AXIS_SCHEDULED_AUDIT_RETENTION_BATCH_LIMIT` | `500` | Max candidate rows per tenant per run. |
| `AXIS_SCHEDULED_SESSION_SWEEP_INTERVAL_SECONDS` | `900` | Session sweep interval. |
| `AXIS_SCHEDULED_SESSION_SWEEP_BATCH_LIMIT` | `500` | Max sessions per category per run. |
| `AXIS_SCHEDULED_TENANT_RECONCILIATION_INTERVAL_SECONDS` | `3600` | Reconciliation interval. |

The session windows are shared with the request path:
`AXIS_OIDC_REFRESH_CLAIM_STALENESS_SECONDS`,
`AXIS_OIDC_SESSION_IDLE_TIMEOUT_SECONDS` and `absolute`/sliding session expiry.

When the master flag is false the schedules are registered in the `paused` state,
so an operator can enable jobs by flipping the flag (or unpausing in the Temporal
UI) without redeploying.

## Observability

Every job returns a structured `JobRunResult` (job name, status, tenants/items
scanned, items affected, duration in ms, audit event ids, per-tenant details,
errors). The worker logs a one-line structured summary per run. Every run also
appends a tenant-scoped (or `platform`-scoped) job-run audit event carrying
counts only — never raw payloads.

## Deployment

The worker is deployed as its own process:

- **docker-compose** (`infra/docker/docker-compose.yml`): a `worker` service
  built from `services/worker/Dockerfile`, depending on `postgres` (healthy) and
  `temporal`, with `AXIS_POSTGRES_DSN`, `AXIS_TEMPORAL_ADDRESS` and
  `AXIS_SCHEDULED_JOBS_ENABLED` wired.
- **Helm** (`infra/helm/limes-axis`): a `worker` Deployment
  (`templates/worker-deployment.yaml`) sharing the platform ConfigMap and Secret.
  Interval/enable settings live under `worker.scheduledJobs` in `values.yaml` and
  flow into the ConfigMap. A single replica avoids redundant schedule
  reconciliation; the schedule overlap policy protects against overlapping runs
  regardless of replica count.
- **Local**: `make worker` runs `python -m axis_worker` against the dev stack.

The worker entry point is `axis_worker.runtime` (`python -m axis_worker`): it
connects to Temporal, reconciles the schedules, then runs a Temporal worker on
the `axis-foundation` task queue hosting the approval workflow plus the three
scheduled maintenance workflows and their activities.

## Testing

- `services/api/tests/test_maintenance_jobs.py` exercises each job directly
  against a DB session: happy path, idempotent re-run, tenant scoping, audit
  evidence, nothing-to-do no-op, dry-run, and the session sweep selection rules
  (stale refreshing revoked, fresh preserved, expired/idle purged, active
  preserved) plus suspended-tenant session remediation.
- `services/worker/tests/test_schedules.py` covers the schedule-registration
  bootstrap idempotency (create then update, no duplicates) with a thin fake
  Temporal client.
- `services/worker/tests/test_maintenance_activities.py` verifies the DB-owning
  activity seam against a real session.
- `services/worker/tests/integration/test_scheduled_jobs_integration.py` drives a
  scheduled workflow end-to-end through the Temporal test environment, behind
  `AXIS_RUN_INTEGRATION` like the other live-Temporal tests.
