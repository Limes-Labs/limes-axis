# Platform Persistence Foundation

The persistence foundation adds the first Postgres-backed storage boundary for
governed operational state.

It is intentionally narrow: schema, ORM models, repository methods, a demo
approval decision endpoint, web console submission, demo permission enforcement,
workflow signal execution, action run creation and tests. Public demo reference
content now comes from persisted tenant-scoped bootstrap records for the main
reference surfaces, while production-grade reference storage and deterministic
workflow replay remain separate Platform work. The API test suite includes a
module-level guard against reintroducing `get_manufacturing_*` runtime
reference factories in the public demo module.

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
Egress policy registry reads append public-safe read audit evidence and report
audit-ledger evidence invariants without copying private endpoint references or
policy documents into the read audit payload.

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

The thirty-first Alembic migration adds:

- `manufacturing_operation_records`: tenant-scoped operational records keyed by
  tenant and record id;
- persisted public-safe production, supply, quality and maintenance records for
  the manufacturing operations reference dataset;
- indexes for tenant, record, domain, type, source system, status, owner role,
  related asset, workflow and risk filtering.

The thirty-second Alembic migration adds:

- `manufacturing_daily_briefs`: tenant-scoped daily brief artifacts keyed by
  tenant and brief/idempotency identifiers;
- required scope, source record, summary payload, permission decision and audit
  event references for each generated brief;
- indexes for tenant, brief, idempotency key, brief date, status, actor and
  audit event type filtering.

The thirty-third Alembic migration adds:

- `manufacturing_risk_scenarios`: tenant-scoped operational risk scenario
  artifacts keyed by tenant and scenario/idempotency identifiers;
- domain, status, risk level, owner role, linked workflow ids, source record
  ids, scenario payload, permission decision and audit event references;
- indexes for tenant, scenario, idempotency key, domain, status, risk, actor,
  owner and audit event type filtering.

The thirty-fifth Alembic migration adds:

- `connector_sync_checkpoints`: tenant-scoped sync execution checkpoint rows
  with connector/run ids, checkpoint sequence, public-safe cursor metadata,
  adapter result summaries and audit evidence refs.

The thirty-sixth Alembic migration adds:

- `connector_sync_checkpoint_claims`: tenant-scoped worker claim/lease rows
  keyed by checkpoint, claim id and idempotency key;
- lease duration and expiration metadata for retry coordination;
- public-safe claim results showing that external sync was not started and
  secret material was not returned;
- indexes for tenant, connector, run, checkpoint, claim, worker actor,
  idempotency and audit event filtering.

The thirty-seventh Alembic migration adds checkpoint claim lifecycle fields:

- nullable renewal actor/timestamp fields and renewal count;
- nullable release actor/timestamp/reason fields;
- indexes for renewal and release actor filtering.

The forty-first Alembic migration adds:

- `platform_notification_acknowledgements`: tenant-scoped, actor-scoped
  notification read/ack state keyed by tenant, notification id and actor id;
- public-safe notification metadata, reason, acknowledgement timestamp and
  linked audit event id/type for each persisted acknowledgement;
- indexes for tenant, notification, actor, state, source, category, severity
  and audit event type filtering.

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
- connector sync checkpoint creation, lookup and tenant-scoped listing.
- connector sync checkpoint claim creation and idempotency lookup.
- connector ontology proposal creation and tenant-scoped listing.
- connector ontology promotion creation, idempotency lookup, tenant-scoped
  listing and proposal promotion update.
- connector promotion policy creation, policy lookup and tenant-scoped listing.
- connector manifest lifecycle status updates with audit evidence references.
- connector manual import request creation, idempotency lookup and
  tenant-scoped listing.
- connector manual import decision recording with workflow signal evidence.
- platform notification acknowledgement upsert, lookup and actor-scoped
  listing for notification read models.

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
- approval decision transitions for linked `action_runs`, including idempotent
  approval gate records when a reviewer decides directly from the inbox before
  an action proposal exists.
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
- self-hosted audit ledger signature proof for export bundles, covering the
  manifest plus hash-chain proof with HMAC-SHA256 when a signing key is
  configured and explicit unsigned status otherwise.
- permission-gated physical audit retention deletion for eligible
  tenant-scoped `audit_events`, with dry-run support, legal-hold blocking and
  redacted `audit.retention_deletion.executed` evidence.
- persisted audit legal hold records for tenant-scoped activation/release, with
  event-type/actor scoping, `audit:legal_hold:write` permission checks and
  `audit.legal_hold.activated` / `audit.legal_hold.released` evidence.
- replay/simulation preview artifacts derived from `workflow_runs`,
  `workflow_timeline_events` and redacted `audit_events`, including governed
  connector policy-set version diff previews.
- persisted workflow run state and tenant-scoped history views.
- approval-driven workflow state reconciliation, where recorded approval
  decisions update a matching `workflow_runs` row, resolve the approval pending
  signal and append `workflow.approval_decision.recorded` timeline evidence
  without requiring a live Temporal worker.
- tenant-scoped connector configuration records for preview-only connector
  setup, with raw credential fields rejected before persistence.
