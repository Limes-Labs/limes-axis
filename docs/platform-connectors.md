# Platform Connector Foundation

The connector foundation introduces a public-safe contract for bringing
external data sources into Axis without enabling live production mutation.

This slice defines connector manifests, runtime policy boundaries, schema
mapping metadata, a preview-only file/CSV connector and a metadata-only
external database preview connector for the manufacturing reference demo. It
also adds tenant-scoped persisted connector manifest records, the first
tenant-scoped connector configuration records and metadata-only connector run
records. Governed dry-run execution now passes through a deferred Axis
connector execution adapter while keeping live sync disabled. Scheduled sync
plans can now be recorded from run records through a deferred scheduler adapter,
also without starting external sync.
It also introduces metadata-only credential handles, rotation history and
short-lived Vault/KMS lease records for future connector execution, without
storing or returning raw credential material in Axis.
External DB live-query preflight now reads tenant-scoped persisted egress policy
records instead of a local policy catalog before secret reference resolution.
The `/connectors` console now requires the Axis API for connector records and
shows an API-required empty state instead of local fallback connector data.
The browser runtime no longer exports connector registry, preview, credential,
run, proposal, import, promotion policy or policy-set default records.
The connector registry API now reads its public-safe reference payload from
`demo_reference_records` using `surface=connectors` and
`reference_id=manufacturing-connector-registry`; missing or invalid persisted
records return explicit API errors instead of silently falling back to runtime
seed data.
Connector configuration creation also resolves connector manifests from that
persisted registry reference, then requires a tenant-scoped persisted manifest
in `active_preview` before storing runtime boundary metadata. A manifest that
is only `registered_preview_only` remains catalogued but cannot be configured
for tenant use, so configuration writes no longer depend on a service-local
connector seed or an unreviewed manifest registration.
Credential handle creation uses the same persisted registry reference before
storing external secret reference metadata, so credential posture writes also
avoid service-local connector seeds.
Ontology proposal creation also resolves connector runtime boundary metadata
from the persisted registry reference before writing proposal records or audit
evidence.
Connector run creation uses that same persisted registry reference before
writing run records or audit evidence, so run runtime boundaries no longer come
from a service-local connector seed.
Manual import request creation also uses the persisted registry reference
before writing approval-gated import rows or audit evidence, so import runtime
boundary evidence no longer comes from a service-local connector seed.
Promotion policy authoring, enablement and revision paths also use the
persisted registry reference before writing policy rows or audit evidence, so
policy governance no longer validates connector ids against a service-local
connector seed.
Promotion policy set activation, replacement and rollback use the same
persisted registry reference before writing policy-set rows or audit evidence,
so active required-gate selection also avoids service-local connector seeds.
Preview-derived ontology proposal records are now persisted for review, with
graph mutation disabled until a controlled promotion is requested. Manual
import requests can now be recorded behind approval, workflow and idempotency
gates without executing a connector import, and approved proposals can be
promoted through the ontology mutation adapter. Promotion policies can now be
authored as metadata, and enabled required policies can be enforced
before ontology mutation execution.

## Current Scope

```text
GET /demo/manufacturing/connectors
GET /demo/manufacturing/connectors/manifests
POST /demo/manufacturing/connectors/manifests
GET /demo/manufacturing/connectors/configurations
POST /demo/manufacturing/connectors/configurations
GET /demo/manufacturing/connectors/credential-handles
POST /demo/manufacturing/connectors/credential-handles
POST /demo/manufacturing/connectors/credential-handles/{handle_id}/rotations
GET /demo/manufacturing/connectors/credential-leases
POST /demo/manufacturing/connectors/credential-leases
POST /demo/manufacturing/connectors/credential-leases/{lease_id}/renew
POST /demo/manufacturing/connectors/credential-leases/{lease_id}/revoke
GET /demo/manufacturing/connectors/egress-policies
POST /demo/manufacturing/connectors/egress-policies
GET /demo/manufacturing/connectors/runs
POST /demo/manufacturing/connectors/runs
GET /demo/manufacturing/connectors/ontology-proposals
POST /demo/manufacturing/connectors/ontology-proposals
POST /demo/manufacturing/connectors/ontology-proposals/promotions
GET /demo/manufacturing/connectors/promotion-policies
POST /demo/manufacturing/connectors/promotion-policies
GET /demo/manufacturing/connectors/manual-imports
POST /demo/manufacturing/connectors/manual-imports
POST /demo/manufacturing/connectors/manual-imports/{import_id}/decision
POST /demo/manufacturing/connectors/file-csv/preview
POST /demo/manufacturing/connectors/external-db/preview
```

