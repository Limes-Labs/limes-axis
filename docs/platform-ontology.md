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
ontology graph; it does not load a local runtime seed.
When a bearer token is present, or when OIDC auth is required by configuration,
the graph endpoint derives actor, tenant and scopes from the principal, rejects
tenant mismatch, filters relationships by token-derived relationship scopes and
returns query metadata that records the filtering decision. Relationship
filtering runs inside the ontology query adapter boundary and evaluates each
relationship scope through the shared Axis permission module
(`evaluate_permission` with relationship-aware scopes), so the deferred
persisted-reference runtime and the TypeDB read-boundary runtime enforce the
same decision before graph rows leave the boundary.
`AXIS_ONTOLOGY_QUERIES_ENABLED=true`
switches the boundary to the TypeDB query runtime while keeping response mapping
and permission filtering behind the same Axis adapter contract. The TypeDB
client normalizes read answers at the boundary: concept documents remain
structured dictionaries, concept rows are converted to public values, and
structured node/relationship documents can be mapped into the public
manufacturing ontology response before relationship-scope filtering runs.

Entity detail reads are authorized at the ontology read service boundary
(`ontology_authorization.py`), not in the route handler: the boundary binds the
OIDC principal's tenant, actor and scopes, loads the persisted detail and
evaluates the token-derived scopes against the relationship scopes connected to
the requested node through the shared permission module. Missing relationship
scope coverage or a tenant mismatch raises a typed permission denial that the
route maps to the standard `PERMISSION_DENIED` error body before the detail is
returned. When OIDC auth is required by configuration, unauthenticated graph
and entity reads return `AUTH_REQUIRED`.

Denied ontology reads append persisted audit evidence. Tenant mismatch on graph
reads appends `ontology.graph_read.denied`; tenant mismatch or missing
relationship scopes on entity detail reads append
`ontology.entity_read.denied`. Denial events are written to the authenticated
actor's own tenant scope and carry the requested tenant, resource, node id,
required permissions and permission decision without token contents or other
sensitive payload material.

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
relationship count, permission decision and relationship metadata. Each
relationship carries owner role, source adapter, confidence, evidence refs,
validity window, last verification time and verification status. Future Platform
work should expand TypeDB query coverage beyond the current structured
read-boundary mapping, broaden live graph promotion coverage and broaden graph
authorization beyond the current demo relationship-scope checks.

Connector-driven ontology mutation is handled outside the read-only explorer.
The connector promotion endpoint can promote an approved proposal through the
Axis ontology mutation adapter, guarded by manual import approval evidence,
workflow signal evidence, a tenant-scoped connector manifest in
`active_preview`, `connectors:ontology:promote`, idempotency and append-only
audit writes. Connector promotion policies can now be attached to a promotion
request; enabled required policies enforce the required scopes, manual import
status, workflow signal status, risk levels and ontology types before the TypeDB
mutation boundary is called. The TypeDB schema includes manufacturing
asset attributes needed by the promotion path: `axis_id`, `display_name`,
`asset_type`, `domain`, `source_system_ref` and `risk_level`. The TypeDB schema
also includes relationship metadata primitives for relationship id, permission
scope, owner role, source adapter, confidence, evidence refs, validity and
verification status.

## Verification

Covered by:

- API tests for graph integrity and endpoint exposure;
- API tests for the persisted ontology reference record, missing-record and
  invalid-payload handling;
- API tests for the ontology query runtime, OIDC principal binding, tenant
  mismatch rejection and relationship-scope filtering;
- API tests for TypeDB read-answer normalization and structured graph response
  mapping;
- API tests for ontology relationship ownership, evidence, confidence,
  validity and verification metadata;
- API tests for TypeDB relationship metadata primitives;
- API tests for entity detail, 404 handling, relationship-scope enforcement and
  endpoint exposure;
- API and service-boundary tests for ontology read authorization: OIDC
  requirement, cross-tenant denial, empty scopes, malformed permission payloads
  and denial audit evidence;
- web unit tests for OIDC session token parsing and authorization headers;
- generated OpenAPI drift check;
- web unit tests for graph helper and detail building contracts with local test
  fixtures only;
- Playwright smoke tests for API-required ontology and entity behavior.
