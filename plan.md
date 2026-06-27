# Limes Axis Public Plan

Last updated: 2026-06-22

## Summary

Limes Axis is the sovereign AI control plane for European operations.

It starts as an open-source core that can run locally or in controlled
infrastructure, then expands into managed cloud, dedicated enterprise and
on-prem deployment paths.

Axis is designed to integrate first and replace gradually: existing systems stay
in place while Axis becomes the governed layer where data, workflows, people,
permissions and AI agents operate together.

## Product Principles

- Sovereignty must be practical: the open core must not require managed services.
- AI agents must be governed, permissioned, observable and auditable.
- Human approval remains central for risky actions.
- Operational ontology is the core context layer.
- Workflow execution must be durable and inspectable.
- Public open-source core and commercial operations should reinforce each other.
- The initial repository is unified, but future extraction into modules/repos is
  expected when parts grow large enough.

## Public Architecture Direction

Axis will use:

- Python + TypeScript as the two-language rule.
- Next.js + React for the governance console.
- FastAPI for the core API.
- REST/OpenAPI for public and internal contracts.
- Postgres for operational and transactional data.
- TypeDB for operational ontology and relationship-aware reasoning.
- Temporal OSS as the initial self-hosted workflow runtime behind an adapter.
- OIDC-first identity, with self-hosted Keycloak support.
- RBAC, ABAC and relationship-aware permissions.
- Append-only audit ledger.
- Provider-agnostic model routing with no external data egress by default.
- Docker Compose for local development and Kubernetes/Helm for production paths.

## Milestone Roadmap

### Foundation

- [x] Create the initial monorepo structure.
- [x] Add Python/FastAPI service foundation.
- [x] Add Next.js governance console foundation.
- [x] Add local Docker Compose runtime.
- [x] Add Postgres, TypeDB and Temporal local services.
- [x] Define tenant, actor, audit, action and workflow schemas.
- [x] Define the operational ontology primitives.
- [x] Define the Workflow Runtime Port and Temporal adapter.
- [x] Define the typed action registry.
- [x] Define the L0-L4 agent autonomy model.
- [x] Add OIDC/Keycloak identity boundary.
- [x] Add initial test, lint and CI commands.
- [x] Add repository issue, PR and security policy templates.
- [x] Generate and check the OpenAPI contract.
- [x] Add API readiness checks and console API status.
- [x] Add opt-in Postgres, TypeDB and Temporal integration tests.
- [x] Add Playwright smoke tests to the web CI gate.

Foundation acceptance is tracked in
[`docs/foundation-acceptance.md`](./docs/foundation-acceptance.md).

### Platform

- [x] Build the governance console overview.
- [x] Build the ontology explorer.
- [x] Build the workflow console.
- [x] Build the agent registry.
- [x] Build the action registry UI.
- [x] Build the approval inbox.
- [x] Build the audit explorer.
- [x] Build the model routing and cost observability layer.
- [x] Add the Postgres persistence foundation for approvals, actions and audit events.
- [x] Add API-backed approval decisions with audit writes.
- [x] Connect the approval console to persisted decision submission without local
  decision fallback.
- [x] Enforce demo approval decision permissions before persistence.
- [x] Signal approval decisions through the workflow runtime adapter.
- [x] Reconcile persisted workflow run state and timeline history when approval
  decisions are recorded.
- [x] Persist typed action run requests with idempotency enforcement.
- [x] Signal workflow runtime from typed action payloads behind policy.
- [x] Bind approval/action mutation endpoints to OIDC-derived actor identity
  and scopes.
- [x] Enforce relationship-derived ontology scopes on entity detail reads and
  action payload resource references.
- [x] Route ontology graph reads through a permission-aware query adapter with
  optional TypeDB read boundary.
- [x] Add a governance console OIDC session bridge for bearer-token API calls.
- [x] Query persisted audit events from the audit explorer.
- [x] Add demo audit export manifests, retention enforcement and integrity proof.
- [x] Add self-hosted KMS-style ledger signature proof for audit export bundles.
- [x] Add permission-gated physical audit retention deletion with dry-run,
  legal-hold blocking and redacted deletion evidence.
- [x] Add persisted audit legal hold activation/release workflow that blocks
  matching retention deletion candidates.
- [x] Persist workflow run state and tenant-scoped history views.
- [x] Build replay and simulation foundations.
- [x] Persist replay simulation outputs as governed audit artifacts.
- [x] Add retention-aware replay windows for simulation responses.
- [x] Add connector manifest foundation and file/CSV preview.
- [x] Add metadata-only external database connector preview.
- [x] Add tenant-scoped persisted connector manifest records.
- [x] Add governed connector manifest lifecycle transitions for preview states.
- [x] Add tenant-scoped connector configuration persistence.
- [x] Require active preview connector manifests before tenant configuration writes.
- [x] Require active preview connector manifests before credential handle creation.
- [x] Require active preview connector manifests before credential lease requests.
- [x] Require active preview connector manifests before connector run creation.
- [x] Require active preview connector manifests before manual import requests.
- [x] Require active preview connector manifests before ontology proposal creation.
- [x] Require active preview connector manifests before ontology promotion execution.
- [x] Persist connector ontology proposals without graph mutation.
- [x] Record manual connector import requests behind approval, workflow and
  idempotency gates.
