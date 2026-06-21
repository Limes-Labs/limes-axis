# Platform Audit Explorer

The audit explorer slice turns the static `/audit` shell into an API-backed
view of synthetic and persisted manufacturing audit events.

It is public-safe and intentionally limited. The explorer shows event metadata,
filters, evidence references and redacted payload previews without claiming that
production audit export, retention enforcement or replay are complete.

## Demo Endpoint

```text
GET /demo/manufacturing/audit
GET /demo/manufacturing/audit/events
GET /demo/manufacturing/audit/export
```

The seed endpoint returns a typed audit explorer for the demo tenant. The
persisted endpoint queries Postgres `audit_events` with tenant-scoped filters:

- `tenant_id`;
- `event_type`;
- `actor_id`;
- `scope`;
- `limit`.

The seed and persisted event endpoints return the same explorer contract:

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
- redacted event records using payload previews only;
- retention notes that identify what is advisory metadata versus future
  enforcement.

## Console Behavior

The `/audit` page first loads persisted events from
`/demo/manufacturing/audit/events`. If the query returns no rows, it uses the
synthetic seed endpoint. When the API is unavailable, the page falls back to the
local synthetic audit seed.

The page supports local filters for tenant, event type and scope. Filtering is
browser-local after the initial tenant-scoped API query.

The page also loads `/demo/manufacturing/audit/export` to show the current
export manifest and retention policy metadata. If the export endpoint is not
available, the page displays a local public-safe fallback bundle.

## Governance Boundary

This slice demonstrates the audit contract and explorer surface. It does not
yet implement retention deletion enforcement, legal hold workflow, immutable
storage hardening or deterministic replay.

The Postgres persistence foundation includes the append-only `audit_events`
table and repository methods for inserting and tenant-scoped listing. Approval
decisions and action run requests now append audit events, and the public audit
explorer can query and export redacted bundles for those persisted records.
Production query permissions, deletion enforcement, legal hold workflows and
immutable storage hardening remain future work.

Future Platform work should connect this contract to:

- tenant-scoped query permissions;
- retention deletion enforcement and legal hold workflows;
- replay and simulation from audit/history;
- evidence bundles for security and operations reviews.

## Verification

The slice is covered by:

- API unit tests for the manufacturing audit explorer seed and endpoint;
- API unit tests for persisted audit event query mapping and filters;
- API unit tests for redacted audit export manifests and retention controls;
- OpenAPI schema export/check;
- web unit tests for local fallback filtering and export metadata;
- Playwright smoke tests for audit rendering and filters on desktop and mobile.
