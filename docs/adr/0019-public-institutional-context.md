# ADR 0019: Optional public institutional context

- Status: Proposed in isolated integration
- Date: 2026-10-04

## Context

Institutional identity/provenance can be useful to an authenticated Axis reader without
importing it into the tenant ontology. Connector egress policy and leases govern
source ingestion. Platform policy scopes govern actions, agents and model invocations;
relabeling this read as one of those operations would claim enforcement it does not have.

## Decision

`create_app(public_context=PublicContextConfig(...))` explicitly registers the read-only
`GET /institutional-context/entities/{gov_entity_id}`. Without that argument there is
no route, no GovCore dependency, no network request and no new default permission.
The MIT SDK wheel is an optional installation; this checkout retains the reviewed
wheel and permission text under `tools/govcore`, without changing API dependency locks.

The existing OIDC principal resolver is mandatory even in anonymous demo mode. The
existing `authorize_principal_scopes` checks the dedicated
`institutional:context:read` scope and binds the tenant. A separate operator-owned
capability policy requires an enabled boolean, immutable local tenant/origin allowlists
and a fixed HTTPS origin (HTTP permitted only for loopback acceptance).

The route checks current policy, resolves the principal again and reads exact persisted
`active` tenant state before and after HTTP. Each tenant transaction closes before
network I/O. A bearer request discards its request-scoped principal cache before these
checks; secure cookies rehydrate current persisted session state/scopes. Bearer scope
or revocation updates depend on the existing verifier/IdP contract: this capability does
not introduce online token introspection. The returned public snapshot cannot retain
an authorization grant, and revocation immediately after the final check is the usual
read-response concurrency boundary rather than permission for a later action.

GovCore receives one canonical public entity ID in a GET path. Tenant/actor IDs, JWTs,
cookies, case records, model inputs and private graph data never enter its client.
The reviewed SDK bounds time/body size, rejects redirects, proxy inheritance,
credentialed URLs, malformed contracts, wrong identity and inactive remote entities.
Responses use `Cache-Control: no-store`. There is no routing cache or local fallback.

This capability guard is **separate from general Axis connector egress**. It neither
registers a connector nor evaluates connector lease/evidence policies. Infrastructure
allowlisting/TLS and deployment approval remain necessary before enabling it in a
real installation. It does not add ontology ingestion/mutation, model invocation,
autonomous tools, workflow execution, provider credentials or action authority.

## Acceptance and limits

Focused tests run the actual Axis identity dependency, scope evaluator and repository
against isolated synthetic tenants. They assert denied reads cause no GovCore request,
no DB connection is held during transport, and concurrent local revocations block the
response. A separate explicit script calls the local GovCore pilot service through
HTTP, using synthetic host identity; it is not live IdP or production egress evidence.
Full deployment, Postgres Axis migration/concurrency, browser UX, external IdP,
infrastructure allowlists and production installation remain separate NOT RUN gates.