- [x] Add Vault/KMS credential lease records with renew/revoke evidence.
- [x] Add optional self-hosted Vault/KMS lease runtime adapter.
- [x] Add provider-specific Vault/KMS credential lease profiles and policy
  hardening without secret material retrieval.
- [x] Add credential lease registry read audit and audit-ledger evidence invariants.
- [x] Author connector promotion policies before required enforcement.
- [x] Enforce enabled required connector promotion policies before ontology
  mutation execution.
- [x] Add connector console policy authoring controls with API persistence only.
- [x] Add connector promotion policy enablement workflow with audit evidence.
- [x] Add versioned connector promotion policy sets for multi-policy required gates.
- [x] Add governed connector promotion policy set replacement and rollback evidence.
- [x] Add atomic adoption of approved draft policy revisions during policy-set replacement.
- [x] Add deferred scheduled connector sync planning from run records.
- [x] Add idempotent deferred dispatch claims for scheduled connector sync.
- [x] Add scheduled connector sync execution boundary with opt-in self-hosted runtime.
- [x] Add Postgres external DB sync adapter boundary with public-safe profile evidence.
- [x] Add external DB live-query preflight policy evidence without live query execution.
- [x] Add credential lease evidence hardening for external DB live-query preflight.
- [x] Add egress policy evidence hardening for external DB live-query preflight.
- [x] Add secret reference resolver evidence hardening for external DB live-query preflight.
- [x] Persist tenant-scoped egress policy records for external DB preflight.
- [x] Add egress policy registry read audit and audit-ledger evidence invariants.
- [x] Persist tenant-scoped sync execution checkpoints for scheduled connector runs.
- [x] Expose tenant-scoped sync execution checkpoints through the connector API.
- [x] Show tenant-scoped sync execution checkpoints in the connector console.
- [x] Require `connectors:sync:checkpoint:read` for checkpoint API reads.
- [x] Add `created_before` pagination filter for checkpoint API reads.
- [x] Add `created_after` time-window filter for checkpoint API reads.
- [x] Reject invalid checkpoint time windows before checkpoint storage reads.
- [x] Write append-only audit evidence for valid checkpoint API reads.
- [x] Report public-safe checkpoint evidence invariants on checkpoint API reads.
- [x] Persist worker-safe sync checkpoint claims without starting live sync.
- [x] Add worker-safe sync checkpoint claim renewal and release.
- [x] Reject competing active worker claims for the same sync checkpoint.
- [x] Expire stale worker claims before replacement sync checkpoint ownership.
- [x] Expose worker checkpoint claim registry with read scope and audit evidence.
- [x] Filter worker checkpoint claim registry by connector and run.
- [x] Paginate worker checkpoint claim registry with opaque cursors.
- [x] Filter worker checkpoint claim registry by claiming worker.
- [x] Filter worker checkpoint claim registry by created time window.
- [x] Report public-safe checkpoint claim evidence invariants on claim registry reads.
- [x] Expose aggregate connector evidence invariant reports across checkpoints,
      claims, credential leases and egress policies.
- [x] Materialize aggregate connector evidence invariant snapshots as
      append-only audit artifacts.
- [x] Expose aggregate connector evidence invariant snapshot history from
      append-only audit artifacts.
- [x] Show aggregate connector evidence invariant snapshot history in the
      connector console from the API-backed history endpoint.
- [x] Add a governed connector console action that creates aggregate evidence
      snapshots through the API-backed snapshot endpoint.
- [x] Link connector evidence snapshot artifacts to their audit ledger event
      detail in the audit explorer.
- [x] Require an active worker checkpoint claim before external DB live-query
  preflight can enter the provider-specific runtime boundary.
- [x] Allow external DB live-query preflight execution to target an explicit
  worker checkpoint claim.
- [x] Show worker checkpoint claim registry in the connector console.
- [x] Make the connector console API-required instead of using local fallback data.
- [x] Make the remaining web consoles API-required instead of using local fallback data.
- [x] Remove non-connector browser-runtime seed records and guard against
  reintroduction.
- [x] Remove connector browser-runtime seed records and guard against
  reintroduction.
- [x] Persist the manufacturing overview reference as a tenant-scoped bootstrap
  record.
- [x] Persist the manufacturing workflow console reference as a tenant-scoped
  bootstrap record.
- [x] Remove the workflow console runtime seed factory from the API module.
- [x] Persist the manufacturing connector registry reference as a
  tenant-scoped bootstrap record.
- [x] Remove the connector registry runtime seed factory from the API module.
- [x] Use the persisted connector registry reference for manual import request
  creation.
- [x] Use the persisted connector registry reference for promotion policy
  authoring, enablement and revision.
- [x] Use the persisted connector registry reference for promotion policy set
  activation, replacement and rollback.
- [x] Use the persisted connector registry reference for file/CSV and external
  DB preview.
