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
storing external secret reference metadata, then requires the tenant-scoped
persisted manifest to be `active_preview`, so credential posture writes also
avoid service-local connector seeds and unreviewed manifest registrations.
Credential lease requests use the same persisted registry reference, then
require the tenant-scoped persisted manifest to be `active_preview` before
lease rows, audit evidence or lease runtime adapter calls can occur.
Ontology proposal creation also resolves connector runtime boundary metadata
from the persisted registry reference, then requires the tenant-scoped
persisted manifest to be `active_preview` before writing proposal records or
audit evidence.
Connector run creation uses that same persisted registry reference, then
requires the tenant-scoped persisted manifest to be `active_preview` before
writing run records or audit evidence. Run runtime boundaries no longer come
from a service-local connector seed, and run evidence cannot be created from a
manifest that is only registered.
Manual import request creation also uses the persisted registry reference, then
requires the tenant-scoped persisted manifest to be `active_preview` or
`active_live` before writing approval-gated import rows or audit evidence. Import runtime boundary
evidence no longer comes from a service-local connector seed, and import
requests cannot be created from a manifest that is only registered.
Ontology promotion execution also uses the persisted registry reference, then
requires the tenant-scoped persisted manifest to be `active_preview` or
`active_live` (the stricter live-enablement state, so proposals produced by
governed live sync stay promotable) before the ontology mutation adapter is
called or promotion/audit evidence is written.
Promotion audit payloads include the manifest runtime boundary that authorized
the controlled mutation path.
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
GET /demo/manufacturing/connectors/evidence-invariants
GET /demo/manufacturing/connectors/evidence-invariants/snapshots
GET /demo/manufacturing/connectors/evidence-invariants/snapshots/export
POST /demo/manufacturing/connectors/evidence-invariants/snapshots/export-requests
POST /demo/manufacturing/connectors/evidence-invariants/snapshots/export-requests/{export_request_id}/decision
POST /demo/manufacturing/connectors/evidence-invariants/snapshots/export-requests/{export_request_id}/materializations
POST /demo/manufacturing/connectors/evidence-invariants/snapshots
GET /demo/manufacturing/connectors/runs
POST /demo/manufacturing/connectors/runs
GET /demo/manufacturing/connectors/runs/checkpoints
GET /demo/manufacturing/connectors/runs/checkpoints/claims
POST /demo/manufacturing/connectors/runs/checkpoints/{checkpoint_id}/claims
POST /demo/manufacturing/connectors/runs/checkpoints/{checkpoint_id}/claims/{claim_id}/renew
POST /demo/manufacturing/connectors/runs/checkpoints/{checkpoint_id}/claims/{claim_id}/release
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
before any credential handle row or audit event is written. After public-safe
secret reference validation, the write requires the matching tenant-scoped
persisted manifest to be `active_preview`; missing manifests or manifests still
in `registered_preview_only` are rejected before credential handle metadata or
audit evidence is written.

Credential lease requests read the same registry reference to validate the
requested connector id before runtime lease execution is considered. Missing or
invalid registry references return explicit 404/422 errors before any lease row
or audit event is written. After raw-secret payload validation and active handle
validation, the request requires the matching tenant-scoped persisted manifest
to be `active_preview`; missing manifests or manifests still in
`registered_preview_only` are rejected before the lease runtime adapter is
called, before lease metadata is written and before audit evidence is appended.

Ontology proposal creation reads the same registry reference to resolve the
connector runtime boundary used in audit evidence. It then requires the matching
tenant-scoped persisted manifest to be `active_preview`; missing manifests or
manifests still in `registered_preview_only` are rejected before any proposal
row or audit event is written. Missing or invalid registry references return
explicit 404/422 errors before lifecycle state is evaluated.

Connector run creation reads the same registry reference to resolve the runtime
boundary stored on run records and audit evidence. It then requires the matching
tenant-scoped persisted manifest to be `active_preview`; missing manifests or
manifests still in `registered_preview_only` are rejected before any run row or
audit event is written. Missing or invalid registry references return explicit
404/422 errors before lifecycle state is evaluated.

Manual import request creation reads the same registry reference to resolve the
connector runtime boundary stored in audit evidence. It then requires the
matching tenant-scoped persisted manifest to be `active_preview` or
`active_live`; missing manifests or manifests still in
`registered_preview_only` are rejected before any manual import row or audit
event is written. Missing or invalid registry
references return explicit 404/422 errors before lifecycle state is evaluated.

