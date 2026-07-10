# Manufacturing Plant Walkthrough

This example is a complete local walkthrough of the Limes Axis reference
scenario: the Plant Operations Cockpit for the fictional "Ravenna Works" plant
under the synthetic demo tenant `tenant_demo_manufacturing`.

Everything here runs against the self-hosted Docker Compose stack. The seed is
intentionally small and public-safe: fictional plant context, role-based owners
and system IDs. It must not include customer data, personal names, private
contacts, pricing, contracts or secrets, and nothing in this walkthrough sends
data outside your machine unless you explicitly enable the flag-gated steps
described below.

## Prerequisites

- Docker with the Compose plugin (the local stack runs Postgres, TypeDB,
  Temporal, MinIO and Keycloak).
- `uv` (Python 3.12+) and `pnpm` (Node 22+), as used by `make install`.
- Roughly 4 GB of free memory for the compose services.

From the repository root:

```bash
make install
```

## 1. Start the stack and migrate

```bash
make demo-stack-up
make demo-db-upgrade
```

`demo-stack-up` starts the compose services from
`infra/docker/docker-compose.yml`. `demo-db-upgrade` applies the Alembic
migrations, including the tenant-scoped bootstrap reference records that every
console page reads (overview, ontology, workflows, approvals, audit, agents,
actions, model routing, connectors).

## 2. Run the API and the console

In one terminal:

```bash
make demo-api
```

The API serves `http://127.0.0.1:8000` (OpenAPI at `/docs`). In a second
terminal:

```bash
make demo-web
```

The governance console serves `http://127.0.0.1:3000`. For the optional local
Keycloak browser-SSO profile use `make demo-api-sso` instead of `make demo-api`
(see `docs/demo-readiness.md`).

Verify the environment:

```bash
make demo-verify      # static checks: openapi-check, demo-check, Helm profile render
make demo-check-live  # live checks against the running API and console
```

## 3. Tour the console

Each page is API-required: it renders persisted tenant state or an explicit
API error, never browser-local fallback records. What you see:

- `/` (Overview): the operations cockpit composed from the persisted
  manufacturing operations snapshot — domain rollups, generated daily briefs
  and risk scenarios, active workflows, pending approvals and recent audit
  evidence, plus the demo readiness report.
- `/ontology`: the typed manufacturing graph — production orders, machines,
  material lots, suppliers, risks, workflows — with relationship mapping,
  permission scopes and entity detail pages.
- `/workflows`: workflow console with runtime adapter metadata, pending
  signals and persisted run timelines.
- `/approvals`: the approval inbox with evidence, risk review and decision
  options; decisions persist through the API with append-only audit events.
- `/audit`: the audit explorer over persisted append-only `audit_events`,
  with filters, redacted payload previews and export bundles carrying
  checksum/hash-chain integrity proofs.
- `/agents`: the governed agent registry (L1/L2 autonomy boundaries, required
  permissions, model egress posture, proposals and approval references).
- `/connectors`: connector manifests, tenant configuration, credential handle
  and lease posture, run/checkpoint evidence and promotion policy governance.
- `/model-routing`: route telemetry, provider boundaries, blocked-egress
  visibility and token/cost estimates.
- `/policies`: the platform policy registry with typed conditions, revision
  history and a dry-run evaluation panel.
- `/simulation`: read-only replay artifacts and policy-set diff previews
  derived from workflow history and audit events.
- `/tenants`: the platform operator console for tenant lifecycle and quotas.
- `/settings`: identity, deployment and support readiness contracts read live
  from the API.

The exact records shown depend on the migrations you applied and any state you
create during the walkthrough, so treat the descriptions above as what each
page is for rather than a pixel-exact script.

## 4. Optional: model routing with a local Ollama endpoint

Model execution is off by default (`AXIS_MODEL_ROUTING_EXECUTION_ENABLED`
defaults to `false`; invocations record an honest deferred status instead of
fabricating output). To route against a local Ollama endpoint, restart the API
with the flag enabled:

```bash
cd services/api
AXIS_MODEL_ROUTING_EXECUTION_ENABLED=true \
  uv run uvicorn axis_api.main:create_app --factory --host 127.0.0.1 --port 8000
```

