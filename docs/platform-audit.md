# Platform Audit Explorer

The audit explorer slice turns the static `/audit` shell into an API-backed
view of reference and persisted manufacturing audit events.

It is public-safe and intentionally limited. The explorer shows event metadata,
filters, evidence references and redacted payload previews. The export path now
enforces the requested retention window and includes a deterministic hash-chain
integrity proof without claiming WORM storage, KMS signing or deterministic
workflow replay are complete.

## Demo Endpoint

```text
GET /demo/manufacturing/audit
GET /demo/manufacturing/audit/events
GET /demo/manufacturing/audit/export
```

The reference endpoint returns a typed audit explorer for the demo tenant. The
persisted endpoint queries Postgres `audit_events` with tenant-scoped filters:

- `tenant_id`;
- `event_type`;
- `actor_id`;
- `scope`;
- `limit`.

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
- redacted event records using payload previews only;
- retention notes that identify enforced behavior and future production
  hardening boundaries.

## Console Behavior

The `/audit` page first loads persisted events from
`/demo/manufacturing/audit/events`. If the query returns no rows, it uses the
reference endpoint served by the API. When the API is unavailable, the page
shows an API-required state and does not render local audit records.

The page supports local filters for tenant, event type and scope. Filtering is
browser-local after the initial tenant-scoped API query.

The page also loads `/demo/manufacturing/audit/export` to show the current
export manifest, retention enforcement status and integrity proof. If the
export endpoint is not available, the page displays an API-required export
state instead of constructing a local bundle.

## Governance Boundary

This slice demonstrates the audit contract and explorer surface. It does not
yet implement physical retention deletion jobs, legal hold workflow, WORM/KMS
storage hardening or deterministic Temporal replay.

The Postgres persistence foundation includes the append-only `audit_events`
table and repository methods for inserting and tenant-scoped listing. Approval
decisions and action run requests now append audit events, and the public audit
explorer can query and export redacted bundles for those persisted records.
Export bundles enforce the requested retention window before records enter the
bundle unless legal hold is active, and every bundle includes a deterministic
SHA-256 hash-chain integrity proof. Production query permissions, physical
deletion jobs, legal hold workflows and WORM/KMS storage hardening remain
future work.

Future Platform work should connect this contract to:

- tenant-scoped query permissions;
- physical retention deletion jobs and legal hold workflows;
- WORM/KMS-backed ledger signing;
- evidence bundles for security and operations reviews.

The replay/simulation foundation now consumes redacted audit metadata for
read-only replay preview artifacts and governed policy-set version diff
previews. Persisted simulation outputs now write
`simulation.replay_output.persisted` evidence. Replay simulation responses now
enforce retention-aware query windows and expose excluded record counts; physical
deletion jobs and production legal-hold workflows remain future work.

## Verification

The slice is covered by:

- API unit tests for the manufacturing audit explorer reference endpoint;
- API unit tests for persisted audit event query mapping and filters;
- API unit tests for redacted audit export manifests, retention enforcement and
  integrity proofs;
- OpenAPI schema export/check;
- web unit tests for filtering, export metadata and integrity fields with local
  test fixtures only;
- Playwright smoke tests for API-required audit behavior on desktop and mobile.
