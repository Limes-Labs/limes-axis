# Platform Workflow Console

The workflow console slice turns the static `/workflows` shell into an
API-backed, read-only view of the manufacturing reference workflow runs.

It is public-safe. The console shows workflow state, runtime
adapter metadata, pending governance signals, timeline evidence and control
metadata without executing live workflow mutations.

## Demo Endpoint

```text
GET /demo/manufacturing/workflows
GET /demo/manufacturing/workflows/runs
```

The reference endpoint returns a typed workflow console for the demo tenant. It
reads the active `demo_reference_records` row for `surface=workflows` and
`reference_id=manufacturing-workflow-console`; missing or invalid persisted
records return explicit API errors. The persisted endpoint reads Postgres
workflow run state and tenant-scoped timeline events with optional filters:

- `tenant_id`;
- `state`;
- `limit`.

Both endpoints return the same workflow console contract:

- runtime status and workflow metrics;
- workflow id, domain, state, owner role and autonomy level;
- Temporal OSS runtime metadata behind the Axis adapter boundary;
- related risk, assets, inputs and proposed outputs;
- pending signals and linked approval ids;
- governance controls and audit scope;
- timeline events for the history preview.

## Console Behavior

The `/workflows` page first loads persisted workflow runs from
`/demo/manufacturing/workflows/runs`. If that query returns no rows, it uses the
reference endpoint served by the API. When the API is unavailable, the page
shows an API-required state and does not render local workflow records.

The page is read-only. It lets an operator inspect workflow runs, pending
signals and history preview data, but it does not signal Temporal, mutate state
or write audit records.

## Runtime Boundary

Temporal remains behind the Axis workflow runtime adapter. The public console
shows the contract Axis expects from that boundary without exposing production
operations.

Approval decision persistence now uses this runtime boundary to signal the
matching workflow when Temporal is available. The workflow console itself stays
read-only: it shows persisted run state and history views without exposing live
mutation controls.

The reference workflow console is a bootstrap reference surface, but it is no
longer constructed inside the FastAPI route. Alembic migration
`0026_workflow_console_reference` inserts the public-safe workflow console
reference payload, and the API validates it against the
`ManufacturingWorkflowConsole` contract before returning it. The API runtime no
longer defines a workflow console seed factory; tests validate the bootstrap
payload directly from the migration.

Typed action run persistence now also uses this boundary for approval-gated
action payloads. The API sends an `action_requested` signal after the action run
is persisted and records either the adapter result or an explicit degraded
status in the action audit event. The signal result is redacted in API and UI
responses and does not expose raw payload content in audit metadata.

Future Platform work should connect this contract to:

- workflow history retention and replay artifacts.

The replay/simulation foundation now derives read-only replay preview artifacts
from persisted workflow history and audit evidence, including governed
policy-set version diff previews over historical workflow events. Full Temporal
deterministic replay and production history retention remain future Platform
work.

## Verification

The slice is covered by:

- API unit tests for the manufacturing workflow console reference endpoint;
- contract tests for the persisted workflow console bootstrap payload;
- API unit tests for persisted workflow run state and tenant-scoped history;
- OpenAPI schema export/check;
- web unit tests for the persisted-data selection contract;
- Playwright smoke tests for API-required workflow behavior on desktop and mobile.
