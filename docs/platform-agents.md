# Platform Agent Registry

The Platform agent registry slice introduces a public-safe, read-only view of
governed agents in the manufacturing reference scenario.

It is intentionally a registry and governance surface, not a production agent
runtime. Agents can recommend, draft proposals and link evidence, but this slice
does not execute actions, persist agent state or mutate external systems.

## Current Scope

- `GET /demo/manufacturing/agents` returns a manufacturing agent reference
  registry.
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

It does not yet include:

- persisted agent state;
- production action execution;
- workflow signal execution from agent proposals;
- model cost and token observability;
- tenant-scoped agent configuration storage;
- SDK or connector-driven agent registration;
- runtime policy enforcement beyond the public reference contract.

Those capabilities remain Platform work and should be implemented behind the
existing typed action registry, workflow runtime adapter, permission primitives,
model router and audit ledger boundaries.

## Acceptance Notes

- The endpoint is covered by API tests and OpenAPI generation.
- The web console shows an API-required state when agent records are unavailable.
- The web unit tests cover filtering, safe lookup and labels with local test
  fixtures only.
- Playwright smoke tests cover the mobile navigation path and API-required agent
  behavior.
- Public documentation avoids customer data, personal names, contacts, pricing,
  credentials and deployment secrets.