- [x] Persist the manufacturing agent registry reference as a tenant-scoped
  bootstrap record.
- [x] Remove the agent registry runtime seed factory from the API module.
- [x] Persist the manufacturing action registry reference as a tenant-scoped
  bootstrap record.
- [x] Remove the action registry runtime seed factory from the API module.
- [x] Persist the manufacturing approval inbox reference as a tenant-scoped
  bootstrap record.
- [x] Remove the approval inbox runtime seed factory from the API module.
- [x] Persist the manufacturing audit explorer reference as a tenant-scoped
  bootstrap record.
- [x] Remove the audit explorer runtime seed factory from the API module.
- [x] Persist the manufacturing model routing reference as a tenant-scoped
  bootstrap record.
- [x] Remove the model routing runtime seed factory from the API module.
- [x] Persist the manufacturing ontology graph and entity detail reference as a
  tenant-scoped bootstrap record.
- [x] Remove the ontology graph/detail runtime seed factory from the API module.
- [x] Add a module-level guard against reintroducing manufacturing runtime
  reference factories in the API module.
- [x] Add tenant-scoped manufacturing operation records with a persisted read
  API for production, supply, quality and maintenance reference data.
- [x] Add an audit-backed daily plant brief generated from persisted operation
  records with idempotency and permission checks.
- [x] Add an audit-backed quality risk scenario generated from persisted
  Quality operation records with idempotency and permission checks.
- [x] Add an audit-backed maintenance risk scenario generated from persisted
  Maintenance operation records with idempotency and permission checks.
- [x] Add an audit-backed supplier delay scenario generated from persisted
  Supply operation records with idempotency and permission checks.
- [x] Add a read-only manufacturing operations snapshot that composes persisted
  operation records, generated artifacts, workflows, approvals and audit evidence.
- [x] Guard all API-owned reference endpoints beyond overview, workflow
  console, approval inbox, audit explorer, model routing, ontology,
  connector registry, agent registry and action registry with persisted,
  tenant-scoped bootstrap records.
- [ ] Build the full connector framework beyond preview-only manifests.
- [ ] Build the manufacturing operations reference demo.

The browser governance console no longer ships local overview fallback records.
Visible records must come from Axis API responses or persisted tenant state. The
manufacturing overview endpoint now reads a tenant-scoped
`demo_reference_records` bootstrap row and returns explicit API errors when the
record is missing or invalid. The connector registry endpoint follows the same
pattern with `surface=connectors` and
`reference_id=manufacturing-connector-registry`. The agent registry endpoint
also reads from `surface=agents` and
`reference_id=manufacturing-agent-registry`; the API module no longer defines
an agent registry runtime seed factory. The action registry endpoint reads from
`surface=actions` and `reference_id=manufacturing-action-registry`; action run
requests validate their action definitions against that same persisted record
instead of a runtime seed factory and derive ontology resource relationship
scopes from `surface=ontology/reference_id=manufacturing-ontology` before
writing action/audit state.
The workflow console reference endpoint reads from `surface=workflows` and
`reference_id=manufacturing-workflow-console`, while
`/demo/manufacturing/workflows/runs` continues to query operational workflow run
state and tenant-scoped timeline events. The API module no longer defines a
workflow console runtime seed factory; tests validate the Alembic bootstrap
payload directly. The approval inbox endpoint reads from
`surface=approvals` and `reference_id=manufacturing-approval-inbox`; approval
decision submissions validate approval ids, workflow ids and required
permissions against that same persisted record before writing approval, audit
or workflow-signal evidence. The API module no longer defines an approval
inbox runtime seed factory; tests validate the Alembic bootstrap payload
directly. The audit explorer reference endpoint reads from
`surface=audit` and `reference_id=manufacturing-audit-explorer`; the separate
audit events and export endpoints continue to query persisted `audit_events`.
The API module no longer defines an audit explorer runtime seed factory; tests
validate the Alembic bootstrap payload directly.
The model routing reference endpoint reads from `surface=model-routing` and
`reference_id=manufacturing-model-routing`; live provider routing, usage
metering and billing adapters remain separate Platform work. The API module no
longer defines a model routing runtime seed factory; tests validate the Alembic
bootstrap payload directly.
The ontology graph and entity detail endpoints read from `surface=ontology` and
`reference_id=manufacturing-ontology`; the query runtime now applies metadata
and relationship-scope filtering to that persisted graph instead of loading a
route-owned seed. The API module no longer defines ontology graph/detail
runtime seed factories; tests validate the Alembic bootstrap payload directly.
The API test suite also includes a consolidated reference-surface guard that
fails if a listed reference endpoint loses its Alembic bootstrap record or if
the API reintroduces a `get_manufacturing_*` runtime reference factory.
The full manufacturing reference demo remains open until it has
live TypeDB graph response mapping, production relationship metadata, approval
actions, workflow execution and replay backed by real persistence paths.

