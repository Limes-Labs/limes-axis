# Platform Ontology Explorer

The first ontology explorer slice maps the manufacturing API reference into a
read-only operational graph.

## Demo Scope

The graph is public-safe. It uses demo IDs, roles and fictional plant context
rather than customer data or personal names. The browser does not carry a local
ontology graph. The API reads the active `demo_reference_records` row for
`surface=ontology` and `reference_id=manufacturing-ontology`; missing or invalid
persisted payloads return explicit 404/422 errors instead of falling back to an
in-route seed.
The API module no longer defines ontology graph or entity-detail runtime seed
factories; contract tests validate the Alembic bootstrap payload directly.

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
- permission notes;
- graph query metadata with adapter, source, query mode, actor, tenant,
  permission decision, returned counts, denied relationship count and generated
  TypeQL.

The entity detail endpoint returns:

- selected node metadata;
- inbound and outbound relationship summaries;
- required permission scopes;
- evidence references;
- related workflows, approvals and agents;
- public-safe data access summaries and detail notes.

In standalone demo mode, graph and entity detail reads remain readable without a
token. Graph and detail reads derive from the same persisted, tenant-scoped
reference graph. Graph reads pass through the Axis ontology query runtime. The
default runtime serves the persisted public reference graph through
`axis-deferred-ontology-query-adapter`.
Entity detail responses are derived by a builder that receives the persisted
ontology graph; it does not load a local demo seed.
When a bearer token is present, or when OIDC auth is required by configuration,
the graph endpoint derives actor, tenant and scopes from the principal, rejects
tenant mismatch, filters relationships by token-derived relationship scopes and
returns query metadata that records the filtering decision. `AXIS_ONTOLOGY_QUERIES_ENABLED=true`
switches the boundary to the TypeDB query runtime while keeping response
mapping and permission filtering behind the same Axis adapter contract.

Entity detail reads evaluate the token-derived scopes against the relationship
scopes connected to the requested node. Missing relationship scope coverage
returns 403 before the graph detail is returned.

The schema is included in `docs/openapi.json` and checked by CI.

## Console Behavior

The `/ontology` page loads the demo endpoint from
`NEXT_PUBLIC_AXIS_API_BASE_URL`. If the API is unavailable, it shows an
API-required state and does not render local graph records.

Entity links open `/ontology/[nodeId]`, which loads the entity detail endpoint
and shows an API-required state when the API is unavailable.
When an OIDC session is attached in the console toolbar, entity detail fetches
include the bearer token so relationship-scope denials can be exercised from
the console.

The current graph and detail pages are read-only. The ontology page now exposes
the active graph query adapter, mode, source, returned counts, denied
relationship count and permission decision. Future Platform work should map
live TypeDB query answers into the full response shape, promote relationship
metadata from the reference graph into production graph storage and broaden graph
authorization beyond the current demo relationship-scope checks.

Connector-driven ontology mutation is handled outside the read-only explorer.
The connector promotion endpoint can promote an approved proposal through the
Axis ontology mutation adapter, guarded by manual import approval evidence,
workflow signal evidence, `connectors:ontology:promote`, idempotency and
append-only audit writes. Connector promotion policies can now be attached to a
promotion request; enabled required policies enforce the required scopes, manual
import status, workflow signal status, risk levels and ontology types before the
TypeDB mutation boundary is called. The TypeDB schema includes manufacturing
asset attributes needed by the promotion path: `axis_id`, `display_name`,
`asset_type`, `domain`, `source_system_ref` and `risk_level`.

## Verification

Covered by:

- API tests for graph integrity and endpoint exposure;
- API tests for the persisted ontology reference record, missing-record and
  invalid-payload handling;
- API tests for the ontology query runtime, OIDC principal binding, tenant
  mismatch rejection and relationship-scope filtering;
- API tests for entity detail, 404 handling, relationship-scope enforcement and
  endpoint exposure;
- web unit tests for OIDC session token parsing and authorization headers;
- generated OpenAPI drift check;
- web unit tests for graph helper and detail building contracts with local test
  fixtures only;
- Playwright smoke tests for API-required ontology and entity behavior.
