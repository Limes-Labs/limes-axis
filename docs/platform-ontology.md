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
- permission scopes on every relationship;
- read-only entity detail pages with connected relationships, evidence refs,
  data access summaries and governance notes.

## API Contract

The FastAPI service exposes:

```text
GET /demo/manufacturing/ontology
GET /demo/manufacturing/ontology/entities/{node_id}
```

The graph endpoint returns:

- node list;
- relationship list;
- source-system list;
- permission notes.

The entity detail endpoint returns:

- selected node metadata;
- inbound and outbound relationship summaries;
- required permission scopes;
- evidence references;
- related workflows, approvals and agents;
- public-safe data access summaries and detail notes.

The schema is included in `docs/openapi.json` and checked by CI.

## Console Behavior

The `/ontology` page loads the demo endpoint from
`NEXT_PUBLIC_AXIS_API_BASE_URL`. If the API is unavailable, it falls back to the
local synthetic ontology seed.

Entity links open `/ontology/[nodeId]`, which loads the entity detail endpoint
and falls back to a local detail builder when the API is unavailable.

The current graph and detail pages are read-only. Future Platform work should
add tenant-scoped TypeDB-backed graph queries, persisted relationship metadata
and permission-aware query enforcement.

## Verification

Covered by:

- API tests for graph integrity and endpoint exposure;
- API tests for entity detail, 404 handling and endpoint exposure;
- generated OpenAPI drift check;
- web unit tests for fallback graph integrity and local detail building;
- Playwright smoke tests for desktop and mobile rendering, including entity
  navigation.