The manufacturing operations dataset now has a dedicated persisted surface:
`GET /demo/manufacturing/operations` reads tenant-scoped
`manufacturing_operation_records` rows and supports server-side filters for
domain, status, record type and source system. The first bootstrap covers
production orders, material lots, supplier posture, quality batch evidence,
machine status and maintenance windows as redacted business metadata from
ERP/MES/QMS/CMMS/Supplier Portal boundaries. Live source-system queries and
secret retrieval remain behind connector runtime, credential lease and egress
policy boundaries.
`GET /demo/manufacturing/operations/snapshot` composes the persisted operation
records with generated daily briefs, risk scenarios, workflow runs, approval
records and recent audit events. It is read-only, stores no new rows and does
not generate artifacts, signal workflows, run connectors or query source
systems.
`POST /demo/manufacturing/operations/daily-brief` creates a persisted daily
plant brief from those operation records, enforces `briefs:generate`,
`audit:read` and `workflows:read`, writes
`manufacturing.daily_brief.generated` audit evidence and returns idempotent
replays for duplicate requests. The brief generator is deterministic and does
not invoke a placeholder model provider or mutate production systems.
`POST /demo/manufacturing/operations/risk-scenarios/quality` creates a
persisted quality risk scenario from `domain=Quality` operation records,
enforces `quality:read`, `workflows:read` and `audit:read`, writes
`manufacturing.risk_scenario.generated` audit evidence and returns idempotent
replays for duplicate requests. The scenario generator does not mutate QMS/MES,
approve a hold or call a model provider.
`POST /demo/manufacturing/operations/risk-scenarios/maintenance` creates a
persisted maintenance risk scenario from `domain=Maintenance` operation records,
enforces `maintenance:read`, `workflows:read` and `audit:read`, writes
`manufacturing.risk_scenario.generated` audit evidence and returns idempotent
replays for duplicate requests. The scenario generator does not mutate CMMS/MES
work orders, approve dispatch changes or call a model provider.
`POST /demo/manufacturing/operations/risk-scenarios/supplier-delay` creates a
persisted supplier delay scenario from `domain=Supply` operation records,
enforces `supply:read`, `workflows:read` and `audit:read`, writes
`manufacturing.risk_scenario.generated` audit evidence and returns idempotent
replays for duplicate requests. The scenario generator does not mutate Supplier
Portal or ERP records, approve expedite actions or call a model provider.

The governance console includes a local OIDC session bridge for demo and
developer workflows. A user can attach a bearer token in the console toolbar;
the console decodes actor, tenant and scopes for display and sends the token as
`Authorization: Bearer ...` to approval decision, action run and ontology entity
detail API calls. Full OIDC authorization-code login, refresh, secure cookie
session management and provider configuration remain Platform/Enterprise work.

The ontology explorer and entity detail pages are currently read-only and API
required; the browser no longer carries a local graph fallback. Graph reads now
pass through the Axis ontology query runtime, expose query metadata and can
filter relationships by OIDC-derived relationship scopes when a bearer token is
present or OIDC auth is required by configuration. The TypeDB read boundary is
optional and separated from graph mutations. Live TypeDB response mapping,
production relationship metadata and broader graph authorization remain Platform
work.

The workflow console is currently read-only and API required, with a persisted
workflow run endpoint available when Postgres records exist. The browser no
longer carries workflow fallback records. Approval decisions now signal the
workflow runtime adapter when available. Deterministic replay, workflow history
retention and workflow mutation controls remain Platform work.

The approval queue is still read-only for listing, but the listing now comes
from a persisted tenant-scoped reference row rather than route-owned seed data.
A demo decision endpoint now persists approval decisions and appends audit
events, and the web console submits reviewer decisions to it without creating a
standalone local decision preview when persistence fails. The decision endpoint
enforces the required demo approval scope before
persistence and signals the workflow runtime adapter. When a bearer token is
present, or when OIDC auth is required by configuration, the endpoint validates
the token against configurable OIDC/JWKS settings and derives tenant, actor and
scopes from token claims before persistence. Broader relationship-aware
permission enforcement remains Platform work.

The audit explorer is API required, its reference view is now loaded from a
persisted tenant-scoped bootstrap row, and it can query persisted
`audit_events` through the demo API when records exist. The browser no longer
carries audit fallback records. The demo API can also return a redacted JSON
export bundle with manifest checksum, applied filters, retention-window
enforcement, hash-chain integrity proof and a ledger signature proof. When
`AXIS_AUDIT_LEDGER_SIGNING_SECRET` is configured, the API signs the export
manifest plus hash-chain proof with a self-hosted HMAC-SHA256 signer; when it
is not configured, the bundle reports an explicit `unsigned` proof instead of
pretending a managed KMS signature exists.
`POST /demo/manufacturing/audit/retention/delete` adds a permission-gated
physical retention deletion execution path for tenant-scoped audit rows. It
supports dry-run, blocks deletion under active persisted legal holds or an
explicit legal-hold request flag and writes
`audit.retention_deletion.executed` evidence with counts and hashes rather than
raw payloads. `POST /demo/manufacturing/audit/legal-holds`,
`GET /demo/manufacturing/audit/legal-holds` and
`POST /demo/manufacturing/audit/legal-holds/{hold_id}/release` provide the
audit-backed legal hold activation/list/release workflow used by retention
deletion. Tenant-scoped query permissions remain Platform work.

