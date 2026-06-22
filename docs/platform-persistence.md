# Platform Persistence Foundation

The persistence foundation adds the first Postgres-backed storage boundary for
governed operational state.

It is intentionally narrow: schema, ORM models, repository methods, a demo
approval decision endpoint, web console submission, demo permission enforcement,
workflow signal execution, action run creation and tests. Public demo reference
content now comes from persisted tenant-scoped bootstrap records for the main
reference surfaces, while production-grade reference storage and deterministic
workflow replay remain separate Platform work.

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

Subsequent connector migrations through `0021` add policy sets, replacement and
rollback evidence, draft revision adoption, replay simulation outputs,
connector manifests, credential leases and egress policy records.

The twenty-second Alembic migration adds:

- `demo_reference_records`: tenant-scoped public-safe reference payloads keyed
  by surface and reference id;
- a persisted manufacturing overview bootstrap record for
  `tenant_demo_manufacturing`;
- indexes for tenant, surface, reference, status and source filtering.

The twenty-third Alembic migration adds:

- a persisted manufacturing connector registry bootstrap record for
  `tenant_demo_manufacturing`;
- the public-safe connector manifest, runtime policy and preview metadata used
  by `GET /demo/manufacturing/connectors`.

The twenty-fourth Alembic migration adds:

- a persisted manufacturing agent registry bootstrap record for
  `tenant_demo_manufacturing`;
- the public-safe L1-L2 agent registry, policy boundaries, proposals and
  evidence references used by `GET /demo/manufacturing/agents`.

The twenty-fifth Alembic migration adds:

- a persisted manufacturing action registry bootstrap record for
  `tenant_demo_manufacturing`;
- the public-safe typed action catalog, schemas, policy boundaries, guardrails
  and dry-run sample payloads used by `GET /demo/manufacturing/actions`.

The twenty-sixth Alembic migration adds:

- a persisted manufacturing workflow console bootstrap record for
  `tenant_demo_manufacturing`;
- the public-safe workflow reference runs, pending governance signals, timeline
  evidence and runtime notes used by `GET /demo/manufacturing/workflows`.

The twenty-seventh Alembic migration adds:

- a persisted manufacturing approval inbox bootstrap record for
  `tenant_demo_manufacturing`;
- the public-safe approval queue, evidence, decision options, required
  permissions and workflow references used by
  `GET /demo/manufacturing/approvals` and the approval decision endpoint.

The twenty-eighth Alembic migration adds:

- a persisted manufacturing audit explorer bootstrap record for
  `tenant_demo_manufacturing`;
- the public-safe reference audit events, filter options, redacted payload
  previews and retention notes used by `GET /demo/manufacturing/audit`.

The twenty-ninth Alembic migration adds:

- a persisted manufacturing model routing bootstrap record for
  `tenant_demo_manufacturing`;
- the public-safe provider options, egress decisions, route telemetry, token
  estimates and cost posture used by `GET /demo/manufacturing/model-routing`.

The thirtieth Alembic migration adds:

- a persisted manufacturing ontology bootstrap record for
  `tenant_demo_manufacturing`;
- the public-safe ontology graph nodes, relationship scopes, source systems and
  permission notes used by `GET /demo/manufacturing/ontology` and
  `GET /demo/manufacturing/ontology/entities/{node_id}`.

## Repository Boundary

`AxisPersistenceRepository` provides:

- append-only audit event insert and tenant-scoped listing;
- approval record creation and decision update;
- approval listing by tenant and optional status;
- action run creation;
- idempotency lookup by tenant, action and key;
- action run result update;
- action run listing by tenant and optional status.
- demo reference record upsert and active record lookup by tenant, surface and
  reference id.
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
- web console submission to the persisted decision endpoint, with API
  persistence errors surfaced instead of local decision fallback.
- demo approval decision permission checks before persistence.
- workflow signal execution through the Axis workflow runtime adapter, with
  explicit degraded status when the runtime is unavailable.
- typed action run creation from demo action payloads, with permission checks,
  idempotency replay/conflict behavior and append-only action audit events.
- workflow signal execution from approval-gated action payloads after action
  run persistence, with redacted signal metadata in audit events.
- OIDC/JWKS token validation and actor binding for approval decision and action
  run mutation endpoints, with demo body actor/scopes kept as optional request
  metadata only when no bearer token is supplied.
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
  `connector.promotion_policy.authored`, `connector.promotion_policy.enabled`
  and `connector.promotion_policy.revised` audit writes. Draft revisions carry
  revision lineage, approval/workflow evidence and a tenant-scoped idempotency
  key; enabled required policies are not rewritten in place.
- connector promotion policy sets with versioned active-set metadata, required
  policy references, activation permission evidence, append-only
  `connector.promotion_policy_set.activated` and
  `connector.promotion_policy_set.replaced` /
  `connector.promotion_policy_set.rolled_back` audit writes, replacement and
  rollback approval/workflow evidence, atomic approved policy-revision adoption
  evidence through `connector.promotion_policy.revision_adopted`, superseded
  prior-set records and `policy_set_id` / `policy_ids` evidence on connector
  ontology promotions and proposals.
