# Python SDK Quickstart

This example uses `limes-axis-sdk` to read the governed manufacturing
reference surface and record an idempotent action run against a locally
running Axis API.

It is public-safe: it only touches the synthetic demo tenant
(`tenant_demo_manufacturing`) and performs a dry-run action request that is
gated behind an approval.

## Prerequisites

Start the local stack and API (see the repository README):

```bash
make dev-stack-up
cd services/api && uv run alembic upgrade head
make demo-api
```

## Run

```bash
cd examples/sdk-python-quickstart
uv run --project ../../packages/sdk-python python quickstart.py
```

Optional environment variables:

- `AXIS_BASE_URL` (default `http://127.0.0.1:8000`)
- `AXIS_BEARER_TOKEN` (default unset; required when the API enforces OIDC)
- `AXIS_TENANT_ID` (default `tenant_demo_manufacturing`)

## What It Shows

- health/readiness checks;
- the approval inbox and a typed approval item;
- the action catalog and an idempotency-keyed action run request;
- persisted workflow runs with timeline evidence;
- audit event queries;
- typed error handling (`PolicyViolationError` on an idempotency conflict).

See [`docs/sdk-python.md`](../../docs/sdk-python.md) for the full SDK guide.