The replay/simulation foundation consumes API replay artifacts from workflow
run history, timeline events and redacted audit evidence. The `/simulation`
page shows baseline versus simulated policy decisions and
governed connector policy-set version diffs over historical events for the
manufacturing demo. Replay outputs can now be persisted as governed audit
artifacts with `simulation.replay_output.persisted` evidence, retention
metadata and idempotency protection. Replay responses now enforce
retention-aware query windows across timeline, audit and persisted output
records, with a legal-hold bypass for governance review. The browser no longer
constructs replay artifacts from local workflow or audit defaults. Temporal
deterministic replay, arbitrary policy diffing, replay-output deletion jobs and
legal hold workflows for non-audit artifacts remain Platform and Enterprise
work.

The connector foundation exposes a public-safe manifest registry, a
preview-only file/CSV connector for manufacturing asset intake and a
metadata-only external database preview connector. The API can validate CSV
rows, map them to ontology entity proposals and return a redacted audit event
preview through `/demo/manufacturing/connectors/file-csv/preview`. The registry
returned by `/demo/manufacturing/connectors` now reads from the tenant-scoped
`demo_reference_records` bootstrap row instead of a route-owned runtime seed.
The API module no longer defines a connector registry factory; tests validate
the Alembic bootstrap payload directly against the registry schema.
Connector configuration creation resolves connector manifests and runtime
boundaries from that persisted registry reference, then requires a matching
tenant-scoped persisted manifest in `active_preview` before storing tenant
configuration state.
Credential handle creation uses the same persisted registry reference to
validate connector manifests, then requires a matching tenant-scoped persisted
manifest in `active_preview` before storing external secret reference metadata.
Credential lease requests use the same persisted registry reference, then
require a matching tenant-scoped persisted manifest in `active_preview` before
writing lease/audit evidence or calling the lease runtime adapter.
Ontology proposal creation also resolves connector runtime boundary metadata
from that persisted registry reference, then requires a matching tenant-scoped
persisted manifest in `active_preview` before writing proposal/audit state.
Connector run creation uses the same persisted registry reference, then requires
a matching tenant-scoped persisted manifest in `active_preview` before writing
run/audit runtime boundary metadata.
Manual import request creation also uses the same persisted registry reference,
then requires a matching tenant-scoped persisted manifest in `active_preview`
before writing approval-gated import audit evidence.
Ontology promotion execution also uses that persisted registry reference, then
requires a matching tenant-scoped persisted manifest in `active_preview` before
calling the ontology mutation adapter or writing promotion/audit evidence.
Promotion policy authoring, enablement and revision also use that persisted
registry reference before writing policy/audit evidence.
Promotion policy set activation, replacement and rollback also use it before
writing policy-set/audit evidence.
It can also preview declared external DB table metadata through
`/demo/manufacturing/connectors/external-db/preview`, using profile ids and
credential handles while blocking raw connection material, SQL text and live
queries. Tenant-scoped connector manifests can now be registered through
`/demo/manufacturing/connectors/manifests`, writing
`connector.manifest.registered` audit evidence while rejecting raw connection
fields, SQL/query text and credential material. The API also stores and
queries tenant-scoped preview connector configuration through
`/demo/manufacturing/connectors/configurations`, requiring an `active_preview`
manifest and rejecting raw credential fields in configuration payloads. The API
now also stores metadata-only credential handles and rotation history through
`/demo/manufacturing/connectors/credential-handles`, using external secret
references instead of raw credential values, requiring a matching
tenant-scoped connector manifest in `active_preview` and failing explicitly if
the persisted connector registry reference is missing or invalid. Short-lived
credential leases can now be requested, renewed and revoked through
`/demo/manufacturing/connectors/credential-leases`, writing
`connector.credential_lease.*` audit evidence while returning only references,
timestamps, permission decisions and adapter evidence. Lease requests require a
matching tenant-scoped connector manifest in `active_preview` before runtime or
audit evidence is written. The lease runtime is deferred by default and can use
the optional self-hosted Vault/KMS adapter when
`AXIS_CREDENTIAL_LEASE_EXECUTION_ENABLED=true`, still without returning secret
material. Provider-specific Vault/KMS adapter profiles can be enabled with
`AXIS_CREDENTIAL_LEASE_PROVIDER_ADAPTERS_ENABLED=true`; the runtime validates
the declared provider mode against the credential handle secret provider,
secret reference prefix and KMS policy metadata for HashiCorp Vault, AWS Secrets
Manager, GCP Secret Manager, Azure Key Vault, KMS and local env refs, while
still returning only lease evidence. Connector run records can now be written through
`/demo/manufacturing/connectors/runs`; each record stores only redacted
summaries and links to an append-only
`connector.run.recorded` audit event. Governed dry-run connector execution now
calls the deferred Axis
connector execution adapter, requires credential handle ids, writes
`connector.run.execution_deferred` audit evidence and still does not start live
sync. Scheduled sync plans can now be recorded through the same run endpoint
with `execution_mode=scheduled_sync_plan`, active credential lease evidence,
schedule metadata and `connector.run.sync_scheduled` audit evidence, while the
deferred scheduler adapter keeps `external_sync_started=false`.
Scheduled plans can now be dispatch-claimed through
`/demo/manufacturing/connectors/runs/{run_id}/dispatch`, requiring
`connectors:sync:dispatch`, active lease evidence and an idempotency key. The
dispatch boundary writes `connector.run.sync_dispatch_deferred` and still keeps
`external_sync_started=false`.
Dispatch-claimed plans can now receive a sync execution attempt through
`/demo/manufacturing/connectors/runs/{run_id}/execute-sync`, requiring
`connectors:sync:execute`, active lease evidence and an idempotency key. The
default execution runtime writes `connector.run.sync_execution_deferred`; the
opt-in self-hosted demo runtime, enabled with
`AXIS_CONNECTOR_SYNC_EXECUTION_ENABLED=true`, can write
`connector.run.sync_execution_completed` without external egress, credential
material retrieval or graph mutation.
External DB sync can opt into the Postgres profile adapter boundary with
`AXIS_EXTERNAL_DB_SYNC_EXECUTION_ENABLED=true`, adding public-safe
provider/profile/table/count evidence while still omitting raw connection
strings and credential material.
When an external DB run explicitly requests live query execution, Axis now
records a separate preflight result instead of starting the query. The default
decision is `connector.run.sync_execution_preflight_blocked`; setting
`AXIS_EXTERNAL_DB_LIVE_QUERY_PREFLIGHT_ENABLED=true` can produce
`connector.run.sync_execution_preflight_passed` only when the run carries an
approved private endpoint egress boundary, egress policy id, lease-scoped
secret reference and a targeted active checkpoint claim owned by the executing
worker. Missing `checkpoint_claim_id` or inactive target claims are rejected
before the provider-specific runtime is called, before preflight audit is
written and before a new execution checkpoint is created. Passed and blocked
preflights with a valid target claim include public-safe checkpoint claim
evidence in the sync result summary. When `live_query_requested=true`,
`execute-sync` must provide `checkpoint_claim_id`; Axis rejects the request
unless that exact claim is active, unexpired, owned by `executed_by` and
backed by `connector.run.sync_checkpoint_claimed` audit evidence whose audit id
resolves in the tenant-scoped append-only audit ledger with matching
connector/run/checkpoint/claim/worker binding and worker-lease-only payload before being
attached to an eligible `sync_execution_preflight_passed` checkpoint for the
same connector and run with `connector.run.sync_execution_preflight_passed`
audit evidence referenced by `evidence_refs`. The referenced audit id must
resolve to a persisted tenant-scoped audit ledger event with the same
connector/run/checkpoint binding, its payload must remain public-safe and the target
checkpoint result evidence must remain public-safe. The target claim result
must remain worker-lease-only with `external_sync_started=false`,
`secret_material_returned=false` and `worker_claim_only=true`. This still keeps
`external_query_started=false`, returns no credential material and performs no
graph mutation. The passed preflight now depends on validated egress policy
evidence from persisted tenant-scoped policy records and the validated
credential lease result: the runtime records policy
runtime/ref/scope/private-endpoint evidence, blocks unknown or unpersisted
policies before secret retrieval is considered, records lease
id/mode/runtime/result status/reference evidence, records reference-only secret
resolver evidence and blocks the path if the lease reference is missing or if
the lease evidence says secret material was returned. Network policy
preflight and completed/deferred sync execution attempts now also write
tenant-scoped `connector_sync_checkpoints` rows with public-safe cursor and
result evidence for future retry/checkpoint-aware provider adapters. The
checkpoint registry is queryable at
`/demo/manufacturing/connectors/runs/checkpoints` with tenant, connector, run,
status, `created_after`, `created_before` and limit filters, and requires the
`connectors:sync:checkpoint:read` scope. Invalid windows where `created_after`
is equal to or later than `created_before` are rejected before checkpoint
storage is queried. Valid checkpoint reads write
`connector.run.sync_checkpoints_read` audit evidence with filters, count,
evidence invariant count and checkpoint ids only. The registry response reports
public-safe evidence invariants for missing, unresolved, mismatched or unsafe
checkpoint audit evidence without copying cursor or result summaries into the
read-audit payload.
Worker claim records are persisted at
`/demo/manufacturing/connectors/runs/checkpoints/{checkpoint_id}/claims` with
the `connectors:sync:checkpoint:claim` scope, lease duration metadata,
idempotency-key replay and `connector.run.sync_checkpoint_claimed` audit
evidence. A claim is a worker lease only: it does not start external sync,
retrieve secret material or execute provider-specific connector code. A second
unexpired active claim for the same checkpoint is rejected with 409 before a
duplicate claim/audit record is written. Expired claims are marked `expired`
with `connector.run.sync_checkpoint_claim_expired` before replacement ownership
is created. Claim records are queryable at
`/demo/manufacturing/connectors/runs/checkpoints/claims` with tenant, connector,
run, checkpoint, worker, status, `created_after`, `created_before`, cursor and
limit filters. Invalid time windows are rejected before storage reads. Reads
return `has_more` and `next_cursor` for stable cursor-based pagination. Reads require
`connectors:sync:checkpoint:claim:read` and append
`connector.run.sync_checkpoint_claims_read` audit evidence with filters,
pagination metadata, returned claim count and claim ids only. Claim renewal and
release update the same persisted lease record through dedicated scopes, writing
`connector.run.sync_checkpoint_claim_renewed` and
`connector.run.sync_checkpoint_claim_released` audit evidence without
provider-specific connector execution.
enforcement, real secret retrieval and real query execution stay outside this
slice.
The `/connectors` console now fetches connector, credential, egress policy,
run, sync checkpoint, checkpoint claim, evidence invariant, evidence snapshot,
proposal, import and promotion records from the Axis API. Checkpoint rows are
requested with the checkpoint read scope and shown per selected connector with
sequence, adapter, cursor summary, result evidence and audit refs. Checkpoint
claim rows are requested with
`connectors:sync:checkpoint:claim:read` and shown next to the selected
connector checkpoints with worker ownership, lease, renewal/release, invariant
status and secret-material evidence. Evidence snapshot history is requested
with `connectors:evidence:snapshot:read` and shown with newest snapshot id,
invariant totals, evidence surface count and digest prefixes. The console can
create a selected-connector evidence snapshot through
`POST /demo/manufacturing/connectors/evidence-invariants/snapshots` with
`connectors:evidence:snapshot`, generated snapshot/idempotency ids and a
public-safe review reason, then refreshes API-backed history. Snapshot artifacts
with audit event ids link to `/audit?event_id=...`, where the audit explorer
selects the matching persisted event after loading API-backed ledger records. If the backend is
unavailable it shows an API-required empty state instead of rendering local
connector fallback records.
Preview-derived ontology proposals can now be persisted through
`/demo/manufacturing/connectors/ontology-proposals`; each proposal is
audit-backed, initially marked with `graph_mutation_status=not_applied` and
fails explicitly when the persisted connector registry reference is missing or
invalid.
Manual connector import requests can now be recorded through
`/demo/manufacturing/connectors/manual-imports`; each request is tenant-scoped,
idempotent, approval-gated, workflow-referenced and audit-backed with
`connector.manual_import.requested`, while graph mutation remains
`not_applied`. Creation resolves connector runtime boundary metadata from the
persisted connector registry reference and fails explicitly if that reference
is missing or invalid before writing rows or audit events. Decisions can now be
recorded through
`/demo/manufacturing/connectors/manual-imports/{import_id}/decision`; each
decision stores the approval outcome, workflow signal status and
`connector.manual_import.decision_recorded` audit evidence without executing
the connector. Approved proposal promotion can now be requested through
`/demo/manufacturing/connectors/ontology-proposals/promotions`; each promotion
requires approval evidence, workflow signal evidence, idempotency,
`connectors:ontology:promote` and a tenant-scoped connector manifest in
`active_preview`, then applies or defers the TypeDB graph mutation through the
Axis ontology mutation adapter with append-only
`connector.ontology_promotion.*` audit evidence. Replays with the same
idempotency key and payload return the existing request or promotion instead of
writing duplicate audit events. Connector promotion policies can now be
authored through `/demo/manufacturing/connectors/promotion-policies`; each
policy records the authoring permission, required promotion scopes, approved
manual import state, workflow signal state, allowed risk levels and
`connector.promotion_policy.authored` audit evidence without executing
connectors or mutating TypeDB. Authoring validates connector ids through the
persisted registry reference and fails explicitly if that reference is missing
or invalid before writing rows or audit events. Policies are enabled through
`/demo/manufacturing/connectors/promotion-policies/{policy_id}/enable`, which
requires `connectors:promotion_policy:enable`, an approved decision, workflow
signal evidence and writes `connector.promotion_policy.enabled`; enablement
revalidates the policy connector through the persisted registry reference
before updating state. Draft policies can be revised append-only through
`/demo/manufacturing/connectors/promotion-policies/{policy_id}/revise`, which
requires `connectors:promotion_policy:revise`, approved revision evidence,
workflow signal evidence and an idempotency key. Revisions validate the
requested connector through the persisted registry reference before writing the
new draft or audit evidence. Enabled required policies are not revised in
place; future versions must be adopted through a governed policy-set
transition. Enabled required policies are auto-selected when a
promotion request omits `policy_id` and are enforced before the TypeDB mutation
adapter is called. When more than one enabled required policy applies,
`/demo/manufacturing/connectors/promotion-policy-sets`
can activate a versioned active set with
`connectors:promotion_policy_set:activate`; activation validates the connector
through the persisted registry reference before writing set/audit evidence. The
promotion endpoint evaluates all policies in that set and stores
`policy_set_id`, `policy_ids` and
`policy_set_enforced` evidence. When a policy set is active, explicit single
`policy_id` selection is rejected so promotions cannot bypass the full
required-gate set. Replacing or rolling back an active set requires
`replaces_policy_set_id`, an approved transition decision and workflow evidence.
Replacement writes `connector.promotion_policy_set.replaced`; rollback restores a
superseded target through a new active version, writes
`connector.promotion_policy_set.rolled_back` and marks the previous active set
`superseded`. Replacement can carry `policy_revision_adoptions` so approved
draft revisions are adopted atomically with the set transition; Axis writes
`connector.promotion_policy.revision_adopted`, supersedes the current required
policy and stores adoption evidence on the new active set. Policy and
policy-set promotion rejections write
`connector.ontology_promotion.rejected` audit evidence with the effective
policy context before the API returns 422. If multiple required policies exist
without an active set, Axis still rejects implicit selection.
The file/CSV and external DB preview endpoints now resolve connector ids,
schema fields, runtime row limits and public-safe sample rows through the same
persisted connector registry reference before returning preview output. Missing
or invalid registry references return explicit 404/422 responses before any
preview mapping is generated.
The `/connectors` console shows runtime boundaries, required permissions,
blocked operations, tenant configuration, credential handle posture, connector
run evidence from persisted registry-backed run creation, deferred execution metadata,
persisted ontology proposal
evidence, promotion evidence, manual import decision evidence, promotion policy
authoring/enforcement evidence, versioned policy-set evidence, aggregate
evidence invariant posture, evidence snapshot history and schema mapping from
API-backed records only.
It can author promotion policies through the API when available, enable them
with approval/workflow evidence and reports API persistence errors without
recording local public-safe previews when the API is offline. The browser
runtime no longer exports connector registry, preview, credential, run,
proposal, import, promotion policy or policy-set default records; connector
unit tests use local fixtures instead of product runtime fallbacks.
Live connector manifest enablement, live provider secret retrieval,
provider-specific scheduled live sync beyond the self-hosted execution boundary,
live external database adapters and connector-backed production actions remain
Platform work.