- connector ontology promotion rejection audit events with
  `connector.ontology_promotion.rejected`, effective policy/policy-set context,
  matched constraints, violations and permission evidence when policy gates
  block the mutation boundary before any promotion record is written.
- replay simulation outputs with governed `simulation.replay_output.persisted`
  audit writes, idempotency keys, artifact hashes, redacted artifact payloads,
  evidence refs, retention metadata and permission decisions.
- retention-aware replay response filtering across timeline events, audit
  events and persisted simulation outputs, including legal-hold bypass metadata.
- persisted manufacturing overview reference records through
  `demo_reference_records`, with the runtime seed function removed and the API
  returning 404/422 for missing or invalid persisted payloads.
- persisted manufacturing connector registry reference records through
  `demo_reference_records`, with the API reading
  `surface=connectors/reference_id=manufacturing-connector-registry` and
  returning 404/422 for missing or invalid persisted payloads.
- the connector registry runtime seed factory has been removed from the API
  module; registry contract tests now validate the Alembic bootstrap payload
  directly.
- file/CSV and external DB preview endpoints now read
  `surface=connectors/reference_id=manufacturing-connector-registry` to resolve
  connector ids, schema fields, row limits and public-safe sample rows before
  generating preview output, with 404/422 responses for missing or invalid
  registry references.
- connector configuration creation now reads
  `surface=connectors/reference_id=manufacturing-connector-registry` to resolve
  connector manifests and runtime boundaries before tenant configuration state
  is written.
- connector credential handle creation now reads
  `surface=connectors/reference_id=manufacturing-connector-registry` to validate
  connector ids before external secret reference metadata is written.
- connector ontology proposal creation now reads
  `surface=connectors/reference_id=manufacturing-connector-registry` to resolve
  connector runtime boundary metadata before proposal rows or audit events are
  written.
- connector run creation now reads
  `surface=connectors/reference_id=manufacturing-connector-registry` to resolve
  connector runtime boundary metadata before run rows or audit events are
  written.
- connector manual import request creation now reads
  `surface=connectors/reference_id=manufacturing-connector-registry` to resolve
  connector runtime boundary metadata before approval-gated import rows or
  audit events are written.
- connector promotion policy authoring, enablement and revision now read
  `surface=connectors/reference_id=manufacturing-connector-registry` to
  validate connector ids before policy rows, revision rows, enablement updates
  or audit events are written.
- connector promotion policy set activation, replacement and rollback now read
  `surface=connectors/reference_id=manufacturing-connector-registry` to
  validate connector ids before policy-set rows, replacement/rollback updates
  or audit events are written.
- persisted manufacturing agent registry reference records through
  `demo_reference_records`, with the API reading
  `surface=agents/reference_id=manufacturing-agent-registry` and returning
  404/422 for missing or invalid persisted payloads; the runtime seed factory
  has been removed from the API module and tests validate the Alembic bootstrap
  payload directly.
- persisted manufacturing action registry reference records through
  `demo_reference_records`, with the API reading
  `surface=actions/reference_id=manufacturing-action-registry`, action run
  creation validating against that persisted record, and both paths returning
  404/422 for missing or invalid persisted payloads; the runtime seed factory
  has been removed from the API module and tests validate the Alembic bootstrap
  payload directly.
- persisted manufacturing workflow console reference records through
  `demo_reference_records`, with the API reading
  `surface=workflows/reference_id=manufacturing-workflow-console` while the
  separate `/demo/manufacturing/workflows/runs` endpoint continues to query
  operational workflow run and timeline tables; the runtime seed factory has
  been removed from the API module and tests validate the Alembic bootstrap
  payload directly.
- persisted manufacturing approval inbox reference records through
  `demo_reference_records`, with the API reading
  `surface=approvals/reference_id=manufacturing-approval-inbox`, approval
  decisions validating against the same persisted inbox record and both paths
  returning 404/422 for missing or invalid persisted payloads; the runtime seed
  factory has been removed from the API module and tests validate the Alembic
  bootstrap payload directly.
- persisted manufacturing audit explorer reference records through
  `demo_reference_records`, with the API reading
  `surface=audit/reference_id=manufacturing-audit-explorer` while the separate
  `/demo/manufacturing/audit/events` and `/demo/manufacturing/audit/export`
  endpoints continue to query persisted `audit_events`; the runtime seed
  factory has been removed from the API module and tests validate the Alembic
  bootstrap payload directly.
- persisted manufacturing model routing reference records through
  `demo_reference_records`, with the API reading
  `surface=model-routing/reference_id=manufacturing-model-routing` while live
  provider routing, usage metering and billing adapters remain out of scope;
  the runtime seed factory has been removed from the API module and tests
  validate the Alembic bootstrap payload directly.
- persisted manufacturing ontology reference records through
  `demo_reference_records`, with graph and entity detail endpoints reading
  `surface=ontology/reference_id=manufacturing-ontology` before the ontology
  query runtime applies metadata and relationship-scope filtering; the runtime
  seed factory has been removed from the API module and tests validate the
  Alembic bootstrap payload directly.
- action run creation now also reads
  `surface=ontology/reference_id=manufacturing-ontology` to derive
  relationship scopes for typed payload fields marked as ontology references
  before action/audit state is written.

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
- deterministic Temporal replay and physical retention deletion jobs for
  simulation outputs.
