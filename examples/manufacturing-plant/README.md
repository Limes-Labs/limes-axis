# Manufacturing Plant Reference Demo

This example documents the first synthetic reference scenario for Limes Axis:
the Plant Operations Cockpit.

The seed is intentionally small and public-safe. It represents a fictional demo
tenant, fictional plant context, role-based owners and system IDs. It must not
include customer data, personal names, private contacts, pricing, contracts or
secrets.

## Current Seed

The current seed is served by:

```text
GET /demo/manufacturing/overview
GET /demo/manufacturing/ontology
GET /demo/manufacturing/workflows
GET /demo/manufacturing/approvals
GET /demo/manufacturing/audit
GET /demo/manufacturing/agents
GET /demo/manufacturing/actions
```

It includes:

- Ravenna Works as the fictional plant;
- supplier delay, quality drift and maintenance risk signals;
- active workflow summaries;
- pending approval summaries;
- governed L1/L2 agents;
- recent audit evidence;
- read-only ontology nodes and relationships for source systems, permission
  scopes, risks, workflows, approvals and agents.
- read-only workflow runs with runtime adapter metadata, pending signals,
  controls and timeline preview.
- approval inbox proposals with evidence, data accessed, risk review,
  alternatives, model policy and audit event preview.
- read-only audit explorer events with tenant, event type and scope filters,
  evidence references and redacted payload previews.
- read-only agent registry entries with autonomy boundaries, required
  permissions, model egress posture, action proposals, workflow links and
  approval references.
- read-only action registry entries with typed input/output schemas, risk
  levels, approval modes, permissions, guardrails, workflow bindings and dry-run
  payload previews.

## Next Expansion

The reference demo should grow into an end-to-end Platform scenario:

- realistic orders, machines, materials, suppliers, quality and maintenance
  entities;
- TypeDB ontology relationships;
- Postgres-backed workflow and audit state;
- Temporal signal execution through the Axis workflow runtime adapter;
- persisted approval inbox actions and workflow signals;
- persisted append-only audit storage, export and retention controls;
- production action registry execution, persisted agent state and model cost
  observability;
- persisted action state, idempotency storage and workflow signal execution from
  typed action payloads;
- replay and simulation artifacts.
