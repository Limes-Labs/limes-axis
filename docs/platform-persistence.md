# Platform Persistence Foundation

The persistence foundation adds the first Postgres-backed storage boundary for
governed operational state.

It is intentionally narrow: schema, ORM models, repository methods, a demo
approval decision endpoint, web console submission, demo permission enforcement,
workflow signal execution, action run creation and tests. It does not yet
replace all public demo seeds or implement deterministic workflow replay.

## Tables

The second Alembic migration adds:

- `approval_records`: tenant-scoped approval requests, owner role, risk level,
  decision state, decision actor and decision timestamp.
- `action_runs`: tenant-scoped action execution records, idempotency key,
  execution mode, requested actor, optional approval/workflow references and
  result payload.

The existing `audit_events` table remains the append-only event foundation.

The third Alembic migration adds:

- `workflow_runs`: tenant-scoped workflow state, owner, runtime adapter,
  governance metadata, pending signals and replay flag.
- `workflow_timeline_events`: tenant-scoped workflow history events ordered by
  workflow-local sequence.

## Repository Boundary

`AxisPersistenceRepository` provides:

- append-only audit event insert and tenant-scoped listing;
- approval record creation and decision update;
- approval listing by tenant and optional status;
- action run creation;
- idempotency lookup by tenant, action and key;
- action run result update;
- action run listing by tenant and optional status.
- workflow run creation and tenant-scoped listing;
- workflow timeline event append and tenant-scoped history listing.

Repository methods flush but do not commit. Callers keep transaction ownership
through `session_scope` or an explicit SQLAlchemy session.

## Current Scope

Delivered:

- Alembic migration `0002_persistence_foundation`;
- SQLAlchemy models for `ApprovalRecord` and `ActionRun`;
- portable unit tests with SQLite in memory;
- Postgres integration check through Alembic head;
- tenant-scoped repository methods;
- idempotency uniqueness for action runs.
- persisted demo approval decisions with `approval.decision.recorded` audit
  events.
- web console submission to the persisted decision endpoint, with standalone
  local fallback when the API is unavailable.
- demo approval decision permission checks before persistence.
- workflow signal execution through the Axis workflow runtime adapter, with
  explicit degraded status when the runtime is unavailable.
- typed action run creation from demo action payloads, with permission checks,
  idempotency replay/conflict behavior and append-only action audit events.
- API-backed audit explorer queries from persisted `audit_events`, with tenant,
  event, actor, scope and limit filters.
- redacted audit export bundles with manifest checksum, applied filters and
  retention policy metadata.
- persisted workflow run state and tenant-scoped history views.

Still Platform work:

- production connector mutations from action runtime paths;
- production identity-bound permission enforcement;
- immutable storage hardening beyond insert-only repository shape;
- retention deletion enforcement and legal hold workflows;
- deterministic replay and simulation from persisted histories.