- metadata-only connector credential handles with external secret references,
  tenant-scoped `active_preview` manifest gating and rotation history, without
  storing raw credential values.
- short-lived connector credential leases with tenant-scoped `active_preview`
  manifest gating, permission decisions, Vault/KMS policy metadata and adapter
  evidence, read audit events and audit-ledger evidence invariants, without
  returning raw secret material.
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
  evidence, tenant-scoped `active_preview` manifest gating, TypeDB mutation
  adapter result, idempotency enforcement, append-only
  `connector.ontology_promotion.*` audit writes and latest promotion evidence
  on the proposal record.
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
  connector manifests and runtime boundaries, then requires the tenant-scoped
  persisted manifest to be `active_preview` before tenant configuration state is
  written.
- connector credential handle creation now reads
  `surface=connectors/reference_id=manufacturing-connector-registry` to validate
  connector ids, then requires the tenant-scoped persisted manifest to be
  `active_preview` before external secret reference metadata or audit evidence
  is written.
- connector credential lease request creation now reads
  `surface=connectors/reference_id=manufacturing-connector-registry` to validate
  connector ids, then requires the tenant-scoped persisted manifest to be
  `active_preview` before lease rows, audit evidence or lease runtime adapter
  calls are made.
- connector credential lease registry reads now append
  `connector.credential_leases_read` evidence and report missing, unresolved,
  mismatched or unsafe audit bindings through `lease_evidence_invariants`.
- connector ontology proposal creation now reads
  `surface=connectors/reference_id=manufacturing-connector-registry` to resolve
  connector runtime boundary metadata, then requires the tenant-scoped
  persisted manifest to be `active_preview` before proposal rows or audit
  events are written.
- connector run creation now reads
  `surface=connectors/reference_id=manufacturing-connector-registry` to resolve
  connector runtime boundary metadata, then requires the tenant-scoped
  persisted manifest to be `active_preview` before run rows or audit events are
  written.
- connector manual import request creation now reads
  `surface=connectors/reference_id=manufacturing-connector-registry` to resolve
  connector runtime boundary metadata, then requires the tenant-scoped
  persisted manifest to be `active_preview` before approval-gated import rows
  or audit events are written.
- connector ontology promotion execution now reads
  `surface=connectors/reference_id=manufacturing-connector-registry` to
  validate the proposal connector id, then requires the tenant-scoped persisted
  manifest to be `active_preview` before the ontology mutation adapter runs,
  promotion rows are written or promotion audit evidence is appended.
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
- a consolidated reference-surface guard covering overview, workflows,
  connectors, agents, actions, approvals, audit, model routing and ontology so
  those endpoints retain persisted bootstrap rows and cannot reintroduce
  `get_manufacturing_*` runtime reference factories.
- action run creation now also reads
  `surface=ontology/reference_id=manufacturing-ontology` to derive
  relationship scopes for typed payload fields marked as ontology references
  before action/audit state is written.
- persisted manufacturing operation records through
  `manufacturing_operation_records`, with
  `/demo/manufacturing/operations` reading tenant-scoped production order,
  material lot, supplier posture, quality batch, machine status and maintenance
  window metadata through repository queries and server-side filters.
- a read-only manufacturing operations snapshot at
  `/demo/manufacturing/operations/snapshot`, composing persisted operation
  records, generated daily briefs, risk scenarios, workflow runs, approval
  records and recent audit evidence without writing new state.
- persisted manufacturing daily briefs through `manufacturing_daily_briefs`,
  with `/demo/manufacturing/operations/daily-brief` generating deterministic
  summaries from operation records, enforcing brief/audit/workflow scopes,
  writing append-only `manufacturing.daily_brief.generated` audit evidence and
  returning idempotent replays for duplicate requests.
- persisted manufacturing risk scenarios through
  `manufacturing_risk_scenarios`, with
  `/demo/manufacturing/operations/risk-scenarios/quality` generating a
  deterministic quality risk artifact from persisted Quality operation records,
  enforcing quality/workflow/audit scopes, writing append-only
  `manufacturing.risk_scenario.generated` audit evidence and returning
  idempotent replays for duplicate requests.
- persisted maintenance risk scenarios through the same
  `manufacturing_risk_scenarios` table, with
  `/demo/manufacturing/operations/risk-scenarios/maintenance` generating a
  deterministic maintenance risk artifact from persisted Maintenance operation
  records, enforcing maintenance/workflow/audit scopes, writing append-only
  `manufacturing.risk_scenario.generated` audit evidence and returning
  idempotent replays for duplicate requests.
- persisted supplier delay scenarios through the same
  `manufacturing_risk_scenarios` table, with
  `/demo/manufacturing/operations/risk-scenarios/supplier-delay` generating a
  deterministic supply risk artifact from persisted Supply operation records,
  enforcing supply/workflow/audit scopes, writing append-only
  `manufacturing.risk_scenario.generated` audit evidence and returning
  idempotent replays for duplicate requests.
