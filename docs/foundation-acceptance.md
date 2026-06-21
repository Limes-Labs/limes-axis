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
```

Coverage:

- FastAPI app metadata and health endpoint.
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

## Web Checks

Verified locally:

```bash
pnpm --filter @limes-axis/web lint
pnpm --filter @limes-axis/web typecheck
pnpm --filter @limes-axis/web test
pnpm --filter @limes-axis/web build
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

## CI Gate

GitHub Actions runs:

- web lint, typecheck, tests and build;
- API dependency sync, lint and tests;
- worker dependency sync, lint and tests.