Ontology promotion execution reads the same registry reference to validate the
connector id on the persisted proposal, then requires the matching
tenant-scoped persisted manifest to be `active_preview` or `active_live`;
missing manifests or manifests still in `registered_preview_only` are rejected
before the ontology mutation adapter runs, before promotion rows are written
and before promotion audit evidence is appended. Accepting `active_live` keeps
proposals recorded by governed live sync inside the same approval-gated
promotion path; every other promotion gate (approved manual import evidence,
workflow signals, promotion policies and policy sets) applies unchanged. Missing or invalid registry references return
explicit 404/422 errors before lifecycle state is evaluated.

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

`GET /demo/manufacturing/connectors/evidence-invariants` composes the persisted
checkpoint, checkpoint-claim, credential-lease and egress-policy registries into
a single public-safe evidence report. It returns only evidence type, subject id,
parent id, audit event id, reason and detail fields; it does not copy secret
references, private endpoint references, DSNs, raw payloads or result summaries
into the response. Valid reads append `connector.evidence_invariants_read`
audit evidence with counts and subject ids only.

`POST /demo/manufacturing/connectors/evidence-invariants/snapshots`
materializes that report as an append-only audit artifact. The request requires
`connectors:evidence:snapshot`, a tenant-scoped idempotency key and a snapshot
id. The persisted audit payload stores counts, subject ids, reason ids,
permission evidence and a deterministic `sha256-canonical-json-v1` digest of
the public-safe report payload. It does not store secret refs, private endpoint
refs, DSNs, raw audit payloads or result summaries. Replaying the same
idempotency key returns the existing snapshot event; conflicting idempotency
reuse is rejected with 409.

`GET /demo/manufacturing/connectors/evidence-invariants/snapshots` reads those
persisted snapshot artifacts back from the append-only audit ledger. The request
requires `connectors:evidence:snapshot:read` and supports tenant, connector,
snapshot id, idempotency key and bounded limit filters. Valid reads append
`connector.evidence_invariant_snapshots_read` audit evidence containing only
the filters, returned count and returned snapshot ids. The response returns
public-safe snapshot metadata and report digests; it does not copy secret refs,
private endpoint refs, DSNs, raw audit payloads or result summaries.
The public audit event preview exposes only the snapshot id, connector id and
idempotency key needed for review navigation; the audit explorer can link back
to `/connectors?snapshot_id=...&connector_id=...` without exposing raw evidence.

`GET /demo/manufacturing/connectors/evidence-invariants/snapshots/export`
returns a signed/exportable public-safe bundle for persisted snapshot
artifacts. The request uses the same `connectors:evidence:snapshot:read` scope
and supports tenant, connector, snapshot id, idempotency key, limit and export
reason filters. The bundle includes a manifest checksum, deterministic
SHA-256 hash-chain proof and the same self-hosted audit ledger signature proof
used by audit exports when a signing secret is configured. The export audit
event stores only filters, snapshot ids, checksum, export id and signature
status; it does not store raw connector payloads, DSNs, private endpoint refs,
secret refs or credential values.

`POST /demo/manufacturing/connectors/evidence-invariants/snapshots/export-requests`
records a governed export request before any storage artifact is written. The
request requires `connectors:evidence:snapshot:export:request`,
approval id, workflow id, idempotency key, owner role and risk level. Axis
persists an approval-required metadata record, creates an approval record,
writes `connector.evidence_snapshot_export.requested` audit evidence and returns
the snapshot filter, requested snapshot count, checksum preview, redaction
policy, storage status `not_written` and workflow signal status
`pending_approval_decision`. Idempotent replays return the original request
without duplicating audit evidence; conflicting payloads for the same
idempotency key return 409. The endpoint does not write files, object storage
keys, raw connector payloads, DSNs, private endpoint refs, secret refs or
credential values.