The registry endpoint returns:

- connector id, type, version and display name;
- supported sync modes;
- runtime sandbox boundary;
- required permissions;
- credential storage posture;
- schema fields and ontology mapping targets;
- allowed and blocked runtime operations;
- preview sample metadata.

The registry endpoint is still a bootstrap reference surface, but it is no
longer constructed inside the FastAPI route. The bootstrap record is inserted
by Alembic migration `0023_connector_registry_reference`, validated against the
`ManufacturingConnectorRegistry` contract and queried through the persistence
repository. The API runtime no longer defines a connector registry seed
factory; tests validate the bootstrap payload directly from the migration.

The file/CSV and external DB preview endpoints read that same persisted
registry reference before generating output. Connector ids, connector type,
schema fields, runtime row limits and public-safe external DB sample rows are
resolved from `surface=connectors` and
`reference_id=manufacturing-connector-registry`; missing or invalid registry
references return explicit 404/422 errors before any preview mapping is
generated. The preview runtime does not carry its own manifest or sample seed.

Connector configuration creation reads that same persisted registry reference
to resolve the connector manifest and runtime boundary for the requested
connector id. If the registry reference is missing or invalid, configuration
creation returns explicit 404/422 errors before storing tenant configuration
state. The write then checks the tenant-scoped persisted manifest record and
requires `active_preview`; missing manifests or manifests still in
`registered_preview_only` are rejected before any configuration row is written.

Credential handle creation also reads the persisted registry reference to
validate the requested connector id before storing external secret reference
metadata. Missing or invalid registry references return explicit 404/422 errors
before any credential handle row or audit event is written.

Ontology proposal creation reads the same registry reference to resolve the
connector runtime boundary used in audit evidence. Missing or invalid registry
references return explicit 404/422 errors before any proposal row or audit event
is written.

Connector run creation reads the same registry reference to resolve the runtime
boundary stored on run records and audit evidence. Missing or invalid registry
references return explicit 404/422 errors before any run row or audit event is
written.

Manual import request creation reads the same registry reference to resolve the
connector runtime boundary stored in audit evidence. Missing or invalid
registry references return explicit 404/422 errors before any manual import row
or audit event is written.

Promotion policy authoring, enablement and revision read the same registry
reference to validate connector ids before writing policy rows or audit
evidence. Missing or invalid registry references return explicit 404/422 errors
before any policy row, revision row, enablement update or audit event is
written.

Promotion policy set activation, replacement and rollback read the same
registry reference to validate the requested connector before writing set rows
or audit evidence. Missing or invalid registry references return explicit
404/422 errors before any policy-set row, replacement/rollback update or audit
event is written.

The manifest management endpoints store and query tenant-scoped connector
manifest records. A manifest record includes:

- tenant id;
- connector id, display name, type, source type and version;
- preview-only registration status;
- runtime boundary;
- registering role/system id;
- public-safe manifest payload;
- runtime policy metadata;
- preview sample metadata;
- linked audit event id and type;
- notes.

Creating a manifest record writes append-only
`connector.manifest.registered` audit evidence. It does not enable live sync,
retrieve credentials, execute connector code or mutate the ontology graph. The
create endpoint rejects raw connection fields, DSNs, SQL/query text and raw
credential material before persisting the record.

`POST /demo/manufacturing/connectors/manifests/{connector_id}/lifecycle`
transitions a persisted manifest from `registered_preview_only` to
`active_preview`, or from preview states to `deprecated`, when the actor has
`connectors:manifest:lifecycle`. The endpoint writes
`connector.manifest.lifecycle_transitioned` audit evidence and records the
lifecycle note on the manifest. Live targets such as `live_enabled` are rejected
explicitly; the lifecycle path does not start sync, retrieve credentials,
execute connector code or mutate the ontology graph.

