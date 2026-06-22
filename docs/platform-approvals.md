# Platform Approval Inbox

The approval inbox slice turns the `/approvals` console into an API-backed
governance surface for the manufacturing reference demo.

It is intentionally public-safe and synthetic. The queue endpoint is read-only,
and now reads a persisted tenant-scoped bootstrap record instead of a route-owned
runtime seed. The decision endpoint validates against the same persisted inbox,
then can persist a demo approval decision and append an audit event. The web
console submits reviewer decisions to the endpoint when the API is reachable and
reports persistence errors when it is not.

## Demo Endpoint

```text
GET /demo/manufacturing/approvals
POST /demo/manufacturing/approvals/{approval_id}/decision
```

The queue endpoint reads the active `demo_reference_records` row for
`surface=approvals` and `reference_id=manufacturing-approval-inbox`, then
returns a typed approval queue for the demo tenant:

- approval id, action, status, risk level and due date;
- requesting agent, owner role, workflow id and domain;
- evidence, data accessed, risks and alternatives;
- estimated cost exposure;
- model policy and required permission;
- decision options for approve, reject and request changes;
- audit event preview for the eventual append-only approval record.

Missing persisted reference records return 404. Invalid or tenant-mismatched
payloads return 422 before any approval data is rendered.

The decision endpoint accepts a decision, actor id, actor scopes and optional
note. It loads approval definitions, workflow ids and required permissions from
the same persisted inbox reference record used by the queue endpoint. In
standalone demo mode those actor fields are evaluated against the approval's
required permission before persistence. When an `Authorization: Bearer ...`
header is present, or when OIDC auth is required by configuration, the endpoint
validates the token against configurable OIDC/JWKS settings, derives tenant,
actor and scopes from token claims, and binds the request to that authenticated
principal. Actor impersonation attempts return 403 before any approval record
or audit event is written. If the required `approvals:*:decide` scope is
missing, the endpoint returns 403 and does not write the approval record or
audit event. When allowed, it creates or reuses the matching tenant-scoped
`approval_records` row, records the decision and appends an
`approval.decision.recorded` audit event. It also signals the Axis workflow
runtime adapter. When Temporal is unavailable or the workflow is not running,
the decision still persists and the response returns an explicit degraded
workflow signal status.

## Console Behavior

The `/approvals` page loads the endpoint from `NEXT_PUBLIC_AXIS_API_BASE_URL`.
When the API is not reachable, the page shows an API-required state and does not
render local approval records.

The page lets a reviewer select approval proposals and submit a decision. The
console sends a typed `decision`, `actor_id`, `actor_scopes` and note payload to
the demo API. In authenticated deployments, the API treats those actor fields as
demo request metadata and binds persistence to the bearer token principal
instead. When an OIDC session is attached in the console toolbar, approval
fetches and decision submissions include the bearer token. When the request
succeeds, the panel shows the persisted audit event, permission result and
workflow signal result returned by the API. When the request fails, the panel
keeps the approval pending and shows the API persistence error.

## Governance Boundary

This slice demonstrates the approval contract and review experience. Alembic
migration `0027_approval_inbox_reference` inserts the public-safe approval
inbox reference payload. The API validates that persisted payload against the
`ManufacturingApprovalInbox` contract before returning it or using it for
decision persistence. The demo endpoint enforces the approval's required
permission from supplied demo actor scopes or from OIDC-derived token scopes,
rejects actor impersonation before persistence and signals the workflow runtime
adapter.

Future Platform work should connect this contract to:

- broader relationship-aware permission checks for `approvals:*:decide`;
- replay and simulation of approval outcomes.

## Verification

The slice is covered by:

- API unit tests for the manufacturing approval inbox persisted reference
  endpoint, bootstrap payload and missing/invalid record handling;
- API unit tests for persisted approval decisions and audit writes;
- API unit tests proving approval decisions read workflow and permission data
  from the persisted inbox reference;
- API unit tests for approval decision permission denial;
- API unit tests for OIDC/JWKS token validation, actor binding and
  impersonation denial;
- API unit tests for workflow signal success and degraded runtime paths;
- OpenAPI schema export/check;
- web unit tests for the persisted decision payload contract;
- Playwright smoke tests for API-required approval behavior.