`POST /demo/manufacturing/connectors/evidence-invariants/snapshots/export-requests/{export_request_id}/decision`
records the human approval decision for a governed export request. The endpoint
requires `approvals:connectors:export:decide`, records the approval decision on
the approval row, signals the Axis workflow runtime with
`connector_evidence_snapshot_export_decided`, writes
`connector.evidence_snapshot_export.decision_recorded` audit evidence and
updates the request record with decision actor, decision note, decided timestamp,
workflow signal status and export status. Approvals become
`approval_approved` with `export_status=approved_not_exported`; rejections
become `approval_rejected` with `export_status=rejected_not_exported`.
`storage_status` remains `not_written` until the approved request is explicitly
materialized. The decision payload and audit event remain metadata-only and do
not include connector payloads, DSNs, private endpoint refs, secret refs or
credential values.

`POST /demo/manufacturing/connectors/evidence-invariants/snapshots/export-requests/{export_request_id}/materializations`
materializes an approved export request through the configured object-store
adapter. Local demos use the filesystem adapter; S3-compatible deployments can
write retained objects when endpoint, bucket, credentials, object lock and
retention days are configured. The endpoint requires
`connectors:evidence:snapshot:export:materialize`, rejects unapproved requests,
rejects duplicate conflicting materialization ids, rebuilds the public-safe
snapshot bundle from the stored request filter, verifies the checksum still
matches the approved request, writes canonical JSON and returns only storage
metadata: adapter, safe key, opaque storage URI, content type, byte size and
SHA-256 checksum. It appends
`connector.evidence_snapshot_export.materialized` audit evidence with artifact
metadata only. The storage boundary does not expose filesystem paths, raw
connector payloads, DSNs, private endpoint refs, secret refs, S3 access keys or
credential values.

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
`active_preview`, from `active_preview` to `active_live`, or from active states
to `deprecated`. Preview transitions require `connectors:manifest:lifecycle`.
The `active_live` transition requires the separate
`connectors:manifest:enable_live` scope in addition to
`connectors:manifest:lifecycle`, a live-capable manifest sync mode, a runtime
policy that explicitly allows `live_query` and `external_egress`, no runtime
policy block on those operations, and approval, policy and credential evidence
references. Preview transitions write
`connector.manifest.lifecycle_transitioned` audit evidence; live enablement
writes `connector.manifest.live_enabled` audit evidence with
`external_sync_started=false`. Alias targets such as `live_enabled` remain
rejected explicitly. The lifecycle path does not start sync, retrieve
credentials, execute connector code or mutate the ontology graph.

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
policy metadata. It also requires the matching tenant-scoped connector manifest
to be `active_preview` before the lease runtime adapter is called. It writes
`connector.credential_lease.requested` audit evidence and returns only
references, timestamps, decisions and adapter evidence. Renewing and revoking
leases require
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
Credential lease registry reads write `connector.credential_leases_read` audit
evidence with only query filters, returned lease ids and invariant counts. The
registry also reports `lease_evidence_invariants` for missing audit ids,
unresolved audit ids, audit type mismatches, connector/handle/lease payload
mismatches and evidence that reports secret material access. These invariants
are exposed in the connector console per selected connector lease.

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
evidence for non-live profile syncs, keeps `external_query_started=false` and
never returns raw connection strings or credential material.
If the run input explicitly sets `live_query_requested=true`, the adapter enters
a live-query preflight path. By default it writes
`connector.run.sync_execution_preflight_blocked`; with
`AXIS_EXTERNAL_DB_LIVE_QUERY_PREFLIGHT_ENABLED=true`, the self-hosted egress
policy boundary must validate a persisted tenant-scoped connector egress policy
for the connector profile, and the executing worker must target an active
checkpoint claim for the same connector and run with `checkpoint_claim_id`,
backed by `connector.run.sync_checkpoint_claimed` claim audit evidence and
an audit id that resolves in the tenant-scoped append-only audit ledger for the
same connector, run, checkpoint, claim and worker, with worker-lease-only claim
audit payload, plus
`sync_execution_preflight_passed` checkpoint evidence whose audit event type is
`connector.run.sync_execution_preflight_passed` and whose checkpoint audit event
id is present in `evidence_refs`. The referenced checkpoint audit id must also
resolve to a persisted tenant-scoped audit ledger event for the same connector
run and checkpoint before
`connector.run.sync_execution_preflight_passed` can be written. Policies are
created and listed through
`/demo/manufacturing/connectors/egress-policies`; runtime preflight consumes
the repository-backed record and does not rely on a hardcoded policy catalog.
Egress policy registry reads write `connector.egress_policies_read` audit
evidence with only query filters, returned policy ids and invariant counts. The
registry also reports `policy_evidence_invariants` for missing audit ids,
missing audit refs, unresolved audit ids, audit type mismatches,
connector/policy/profile payload mismatches and evidence that reports external
query or credential material access. These invariants are exposed in the
connector console per selected connector policy.
Missing `checkpoint_claim_id`, inactive target claims or missing checkpoint
evidence are rejected before the provider-specific runtime is called, before
preflight audit is written and before a new execution checkpoint is created.
Claim evidence with the wrong audit event type is rejected with
`target_sync_checkpoint_claim_audit_invalid`. Claim evidence referencing a
missing audit ledger event is rejected with
`target_sync_checkpoint_claim_audit_event_not_found`; claim evidence backed by
a mismatched audit ledger event is rejected with
`target_sync_checkpoint_claim_audit_event_mismatch`. Claim audit payload that
says external sync started, secret material was returned or the record is not
worker-lease-only is rejected with
`target_sync_checkpoint_claim_audit_payload_unsafe`.
Checkpoint evidence with the wrong type or status is rejected with
`target_sync_checkpoint_claim_checkpoint_not_eligible`; checkpoint evidence
with the wrong audit event type is rejected with
`target_sync_checkpoint_claim_checkpoint_audit_invalid`; checkpoint evidence
that does not reference its audit event id is rejected with
`target_sync_checkpoint_claim_checkpoint_evidence_ref_missing`; checkpoint
evidence referencing a missing audit ledger event is rejected with
`target_sync_checkpoint_claim_checkpoint_audit_event_not_found`, and a
connector/run/checkpoint mismatch is rejected with
`target_sync_checkpoint_claim_checkpoint_audit_event_mismatch`. Referenced
audit payload that says an external query started, credential material was
returned or a graph mutation started is rejected with
`target_sync_checkpoint_claim_checkpoint_audit_payload_unsafe`. Checkpoint
result evidence that says an external query started, credential material was
returned or a graph mutation started is rejected with
`target_sync_checkpoint_claim_checkpoint_result_unsafe`. Claim result evidence
that says external sync started, secret material was returned or the record is
not worker-lease-only is rejected with
`target_sync_checkpoint_claim_result_unsafe`. When the target claim is valid,
the preflight result summary records public-safe claim evidence: claim id,
checkpoint id, worker and lease expiry. For non-live execution paths,
`checkpoint_claim_id` remains optional.
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
If the same run also sets `live_query_execute=true` and
`AXIS_EXTERNAL_DB_LIVE_QUERY_EXECUTION_ENABLED=true`, Axis can execute a bounded
read-only Postgres live read after preflight passes. This requires the
connector manifest to be `active_live`, with live-query and external-egress
operations explicitly allowed by the manifest lifecycle gate. The runtime also
requires a configured allowlisted profile through
`AXIS_EXTERNAL_DB_LIVE_QUERY_DSN`,
`AXIS_EXTERNAL_DB_LIVE_QUERY_PROFILE_ID`,
`AXIS_EXTERNAL_DB_LIVE_QUERY_SCHEMA`,
`AXIS_EXTERNAL_DB_LIVE_QUERY_TABLE`,
`AXIS_EXTERNAL_DB_LIVE_QUERY_COLUMNS`,
`AXIS_EXTERNAL_DB_LIVE_QUERY_ROW_LIMIT` and
`AXIS_EXTERNAL_DB_LIVE_QUERY_PRIVATE_ENDPOINT_REF`. The persisted egress policy
document must also include `approved_endpoint_target_sha256`, a SHA-256 digest
of the DSN network target (`host:port`) computed outside the public policy
payload. The runtime computes the same digest from
`AXIS_EXTERNAL_DB_LIVE_QUERY_DSN` and blocks execution if the private endpoint
reference or digest does not match the policy evidence. The request profile id,
schema and table must match that configuration before any query is opened.
If `selected_columns` is omitted, Axis reads all configured allowlisted columns;
if it is provided, every selected column must be in the allowlist and use a safe
Postgres identifier. The adapter builds a bounded count query with typed
Postgres identifiers, starts a read-only transaction and persists only row
counts, profile id, row limit, query status and checkpoint evidence. It does
not persist or return DSNs, SQL text, row payloads, credential material or graph
mutations. Failed profile validation, endpoint binding or query execution
records
`connector.run.sync_execution_live_query_blocked` with a public-safe reason and
`external_query_started=false`.
Scheduled runs that set `live_sync_requested=true` in their input summary can
opt into GOVERNED LIVE SYNC EXECUTION on the same execute-sync endpoint. The
live sync boundary stays deferred by default: it activates only when both
`AXIS_CONNECTOR_SYNC_EXECUTION_ENABLED=true` and
`AXIS_CONNECTOR_LIVE_SYNC_EXECUTION_ENABLED=true` are set, and each source type
still needs its own configured profile. The file/CSV connector reads an
allowlisted local dropzone file configured through
`AXIS_FILE_CSV_LIVE_SYNC_ROOT`, `AXIS_FILE_CSV_LIVE_SYNC_PROFILE_ID`,
`AXIS_FILE_CSV_LIVE_SYNC_MAX_ROWS` and `AXIS_FILE_CSV_LIVE_SYNC_BATCH_SIZE`;
file references are validated against traversal, suffix and size limits before
any read. The external Postgres connector reuses the allowlisted live-query
profile plus `AXIS_EXTERNAL_DB_LIVE_SYNC_BATCH_SIZE`, and additionally requires
`AXIS_EXTERNAL_DB_SYNC_EXECUTION_ENABLED`,
`AXIS_EXTERNAL_DB_LIVE_QUERY_PREFLIGHT_ENABLED` and
`AXIS_EXTERNAL_DB_LIVE_QUERY_EXECUTION_ENABLED` before batched reads are
considered. Live sync execution also requires the tenant-scoped connector
manifest to be `active_live` (`connector_manifest_not_active_live` otherwise),
an active credential lease with lease-scoped secret-reference evidence and, for
the external DB source, validated persisted egress policy evidence bound to the
approved private endpoint target digest. Unapproved egress evidence, profile or
endpoint mismatches and unsupported credential access modes persist a
`sync_execution_live_sync_blocked` run with
`connector.run.sync_execution_live_sync_blocked` audit evidence before any
source read.
A permitted live sync executes in bounded batches through the orchestrated
runtime boundary. Every execution writes
`connector.run.sync_execution_started` stage evidence with the resume offset,
then commits one `sync_batch` checkpoint per batch with
`connector.run.sync_batch_committed` audit evidence and public-safe counts and
offsets only. Rows read from the source are mapped through the persisted
manifest schema fields into review-only ontology proposal records
(`connector.ontology_proposals.recorded`, `proposal_only`,
`graph_mutation_status=not_applied`, mapping profile
`connector_live_sync_v1`), so live sync output feeds the existing
approval-gated promotion path and never mutates the graph directly. Row
payloads live only in proposal field summaries; run records, checkpoints and
audit payloads keep counts, offsets and references. Proposals are written with
an insert-or-ignore on `(tenant_id, proposal_id)`, so a resumed run whose
proposal ids overlap a committed batch never raises a duplicate-key error.
Each committed batch checkpoint carries cumulative totals, and resume reads the
single latest committed batch checkpoint deterministically (highest sequence),
so progress cannot regress even past large checkpoint counts.
Failure semantics are deterministic and fail-closed. Source unavailability
(`connector_unavailable`), schema mismatches (`source_schema_mismatch`), query
failures (`query_failed`), mid-run credential lease expiry
(`credential_lease_expired_mid_run`) and batch limits persist a
`sync_execution_failed` run with `connector.run.sync_execution_failed` audit
evidence and a `sync_error_code`; committed batch checkpoints and their
proposals are never rolled back into silent partial success. A failed live
sync run can be retried with a new execution id and idempotency key: the retry
resumes from the `next_offset` of the last committed `sync_batch` checkpoint
and must present an active worker claim on that checkpoint through
`checkpoint_claim_id` (claimed via the existing checkpoint claim endpoint), so
two workers cannot resume the same run concurrently. Missing, expired,
foreign-worker or unsafe resume claims are rejected before any source read.
Replaying a completed execution with the same execution id and idempotency key
returns the persisted run without duplicate evidence; any other reuse is
rejected with 409.
Every sync execution attempt now records a tenant-scoped
`connector_sync_checkpoints` row after the runtime adapter returns. Checkpoints
store public-safe cursor metadata, adapter status, result summaries and audit
evidence refs; they do not store raw DSNs, SQL text, credential values or
secret material. External DB live-read checkpoints may record
`external_query_started=true` only together with
`source_mode=external_db_live_read`,
`live_query_execution_status=completed`, `credential_material_returned=false`
and `graph_mutation_started=false`. External DB live sync evidence may record
`external_query_started=true` only together with
`source_mode=external_db_live_sync`, an in-progress/completed/failed
`live_sync_execution_status`, `credential_material_returned=false`,
`graph_mutation_started=false` and an allowlisted public-safe key set.
The checkpoint registry is exposed at
`/demo/manufacturing/connectors/runs/checkpoints` and supports tenant,
connector, run, status, `created_after`, `created_before` and limit filters.
The endpoint requires `connectors:sync:checkpoint:read` and rejects callers
without that scope before querying checkpoint storage. It also rejects invalid
time windows where `created_after` is equal to or later than `created_before`
before querying checkpoint storage. Valid reads append
`connector.run.sync_checkpoints_read` audit evidence with query filters,
returned checkpoint count, evidence invariant count and checkpoint ids only;
checkpoint cursor and result payloads are not duplicated into the read audit
event. The registry includes public-safe `evidence_invariants` for missing or
unresolved checkpoint audit events, missing evidence refs, audit event type or
connector/run/checkpoint payload mismatches, unsafe audit payloads and unsafe
checkpoint result summaries.
Checkpoint claims are persisted at
`/demo/manufacturing/connectors/runs/checkpoints/{checkpoint_id}/claims` for
worker-safe retry coordination. The endpoint requires
`connectors:sync:checkpoint:claim`, records a lease duration and expiration,
returns idempotent replays for the same checkpoint/idempotency key and appends
`connector.run.sync_checkpoint_claimed` audit evidence. A claim record does
not start external sync, return secret material or execute provider connector
code. A second unexpired active claim for the same checkpoint is rejected with
409 before duplicate audit evidence or competing worker ownership is written. A
partial unique index on `(tenant_id, checkpoint_id) WHERE status='claimed'`
backs the app-level read-active-then-insert check, so a racing worker that also
passes the in-process check still loses at the database and is reported as the
same 409 claim conflict.
Expired claims are marked `expired` with
`connector.run.sync_checkpoint_claim_expired` before replacement ownership is
created.
Checkpoint claims are queryable at
`/demo/manufacturing/connectors/runs/checkpoints/claims` with tenant, connector,
run, checkpoint, worker, status, `created_after`, `created_before`, cursor and
limit filters. Invalid time windows are rejected before storage reads. The
endpoint returns `has_more` and `next_cursor` for stable cursor-based pagination. It requires
`connectors:sync:checkpoint:claim:read` and appends
`connector.run.sync_checkpoint_claims_read` audit evidence with public-safe
filters, pagination metadata, returned claim count, claim evidence invariant
count and claim ids only. The registry reports public-safe
`claim_evidence_invariants` for missing or unresolved claim audit events, audit
event type or connector/run/checkpoint/claim/worker payload mismatches, unsafe
claim audit payloads and unsafe claim result summaries. The `/connectors`
console uses the same read scope and registry endpoint to show worker
ownership, lease, renewal/release, invariant status and secret-material
evidence for claims attached to the selected connector checkpoints.
Claim renewal and release are exposed through dedicated endpoints with
`connectors:sync:checkpoint:claim:renew` and
`connectors:sync:checkpoint:claim:release`, updating the same persisted lease
record and writing `connector.run.sync_checkpoint_claim_renewed` /
`connector.run.sync_checkpoint_claim_released` audit evidence.
The `/connectors` console consumes the same endpoint and renders checkpoint
rows per selected connector without local fallback data or raw payload dumps.

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
- a tenant-scoped connector manifest in `active_preview`;
- a tenant-scoped idempotency key;
- actor scope `connectors:ontology:promote`.