The CSV preview endpoint accepts a demo CSV payload and returns:

- validation status;
- accepted and rejected record counts;
- ontology entity proposals;
- redacted audit event preview;
- public-safe preview notes.

The endpoint does not persist raw file content, store credentials, call external
systems or write ontology graph records.

The external DB preview endpoint accepts only metadata references:

- connection profile id;
- schema and table names;
- selected column names;
- sample limit;
- credential handle id.

It returns:

- preview status;
- live query flag, always `false` in this slice;
- inspected table and mapped column metadata;
- registry-provided public-safe sample rows;
- ontology entity proposals;
- redacted audit event preview;
- public-safe preview notes.

The endpoint rejects raw connection material, DSNs, host/port details, SQL or
query text and raw credential material. It does not connect to Postgres, inspect
a real database, retrieve credentials, execute SQL, persist imported rows or
write ontology graph records.

The configuration endpoints store and query tenant-scoped preview connector
configuration records. A configuration includes:

- tenant id;
- connector id;
- display name;
- preview sync mode;
- runtime boundary;
- creator role/system id;
- public-safe configuration payload;
- credential reference ids;
- configuration notes.

Configuration payloads reject raw credential fields such as passwords, API keys
and credential values. Creating a configuration requires the matching
tenant-scoped connector manifest to have passed the governed lifecycle gate into
`active_preview`; registration alone is intentionally insufficient. The current
configuration status is `configured_preview_only`; scheduled sync and connector
execution remain future Platform work.

The credential handle endpoints store and query tenant-scoped metadata for
external secret references. A handle includes:

- tenant id;
- connector id;
- handle id;
- display name;
- external secret provider;
- external secret reference;
- purpose;
- rotation interval;
- last and next rotation timestamps;
- labels and notes;
- latest rotation evidence.

The create endpoint accepts references such as `vault://...`,
`external-secret://...`, `kms://...` or environment-backed development refs. It
rejects inline values that do not look like external references. Rotation
records update handle metadata and append rotation history. Axis does not
retrieve, store or return raw credential values.

The credential lease endpoints store and query tenant-scoped Vault/KMS lease
records for connector execution. A lease includes:

- tenant id;
- connector id;
- credential handle id;
- lease id;
- active/revoked status;
- lease mode and runtime boundary;
- requester role/system id;
- purpose;
- external secret provider and reference;
- Vault/KMS policy metadata;
- permission decision;
- deferred, self-hosted or provider-specific adapter result;
- granted, expiry and renewal timestamps;
- renewal/revocation evidence;
- linked audit event id and type;
- lease notes.

Creating a lease requires `connectors:credential_lease:request`, an active
credential handle in the same tenant and connector, and public-safe Vault/KMS
policy metadata. It writes `connector.credential_lease.requested` audit
evidence and returns only references, timestamps, decisions and adapter
evidence. Renewing and revoking leases require
`connectors:credential_lease:renew` and
`connectors:credential_lease:revoke` respectively, writing
`connector.credential_lease.renewed` and
`connector.credential_lease.revoked`. The default adapter is deferred.
`AXIS_CREDENTIAL_LEASE_EXECUTION_ENABLED=true` switches the boundary to the
self-hosted Vault/KMS lease adapter, which records a provider lease reference
without returning secret material, without requiring a managed service, without
starting live sync and without mutating the ontology graph.
`AXIS_CREDENTIAL_LEASE_PROVIDER_ADAPTERS_ENABLED=true` switches the same
boundary to provider-specific profiles for HashiCorp Vault, AWS Secrets
Manager, GCP Secret Manager, Azure Key Vault, KMS and local env refs. The
runtime validates the declared provider mode, credential handle provider,
secret reference prefix, lease path requirements and optional `kms://` key
reference before writing lease evidence. It still never reads external secret
material or returns raw credential values.

The connector run endpoints store and query tenant-scoped run evidence. A run
record includes:

