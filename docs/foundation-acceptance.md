# Platform Foundation Acceptance

This document records the acceptance checks for the Platform Foundation track.

## Local Runtime

Verified locally on 2026-06-21:

```bash
cp .env.example .env
make dev-stack-up
```

Services started:

- Postgres on `localhost:5432`
- TypeDB gRPC on `localhost:1729`
- TypeDB HTTP on `localhost:8001`
- Temporal on `localhost:7233`
- Temporal UI on `localhost:8088`
- MinIO on `localhost:9000` and `localhost:9001`
- Keycloak on `localhost:8080`

## API And Worker Checks

Verified locally:

```bash
cd services/api && uv run ruff check . && uv run pytest
cd services/worker && uv run ruff check . && uv run pytest
make openapi-check
```

Coverage:

- FastAPI app metadata and health endpoint.
- Readiness endpoint covering Postgres, TypeDB, Temporal configuration and
  external model egress policy.
- CORS preflight behavior for the configured public base URL.
- Generated OpenAPI schema committed at `docs/openapi.json`.
- Public error envelope.
- Tenant and audit primitives.
- Action registry approval rules.
- Permission evaluator.
- Model router egress block.
- TypeDB ontology primitive checks.
- Worker runtime port contract.

## Database Checks

Verified locally against the Docker Postgres runtime:

```bash
cd services/api && uv run alembic upgrade head
make test-integration
```

The first migration creates tenants, actors and audit events.

## TypeDB Checks

Verified locally against the Docker TypeDB runtime with a temporary database:

```bash
cd services/api
AXIS_TYPEDB_DATABASE=axis_foundation_check uv run python - <<'PY'
from pathlib import Path
from axis_api.ontology.client import OntologyClient, OntologyClientConfig

client = OntologyClient(
    OntologyClientConfig(
        address="localhost:1729",
        username="admin",
        password="password",
        database="axis_foundation_check",
    )
)
try:
    client.load_schema(Path("src/axis_api/ontology/schema.tql").read_text())
finally:
    client.close()
PY
```

The schema uses TypeDB 3.x syntax and `axis_` labels to avoid TypeQL keyword
collisions.

The opt-in integration suite also verifies that a temporary TypeDB database can
be created, loaded with the schema, inspected and dropped.

## Workflow Integration Checks

Verified locally against the Docker Temporal runtime:

```bash
make test-integration
```

Coverage:

- Temporal self-hosted service connectivity on `localhost:7233`.
- Worker registration through the Axis workflow runtime adapter.
- Approval workflow start, approval signal and completion result.

## Web Checks

Verified locally:

```bash
pnpm --filter @limes-axis/web lint
pnpm --filter @limes-axis/web typecheck
pnpm --filter @limes-axis/web test
pnpm --filter @limes-axis/web build
pnpm --filter @limes-axis/web test:e2e
```

Also verified with a local Next.js server and browser automation:

- `/`
- `/ontology`
- `/workflows`
- `/agents`
- `/approvals`
- `/audit`

Desktop and mobile renders were checked for non-empty content and no document
level horizontal overflow.

The console overview now reads `/health` and `/ready` and shows a public-safe
API availability summary. The fallback state was verified with the API stopped.

The Playwright smoke suite covers desktop and mobile rendering, overview API
status fallback, main navigation and autonomy level visibility.

## CI Gate

GitHub Actions runs:

- web lint, typecheck, unit tests, build and Playwright smoke tests;
- API dependency sync, lint and tests;
- OpenAPI schema drift check;
- worker dependency sync, lint and tests.
