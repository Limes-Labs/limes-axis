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

## Next Expansion

The reference demo should grow into an end-to-end Platform scenario:

- realistic orders, machines, materials, suppliers, quality and maintenance
  entities;
- TypeDB ontology relationships;
- Postgres-backed workflow and audit state;
- Temporal signal execution through the Axis workflow runtime adapter;
- persisted approval inbox actions and workflow signals;
- replay and simulation artifacts.