- tenant id;
- connector id;
- run id;
- preview/manual-import-record/governed-dry-run/scheduled-sync-plan execution mode;
- runtime boundary;
- requester role/system id;
- credential handle ids;
- redacted input and result summaries;
- optional execution result metadata;
- optional schedule result metadata;
- optional dispatch result metadata;
- optional sync execution result metadata;
- linked audit event id and type;
- run notes.

Creating a run record writes an append-only `connector.run.recorded` audit event
with the same redacted metadata. The endpoint rejects raw payload fields such as
`csv_content`, raw file content, passwords, API keys, tokens and secret refs.
When `execution_mode=governed_dry_run`, the endpoint requires active credential
handle ids, calls the Axis connector execution runtime adapter, writes
`connector.run.execution_deferred` audit evidence and records
`external_sync_started=false`. The deferred adapter does not retrieve
credential material, call external systems, start live sync or mutate the
ontology graph. When `execution_mode=scheduled_sync_plan`, the endpoint also
requires an active credential lease id, schedule id, cadence, timezone and
next-run timestamp. It writes `connector.run.sync_scheduled`, returns a
deferred scheduler result with `external_sync_started=false` and persists only
public-safe schedule references. Scheduled plans can then be dispatch-claimed
through `POST /demo/manufacturing/connectors/runs/{run_id}/dispatch`, which
requires `connectors:sync:dispatch`, an active credential lease id and an
idempotency key. Dispatch writes `connector.run.sync_dispatch_deferred`, stores
a deferred dispatch result on the run record and replays the same idempotency
key without duplicate audit events. It still does not start external sync.
Dispatch-claimed plans can then receive a sync execution attempt through
`POST /demo/manufacturing/connectors/runs/{run_id}/execute-sync`, which requires
`connectors:sync:execute`, an active credential lease id and an idempotency key.
The default runtime writes `connector.run.sync_execution_deferred` with
`external_sync_started=false`. Setting
`AXIS_CONNECTOR_SYNC_EXECUTION_ENABLED=true` switches the boundary to the
self-hosted demo executor, which can complete the run with
`connector.run.sync_execution_completed` while still avoiding external egress,
credential material retrieval and graph mutation.
For `external_db_operational_mirror`, setting
`AXIS_EXTERNAL_DB_SYNC_EXECUTION_ENABLED=true` selects the Postgres external DB
profile adapter boundary. That adapter writes provider/profile/table/count
evidence, keeps `external_query_started=false` in this slice and never returns
raw connection strings or credential material.
If the run input explicitly sets `live_query_requested=true`, the adapter enters
a live-query preflight path. By default it writes
`connector.run.sync_execution_preflight_blocked`; with
`AXIS_EXTERNAL_DB_LIVE_QUERY_PREFLIGHT_ENABLED=true`, the self-hosted egress
policy boundary must validate a persisted tenant-scoped connector egress policy
for the connector profile before
`connector.run.sync_execution_preflight_passed` can be written. Policies are
created and listed through
`/demo/manufacturing/connectors/egress-policies`; runtime preflight consumes
the repository-backed record and does not rely on a hardcoded policy catalog.
The result summary includes the egress policy runtime boundary, policy
reference, scope, mode and private endpoint reference. Unknown, unpersisted or
unapproved egress policies write
`connector.run.sync_execution_preflight_blocked` with
`egress_policy_decision=blocked_policy_not_found` before secret retrieval is
considered. Passing preflight also requires the already validated credential
lease result to include a lease reference, an executed/renewed lease status and
`secret_material_returned=false`. The secret reference resolver then records
its own runtime boundary, scope, access mode, lease reference and
`secret_reference_material_returned=false` without fetching credential material.
Missing lease references write
`secret_retrieval_decision=blocked_secret_reference_evidence`; lease evidence
that says secret material was returned writes
`secret_retrieval_decision=blocked_secret_material_returned`. The preflight
still does not start a database query, return credential material or mutate the
graph.

The ontology proposal endpoints store and query tenant-scoped proposals derived
from connector preview output. A proposal includes:

- tenant id;
- connector id;
- proposal id;
- optional source run id;
- source file name;
- mapping profile;
- proposal-only write mode;
- graph mutation status;
- proposer role/system id;
- proposed node id, node type and ontology type;
- redacted field summary;
- evidence refs;
- linked audit event id and type;
- proposal notes.

