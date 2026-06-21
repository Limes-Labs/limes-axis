# Platform Workflow Console

The workflow console slice turns the static `/workflows` shell into an
API-backed, read-only view of the manufacturing reference workflow runs.

It is synthetic and public-safe. The console shows workflow state, runtime
adapter metadata, pending governance signals, timeline evidence and control
metadata without executing live workflow mutations.

## Demo Endpoint

```text
GET /demo/manufacturing/workflows
```

The endpoint returns a typed workflow console for the demo tenant:

- runtime status and workflow metrics;
- workflow id, domain, state, owner role and autonomy level;
- Temporal OSS runtime metadata behind the Axis adapter boundary;
- related risk, assets, inputs and proposed outputs;
- pending signals and linked approval ids;
- governance controls and audit scope;
- timeline events for the history preview.

## Console Behavior

The `/workflows` page loads the endpoint from `NEXT_PUBLIC_AXIS_API_BASE_URL`.
When the API is unavailable, the page falls back to the local synthetic workflow
seed.

The page is read-only. It lets an operator inspect workflow runs, pending
signals and history preview data, but it does not signal Temporal, mutate state
or write audit records.

## Runtime Boundary

Temporal remains behind the Axis workflow runtime adapter. The public console
shows the contract Axis expects from that boundary without exposing production
operations.

Future Platform work should connect this contract to:

- persisted workflow run state;
- tenant-scoped history views;
- workflow signal execution behind permission checks;
- append-only audit ledger writes;
- deterministic replay and simulation outputs.

## Verification

The slice is covered by:

- API unit tests for the manufacturing workflow console seed and endpoint;
- OpenAPI schema export/check;
- web unit tests for the local fallback contract;
- Playwright smoke tests for workflow rendering on desktop and mobile.
