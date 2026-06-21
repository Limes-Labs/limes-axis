# Platform Audit Explorer

The audit explorer slice turns the static `/audit` shell into an API-backed,
read-only view of synthetic manufacturing audit events.

It is public-safe and intentionally limited. The explorer shows event metadata,
filters, evidence references and redacted payload previews without claiming that
production audit export, retention enforcement or replay are complete.

## Demo Endpoint

```text
GET /demo/manufacturing/audit
```

The endpoint returns a typed audit explorer for the demo tenant:

- ledger status and audit metrics;
- tenant, event type, scope, actor and category filter options;
- event id, timestamp, actor, category, domain, scope and result;
- permission scope and data classification;
- related workflow, approval and agent ids;
- evidence references;
- redacted payload preview fields.

## Console Behavior

The `/audit` page loads the endpoint from `NEXT_PUBLIC_AXIS_API_BASE_URL`. When
the API is unavailable, the page falls back to the local synthetic audit seed.

The page supports local filters for tenant, event type and scope. Filtering is
browser-local and does not query a production ledger.

## Governance Boundary

This slice demonstrates the audit contract and explorer surface. It does not
yet implement production ledger export, retention policy enforcement, immutable
storage guarantees or deterministic replay.

The Postgres persistence foundation now includes the append-only `audit_events`
table and repository methods for inserting and tenant-scoped listing. The
public audit explorer still reads the synthetic demo seed until production query
permissions and retention/export controls are added.

Future Platform work should connect this contract to:

- API-backed audit explorer queries from persisted append-only audit storage;
- tenant-scoped query permissions;
- export and retention policy controls;
- replay and simulation from audit/history;
- evidence bundles for security and operations reviews.

## Verification

The slice is covered by:

- API unit tests for the manufacturing audit explorer seed and endpoint;
- OpenAPI schema export/check;
- web unit tests for local fallback filtering;
- Playwright smoke tests for audit rendering and filters on desktop and mobile.