Creating proposal records writes an append-only
`connector.ontology_proposals.recorded` audit event with redacted batch
metadata. The endpoint rejects raw payload fields such as `csv_content`, raw
file content, passwords, API keys, tokens and secret refs. It also rejects graph
write modes; persisted proposals remain review-only with
`graph_mutation_status=not_applied`.

The manual import endpoints store and query tenant-scoped requests to import
reviewed connector proposals later. A request includes:

- tenant id;
- connector id;
- import id;
- idempotency key;
- approval-required status;
- manual-import-request mode;
- requester role/system id;
- owner role;
- risk level;
- approval id;
- workflow id;
- proposal ids;
- redacted import summary;
- required controls;
- graph mutation status;
- workflow signal status;
- optional decision, actor and decision timestamp after approval review;
- optional workflow signal evidence after the decision is recorded;
- linked audit event id and type;
- request notes.

Creating a manual import request writes an append-only
`connector.manual_import.requested` audit event after resolving the connector
manifest from the persisted registry reference. Replaying the same request with
the same idempotency key returns the existing record and does not append another
audit event. Reusing an idempotency key for a different import request returns a
conflict. The endpoint returns explicit 404/422 errors when the persisted
registry reference is missing or invalid, rejects raw payload fields and direct
graph-write import modes; persisted requests remain approval-gated with
`graph_mutation_status=not_applied` and
`workflow_signal_status=pending_approval_decision`.

Manual import decisions are recorded through
`POST /demo/manufacturing/connectors/manual-imports/{import_id}/decision`.
The decision endpoint requires `approvals:connectors:decide`, records the
approval decision, signals the workflow runtime with
`connector_manual_import_decided`, stores signal evidence on the import request
and writes an append-only `connector.manual_import.decision_recorded` audit
event. A runtime outage is captured as `runtime_signal_unavailable` instead of
executing the connector. The graph remains `not_applied`; the decision only
moves governance metadata forward.

Approved ontology proposals can be promoted through
`POST /demo/manufacturing/connectors/ontology-proposals/promotions`. The
promotion endpoint requires:

- a persisted proposal still waiting for promotion;
- an approved manual import that references the proposal;
- workflow signal evidence from the manual import decision;
- a tenant-scoped idempotency key;
- actor scope `connectors:ontology:promote`.

Successful promotions write through the Axis ontology mutation runtime adapter
and record `type_db_mutation_applied` on the proposal. If the TypeDB mutation
runtime is disabled, the default adapter records `type_db_mutation_deferred`
without mutating the graph. Runtime failures are recorded as
`type_db_mutation_unavailable`. Every promotion attempt writes append-only
`connector.ontology_promotion.*` audit evidence and never stores raw CSV
content or credential material.

Promotion policies are authored through
`POST /demo/manufacturing/connectors/promotion-policies` and listed through
`GET /demo/manufacturing/connectors/promotion-policies`. Policy authoring
requires `connectors:promotion_policy:author` and records:

- policy id, version, status and enforcement mode;
- required promotion scopes, including `connectors:ontology:promote`;
- required manual import and workflow signal states;
- allowed risk levels and ontology types;
- review window metadata;
- append-only `connector.promotion_policy.authored` audit evidence.