The agent registry is currently read-only and API required. The browser no
longer carries local agent fallback records, and the API module no longer
defines an agent registry runtime seed factory. Production action execution,
persisted agent state, tenant-scoped agent configuration, runtime policy
enforcement and model cost observability remain Platform work.

The action registry UI is API required for catalog browsing. The browser no
longer carries local action fallback records, and the API module no longer
defines an action registry runtime seed factory. Typed dry-run/proposal action
requests can now be persisted through the demo API with idempotency enforcement
and append-only audit events. Approval-gated action payloads now signal the Axis
workflow runtime adapter after persistence, with explicit degraded status when
the runtime is unavailable. When a bearer token is present, or when OIDC auth is
required by configuration, action run creation derives tenant, actor and scopes
from token claims and rejects actor impersonation before persistence. Action
payload fields marked as ontology references also require the scopes attached to
their connected ontology relationships from the persisted ontology reference
record, preventing cross-domain resource references from bypassing the typed
action permission check. Live production execution, connector invocation and
broader relationship-aware permission enforcement remain Platform work.

Approval decisions now also reconcile persisted workflow state when the linked
`workflow_runs` row exists: the pending signal records the decision, the run
state/status/current step are updated and a workflow timeline event is appended.
This keeps the persisted workflow console coherent without requiring a live
Temporal worker.