Ollama exposes an OpenAI-compatible API at `http://127.0.0.1:11434/v1`
(install from <https://ollama.com>, then e.g. `ollama pull llama3.2`). Register
it as a self-hosted endpoint (scope `platform:model:endpoint:admin`). Either
`base_url` shape works — `http://127.0.0.1:11434` or
`http://127.0.0.1:11434/v1` — because Axis appends `/v1/chat/completions` and
never doubles a trailing `/v1`:

```bash
curl -sS -X POST http://127.0.0.1:8000/platform/models/endpoints \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "tenant_demo_manufacturing",
    "endpoint_id": "ollama_local",
    "display_name": "Local Ollama",
    "provider_type": "openai_compatible",
    "hosting_boundary": "self_hosted",
    "base_url": "http://127.0.0.1:11434/v1",
    "default_model": "llama3.2",
    "task_types": ["agent_proposal", "summarize"],
    "created_by": "platform-admin",
    "actor_scopes": ["platform:model:endpoint:admin"]
  }'
```

Then request a governed invocation (scope `models:invoke`) through
`POST /platform/models/invocations`; see `/docs` for the request contract.
Every invocation persists a metadata-only record (token counts, latency,
status, audit evidence) — prompt text is excerpted only up to
`AXIS_MODEL_INVOCATION_PROMPT_EXCERPT_CHARS`, which defaults to `0`.

If you mis-register an endpoint (for example a wrong port or model id),
disable it with the governed status route instead of leaving it to capture
routing:

```bash
curl -sS -X POST http://127.0.0.1:8000/platform/models/endpoints/ollama_local/status \
  -H 'Content-Type: application/json' \
  -d '{
    "tenant_id": "tenant_demo_manufacturing",
    "target_status": "disabled",
    "reason": "Mis-registered during walkthrough",
    "updated_by": "platform-admin",
    "actor_scopes": ["platform:model:endpoint:admin"]
  }'
```

Disabled endpoints are skipped by the deterministic router, so re-registering
a corrected endpoint id takes over cleanly.

Because the endpoint is registered with `hosting_boundary: self_hosted`, no
external egress is involved; `AXIS_EXTERNAL_MODEL_EGRESS_ENABLED` stays
`false` and any non-self-hosted routing remains blocked.

## 5. Optional: a governed agent dry-run

Agent run execution is also off by default
(`AXIS_AGENT_RUN_EXECUTION_ENABLED=false`; runs record an honest deferred
status). Restart the API with both flags:

```bash
cd services/api
AXIS_MODEL_ROUTING_EXECUTION_ENABLED=true \
AXIS_AGENT_RUN_EXECUTION_ENABLED=true \
  uv run uvicorn axis_api.main:create_app --factory --host 127.0.0.1 --port 8000
```

Start a dry-run of the L1 daily-brief agent (scopes `agents:run:execute`,
`models:invoke` plus the agent's registry permissions):

```bash
curl -sS -X POST \
  http://127.0.0.1:8000/demo/manufacturing/agents/agent_daily_brief/runs \
  -H 'Content-Type: application/json' \
  -d '{
    "actor_id": "plant-operations-owner",
    "actor_scopes": [
      "agents:run:execute", "models:invoke",
      "agents:read", "audit:read", "workflows:read"
    ],
    "idempotency_key": "walkthrough-dry-run-001",
    "mode": "dry_run"
  }'
```

The response is an `AgentRunResult` (the same shape published as
`packages/schemas/agent-run.schema.json`): a persisted step timeline
(`context_read` → `model_invocation` → `proposal`), permission and policy
decisions, model invocation references and audit evidence. In `dry_run` mode
the proposal is recorded but no action run is created; in `propose` mode an L2
agent's valid proposal creates an approval-gated action run — it still never
executes side effects directly. If the model output cannot be parsed into a
registered, permitted action proposal, the run fails closed rather than
fabricating a proposal. Inspect runs with
`GET /demo/manufacturing/agents/agent_daily_brief/runs`.

## 6. SDK step

The Python SDK quickstart reuses this same stack and tenant:

```bash
cd examples/sdk-python-quickstart
uv run --project ../../packages/sdk-python python quickstart.py
```

It walks health checks, the approval inbox, an idempotency-keyed action run,
persisted workflow timelines, audit queries and typed error handling. See
[`examples/sdk-python-quickstart`](../sdk-python-quickstart) and
[`docs/sdk-python.md`](../../docs/sdk-python.md).

## 7. Teardown

```bash
make demo-stack-down
```

This stops the compose services. Volumes persist between runs; see
[`docs/backup-restore.md`](../../docs/backup-restore.md) for the demo
backup/restore runbook (`make demo-backup-local`, `make demo-restore-local`).

## Boundaries

- This is a demo walkthrough, not a production deployment: see
  `docs/demo-readiness.md`, `docs/deployment.md` and `docs/threat-model.md`.
- All execution paths beyond reads are flag-gated and off by default:
  model routing (`AXIS_MODEL_ROUTING_EXECUTION_ENABLED`), agent runs
  (`AXIS_AGENT_RUN_EXECUTION_ENABLED`), external model egress
  (`AXIS_EXTERNAL_MODEL_EGRESS_ENABLED`), connector sync and live sync
  (`AXIS_CONNECTOR_SYNC_EXECUTION_ENABLED`,
  `AXIS_CONNECTOR_LIVE_SYNC_EXECUTION_ENABLED`) and their scheduled variant
  (`AXIS_CONNECTOR_SCHEDULED_LIVE_SYNC_ENABLED`).
- Never enter real credentials, DSNs or customer data into the demo
  environment; connector surfaces reject raw secret material by design.