Authoring a policy does not execute a connector, approve a proposal or mutate
TypeDB. It validates the connector id through the persisted registry reference
and returns explicit 404/422 errors before writing policy/audit state if that
reference is missing or invalid. Creating a policy with `enabled` status is
rejected; policies must be enabled through
`POST /demo/manufacturing/connectors/promotion-policies/{policy_id}/enable`.
Enablement requires `connectors:promotion_policy:enable`, an approved decision,
workflow signal evidence and writes append-only
`connector.promotion_policy.enabled` audit evidence. Enablement revalidates the
policy connector through the persisted registry reference before updating state.
Draft policies can be revised through
`POST /demo/manufacturing/connectors/promotion-policies/{policy_id}/revise`.
Revision requires `connectors:promotion_policy:revise`, an approved revision
decision, `policy_revision_signal_recorded` workflow evidence and an
idempotency key. It validates the requested connector through the persisted
registry reference before writing the new draft or revision audit evidence. The
target must still be `draft`; enabled required policies are not revised in
place, which keeps active policy sets and historical replay stable until a
future governed policy-set transition adopts a new version. When
an enabled required policy exists for the connector, Axis auto-selects it if the
promotion request omits `policy_id`, then enforces the required scopes, manual
import status, workflow signal status, allowed risk levels and allowed ontology
types before calling the TypeDB mutation adapter. Draft or advisory policies
remain visible governance evidence without blocking promotion. If more than one enabled
required policy matches the same connector, Axis requires a versioned active
policy set. `POST /demo/manufacturing/connectors/promotion-policy-sets`
requires `connectors:promotion_policy_set:activate`, validates the connector
through the persisted registry reference, verifies every referenced policy is
enabled and required, writes
`connector.promotion_policy_set.activated` audit evidence and allows the
promotion endpoint to evaluate all policies in the set with
`policy_set_enforced` evidence. When a policy set is active, explicit single
`policy_id` selection is rejected so callers cannot evaluate only part of the
required-gate set. A new active set can replace the current active set only when
the request names `replaces_policy_set_id`, carries an approved replacement
decision and includes `policy_set_replacement_signal_recorded` workflow
evidence; Axis writes `connector.promotion_policy_set.replaced` and marks the
previous set `superseded`. Replacement can include `policy_revision_adoptions`
for approved draft revisions; each adoption requires approval evidence,
`policy_revision_adoption_signal_recorded`, matching revision lineage and an
active-set current policy. Axis writes
`connector.promotion_policy.revision_adopted`, supersedes the current policy,
enables the revised policy as required and stores adoption evidence on the new
active set in the same transaction. A rollback also names the current active set, points
at a superseded `rollback_to_policy_set_id`, carries approved rollback evidence,
requires `policy_set_rollback_signal_recorded`, writes
`connector.promotion_policy_set.rolled_back` and creates a new active version
instead of reactivating old rows. Policy and policy-set promotion rejections write
`connector.ontology_promotion.rejected` audit evidence with policy ids,
matched constraints, violations and permission context before the API returns
422. Without an active set, multi-policy auto-selection is rejected with
`promotion_policy_selection_ambiguous`.

Replay simulation can compare governed connector policy-set versions over
historical workflow and audit events without activating a new set or executing
connector mutation.

The connector console includes a compact promotion policy authoring control for
policy id, status and enforcement mode. When the API is available, the control
posts to `POST /demo/manufacturing/connectors/promotion-policies`; when the API
is unavailable, it records a local public-safe preview and refreshes the policy
metrics. It also includes a compact enablement control that posts approval and
workflow evidence to the enable endpoint or records a local public-safe preview.
It also shows versioned policy-set evidence so reviewers can inspect active,
superseded, replaced and rolled-back required-gate sets before promotion. This
does not add mutable policy update or connector execution; policy-set transitions
are append-only in this slice.

## Manufacturing CSV Manifest

The first connector is `file_csv_manufacturing_assets`.

It maps these source columns to manufacturing asset proposals:

- `asset_id`;
- `asset_name`;
- `domain`;
- `station`;
- `risk_level`.

Required columns are validated before proposals are generated. Unsupported
connector ids are blocked. The response includes ontology proposals only; the
raw `csv_content` field is not returned.

## External DB Manifest

The second connector is `external_db_operational_mirror`.

It maps declared table metadata from `operations.production_orders` to
production order proposals:

- `order_id`;
- `asset_id`;
- `work_center`;
- `status`;
- `risk_level`.

The preview contract uses `profile_postgres_ops_readonly` and
`cred_external_db_readonly` as public-safe references. These are identifiers,
not live connection strings. The endpoint blocks raw connection details and
query text, returns `live_query_executed=false`, and uses
`connector.external_db.previewed` as the audit event preview type.

## Console Behavior

