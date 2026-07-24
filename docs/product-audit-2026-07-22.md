# Product audit and hardening checklist — 2026-07-22

This checklist records the repository-wide product review requested on 2026-07-22. It prioritizes product trust, tenant isolation, truthful data presentation, and repeatable verification over decorative UI changes.

## P0 — Tenant and identity correctness

- [x] Scope every core console route to the API-verified tenant: workflows, agents, ontology, connectors, model routing, policies, audit, simulation, and command search.
- [x] Disable tenant-scoped requests until `/identity/session` resolves successfully.
- [x] Reject mismatched response tenants in the Web runtime layer.
- [x] Cover authenticated non-demo and explicitly unauthenticated demo sessions in tests.

## P1 — Data fidelity and operational correctness

- [ ] Do not replace valid empty persisted datasets with reference/demo records.
- [ ] Distinguish live, stale-after-refresh-failure, empty, and unavailable sources.
- [ ] Replace proxy or invented overview metrics with values backed by the named dataset.
- [x] Treat a zero-artifact replay response as an empty state, not an API error.
- [x] Reconcile the connector live-sync Temporal schedule when the feature is disabled.
- [x] Remove wall-clock expiry from fixed-date API tests so the full suite is deterministic.
- [x] Rename overview shortcuts that only navigate to read-only pages.

## P1 — External side-effect integrity (follow-up architecture)

- [ ] Extend the durable outbox/state-machine boundary beyond approval decisions to action signals, connector export signals, object writes, and paid model calls.
- [ ] Decide when the approval decision outbox becomes the default deployment mode.
- [ ] Build, scan, approve, sign, and publish the same immutable container digest.

## P2 — UX, navigation, and accessibility

- [x] Provide a skip link and a stable main-content target; remove nested `main` landmarks.
- [ ] Give mobile navigation an explicit navigation landmark and a discoverable overflow/menu pattern.
- [x] Give loading regions accessible status text while keeping the skeleton visual concise.
- [ ] Expose status and sparkbar values without relying on color or pointer-only `title` text.
- [ ] Add route-level loading, error, and not-found boundaries and route-specific metadata.
- [ ] Keep selected filters, records, and deep links synchronized with the URL.
- [ ] Replace implementation-oriented tenant copy with operator-facing language.

## P2 — Runtime and deployment follow-ups

- [ ] Add worker/outbox health and backlog-age evidence to deployment readiness.
- [ ] Resolve registered model credential handles during provider invocation.
- [ ] Make model endpoint and invocation idempotency race-safe.
- [ ] Implement the documented `X-Request-Id` correlation boundary, including CORS.
- [ ] Decide whether production admits valid identity claims for unknown tenant records.
- [ ] Expand the Python SDK beyond the current demo-manufacturing surface.

## P3 — Component and code consistency

- [ ] Use semantic source/status badges instead of unconditional green source pills.
- [x] Use semantic connector governance tones and the defined danger token for failed agent runs.
- [x] Correct singular/plural operational copy.
- [ ] Consolidate repeated cards, tables, and action styles onto shared primitives.
- [ ] Split the API composition root into bounded route modules without weakening cross-cutting controls.

## Verification gates

- [x] Web unit tests, lint, typecheck, and production build.
- [x] API, worker, SDK, schema, OpenAPI, security, and deployment contract checks.
- [x] Desktop, mobile, tablet, and small-laptop browser sweeps with overflow checks.
- [x] Keyboard focus, dialogs, drawers, filters, empty/loading/error states, refreshes, and repeated submissions.
- [x] Authenticated non-demo tenant contract test across all tenant-scoped routes.
- [ ] Live Postgres, Temporal, TypeDB, object-store, and OIDC checks when Docker is healthy.
- [x] Second-pass product review after implementation.

### Verification evidence

- Web: 605 unit/component tests; lint, typecheck, and the production Next.js build passed.
- Browser: 69 mocked Chromium smoke tests passed across desktop, Pixel 7, and iPad profiles; 9 live-API Chromium scenarios passed against the real FastAPI and Next.js applications.
- Persisted product sweep: 12 console routes rendered with one `main` landmark and no horizontal overflow; audit filtering/reset and truthful empty workflow/replay states were exercised.
- Services: API 1,394 passed / 14 infrastructure-gated skipped; worker 51 passed / 3 skipped; Python SDK 103 passed.
- Contracts: OpenAPI export, schema, security posture, deployment package, all three Helm profiles, container-image, release, scan, and vulnerability-management checks passed.

## Current environment boundary

Docker returned `EOF` during this review. The persisted browser pass therefore uses the repository's canonical migration payloads in a temporary SQLite database through the real FastAPI and Next.js applications. Live distributed-infrastructure claims remain unverified until Docker is healthy.
