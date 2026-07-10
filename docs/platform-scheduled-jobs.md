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

### 4. Connector scheduled live sync — `axis-connector-scheduled-live-sync`

Worker-scheduled execution of governed connector live-sync runs (the doc-167
pattern applied to the connector stack; see
`docs/platform-connectors.md`, "Scheduled Live Sync Last Mile"). Unlike the
maintenance jobs this schedule is **registered only** when
`AXIS_CONNECTOR_SCHEDULED_LIVE_SYNC_ENABLED=true`, so flag-off deployments
keep today's exact schedule set. It additionally requires
`AXIS_CONNECTOR_SYNC_EXECUTION_ENABLED` and
`AXIS_CONNECTOR_LIVE_SYNC_EXECUTION_ENABLED`; with either off the candidate
listing is empty and nothing executes.

Each tick the `ConnectorScheduledLiveSyncWorkflow` drives four DB-owning
activities (`axis_worker.connector_live_sync_activities`), which call the
existing API-side claim/execute/release functions in
`axis_api.connector_runs` in process:

1. **list** dispatched (or failed-resumable) `scheduled_sync_plan` runs with
   `live_sync_requested=true` and an active credential lease for the
   configured tenant;
2. **claim** the latest committed batch checkpoint for resume runs. A racing
   worker hits the existing single-active-claim conflict (backed by the
   migration-0045 partial unique index) and the run is skipped as
   `skipped_claim_conflict`. Fresh runs need no resume claim. A claim inside
   its renewal guard is renewed before execution;
3. **execute** the existing sync-execution batch loop, which persists one
   committed checkpoint per batch and fails closed with resumable evidence;
4. **release** the claim with `scheduled_live_sync_completed` or
   `scheduled_live_sync_failed` — the failure path always releases so the next
   tick can re-claim and resume from the last committed checkpoint.

Idempotent: per-attempt execution ids/idempotency keys plus the run-level
replay rules make a repeated tick a no-op for completed runs; the schedule's
`SKIP` overlap policy prevents concurrent ticks.

Evidence: the standard connector run/checkpoint/claim audit trail
(`connector.run.sync_execution_*`, `connector.run.sync_batch_committed`,
`connector.run.sync_checkpoint_claim*`) recorded by the reused API functions,
with the worker actor `axis-scheduled-live-sync-worker`.

## Schedules, overlap and idempotency

Schedules use the modern Temporal Python SDK Schedule API (the repo pins
`temporalio` 1.29). Each job maps to one Schedule with an interval read from
`Settings`. The overlap policy is `SKIP`: a slow run never overlaps its
successor. Combined with each job being individually idempotent, repeated and
overlapping invocations are safe.

`axis_worker.schedules.register_maintenance_schedules` reconciles the schedules
on worker startup. It is create-or-update idempotent: the first run creates each
Schedule, subsequent runs update the existing Schedule's definition (action,
interval, overlap) in place without creating duplicates. The Temporal client is
used behind a narrow `ScheduleClientPort` protocol so tests drive a thin
in-memory fake and never require a live Temporal.

The reconciliation owns the schedule **definition**, not the operator's runtime
pause intent. The `AXIS_SCHEDULED_JOBS_ENABLED` flag governs only the paused
state of a **newly created** schedule. On update the existing paused state is
**preserved**, so an operator's pause or unpause in the Temporal UI survives
worker restarts and is never clobbered by reconciliation.

## Configuration

All flags default so that existing deployments and the default test suite are
unaffected (`AXIS_SCHEDULED_JOBS_ENABLED=false`).