The `/connectors` page loads the connector registry and preview result from the
API when available. It also loads tenant-scoped connector configurations from
`/demo/manufacturing/connectors/configurations` and metadata-only credential
handles from `/demo/manufacturing/connectors/credential-handles`, plus run
records from `/demo/manufacturing/connectors/runs` and review-only ontology
proposal records from `/demo/manufacturing/connectors/ontology-proposals`, plus
manual import request gates from
`/demo/manufacturing/connectors/manual-imports` and promotion policies from
`/demo/manufacturing/connectors/promotion-policies`. If the API is unavailable,
it shows an API-required state and does not render local connector records.
The runtime library keeps connector types, request builders and formatting
helpers only; fixture data lives in tests and is not exported to product code.

The console displays:

- connector manifest and runtime boundary;
- preview-only sync posture;
- required permissions;
- blocked operations;
- tenant-scoped preview configuration;
- credential handle references and rotation posture;
- credential lease posture with deferred Vault/KMS adapter evidence;
- audit-backed connector run records, deferred execution metadata and scheduled
  sync plan/dispatch evidence;
- review-only ontology proposal records with graph mutation status;
- controlled ontology promotion evidence and TypeDB mutation status;
- manual import requests with approval, decision, workflow signal and idempotency evidence;
- promotion policy authoring and enforcement evidence;
- promotion policy authoring controls with API persistence only;
- public-safe configuration payload fields;
- schema mapping;
- redacted ontology proposals and audit event preview.

The page is read-only for operators. It does not upload files to storage,
capture credentials or trigger live sync. Governed connector dry-runs are shown
as deferred runtime evidence, and scheduled sync plans are shown as deferred
scheduler/dispatch/execution evidence. The self-hosted sync executor is opt-in
for local/demo execution and does not represent provider-specific production
egress.

## Governance Boundary

Connectors are designed as extractable from day one. The current manifest
contract keeps these boundaries visible:

- connector runtime sandbox;
- typed permission requirements;
- credential handles instead of raw credential values;
- rotation metadata and short-lived credential lease records before live vault
  adapters;
- no external egress by default;
- redacted preview payloads;
- audit event preview before live connector execution;
- tenant-scoped persisted manifest records before scheduled sync exists;
- tenant-scoped run records with deferred execution evidence;
- scheduled sync execution boundary with opt-in self-hosted demo runtime;
- tenant-scoped persisted egress policy records before external DB live-query
  preflight can pass;
- persisted ontology proposal records before controlled graph mutation;
- approval/workflow/idempotency-gated manual import requests before controlled
  promotion;
- promotion policy authoring before required enforcement;
- TypeDB ontology mutation adapter, deferred by default unless explicitly
  enabled.

Future Platform work should add:

- live connector manifest enablement beyond preview lifecycle states;
- live provider secret retrieval beyond provider-specific lease validation;
- provider-specific scheduled live sync beyond the self-hosted execution boundary;
- live external database adapters behind the Axis connector runtime boundary;
- connector-backed action invocation behind policy and approval gates.

Future extraction to `limes-axis-connectors` becomes mandatory when the
connector surface gains independent release cadence, customer-specific
integrations, separate ownership or substantial runtime/deployment concerns.

## Verification

The slice is covered by:

- API unit tests for manifest shape, public-safety checks, manifest persistence,
  audit evidence, CSV mapping and metadata-only external DB preview;
- API unit tests for tenant-scoped connector configuration persistence,
  `active_preview` manifest gating and raw credential field rejection;
- API unit tests for credential handle metadata, secret reference guardrails
  and rotation history;
- API unit tests for credential lease request, renewal, revocation, permission
  checks and raw secret material rejection;
- API unit tests for tenant-scoped egress policy persistence, endpoint listing
  and live-query preflight enforcement;
- API unit tests for connector run records, audit writes and raw payload
  rejection;
- API unit tests for connector ontology proposal persistence, audit writes,
  graph-write rejection and raw payload rejection;
- API unit tests for manual import request persistence, audit writes,
  idempotent replay, conflict detection, graph-write rejection and raw payload
  rejection;
- API unit tests for required-column and unsupported-connector guardrails;
- API endpoint and OpenAPI exposure tests;
- web unit tests for connector helper contracts and regression coverage that
  forbids default connector seed records in runtime libraries;
- Playwright smoke tests for `/connectors` API-required behavior when the
  backend is unavailable.
