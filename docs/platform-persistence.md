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

The sixth Alembic migration adds:

- `connector_runs`: tenant-scoped metadata-only connector run records with
  redacted input/result summaries and linked audit event ids.

The seventh Alembic migration adds:

- `connector_ontology_proposals`: tenant-scoped review-only ontology proposal
  records derived from connector preview output, with redacted field summaries,
  linked audit event ids and `graph_mutation_status=not_applied`.

The eighth Alembic migration adds:

- `connector_manual_import_requests`: tenant-scoped approval-gated manual
  import request records with idempotency keys, workflow ids, proposal ids,
  redacted import summaries, linked audit event ids and
  `graph_mutation_status=not_applied`.

The ninth Alembic migration adds decision evidence to manual import requests:

- nullable decision, decision actor, note and timestamp columns;
- nullable workflow signal JSON evidence;
- indexes for decision and decision actor filtering.

The tenth Alembic migration adds controlled ontology promotion evidence:

- nullable latest promotion fields on `connector_ontology_proposals`;
- `connector_ontology_promotions`: tenant-scoped, idempotent promotion records
  that link a proposal, approved manual import, actor, permission decision,
  ontology mutation result and append-only audit event;
- unique constraints for `(tenant_id, promotion_id)` and
  `(tenant_id, idempotency_key)`;
- indexes for promotion, proposal, manual import, status and graph mutation
  filtering.

The eleventh Alembic migration adds connector promotion policy authoring
evidence:

- `connector_promotion_policies`: tenant-scoped policy drafts for connector
  proposal promotion governance;
- unique constraint for `(tenant_id, policy_id)`;
- required authoring scope, required promotion scopes, manual import status,
  workflow signal status, allowed risk levels, allowed ontology types and review
  window metadata;
- linked append-only `connector.promotion_policy.authored` audit event;
- indexes for connector, policy, version, status, enforcement mode and author
  filtering.

The twelfth Alembic migration adds connector promotion policy enforcement
evidence:

- nullable `policy_id` and `policy_decision` fields on connector ontology
  promotions;
- nullable `policy_id` and `policy_decision` fields on connector ontology
  proposals for latest promotion evidence;
- indexes for policy-linked proposal and promotion filtering.

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
- connector run creation and tenant-scoped listing.
- connector ontology proposal creation and tenant-scoped listing.
- connector ontology promotion creation, idempotency lookup, tenant-scoped
  listing and proposal promotion update.
- connector promotion policy creation, policy lookup and tenant-scoped listing.
- connector manual import request creation, idempotency lookup and
  tenant-scoped listing.
- connector manual import decision recording with workflow signal evidence.

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
  `workflow_timeline_events` and redacted `audit_events`, including governed
  connector policy-set version diff previews.
- persisted workflow run state and tenant-scoped history views.
- tenant-scoped connector configuration records for preview-only connector
  setup, with raw credential fields rejected before persistence.
- metadata-only connector credential handles with external secret references
  and rotation history, without storing raw credential values.
- metadata-only connector run records with append-only
  `connector.run.recorded` audit writes and raw payload field rejection.
- review-only connector ontology proposals with append-only
  `connector.ontology_proposals.recorded` audit writes, graph-write rejection
  and raw payload field rejection.
- approval/workflow/idempotency-gated connector manual import requests with
  append-only `connector.manual_import.requested` audit writes, idempotent
  replay, conflict detection, graph-write rejection and raw payload field
  rejection.
- connector manual import decisions with approval outcome persistence,
  workflow signal evidence and append-only
  `connector.manual_import.decision_recorded` audit writes, while graph
  mutation remains `not_applied`.
- controlled connector ontology promotions with approval/manual-import
  evidence, TypeDB mutation adapter result, idempotency enforcement,
  append-only `connector.ontology_promotion.*` audit writes and latest
  promotion evidence on the proposal record.
- connector promotion policies with authoring permission evidence, required
  promotion scopes, required manual-import/workflow states, enforcement evidence
  on promotions, auto-selected required policy ids on promotion/proposal
  records, approval/workflow-gated enablement evidence and append-only
  `connector.promotion_policy.authored` plus `connector.promotion_policy.enabled`
  audit writes.
- connector promotion policy sets with versioned active-set metadata, required
  policy references, activation permission evidence, append-only
  `connector.promotion_policy_set.activated` and
  `connector.promotion_policy_set.replaced` /
  `connector.promotion_policy_set.rolled_back` audit writes, replacement and
  rollback approval/workflow evidence, superseded prior-set records and
  `policy_set_id` / `policy_ids` evidence on connector ontology promotions and
  proposals.
- connector ontology promotion rejection audit events with
  `connector.ontology_promotion.rejected`, effective policy/policy-set context,
  matched constraints, violations and permission evidence when policy gates
  block the mutation boundary before any promotion record is written.

Still Platform work:

- connector execution from persisted run records;
- production vault/KMS integration, secret leasing and automated rotation;
- scheduled connector sync lifecycle;
- production connector mutations from action runtime paths;
- broader relationship-aware permission enforcement beyond the current demo
  ontology-scope checks;
- WORM/KMS-backed immutable storage hardening beyond insert-only repository
  shape and export hash-chain proof;
- physical retention deletion jobs and legal hold workflows;
- deterministic Temporal replay and persisted simulation outputs.
