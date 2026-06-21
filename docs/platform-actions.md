# Platform Action Registry

The Platform action registry slice introduces a public-safe view of typed
actions in the manufacturing reference scenario.

It exposes the boundary between agent proposals and production execution:
actions have schemas, risk levels, approval modes, required permissions,
guardrails, validation checks, workflow bindings and audit event types. This
slice does not execute production actions.

## Current Scope

- `GET /demo/manufacturing/actions` returns a synthetic manufacturing action
  registry.
- `POST /demo/manufacturing/actions/{action_id}/runs` records a typed dry-run
  or proposal request with action idempotency enforcement and append-only audit.
- Approval-gated action runs signal the Axis workflow runtime adapter after
  persistence when a workflow binding and runtime policy are present.
- The Next.js console renders the registry on `/agents`, below the agent
  registry.
- The UI supports local filters for domain, risk level, approval mode and
  status.
- Each action exposes its typed input and output schemas, required permissions,
  owner role, runtime adapter, autonomy ceiling, model egress policy, workflow
  bindings, approval references, guardrails, blocked conditions and synthetic
  dry-run payload previews.
- High-risk demo actions require owner approval.
- Live runtime execution is disabled in the public demo.

## Demo Actions

The seed currently includes:

- Generate daily plant brief: low-risk read-only summary generation.
- Request supplier expedite: high-risk supply action proposal gated by owner
  approval.
- Place quality hold: high-risk quality action proposal gated by quality owner
  approval.
- Shift maintenance window: medium-risk maintenance proposal with conditional
  approval.

These actions connect the agent registry, workflow console, approval inbox and
audit explorer without enabling live mutation.

## Boundaries

The registry remains read-only at the catalog boundary, while action run
requests are now persisted as dry-run/proposal records.

The Postgres persistence foundation now includes `action_runs`, action
idempotency uniqueness and repository methods for recording action run results.
The action run path emits a redacted workflow signal result for approval-gated
demo actions through the Axis workflow runtime adapter. The action registry UI
still uses the synthetic seed for catalog data and does not execute production
actions or connector mutations.

It does not yet include:

- live runtime execution;
- connector-backed production mutations;
- tenant-scoped action configuration;
- connector-backed action invocation;
- policy simulation or replay from real histories.

Those capabilities remain Platform work and should be implemented behind the
existing typed action registry, workflow runtime adapter, permission primitives,
approval inbox and append-only audit ledger boundaries.

## Acceptance Notes

- The endpoint is covered by API tests, workflow signal adapter tests and
  OpenAPI generation.
- The web fallback seed mirrors the API contract for offline demo rendering.
- The web unit tests cover filtering, fallback lookup, schema formatting,
  public-safety checks, action run request building and approval-gating
  invariants.
- Playwright smoke tests cover the mobile navigation path, action risk filtering
  and schema visibility.
- Public documentation avoids customer data, personal names, contacts, pricing,
  credentials and deployment secrets.
