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
```

It includes:

- Ravenna Works as the fictional plant;
- supplier delay, quality drift and maintenance risk signals;
- active workflow summaries;
- pending approval summaries;
- governed L1/L2 agents;
- recent audit evidence.

## Next Expansion

The reference demo should grow into an end-to-end Platform scenario:

- realistic orders, machines, materials, suppliers, quality and maintenance
  entities;
- TypeDB ontology relationships;
- Postgres-backed workflow and audit state;
- approval inbox actions;
- replay and simulation artifacts.