The model routing and cost observability layer is currently read-only and API
required. The browser no longer carries local route telemetry fallback records,
and the API reference now comes from a persisted tenant-scoped bootstrap row.
The API module no longer defines a route telemetry seed factory.
Live provider adapters, provider-specific billing ingestion, tenant budget
enforcement, persisted usage records, OpenTelemetry spans from runtime code and
audit writes from live route decisions remain Platform work.

### Enterprise

- [ ] Add single-tenant managed deployment path.
- [ ] Add on-prem/private cloud reference architecture.
- [ ] Add Helm charts and production deployment guides.
- [ ] Add backup and restore procedures.
- [ ] Add enterprise-grade audit export workflows beyond the current retention
  and integrity controls.
- [ ] Add enterprise identity and SSO hardening.
- [ ] Add security review and threat model documentation.
- [ ] Add support and operations runbooks.

## Expansion Rule

Axis starts unified, but the architecture must keep boundaries extractable.

Future repositories may include:

- `limes-axis-cloud`
- `limes-axis-enterprise`
- `limes-axis-connectors`
- `limes-axis-sdk`
- `limes-axis-deploy`
- `limes-axis-docs`

Extraction should happen when a module has at least two of these traits:

- independent release cadence;
- separate team or ownership;
- enterprise-only secrets, permissions or deployment logic;
- customer-specific integrations;
- independent SDK versioning;
- large connector surface;
- cloud operations that differ materially from the open-source core;
- documentation needs that outgrow the product repo.

## Contribution Policy

The project uses Apache-2.0 for the open-source core and plans to require a
Contributor License Agreement before accepting substantial external
contributions.

The CLA text in this repository is an initial project baseline and should be
reviewed legally before broad external contribution intake.

## What Is Intentionally Not Promised Yet

- No production readiness claim.
- No completed ERP/MES/CRM integrations.
- No uncontrolled autonomous agents.
- No dependency on a proprietary hosted model provider.
- No promise that commercial Cloud or Enterprise code will live in this repo.
