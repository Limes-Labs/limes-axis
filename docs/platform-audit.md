# Platform Audit Explorer

The audit explorer slice turns the static `/audit` shell into an API-backed
view of reference and persisted manufacturing audit events.

It is public-safe and intentionally limited. The explorer shows event metadata,
filters, evidence references and redacted payload previews. The export path now
enforces the requested retention window and includes a deterministic hash-chain
integrity proof plus a self-hosted ledger signature proof when signing is
configured. It does not claim provider-specific KMS signing, customer bucket
policy review or deterministic workflow replay are complete.
Governed connector evidence exports can use the S3-compatible object-store
adapter with object-lock retention. When the object store is configured for
COMPLIANCE retention, audit exports are WORM-enforced: the export path verifies
that the backing bucket was created with S3 object-lock enabled and fails closed
otherwise. Provider-specific KMS signing and production legal operations remain
future work before any external compliance certification.

## Demo Endpoint

```text
GET /demo/manufacturing/audit
GET /demo/manufacturing/audit/events
GET /demo/manufacturing/audit/export
POST /demo/manufacturing/audit/retention/delete
GET /demo/manufacturing/audit/legal-holds
POST /demo/manufacturing/audit/legal-holds
POST /demo/manufacturing/audit/legal-holds/{hold_id}/release
POST /demo/manufacturing/audit/object-legal-holds
POST /demo/manufacturing/audit/object-legal-holds/release
```

The reference endpoint returns a typed audit explorer for the demo tenant. It
reads the active `demo_reference_records` row for `surface=audit` and
`reference_id=manufacturing-audit-explorer`; missing or invalid persisted
payloads return 404/422 instead of falling back to route-owned seed data. The
persisted endpoint queries Postgres `audit_events` with tenant-scoped filters:

- `tenant_id`;
- `event_type`;
- `actor_id`;
- `scope`;
- `limit`.

When OIDC is configured as required, persisted audit event reads require
`audit:read` from the verified bearer token or server-side browser session.
The authenticated tenant must match the requested tenant. In optional local
demo mode, unauthenticated reads remain available for public-safe walkthroughs.

The reference and persisted event endpoints return the same explorer contract:

- ledger status and audit metrics;
- tenant, event type, scope, actor and category filter options;
- event id, timestamp, actor, category, domain, scope and result;
- permission scope and data classification;
- related workflow, approval and agent ids;
- evidence references;
- redacted payload preview fields.

The export endpoint uses the same tenant-scoped filters and returns a public-safe
JSON bundle:

- export manifest id, generation time, record count and checksum;
- applied tenant/event/actor/scope/limit filters;
- retention policy id, retention days, legal hold flag and review requirement;
- retention enforcement flag, window start and excluded record count;
- hash-chain algorithm, chain tip and per-event hashes;
- ledger signature status, key id, payload digest and signature metadata;
- redacted event records using payload previews only;
- retention notes that identify enforced behavior and future production
  hardening boundaries.

When OIDC is present or required, export authorization is evaluated from the
verified principal and requires `audit:read`; request query parameters cannot
override the authenticated tenant boundary.

Audit ledger signing is configured with `AXIS_AUDIT_LEDGER_SIGNING_SECRET` and
`AXIS_AUDIT_LEDGER_SIGNING_KEY_ID`. The default path is self-hosted
HMAC-SHA256 over the export manifest plus hash-chain integrity proof. Secret
material is never returned in the bundle. If signing is not configured, the API
returns an explicit unsigned proof with the canonical payload digest.

The legal hold endpoints create, list and release tenant-scoped hold records.
They require `audit:legal_hold:write`, append
`audit.legal_hold.activated` / `audit.legal_hold.released` evidence, and store
scope filters for event type and actor without raw payload material.
When authenticated, the API derives the legal-hold actor and scopes from the
OIDC principal and rejects actor or tenant impersonation before evaluating the
legal-hold permission.

The retention delete endpoint accepts a typed request with tenant, actor,
scopes, retention days, dry-run mode and legal-hold flag. It requires
`audit:retention:delete`. Dry runs count candidates without deleting rows.
Active persisted legal holds, or the explicit request legal-hold flag, block
deletion. Executed runs physically delete eligible tenant-scoped `audit_events`
rows older than the retention cutoff and append a fresh
`audit.retention_deletion.executed` evidence event containing counts, filters
and SHA-256 hashes of deleted records, not raw payloads.
When authenticated, the API derives the deletion actor and scopes from the OIDC
principal and rejects body-level actor or tenant impersonation before any
candidate query, deletion or evidence write.

## Console Behavior

The `/audit` page first loads persisted events from
`/demo/manufacturing/audit/events`. If the query returns no rows, it uses the
reference endpoint served by the API. When the API is unavailable, the page
shows an API-required state and does not render local audit records.

The page supports local filters for tenant, event type and scope. Filtering is
browser-local after the initial tenant-scoped API query.
The page also accepts `event_id` in the URL query string. When the requested
event is present in the API-backed result set, the explorer opens that ledger
event directly; otherwise it falls back to the visible filtered event list.

The page also loads `/demo/manufacturing/audit/export` to show the current
export manifest, retention enforcement status and integrity proof. If the
export endpoint is not available, the page displays an API-required export
state instead of constructing a local bundle.

## Governance Boundary

