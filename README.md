# Limes Axis

The sovereign AI control plane for European operations.

Limes Axis is an open-source, self-hostable foundation for governing enterprise
data, workflows, humans and AI agents in one operational control plane.

It is not another chatbot, dashboard or single-purpose agent framework. Axis is
designed to sit above existing systems of record, model the organization as an
operational ontology, and let humans and AI agents act through typed,
permissioned, auditable workflows.

## What Axis Is For

European organizations increasingly want AI inside real operations, but not at
the cost of losing control over data, approvals, audit trails or deployment.
Axis is built around a few core ideas:

- integrate above existing ERP, CRM, MES, databases, documents and internal tools;
- model operational context through an ontology;
- give humans, services and AI agents explicit identities and permissions;
- route agent actions through typed schemas, policy checks and approval gates;
- keep every important read, proposal, approval and action auditable;
- support SaaS, dedicated, private-cloud and on-prem deployment paths;
- avoid required managed-service dependencies for the open-source core.

The first reference demo will use a realistic operations cockpit for
manufacturing, but Axis is designed as a platform for European operations more
generally.

## Current Status

Axis is in the Platform Foundation track. The repository now includes the
monorepo structure, self-hosted local runtime, FastAPI foundation, Postgres
migration baseline, TypeDB ontology boundary, workflow runtime port, Temporal
adapter, typed action registry, model egress guard, permission primitives and a
Next.js governance console shell. Foundation hardening adds API readiness,
generated OpenAPI checks, opt-in runtime integration tests, API status in the
console and Playwright smoke tests in CI. The first Platform slice adds a
synthetic manufacturing overview seed and API-backed governance console
overview. The ontology slice adds a read-only manufacturing graph for typed
nodes, source-system links, relationship mapping and permission scopes. The
approval slice adds a synthetic approval inbox with evidence, risk review,
decision options and local audit preview. The workflow slice adds a read-only
runtime console for workflow state, pending signals and history preview. The
audit slice adds a read-only explorer for synthetic ledger events, filters and
redacted payload previews.

## Architecture Defaults

- Frontend: Next.js + React.
- Backend/API: Python + FastAPI.
- API style: REST/OpenAPI first.
- Data: Postgres + TypeDB.
- Workflow runtime: Temporal OSS self-hosted behind an Axis adapter.
- Identity: OIDC-first, with Keycloak/self-hosted support.
- Tenancy: multi-tenant SaaS, single-tenant managed and on-prem/private cloud.
- Agents: L0-L4 autonomy model and typed action registry.
- Permissions: RBAC + ABAC + relationship-aware checks.
- Audit: append-only audit ledger.
- Observability: OpenTelemetry-first.
- Deployment: Docker Compose for local/dev, Kubernetes/Helm for production.
- Tooling direction: `uv`, `pnpm`, Docker.

## Local Runtime

The development runtime is self-hosted through Docker Compose:

```bash
cp .env.example .env
make dev-stack-up
```

Services:

- Postgres: `localhost:5432`
- TypeDB gRPC: `localhost:1729`
- TypeDB HTTP: `http://localhost:8001`
- Temporal: `localhost:7233`
- Temporal UI: `http://localhost:8088`
- MinIO API: `http://localhost:9000`
- MinIO Console: `http://localhost:9001`
- Keycloak: `http://localhost:8080`

Stop the stack with:

```bash
make dev-stack-down
```

## Development

Install dependencies:

```bash
make install
```

Run checks:

```bash
make lint
make test
make build-web
make openapi-check
```

Run opt-in integration checks against the local Docker runtime:

```bash
make dev-stack-up
make test-integration
```

Run web smoke tests against the production build:

```bash
pnpm --filter @limes-axis/web build
pnpm --filter @limes-axis/web exec playwright install chromium
pnpm --filter @limes-axis/web test:e2e
```

Run the web console locally:

```bash
pnpm --filter @limes-axis/web dev --hostname 127.0.0.1 --port 3000
```

Apply the first Postgres migration:

```bash
cd services/api
uv run alembic upgrade head
```

## Repository Strategy

Axis starts as one public repository to keep the core coherent. It is still
designed with extractable boundaries from day one.

Cloud, Enterprise, connectors, SDKs, deployment and docs may become separate
repositories when they develop different release cadences, ownership, security
requirements or customer-specific concerns.

## Roadmap

See [`plan.md`](./plan.md) for the public milestone roadmap.

The roadmap is organized as:

- Foundation: trustworthy self-hostable platform base.
- Platform: usable governance control plane with reference demo.
- Enterprise: deployment, security, support and compliance hardening.

Architecture and acceptance notes:

- [`docs/architecture.md`](./docs/architecture.md)
- [`docs/foundation-acceptance.md`](./docs/foundation-acceptance.md)
- [`docs/platform-overview.md`](./docs/platform-overview.md)
- [`docs/platform-ontology.md`](./docs/platform-ontology.md)
- [`docs/platform-workflows.md`](./docs/platform-workflows.md)
- [`docs/platform-approvals.md`](./docs/platform-approvals.md)
- [`docs/platform-audit.md`](./docs/platform-audit.md)

Reference examples:

- [`examples/manufacturing-plant`](./examples/manufacturing-plant)

## Contributing

Axis is early. Contributions are welcome once contribution and CLA processes are
in place.

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) and [`CLA.md`](./CLA.md).

## License

Apache-2.0. See [`LICENSE`](./LICENSE).
