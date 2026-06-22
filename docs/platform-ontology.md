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

In standalone demo mode, the entity detail endpoint remains readable without a
token. When a bearer token is present, or when OIDC auth is required by
configuration, the endpoint evaluates the token-derived scopes against the
relationship scopes connected to the requested node. Missing relationship scope
coverage returns 403 before the graph detail is returned.

The schema is included in `docs/openapi.json` and checked by CI.

## Console Behavior

The `/ontology` page loads the demo endpoint from
`NEXT_PUBLIC_AXIS_API_BASE_URL`. If the API is unavailable, it falls back to the
local synthetic ontology seed.

Entity links open `/ontology/[nodeId]`, which loads the entity detail endpoint
and falls back to a local detail builder when the API is unavailable.
When an OIDC session is attached in the console toolbar, entity detail fetches
include the bearer token so relationship-scope denials can be exercised from
the console.

The current graph and detail pages are read-only. Future Platform work should
add tenant-scoped TypeDB-backed graph queries, persisted relationship metadata
and broader graph authorization beyond the current demo relationship-scope
checks.

Connector-driven ontology mutation is handled outside the read-only explorer.
The connector promotion endpoint can promote an approved proposal through the
Axis ontology mutation adapter, guarded by manual import approval evidence,
workflow signal evidence, `connectors:ontology:promote`, idempotency and
append-only audit writes. Connector promotion policy drafts can now document
the required promotion scopes and import/workflow states before full policy
enforcement. The TypeDB schema includes manufacturing asset attributes needed by
the promotion path: `axis_id`, `display_name`, `asset_type`, `domain`,
`source_system_ref` and `risk_level`.

## Verification

Covered by:

- API tests for graph integrity and endpoint exposure;
- API tests for entity detail, 404 handling, relationship-scope enforcement and
  endpoint exposure;
- web unit tests for OIDC session token parsing and authorization headers;
- generated OpenAPI drift check;
- web unit tests for fallback graph integrity and local detail building;
- Playwright smoke tests for desktop and mobile rendering, including entity
  navigation.
