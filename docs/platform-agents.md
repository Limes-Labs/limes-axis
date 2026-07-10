# Platform Agent Registry

The Platform agent registry slice introduces a public-safe, read-only view of
governed agents in the manufacturing reference scenario.

It is a registry and governance surface first. A separate flag-gated slice
adds governed agent run execution: `POST/GET
/demo/manufacturing/agents/{agent_id}/runs` runs a registry agent in dry-run
or propose mode behind `AXIS_AGENT_RUN_EXECUTION_ENABLED=true` (default
`false`; disabled runs record an honest deferred status). Runs require
`agents:run:execute` and `models:invoke` plus the agent's registry
permissions, persist an append-only step timeline (`context_read`,
`model_invocation`, `proposal`), enforce autonomy ceilings and platform
policies, route model calls through registered model endpoints and turn
parseable proposals into approval-gated action runs. Agents never execute
actions or mutate external systems directly, and runs fail closed on
unparseable or unpermitted model output.

## Current Scope

- `GET /demo/manufacturing/agents` returns a manufacturing agent reference
  registry.
- The endpoint reads the active `demo_reference_records` row for
  `surface=agents` and `reference_id=manufacturing-agent-registry`; missing or
  invalid persisted records return explicit API errors.
- The API module no longer defines an agent registry runtime seed factory; tests
  validate the Alembic bootstrap payload directly.
- The Next.js console renders the registry at `/agents`.
- The UI supports local filters for domain, autonomy level and status.
- Each agent exposes owner role, purpose, policy boundary, model egress posture,
  required permissions, guardrails, connected systems, data access, allowed and
  blocked actions, proposals, workflows, approvals and audit evidence.
- The public reference keeps every demo agent within L1-L2 autonomy.
- External model egress is blocked for every reference agent by default.

## Demo Agents

The reference registry currently includes:

- Daily Brief Agent: L1 operations summary and evidence ranking.
- Supply Risk Agent: L2 supply proposal drafting with owner approval required.
- Quality Risk Agent: L2 quality hold recommendation drafting.
- Maintenance Planner Agent: L2 maintenance reschedule proposal drafting.

The registry connects these agents to the existing manufacturing reference
overview, workflow console, approval inbox and audit explorer.

## Boundaries

This slice remains read-only at the API boundary.

The registry is a bootstrap reference surface, but it is no longer constructed
inside the FastAPI route or the API demo module. Alembic migration
`0024_agent_registry_reference` inserts the public-safe payload, the API
validates it against the
`ManufacturingAgentRegistry` contract and the repository provides the active
tenant-scoped record.

It does not yet include:

- direct production action execution (agent proposals stay approval-gated);
- tenant-scoped agent configuration storage;
- SDK or connector-driven agent registration.

Governed run execution, persisted run/step state, platform policy enforcement
on runs and model token/cost accounting exist behind
`AXIS_AGENT_RUN_EXECUTION_ENABLED` as described above.

Those capabilities remain Platform work and should be implemented behind the
existing typed action registry, workflow runtime adapter, permission primitives,
model router and audit ledger boundaries.

## Acceptance Notes

- The endpoint is covered by API tests and OpenAPI generation.
- The persisted bootstrap payload is covered by a contract test.
- A guard test blocks reintroducing the runtime seed factory in the API module.
- The web console shows an API-required state when agent records are unavailable.
- The web unit tests cover filtering, safe lookup and labels with local test
  fixtures only.
- Playwright smoke tests cover the mobile navigation path and API-required agent
  behavior.
- Public documentation avoids customer data, personal names, contacts, pricing,
  credentials and deployment secrets.