- persisted connector sync checkpoints through `connector_sync_checkpoints`,
  with scheduled sync execution creating tenant-scoped checkpoint rows after
  the runtime adapter returns. Checkpoints carry connector/run ids,
  checkpoint type/status/sequence, public-safe cursor metadata, adapter result
  summaries and audit evidence refs, without raw DSNs, SQL text, credential
  values or secret material. The API exposes these rows through
  `/demo/manufacturing/connectors/runs/checkpoints` with tenant-scoped filters,
  validated `created_after`/`created_before` time windows and the dedicated
  `connectors:sync:checkpoint:read` scope. Successful checkpoint reads append
  `connector.run.sync_checkpoints_read` audit events with public-safe query
  filters, counts and checkpoint ids.
- persisted connector sync checkpoint claims through
  `connector_sync_checkpoint_claims`, with
  `/demo/manufacturing/connectors/runs/checkpoints/{checkpoint_id}/claims`
  creating worker-safe lease records behind the
  `connectors:sync:checkpoint:claim` scope. Replays with the same checkpoint
  and idempotency key return the original claim without duplicating audit
  evidence, while competing unexpired active claims for the same checkpoint
  return 409 before duplicate worker ownership is written. Claim results
  explicitly record `external_sync_started=false`,
  `secret_material_returned=false` and `worker_claim_only=true`.
- stale checkpoint claims are marked `expired` on the same table before
  replacement ownership is created, with
  `connector.run.sync_checkpoint_claim_expired` audit evidence linking the
  expired claim and replacement claim ids.
- checkpoint claim registry reads are exposed through
  `/demo/manufacturing/connectors/runs/checkpoints/claims` with tenant,
  connector, run, checkpoint, worker, status, `created_after`,
  `created_before`, cursor and limit filters. Invalid time windows are rejected
  before storage reads. Responses include `has_more` and `next_cursor` for stable cursor-based pagination.
  Reads require
  `connectors:sync:checkpoint:claim:read` and append
  `connector.run.sync_checkpoint_claims_read` audit evidence with public-safe
  filters, pagination metadata, returned claim count, claim evidence invariant
  count and claim ids only. Responses include public-safe
  `claim_evidence_invariants` for missing audit refs, unresolved ledger events,
  audit type mismatches, connector/run/checkpoint/claim/worker payload
  mismatches and worker-lease-only evidence violations.
- external DB live-query preflight requires `checkpoint_claim_id` and a persisted
  active checkpoint claim owned by the executing worker before the
  provider-specific runtime boundary is called. The targeted persisted claim
  must be active, unexpired, owned by the executing worker and attached to the
  same connector and run. Its audit event type must be
  `connector.run.sync_checkpoint_claimed`, and its audit event id must resolve
  through the tenant-scoped append-only audit ledger with matching connector,
  run, checkpoint, claim and worker payload binding. Its audit payload must
  also remain worker-lease-only with `external_sync_started=false`,
  `secret_material_returned=false` and `worker_claim_only=true`. Its checkpoint
  id must resolve to persisted
  `sync_execution` checkpoint evidence with status
  `sync_execution_preflight_passed` and audit event type
  `connector.run.sync_execution_preflight_passed` for the same connector and
  run, and the checkpoint `evidence_refs` must include its audit event id. That
  audit id must resolve through the tenant-scoped append-only audit ledger
  with matching connector, run and checkpoint payload binding plus public-safe
  audit payload before Axis lets an external DB live-query
  preflight enter the provider runtime. The checkpoint result evidence must also keep
  `external_query_started=false`, `credential_material_returned=false` and
  `graph_mutation_started=false`. The target claim result evidence must remain
  worker-lease-only with `external_sync_started=false`,
  `secret_material_returned=false` and `worker_claim_only=true`.
  Non-live execution paths do not require a checkpoint claim target.
- checkpoint registry reads return public-safe `evidence_invariants` for
  persisted checkpoint audit drift: missing audit refs, audit ids absent from
  evidence refs, unresolved ledger events, audit type mismatches,
  connector/run/checkpoint payload mismatches and unsafe checkpoint evidence.
  The read audit event stores only filters, returned checkpoint count,
  invariant count and checkpoint ids. It does not copy checkpoint cursor or
  result summaries into the read-audit payload.
- checkpoint claim lifecycle updates on the same
  `connector_sync_checkpoint_claims` row, with renew/release endpoints using
  dedicated scopes, updating lease expiry or release state and writing
  `connector.run.sync_checkpoint_claim_renewed` /
  `connector.run.sync_checkpoint_claim_released` audit evidence.
  The `/connectors` console consumes the endpoint directly and renders
  checkpoint summaries per connector without browser-local fallback records.

Still Platform work:

- provider-specific live connector execution beyond the current deferred and
  checkpointed self-hosted boundaries;
- production vault/KMS integration beyond provider-specific validation,
  secret leasing and automated rotation;
- production connector mutations from action runtime paths;
- broader relationship-aware permission enforcement beyond the current demo
  ontology-scope checks;
- WORM object-store retention hardening and provider-specific KMS adapters
  beyond insert-only repository shape, export hash-chain proof and self-hosted
  ledger signing;
- richer enterprise legal hold administration UI and WORM retention policy
  integration;
- deterministic Temporal replay and retention deletion jobs for simulation
  outputs.