This slice demonstrates the audit contract and explorer surface. Alembic
migration `0028_audit_explorer_reference` inserts the public-safe reference
explorer payload. The API runtime no longer defines an audit explorer seed
factory; tests validate the bootstrap payload directly from the migration. It
implements a first physical retention deletion execution path with dry-run and
persisted legal-hold safeguards and self-hosted ledger signing for export
proofs. Governed connector evidence materializations can use the
S3-compatible object-store adapter with object-lock retention, but audit export
bundles still need provider-specific KMS adapters and deterministic Temporal
replay.

The Postgres persistence foundation includes the append-only `audit_events`
table and repository methods for inserting and tenant-scoped listing. Approval
decisions and action run requests now append audit events, and the public audit
explorer can query and export redacted bundles for those persisted records.
Export bundles enforce the requested retention window before records enter the
bundle unless legal hold is active, and every bundle includes a deterministic
SHA-256 hash-chain integrity proof. Retention deletion can physically remove
eligible audit rows with audit evidence, while active legal hold records block
execution. Persisted audit read/export/admin routes now bind tenant, actor and
scope checks to OIDC principals when authentication is present or required.
Provider-specific KMS adapters, customer bucket-policy review and richer
enterprise legal review workflows remain future work.

## WORM / Object-Lock Enforcement For Compliance Exports

Audit export bundles can be pinned under S3 object-lock (WORM) when the export
object store runs in COMPLIANCE retention mode. Enforcement is real and
fail-closed rather than advisory:

- **Bucket must be created with object-lock enabled.** S3/MinIO only accepts
  COMPLIANCE-mode retention on buckets created with object-lock. The platform
  verifies this by probing the bucket object-lock configuration
  (`get_object_lock_config`) at bootstrap. A bucket without object-lock, or a
  probe failure, is treated as non-enforceable.
- **Readiness reports the truth.** `/deployment/readiness` and
  `/support/diagnostics` expose `object_store_object_lock_bucket_verified` and
  `object_store_compliance_enforceable`. When COMPLIANCE is configured but the
  bucket lacks object-lock, the object-store readiness check reports
  `action_required` with the missing requirement `verified object-lock bucket`.
- **Export fails closed.** A COMPLIANCE-configured audit export
  (`GET /demo/manufacturing/audit/export`) refuses to produce a bundle with
  `503 CONNECTOR_UNAVAILABLE` if the store cannot enforce object-lock. The
  manifest `worm_retention_enforced` flag reflects the *actual* verified
  capability, never an optimistic default; `worm_retain_until` carries the
  explicit RetainUntilDate derived from the configured retention days.
- **The local filesystem store cannot provide WORM.** COMPLIANCE with the
  `local_filesystem` adapter is never enforceable; readiness reports this
  explicitly and the compliance export path fails closed.

### Two Layers Of Legal Hold

There are two complementary, independently-audited legal-hold layers:

- **DB-level audit legal hold** (`/demo/manufacturing/audit/legal-holds`)
  suspends physical retention *deletion* of persisted audit ledger rows and
  blocks matching retention-deletion candidates.
- **Object-store legal hold** (`/demo/manufacturing/audit/object-legal-holds`)
  places or releases an S3 object-lock legal hold on a materialized export
  *artifact* (`enable_object_legal_hold` / `disable_object_legal_hold`), so the
  stored WORM bundle cannot be deleted or overwritten before retention expiry.

Both layers are permission-gated on `audit:legal_hold:write`, OIDC-bound and
append audit evidence (`audit.object_legal_hold.applied` /
`audit.object_legal_hold.released` for the object-store layer). They are not a
parallel or conflicting concept: the DB hold protects the source ledger, the
object hold protects the exported artifact.

Future Platform work should connect this contract to:

- richer legal review workflows and UI for legal hold administration;
- provider-specific KMS signers and customer bucket retention policy review;
- evidence bundles for security and operations reviews.

The replay/simulation foundation now consumes redacted audit metadata for
read-only replay preview artifacts and governed policy-set version diff
previews. Persisted simulation outputs now write
`simulation.replay_output.persisted` evidence. Replay simulation responses now
enforce retention-aware query windows and expose excluded record counts; physical
deletion for replay outputs and production legal-hold workflows remain future
work.

## Verification

The slice is covered by:

- API unit tests for the manufacturing audit explorer persisted reference
  endpoint, bootstrap payload and missing/invalid record handling;
- API unit tests for persisted audit event query mapping and filters;
- API unit tests for connector snapshot audit preview fields used by public
  audit-to-connector navigation;
- API unit tests for redacted audit export manifests, retention enforcement and
  integrity proofs;
- API unit tests for verifiable audit ledger signatures and tamper detection;
- API unit tests for audit legal hold activation/release, physical retention
  deletion dry-run, persisted legal-hold blocking, tenant isolation and
  redacted deletion evidence;
- API unit tests for OIDC-required persisted audit read/export/admin routes,
  token-derived actor/scope binding and tenant/actor impersonation rejection;
- object-store unit tests for bucket object-lock verification, explicit
  RetainUntilDate computation, COMPLIANCE put fail-closed without object-lock,
  the local-store WORM limitation and readiness compliance-enforceable fields;
- API unit tests for COMPLIANCE audit export WORM enforcement (verified bucket
  succeeds, missing object-lock fails closed 503, manifest
  `worm_retention_enforced` truthfulness) and audited object-store legal hold
  apply/release;
- OpenAPI schema export/check;
- web unit tests for filtering, export metadata and integrity fields with local
  test fixtures only;
- Playwright smoke tests for API-required audit behavior on desktop and mobile.
