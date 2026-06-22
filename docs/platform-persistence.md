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

The fourth Alembic migration adds:

- `connector_configurations`: tenant-scoped preview connector configuration,
  connector id, sync mode, runtime boundary, creator, public-safe configuration
  payload and credential reference ids.

The fifth Alembic migration adds:

- `connector_credential_handles`: tenant-scoped external secret references,
  rotation metadata, purpose, labels and notes for connector credentials.
- `connector_credential_rotations`: append-only rotation history metadata for
  credential handles.

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
- connector configuration creation and tenant-scoped listing.
- connector credential handle creation and tenant-scoped listing.
- connector credential rotation recording and tenant-scoped history listing.

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
- workflow signal execution from approval-gated action payloads after action
  run persistence, with redacted signal metadata in audit events.
- OIDC/JWKS token validation and actor binding for approval decision and action
  run mutation endpoints, with demo body actor/scopes kept as standalone
  fallback only.
- relationship-derived permission checks for authenticated ontology entity
  detail reads and action payload resource references.
- API-backed audit explorer queries from persisted `audit_events`, with tenant,
  event, actor, scope and limit filters.
- redacted audit export bundles with manifest checksum, applied filters and
  retention-window enforcement, legal-hold bypass metadata and hash-chain
  integrity proof.
- replay/simulation preview artifacts derived from `workflow_runs`,
  `workflow_timeline_events` and redacted `audit_events`.
- persisted workflow run state and tenant-scoped history views.
- tenant-scoped connector configuration records for preview-only connector
  setup, with raw credential fields rejected before persistence.
- metadata-only connector credential handles with external secret references
  and rotation history, without storing raw credential values.

Still Platform work:

- connector run records and append-only audit writes from connector execution;
- production vault/KMS integration, secret leasing and automated rotation;
- scheduled connector sync lifecycle;
- production connector mutations from action runtime paths;
- broader relationship-aware permission enforcement beyond the current demo
  ontology-scope checks;
- WORM/KMS-backed immutable storage hardening beyond insert-only repository
  shape and export hash-chain proof;
- physical retention deletion jobs and legal hold workflows;
- deterministic Temporal replay and persisted simulation outputs.
