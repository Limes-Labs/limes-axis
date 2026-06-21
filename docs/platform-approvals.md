# Platform Approval Inbox

The approval inbox slice turns the static `/approvals` shell into an API-backed
governance surface for the manufacturing reference demo.

It is intentionally public-safe and synthetic. The API is read-only, while the
web console keeps decision state locally in the browser to demonstrate how a
human review flow should feel before production persistence is introduced.

## Demo Endpoint

```text
GET /demo/manufacturing/approvals
```

The endpoint returns a typed approval queue for the demo tenant:

- approval id, action, status, risk level and due date;
- requesting agent, owner role, workflow id and domain;
- evidence, data accessed, risks and alternatives;
- estimated cost exposure;
- model policy and required permission;
- decision options for approve, reject and request changes;
- audit event preview for the eventual append-only approval record.

## Console Behavior

The `/approvals` page loads the endpoint from `NEXT_PUBLIC_AXIS_API_BASE_URL`.
When the API is not reachable, the page falls back to the local synthetic seed.

The page lets a reviewer select approval proposals and record a local decision
preview. This updates the visible queue state and audit result for the current
browser session only.

## Governance Boundary

This slice demonstrates the approval contract and review experience. It does
not yet persist approval decisions, signal Temporal workflows or write tenant
audit records.

Future Platform work should connect this contract to:

- tenant-scoped approval records in Postgres;
- workflow signal execution behind the Axis workflow runtime adapter;
- append-only audit ledger writes;
- permission checks for `approvals:*:decide`;
- replay and simulation of approval outcomes.

## Verification

The slice is covered by:

- API unit tests for the manufacturing approval inbox seed and endpoint;
- OpenAPI schema export/check;
- web unit tests for the local fallback contract;
- Playwright smoke tests for queue rendering and local decision preview.