Successful promotions write through the Axis ontology mutation runtime adapter
and record `type_db_mutation_applied` on the proposal. If the TypeDB mutation
runtime is disabled, the default adapter records `type_db_mutation_deferred`
without mutating the graph. Runtime failures are recorded as
`type_db_mutation_unavailable`. Successful, deferred and failed promotion
attempts write append-only `connector.ontology_promotion.*` audit evidence with
the manifest runtime boundary that authorized the mutation path, and never
store raw CSV content or credential material.

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
`/demo/manufacturing/connectors/promotion-policies`. It also loads
tenant-scoped sync checkpoints from
`/demo/manufacturing/connectors/runs/checkpoints` and shows sequence, adapter,
cursor summary, result evidence, audit refs and invariant status for the
selected connector. The console also loads the aggregate evidence invariant
report from `/demo/manufacturing/connectors/evidence-invariants` and renders
checkpoint, claim, credential lease and egress policy finding counts from the
API response. It loads evidence snapshot history from
`/demo/manufacturing/connectors/evidence-invariants/snapshots` with
`connectors:evidence:snapshot:read` and renders newest snapshot id, invariant
totals, evidence surface count and digest prefixes from the API response. The
console can also create a selected-connector snapshot through
`POST /demo/manufacturing/connectors/evidence-invariants/snapshots` with
`connectors:evidence:snapshot`; the request carries generated snapshot and
idempotency ids, public-safe review reason metadata and no raw connector payload
or credential material. Snapshot rows with an audit event id link to
`/audit?event_id=...`, letting reviewers open the matching audit ledger event
without copying raw payloads into the connector console. Snapshot persisted
audit events then link back to `/connectors?snapshot_id=...&connector_id=...`;
the console resolves those query params against API snapshot history, selects
the matching connector and highlights the selected artifact. The checkpoint
request includes `connectors:sync:checkpoint:read`; if the API is unavailable
or rejects the request, the page shows an API-required state and does not render local
connector records.
The console also loads the API-backed snapshot export bundle and renders export
id, record count, checksum prefix, redaction policy, integrity algorithm and
ledger signature status. It does not synthesize a local export when the API is
unavailable.
The console can also submit a governed export request for the selected connector
and newest matching snapshot. The POST response is rendered as an API-backed
request record with approval id, workflow status, checksum prefix and storage
status; failed requests do not create local fallback state. When a request is
present, the console can submit an approval decision through the API-backed
decision endpoint and renders the returned decision, export status and workflow
signal status. The console does not mark a request approved locally if the API
call fails.
For approved requests, the console can submit materialization through the
API-backed materialization endpoint and then renders the returned storage
adapter, opaque URI, checksum prefix, byte size and storage status. It does not
write browser-local files and does not infer artifact metadata if the API call
fails.
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
- tenant-scoped sync execution checkpoints before provider-specific retry and
  resume logic;
