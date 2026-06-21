# Platform Overview

The first Platform slice turns the governance console overview into an
API-backed operational demo surface.

## Demo Scope

The manufacturing reference seed is intentionally public and synthetic. It uses
roles, system IDs and demo tenant IDs rather than personal names or customer
data.

It models the first Plant Operations Cockpit scenario:

- workflow load;
- pending approvals;
- governed agents;
- audit evidence;
- supplier, quality and maintenance risk signals.

## API Contract

The FastAPI service exposes:

```text
GET /demo/manufacturing/overview
```

The endpoint returns a typed overview for the demo tenant:

- summary metrics;
- risk signals;
- active workflow summaries;
- approval queue summaries;
- governed agent summaries;
- recent audit evidence.

The schema is included in `docs/openapi.json` and checked by CI through
`make openapi-check`.

## Console Behavior

The Next.js overview page loads the demo endpoint from
`NEXT_PUBLIC_AXIS_API_BASE_URL`. If the API is unavailable, the console falls
back to the local synthetic seed so the UI remains usable in docs, CI and local
frontend-only development.

This is a demo seed, not a production data loading path. Future Platform work
will replace it with tenant-scoped, authenticated API surfaces backed by
Postgres, TypeDB and workflow state.

## Verification

Covered by:

- API unit tests for the manufacturing overview seed and endpoint;
- generated OpenAPI drift check;
- web unit tests for the fallback demo contract;
- Playwright smoke tests for overview rendering on desktop and mobile.
