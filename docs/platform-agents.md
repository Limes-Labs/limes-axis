# Platform Agent Registry

The Platform agent registry slice introduces a public-safe, read-only view of
governed agents in the manufacturing reference scenario.

It is intentionally a registry and governance surface, not a production agent
runtime. Agents can recommend, draft proposals and link evidence, but this slice
does not execute actions, persist agent state or mutate external systems.

## Current Scope

- `GET /demo/manufacturing/agents` returns a synthetic manufacturing agent
  registry.
- The Next.js console renders the registry at `/agents`.
- The UI supports local filters for domain, autonomy level and status.
- Each agent exposes owner role, purpose, policy boundary, model egress posture,
  required permissions, guardrails, connected systems, data access, allowed and
  blocked actions, proposals, workflows, approvals and audit evidence.
- The public seed keeps every demo agent within L1-L2 autonomy.
- External model egress is blocked for every seed agent by default.

## Demo Agents

The seed currently includes:

- Daily Brief Agent: L1 operations summary and evidence ranking.
- Supply Risk Agent: L2 supply proposal drafting with owner approval required.
- Quality Risk Agent: L2 quality hold recommendation drafting.
- Maintenance Planner Agent: L2 maintenance reschedule proposal drafting.

The registry connects these agents to the existing synthetic manufacturing
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
- runtime policy enforcement beyond the public seed contract.

Those capabilities remain Platform work and should be implemented behind the
existing typed action registry, workflow runtime adapter, permission primitives,
model router and audit ledger boundaries.

## Acceptance Notes

- The endpoint is covered by API tests and OpenAPI generation.
- The web fallback seed mirrors the API contract for offline demo rendering.
- The web unit tests cover filtering, fallback lookup, public-safety checks and
  policy-boundary invariants.
- Playwright smoke tests cover the mobile navigation path and domain filtering.
- Public documentation avoids customer data, personal names, contacts, pricing,
  credentials and deployment secrets.
