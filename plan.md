# Limes Axis Public Plan

Last updated: 2026-06-21

## Summary

Limes Axis is the sovereign AI control plane for European operations.

It starts as an open-source core that can run locally or in controlled
infrastructure, then expands into managed cloud, dedicated enterprise and
on-prem deployment paths.

Axis is designed to integrate first and replace gradually: existing systems stay
in place while Axis becomes the governed layer where data, workflows, people,
permissions and AI agents operate together.

## Product Principles

- Sovereignty must be practical: the open core must not require managed services.
- AI agents must be governed, permissioned, observable and auditable.
- Human approval remains central for risky actions.
- Operational ontology is the core context layer.
- Workflow execution must be durable and inspectable.
- Public open-source core and commercial operations should reinforce each other.
- The initial repository is unified, but future extraction into modules/repos is
  expected when parts grow large enough.

## Public Architecture Direction

Axis will use:

- Python + TypeScript as the two-language rule.
- Next.js + React for the governance console.
- FastAPI for the core API.
- REST/OpenAPI for public and internal contracts.
- Postgres for operational and transactional data.
- TypeDB for operational ontology and relationship-aware reasoning.
- Temporal OSS as the initial self-hosted workflow runtime behind an adapter.
- OIDC-first identity, with self-hosted Keycloak support.
- RBAC, ABAC and relationship-aware permissions.
- Append-only audit ledger.
- Provider-agnostic model routing with no external data egress by default.
- Docker Compose for local development and Kubernetes/Helm for production paths.

## Milestone Roadmap

### Foundation

- [x] Create the initial monorepo structure.
- [x] Add Python/FastAPI service foundation.
- [x] Add Next.js governance console foundation.
- [x] Add local Docker Compose runtime.
- [x] Add Postgres, TypeDB and Temporal local services.
- [x] Define tenant, actor, audit, action and workflow schemas.
- [x] Define the operational ontology primitives.
- [x] Define the Workflow Runtime Port and Temporal adapter.
- [x] Define the typed action registry.
- [x] Define the L0-L4 agent autonomy model.
- [x] Add OIDC/Keycloak identity boundary.
- [x] Add initial test, lint and CI commands.
- [x] Add repository issue, PR and security policy templates.
- [x] Generate and check the OpenAPI contract.
- [x] Add API readiness checks and console API status.
- [x] Add opt-in Postgres, TypeDB and Temporal integration tests.
- [x] Add Playwright smoke tests to the web CI gate.

Foundation acceptance is tracked in
[`docs/foundation-acceptance.md`](./docs/foundation-acceptance.md).

### Platform

- [x] Build the governance console overview.
- [x] Build the ontology explorer.
- [x] Build the workflow console.
- [x] Build the agent registry.
- [x] Build the action registry UI.
- [x] Build the approval inbox.
- [x] Build the audit explorer.
- [ ] Build the model routing and cost observability layer.
- [ ] Build the connector framework.
- [ ] Build the manufacturing operations reference demo.
- [ ] Build replay and simulation foundations.

The governance console overview is backed by the first public-safe synthetic
manufacturing seed. The full manufacturing reference demo remains open until it
has ontology relationships, approval actions, workflow execution and replay.

The ontology explorer is currently read-only and backed by the synthetic
manufacturing graph. TypeDB-backed entity detail pages and permission-aware graph
queries remain Platform work.

The workflow console is currently read-only and backed by the synthetic
manufacturing workflow seed. Persisted workflow state, runtime signal execution,
tenant-scoped history views and deterministic replay remain Platform work.

The approval inbox is currently read-only at the API boundary and uses local
browser state for decision previews. Tenant-scoped persistence, workflow signals,
permission enforcement and append-only audit writes remain Platform work.

The audit explorer is currently read-only and backed by the synthetic
manufacturing audit seed. Persisted append-only storage, export, retention policy
enforcement, tenant-scoped query permissions and replay remain Platform work.

The agent registry is currently read-only and backed by the synthetic
manufacturing agent seed. Production action execution, persisted agent state,
tenant-scoped agent configuration, runtime policy enforcement and model cost
observability remain Platform work.

The action registry UI is currently read-only and backed by the synthetic
manufacturing action seed. Persisted action state, live runtime execution,
workflow signals, idempotency storage, production audit writes and connector
invocation remain Platform work.

### Enterprise

- [ ] Add single-tenant managed deployment path.
- [ ] Add on-prem/private cloud reference architecture.
- [ ] Add Helm charts and production deployment guides.
- [ ] Add backup and restore procedures.
- [ ] Add advanced audit export.
- [ ] Add enterprise identity and SSO hardening.
- [ ] Add security review and threat model documentation.
- [ ] Add support and operations runbooks.

## Expansion Rule

Axis starts unified, but the architecture must keep boundaries extractable.

Future repositories may include:

- `limes-axis-cloud`
- `limes-axis-enterprise`
- `limes-axis-connectors`
- `limes-axis-sdk`
- `limes-axis-deploy`
- `limes-axis-docs`

Extraction should happen when a module has at least two of these traits:

- independent release cadence;
- separate team or ownership;
- enterprise-only secrets, permissions or deployment logic;
- customer-specific integrations;
- independent SDK versioning;
- large connector surface;
- cloud operations that differ materially from the open-source core;
- documentation needs that outgrow the product repo.

## Contribution Policy

The project uses Apache-2.0 for the open-source core and plans to require a
Contributor License Agreement before accepting substantial external
contributions.

The CLA text in this repository is an initial project baseline and should be
reviewed legally before broad external contribution intake.

## What Is Intentionally Not Promised Yet

- No production readiness claim.
- No completed ERP/MES/CRM integrations.
- No uncontrolled autonomous agents.
- No dependency on a proprietary hosted model provider.
- No promise that commercial Cloud or Enterprise code will live in this repo.