- governed live sync execution behind explicit runtime flags, per-source
  profiles, `active_live` manifests, credential lease evidence and (for
  external DB sources) persisted egress policy evidence;
- committed per-batch sync checkpoints with stage audit evidence and
  resume-from-last-checkpoint retries behind worker checkpoint claims;
- fail-closed live sync error taxonomy with persisted failed-run evidence and
  no partial silent success;
- live-sync row payload confinement to review-only ontology proposals, keeping
  graph mutation behind the approval-gated promotion path;
- connector API checkpoint queries with dedicated read scope for
  worker/operator observability;
- checkpoint API pagination through `created_before` for stable operator and
  worker reads;
- checkpoint API time windows through `created_after` plus `created_before`;
- checkpoint time-window validation before checkpoint storage reads;
- checkpoint read audit evidence for valid API reads;
- checkpoint worker claims with persisted leases and idempotent replay;
- checkpoint claim renewal/release with dedicated scopes and audit evidence;
- active checkpoint claim conflict handling before duplicate worker ownership;
- stale checkpoint claim expiry before replacement worker ownership;
- checkpoint claim registry reads with dedicated scope and audit evidence;
- checkpoint claim evidence invariant reporting on registry reads;
- connector/run filters for checkpoint claim registry reads;
- opaque cursor pagination for checkpoint claim registry reads;
- claiming-worker filters for checkpoint claim registry reads;
- created time-window filters for checkpoint claim registry reads;
- active worker checkpoint claim gate before external DB live-query preflight;
- explicit checkpoint claim target binding for external DB live-query preflight;
- checkpoint claim audit type gate before external DB live-query preflight;
- checkpoint claim audit ledger lookup before external DB live-query preflight;
- checkpoint claim audit payload worker-lease-only gate before external DB
  live-query preflight;
