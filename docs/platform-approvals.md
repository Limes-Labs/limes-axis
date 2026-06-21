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

The decision endpoint accepts a decision, actor id and optional note. It creates
or reuses the matching tenant-scoped `approval_records` row, records the
decision and appends an `approval.decision.recorded` audit event. Workflow
signal execution remains pending.

## Console Behavior

The `/approvals` page loads the endpoint from `NEXT_PUBLIC_AXIS_API_BASE_URL`.
When the API is not reachable, the page falls back to the local synthetic seed.

The page lets a reviewer select approval proposals and submit a decision. The
console sends a typed `decision`, `actor_id` and note payload to the demo API.
When the request succeeds, the panel shows the persisted audit event and
workflow signal placeholder returned by the API. When the request fails, the
panel keeps a browser-local preview so the standalone console remains usable.

## Governance Boundary

This slice demonstrates the approval contract and review experience. It can
persist decisions through the demo API, and the console now uses that endpoint
when available. No Temporal workflow signal is emitted yet.

Future Platform work should connect this contract to:

- workflow signal execution behind the Axis workflow runtime adapter;
- permission checks for `approvals:*:decide`;
- replay and simulation of approval outcomes.

## Verification

The slice is covered by:

- API unit tests for the manufacturing approval inbox seed and endpoint;
- API unit tests for persisted approval decisions and audit writes;
- OpenAPI schema export/check;
- web unit tests for the persisted decision payload contract;
- Playwright smoke tests for queue rendering and standalone local fallback.
