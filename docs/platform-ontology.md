# Platform Ontology Explorer

The first ontology explorer slice maps the manufacturing reference seed into a
read-only operational graph.

## Demo Scope

The graph is public-safe and synthetic. It uses demo IDs, roles and fictional
plant context rather than customer data or personal names.

It includes:

- typed nodes for organization, assets, risks, workflows, approvals, agents,
  policy and audit evidence;
- relationships such as `contains`, `impacts`, `drives`, `requires_approval`,
  `proposes`, `governs` and `records`;
- source-system labels for ERP, MES, QMS, CMMS, Supplier Portal and Axis Audit;
- permission scopes on every relationship.

## API Contract

The FastAPI service exposes:

```text
GET /demo/manufacturing/ontology
```

The endpoint returns:

- node list;
- relationship list;
- source-system list;
- permission notes.

The schema is included in `docs/openapi.json` and checked by CI.

## Console Behavior

The `/ontology` page loads the demo endpoint from
`NEXT_PUBLIC_AXIS_API_BASE_URL`. If the API is unavailable, it falls back to the
local synthetic ontology seed.

The current page is read-only. Future Platform work should add tenant-scoped
entity detail pages, real TypeDB-backed relationships and permission-aware graph
queries.

## Verification

Covered by:

- API tests for graph integrity and endpoint exposure;
- generated OpenAPI drift check;
- web unit tests for fallback graph integrity;
- Playwright smoke tests for desktop and mobile rendering.