- checkpoint audit payload public-safety gate before external DB live-query preflight;
- checkpoint result public-safety gate before external DB live-query preflight;
- checkpoint claim result worker-lease-only gate before external DB live-query
  preflight;
- connector console checkpoint claim observability without browser-local
  fallback records;
- connector console checkpoint observability without browser-local fallback
  records;
- aggregate connector evidence invariant reports without copying secret or
  private endpoint references into read payloads;
- aggregate connector evidence invariant snapshots as append-only audit
  artifacts before scheduled invariant jobs exist;
- signed connector evidence snapshot exports before provider-specific KMS
  signing exists;
- approval/workflow/idempotency-gated connector evidence snapshot export
  requests before any storage artifact is written;
- approved connector evidence snapshot export materialization to the configured
  filesystem or S3-compatible object-store adapter;
- persisted ontology proposal records before controlled graph mutation;
- approval/workflow/idempotency-gated manual import requests before controlled
  promotion;
- promotion policy authoring before required enforcement;
- TypeDB ontology mutation adapter, deferred by default unless explicitly
  enabled.

Future Platform work should add:

- live provider secret retrieval beyond provider-specific lease validation;
- provider-specific scheduled live sync beyond the checkpointed self-hosted
  execution boundary;
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
- API unit tests for credential handle metadata, `active_preview` manifest
  gating, secret reference guardrails and rotation history;
