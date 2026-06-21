# Platform Approval Inbox

The approval inbox slice turns the static `/approvals` shell into an API-backed
governance surface for the manufacturing reference demo.

It is intentionally public-safe and synthetic. The queue endpoint is read-only,
while the decision endpoint can persist a demo approval decision and append an
audit event. The web console submits reviewer decisions to the endpoint when the
API is reachable and falls back to a local preview when it is not.

## Demo Endpoint

```text
GET /demo/manufacturing/approvals
POST /demo/manufacturing/approvals/{approval_id}/decision
```

The endpoint returns a typed approval queue for the demo tenant:

- approval id, action, status, risk level and due date;
- requesting agent, owner role, workflow id and domain;
- evidence, data accessed, risks and alternatives;
- estimated cost exposure;
- model policy and required permission;
- decision options for approve, reject and request changes;
- audit event preview for the eventual append-only approval record.

The decision endpoint accepts a decision, actor id, actor scopes and optional
note. In standalone demo mode those actor fields are evaluated against the
approval's required permission before persistence. When an `Authorization:
Bearer ...` header is present, or when OIDC auth is required by configuration,
the endpoint validates the token against configurable OIDC/JWKS settings,
derives tenant, actor and scopes from token claims, and binds the request to
that authenticated principal. Actor impersonation attempts return 403 before
any approval record or audit event is written. If the required
`approvals:*:decide` scope is missing, the endpoint returns 403 and does not
write the approval record or audit event. When allowed, it creates or reuses the
matching tenant-scoped `approval_records` row, records the decision and appends
an `approval.decision.recorded` audit event. It also signals the Axis workflow
runtime adapter. When Temporal is unavailable or the workflow is not running,
the decision still persists and the response returns an explicit degraded
workflow signal status.

## Console Behavior

The `/approvals` page loads the endpoint from `NEXT_PUBLIC_AXIS_API_BASE_URL`.
When the API is not reachable, the page falls back to the local synthetic seed.

The page lets a reviewer select approval proposals and submit a decision. The
console sends a typed `decision`, `actor_id`, `actor_scopes` and note payload to
the demo API. In authenticated deployments, the API treats those actor fields as
demo fallback metadata and binds persistence to the bearer token principal
instead. When the request succeeds, the panel shows the persisted audit event,
permission result and workflow signal result returned by the API. When the
request fails, the panel keeps a browser-local preview so the standalone
console remains usable.

## Governance Boundary

This slice demonstrates the approval contract and review experience. It can
persist decisions through the demo API, and the console now uses that endpoint
when available. The demo endpoint enforces the approval's required permission
from supplied demo actor scopes or from OIDC-derived token scopes, rejects actor
impersonation before persistence and signals the workflow runtime adapter.

Future Platform work should connect this contract to:

- persisted workflow state and tenant-scoped runtime history;
- broader relationship-aware permission checks for `approvals:*:decide`;
- replay and simulation of approval outcomes.

## Verification

The slice is covered by:

- API unit tests for the manufacturing approval inbox seed and endpoint;
- API unit tests for persisted approval decisions and audit writes;
- API unit tests for approval decision permission denial;
- API unit tests for OIDC/JWKS token validation, actor binding and
  impersonation denial;
- API unit tests for workflow signal success and degraded runtime paths;
- OpenAPI schema export/check;
- web unit tests for the persisted decision payload contract;
- Playwright smoke tests for queue rendering and standalone local fallback.