| Setting | Default | Meaning |
| --- | --- | --- |
| `AXIS_SCHEDULED_JOBS_ENABLED` | `false` | Master enable flag. Governs the paused state of a **newly created** schedule only; existing schedules keep the operator's paused state on update. |
| `AXIS_SCHEDULED_AUDIT_RETENTION_INTERVAL_SECONDS` | `86400` | Audit retention sweep interval. |
| `AXIS_SCHEDULED_AUDIT_RETENTION_DAYS` | `365` | Retention window passed to the reused deletion function. |
| `AXIS_SCHEDULED_AUDIT_RETENTION_DRY_RUN` | `true` | Count only; set false to physically delete. |
| `AXIS_SCHEDULED_AUDIT_RETENTION_BATCH_LIMIT` | `500` | Max candidate rows per tenant per run. |
| `AXIS_SCHEDULED_SESSION_SWEEP_INTERVAL_SECONDS` | `900` | Session sweep interval. |
| `AXIS_SCHEDULED_SESSION_SWEEP_BATCH_LIMIT` | `500` | Max sessions per category per run. |
| `AXIS_SCHEDULED_TENANT_RECONCILIATION_INTERVAL_SECONDS` | `3600` | Reconciliation interval. |
| `AXIS_CONNECTOR_SCHEDULED_LIVE_SYNC_ENABLED` | `false` | Registers the connector scheduled live-sync schedule. Off keeps today's exact schedule set (the schedule is not created at all). |
| `AXIS_CONNECTOR_SCHEDULED_LIVE_SYNC_INTERVAL_SECONDS` | `3600` | Scheduled live-sync tick interval. |
| `AXIS_CONNECTOR_SCHEDULED_LIVE_SYNC_TENANT_ID` | `tenant_demo_manufacturing` | Tenant whose dispatched live-sync runs the worker executes. |

The session windows are shared with the request path:
`AXIS_OIDC_REFRESH_CLAIM_STALENESS_SECONDS`,
`AXIS_OIDC_SESSION_IDLE_TIMEOUT_SECONDS` and `absolute`/sliding session expiry.

When the master flag is false a newly created schedule is registered in the
`paused` state, so an operator can enable jobs either by flipping the flag and
restarting the worker, or by unpausing in the Temporal UI — an unpause is
preserved across subsequent restarts.

## Trust boundary

The jobs run under the actor id `axis-scheduled-jobs`, a trusted in-process
runner inside the worker with direct DB access. For the audit-retention path it
self-asserts the `audit:retention:delete` scope, so the permission check is
effectively a no-op for the scheduled path. This is **not** privilege
escalation — the code already runs in the trusted worker process and could
perform the deletion directly — but it is called out explicitly: the scheduled
path is not gated by an external principal's RBAC, so the guardrails are the
enable flag, the dry-run default and the tenant-scoped audit evidence, not the
permission decision.

## Scaling and failure isolation

- **All tenants, no silent truncation.** The retention and reconciliation jobs
  page through every tenant with a keyset cursor rather than a single limited
  query. A runaway guard (`MAX_TENANTS_PER_RUN`, 100k) exists only as a safety
  cap; if it is ever hit the job appends a `jobs_tenant_cap_reached` marker to
  its errors and the summary payload (`tenant_cap_reached: true`) and reports
  `partial_failure`, so truncation is never silent.
- **Per-unit commits, partial-failure safe.** Each tenant (retention,
  reconciliation) and each session batch (sweep) commits in its own transaction,
  so a later poisoned unit can never roll back earlier successes. If a unit's DB
  transaction is poisoned, the job records the error and continues; the job-run
  **summary evidence is always written in a fresh transaction**, so partial
  failures are recorded even when a working transaction was aborted.

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
  against a DB session factory: happy path, idempotent re-run, tenant scoping,
  audit evidence, nothing-to-do no-op, dry-run, the session sweep selection rules
  (stale refreshing revoked, fresh preserved, expired/idle purged, active
  preserved), suspended-tenant session remediation, multi-page tenant pagination,
  partial-failure isolation (a poisoned unit does not discard prior successes and
  the summary evidence is still written) and a boundary-equality test proving the
  sweep predicate matches the request-path `_stored_session_lifecycle_failure`
  check at the exact staleness threshold.
- `services/worker/tests/test_schedules.py` covers the schedule-registration
  bootstrap idempotency (create then update, no duplicates), the enable-flag
  paused/active seeding and that an operator's UI pause/unpause is preserved
  across restarts, with a thin fake Temporal client.
- `services/worker/tests/test_maintenance_activities.py` verifies the DB-owning
  activity seam against a real session.
- `services/worker/tests/integration/test_scheduled_jobs_integration.py` drives a
  scheduled workflow end-to-end through the Temporal test environment, behind
  `AXIS_RUN_INTEGRATION` like the other live-Temporal tests.