- API unit tests for credential lease request, `active_preview` manifest
  gating, renewal, revocation, permission checks and raw secret material
  rejection;
- API unit tests for tenant-scoped egress policy persistence, endpoint listing
  and live-query preflight enforcement;
- API unit tests for aggregate connector evidence invariant reporting, read
  audit payloads and public-safety constraints;
- API unit tests for connector evidence invariant snapshot materialization,
  idempotent replay, conflict handling and public-safety constraints;
- API unit tests for connector evidence snapshot export manifests, hash-chain
  integrity proof, self-hosted signature proof, read-scope enforcement and
  public-safety constraints;
- API unit tests for governed connector evidence snapshot export requests,
  approval record creation, idempotent replay, conflict handling, request-scope
  enforcement and public-safety constraints;
- API unit tests for governed connector evidence snapshot export request
  decisions, approval decision persistence, workflow signal evidence,
  decision-scope enforcement and public-safety constraints;
- API unit tests for approved connector evidence snapshot export
  materialization, materialization-scope enforcement, approval gating, checksum
  verification, local object-store writes and public-safety constraints;
- API unit tests for connector run records, `active_preview` manifest gating,
  audit writes and raw payload rejection;
- API unit tests for governed live sync execution: file/CSV dropzone reads
  against real temporary files, Postgres live sync policy gates at the adapter
  seam, batch checkpoints, stage audit evidence, proposal derivation, mid-run
  lease expiry, checkpoint claim resume/conflict handling, egress blocking,
  idempotent replay, tenant isolation and flag-off deferred behavior, plus an
  integration-gated batched live sync read against local Postgres;
- API unit tests for connector ontology proposal persistence, `active_preview`
  manifest gating, audit writes, graph-write rejection and raw payload
  rejection;
- API unit tests for manual import request persistence, `active_preview`
  manifest gating, audit writes, idempotent replay, conflict detection,
  graph-write rejection and raw payload rejection;
- API unit tests for ontology promotion execution, `active_preview` manifest
  gating, mutation-runtime blocking, audit writes, policy evidence and
  idempotent replay;
- API unit tests for required-column and unsupported-connector guardrails;
- API endpoint and OpenAPI exposure tests;
- web unit tests for connector helper contracts and regression coverage that
  forbids default connector seed records in runtime libraries;
- web unit tests for deterministic aggregate evidence invariant count summaries;
- web unit tests for deterministic connector evidence snapshot summaries;
- web unit tests for evidence snapshot history query path scope and filters;
- web unit tests for evidence snapshot export query path scope and filters;
- web unit tests for governed evidence snapshot export request path and payload
  construction;
- web unit tests for governed evidence snapshot export request decision path and
  payload construction;
- web unit tests for evidence snapshot creation request scope and public-safety
  constraints;
- web unit tests for connector snapshot deep-link construction and query
  selection against API-backed registry/history records;
- web unit tests for audit event deep-link construction and requested-event
  selection;
- browser smoke verification for `/connectors` rendering the API-backed snapshot
  history section;
- Playwright smoke tests for `/connectors` API-required behavior when the
  backend is unavailable.
