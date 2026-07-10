# LimesAxis Console Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the governance console per `docs/superpowers/specs/2026-07-10-console-redesign-design.md`: action-first pages, unified states, grouped nav, plain-first copy with Inspect drawers, connector/simulation flows wired to the existing API, guided onboarding + demo switch.

**Architecture:** Six phases, one PR each, in demo-story order. Phase 1 builds the shared foundation (Radix-based primitives styled with existing tokens, unified Loading/Error/Empty states, per-panel data fetching, grouped nav, decomposed topbar, strings/glossary layer). Later phases migrate pages onto the foundation. Existing lib data contracts (`apps/web/lib/*-demo.ts` types, `axisFetchJson`) are reused untouched wherever possible.

**Tech Stack:** Next.js 16 / React 19 / Tailwind 4 (existing), Radix UI primitives + cmdk (new), vitest + @testing-library/react for component tests (new), Playwright (existing).

## Global Constraints

- Visual identity is retained: tokens in `apps/web/app/globals.css` (Signal Blue `--signal`, navy dark theme, Geist fonts, `.eyebrow`, `.status-pill`) must not change meaning. New primitives restyle on top of them.
- Raw snake_case identifiers, IAM scopes, hashes never appear as primary copy — they live in `InspectDrawer` or secondary mono text.
- Every list surface must render an explicit empty state (blank `<tbody>` is banned).
- `source === "loading"` must never render an error/API-required card.
- All new user-facing strings go through `apps/web/lib/strings.ts`.
- All pages keep working against the live API at `NEXT_PUBLIC_AXIS_API_BASE_URL` (default `http://localhost:8000`), tenant `tenant_demo_manufacturing`.
- Package manager: pnpm, workspace filter `@limes-axis/web`. Run web tests with `pnpm --filter @limes-axis/web test`, typecheck with `... typecheck`, lint with `... lint`.
- Node >= 22. Do not add heavy dependencies beyond: `radix-ui` primitives actually used, `cmdk`, `@testing-library/react`, `@testing-library/user-event`, `jsdom` (or `happy-dom`).
- Each phase ends: unit tests green, typecheck green, lint green, Playwright smoke green, manual browser verification, then PR → merge to main.

## Verified API surface (methods confirmed in `services/api/src/axis_api/main.py`)

- `GET/POST /demo/manufacturing/connectors/manifests` (POST creates manifest, 201/403/409/422)
- `POST /demo/manufacturing/connectors/file-csv/preview` (`ConnectorCsvPreviewRequest` → `ConnectorCsvPreviewResult`)
- `POST /demo/manufacturing/connectors/external-db/preview`
- `GET/POST /demo/manufacturing/connectors/runs`, `POST .../runs/{run_id}/dispatch`, `POST .../runs/{run_id}/execute-sync`
- `GET /demo/manufacturing/simulation/replay` (parameterized comparison), `GET .../replay/outputs`
- `POST /demo/manufacturing/approvals/{approval_id}/decision`
- `GET /demo/manufacturing/approvals`, `/agents`, `/workflows`, `/audit`, `/ontology`, `/overview`, `/operations`, `/model-routing`, `/notifications`
- Client types for all of these already exist in `apps/web/lib/*-demo.ts` / `packages/schemas`.

## File structure (created/heavily modified)

```
apps/web/components/ui/
  dialog.tsx sheet.tsx tabs.tsx tooltip.tsx collapsible.tsx dropdown-menu.tsx   # Radix wrappers, token-styled
  command.tsx        # cmdk wrapper
  toast.tsx          # lightweight toast (context + portal, no dep)
  states.tsx         # LoadingPanel / ErrorPanel / EmptyPanel — the ONLY state visuals
  metric-strip.tsx   # <MetricStrip items={...}/> max ~5
  filter-bar.tsx
  master-detail.tsx
  detail-grid.tsx    # DetailGrid + KeyValueRow
  inspect-drawer.tsx # Sheet with key/value + JSON view of raw record
  glossary.tsx       # <Term k="autonomy_level"/> tooltip from strings.ts glossary
  page-header.tsx
apps/web/lib/
  strings.ts         # centralized copy + glossary definitions
  nav.ts             # grouped navigation model (replaces navigationItems usage)
  use-axis-query.ts  # + keepPreviousData (stale-while-revalidate)
apps/web/components/topbar/
  notification-panel.tsx account-panel.tsx help-panel.tsx   # split from console-topbar
apps/web/components/
  console-topbar.tsx      # slimmed orchestrator
  app-shell.tsx           # grouped nav + approvals badge
  console-command-menu.tsx# rebuilt on cmdk
  platform-overview.tsx   # rebuilt (Phase 2)
  approval-inbox.tsx      # rebuilt decision-first (Phase 2)
  agent-registry.tsx workflow-console.tsx          # rebuilt (Phase 3)
  connector-console/      # NEW directory replacing 2,556-line file (Phase 4)
    index.tsx list.tsx detail.tsx add-connector-wizard.tsx runs.tsx governance.tsx
  ontology-explorer.tsx ontology-graph.tsx          # slide-over detail, zoom/pan (Phase 4)
  audit-explorer.tsx policy-*.tsx simulation-console.tsx model-routing-console.tsx  # (Phase 5)
  onboarding-checklist.tsx demo-badge.tsx           # (Phase 6)
  platform-settings-console.tsx                     # (Phase 6)
```

---

# Phase 1 — Foundation (PR: `redesign/foundation`)

### Task 1.1: Test tooling + component-test harness

**Files:** Modify `apps/web/package.json`, create `apps/web/vitest.setup.ts`, modify `apps/web/vitest.config.ts` (or create if config lives in package.json).

Steps:
- [ ] Add devDeps: `@testing-library/react`, `@testing-library/user-event`, `@testing-library/jest-dom`, `jsdom`. Configure vitest `environment: "jsdom"` for `*.test.tsx` only (keep node env for `lib/*.test.ts` — use `environmentMatchGlobs`).
- [ ] Write a trivial `apps/web/components/ui/states.test.tsx` asserting a placeholder renders (will grow in Task 1.2), run `pnpm --filter @limes-axis/web test` → green.
- [ ] Commit.

### Task 1.2: Unified state system

**Files:** Create `apps/web/components/ui/states.tsx`, test `states.test.tsx`. Keep `api-required-state.tsx` as a thin re-export wrapper for compatibility until Phase 5 removes last usage.

**Produces:**
```tsx
export function LoadingPanel(props: { rows?: number; layout?: "list" | "detail" | "metrics" })
export function ErrorPanel(props: { title: string; detail?: string; endpoint?: string; onRetry?: () => void })
// endpoint + base-url info collapsed behind a "Technical details" <Collapsible>; shows
// "Console is using the default http://localhost:8000 — set NEXT_PUBLIC_AXIS_API_BASE_URL"
// when isDefaultApiBaseUrl() (new export in lib/api-status.ts) is true.
export function EmptyPanel(props: { icon?: LucideIcon; title: string; detail: string; action?: { label: string; href?: string; onClick?: () => void } })
```

Steps:
- [ ] Tests: ErrorPanel hides endpoint until expander clicked; EmptyPanel renders CTA link; LoadingPanel renders skeletons and no error text. Run → fail.
- [ ] Implement with existing tokens (dashed border reserved for EmptyPanel; ErrorPanel uses danger tint; LoadingPanel uses `Skeleton`). Add `isDefaultApiBaseUrl()` to `lib/api-status.ts` (+ unit test in `api-status.test.ts`).
- [ ] Run tests, typecheck, commit.

### Task 1.3: Radix/cmdk primitives

**Files:** Create `apps/web/components/ui/{dialog,sheet,tabs,tooltip,collapsible,dropdown-menu,command,toast}.tsx` + `ui/primitives.test.tsx`. Modify `apps/web/package.json` (deps: `radix-ui`, `cmdk`).

Steps:
- [ ] Install `radix-ui` (unified package) + `cmdk`.
- [ ] Implement thin shadcn-style wrappers styled with tokens (portal + overlay `bg-midnight/60 backdrop-blur`, panel `border-line bg-surface`). Toast: small context provider + portal, `useToast().push({title, tone, href?})`, auto-dismiss 6s.
- [ ] Tests: dialog opens/closes via trigger + Escape; tabs switch panels; toast appears and dismisses (fake timers). Run → green. Commit.

### Task 1.4: Scaffold primitives (PageHeader, MetricStrip, FilterBar, MasterDetail, DetailGrid, InspectDrawer, Glossary) + strings layer

**Files:** Create the seven `ui/*` files above + `apps/web/lib/strings.ts` + tests `ui/scaffold.test.tsx`, `lib/strings.test.ts`.

**Produces (exact interfaces later phases rely on):**
```tsx
// page-header.tsx
export function PageHeader(props: { eyebrow: string; title: string; description?: string;
  status?: ReactNode; actions?: ReactNode; meta?: ReactNode })
// metric-strip.tsx — hard cap: renders first 5, warns in dev if more
export type Metric = { label: string; value: string | number; detail?: string; tone?: "ready" | "watch" | "action" }
export function MetricStrip(props: { metrics: Metric[] })
// filter-bar.tsx
export type FilterDef = { id: string; label: string; options: { value: string; label: string }[] }
export function FilterBar(props: { filters: FilterDef[]; values: Record<string, string>;
  onChange: (id: string, value: string) => void; onReset: () => void })
// master-detail.tsx
export function MasterDetail(props: { list: ReactNode; detail: ReactNode })
// detail-grid.tsx
export function DetailGrid(props: { children: ReactNode })
export function KeyValueRow(props: { label: ReactNode; children: ReactNode; mono?: boolean })
// inspect-drawer.tsx — Sheet listing all fields of a record + raw JSON tab
export function InspectDrawer(props: { title: string; record: Record<string, unknown>; trigger?: ReactNode })
// glossary.tsx
export function Term(props: { k: keyof typeof glossary; children?: ReactNode }) // dotted-underline + Tooltip
// lib/strings.ts
export const glossary: Record<string, { label: string; definition: string }> // ontology, autonomy_level, egress, evidence, dry_run, replay, idempotency, connector_manifest, policy_scope
export const strings: { nav: {...}; states: {...}; pages: Record<string, { eyebrow: string; title: string; description: string }> }
```

Steps:
- [ ] Tests first (FilterBar onChange/onReset wiring; MetricStrip caps at 5; InspectDrawer opens and shows JSON; Term renders tooltip content). → fail → implement → green.
- [ ] Commit.

### Task 1.5: Data layer — stale-while-revalidate

**Files:** Modify `apps/web/lib/use-axis-query.ts`; test additions in a new `apps/web/lib/use-axis-query.test.tsx` (jsdom + mocked `axisFetchJson`).

Behavior change: on refetch (refreshNonce/session change), keep previous `data` and expose `isRefreshing: boolean` instead of dropping to `loading`; initial load still starts at `loading`. Signature gains `{ data, source, error, isRefreshing }`. `source` stays `"api"` once data has arrived, even during refresh; only a failed refresh flips to `"unavailable"`.

Steps:
- [ ] Test: first load → loading→api; bump refreshNonce → data retained, isRefreshing toggles; failure after success → source unavailable but data kept for display with error banner. → implement → green. Commit.

### Task 1.6: Grouped navigation + approvals badge

**Files:** Create `apps/web/lib/nav.ts` (+ test), modify `apps/web/components/app-shell.tsx`, `apps/web/lib/foundation.ts` (keep `navigationItems` re-exported from nav.ts for the command menu until Task 1.8).

**Produces:**
```ts
export type NavGroup = { label: string; items: { href: string; label: string; icon: NavIcon; badge?: "approvals" }[] }
export const navGroups: NavGroup[] // Operate / Data & Models / Governance / Platform per spec §4.4
```
Icons unique per item (fix gauge duplication: Models → `route` icon). Badge: `app-shell` renders `<ApprovalsBadge/>` which calls `useAxisQuery<ApprovalRegistry>("/demo/manufacturing/approvals")` and shows pending count when > 0.

Steps:
- [ ] Test nav.ts grouping (all 12 hrefs present exactly once; icons unique). Modify app-shell: section labels (eyebrow style) + items; mobile row keeps flat order. → tests/typecheck → commit.

### Task 1.7: Topbar decomposition

**Files:** Create `apps/web/components/topbar/{notification-panel,account-panel,help-panel}.tsx`; shrink `apps/web/components/console-topbar.tsx` to orchestrator (status pills + icon row + panels). Move helpers (`compactActorLabel`, `operatorInitials`, `formatExpiry`, tone fns) to `apps/web/lib/identity-format.ts` (+ unit tests).

Account panel changes: bearer-token form moves under a `Collapsible` labeled "Developer access" with caption "For local development against a non-SSO API."; visually subordinate (text-xs link-style trigger). No behavior change otherwise.

Steps:
- [ ] Extract, move helpers + tests, verify no import cycles, typecheck, existing behavior manually confirmed (panels open/close). Commit.

### Task 1.8: Command menu on cmdk

**Files:** Rewrite `apps/web/components/console-command-menu.tsx`; test `console-command-menu.test.tsx`.

Features: arrow-key/Enter navigation (cmdk native), page navigation from `navGroups`, actions (refresh, theme, docs), and entity search: when menu opens, lazily fetch (once per open, best-effort, ignore failures) workflows/agents/policies/connectors registries and index names → selecting navigates to the page (with `?highlight=<id>` where pages support it later; plain page href for now).

Steps:
- [ ] Tests: typing filters items; ArrowDown+Enter triggers navigation callback; Escape closes. → implement → green. Commit.

### Task 1.9: Kill double headers + loading-as-error bug on all 12 pages (mechanical migration)

**Files:** Modify `apps/web/components/console-page.tsx` (renders `PageHeader` from strings.ts, plus children); every `app/*/page.tsx` (pass page key); every console component: delete its internal duplicate header card, add `source === "loading"` → `LoadingPanel` branch where missing (agent-registry, action-registry, audit-explorer, model-routing-console reference section, simulation-console), replace blank `<tbody>`/empty grids with `EmptyPanel` rows (overview panels get theirs in Phase 2).

Steps:
- [ ] Migrate page by page; after each: typecheck. Existing `foundation.test.ts`/page tests updated. Dead code: remove unused `foundationMetrics`, `ontologyPrimitives`, `workflowChecks`, `autonomyLevels`, `auditEvents` from `foundation.ts` (+ fix its test).
- [ ] Full gate: unit tests, typecheck, lint, `test:e2e` smoke. Browser walkthrough of all 12 pages. Commit.

### Task 1.10: Phase 1 PR

- [ ] Push branch, open PR "Console redesign phase 1: foundation primitives, unified states, grouped nav", merge after CI/browser verification.

---

# Phase 2 — Overview + Approvals (PR: `redesign/control-room`)

### Task 2.1: Approvals — decision-first rebuild

**Files:** Rewrite `apps/web/components/approval-inbox.tsx` (split detail into `approval-decision-card.tsx` if >400 lines). Test `approval-inbox.test.tsx` (mock `useAxisQuery` + `axisFetchJson`).

Layout: MasterDetail; detail = (1) title + risk pill + plain-language summary; (2) **DecisionCard at top**: option buttons with consequence text VISIBLE under each button label (never `title=`), click → `Dialog` confirm with consequence restated + optional rationale textarea → persist via existing decision endpoint payload + rationale in `note` field if schema allows (check `approval-demo.ts` decision request type; if no note field exists, omit — do NOT invent API fields); (3) success state → toast + inline link `/audit?event_id=<created_event_id>` (endpoint response already returns audit event ref — see `approval-demo.ts` types); (4) evidence/risks/alternatives as `Collapsible` sections default-open only for evidence; (5) raw scopes/policy strings via `InspectDrawer`.

Steps:
- [ ] Tests: consequence text visible without hover; confirm dialog gates persistence (axisFetchJson not called until confirm); post-decision audit link rendered from mocked response. → implement → green → typecheck → commit.

### Task 2.2: Overview — action-first control room

**Files:** Rewrite `apps/web/components/platform-overview.tsx` into `platform-overview.tsx` + `overview/{needs-attention.tsx,posture-cards.tsx,evidence-feed.tsx,side-rail.tsx}`. Tests per section component.

Structure per spec §5.1. Data: replace the single `Promise.all` gate with four independent `useAxisQuery` calls (`/overview`, `/operations/snapshot`, `/model-routing`, `/agents`); each section renders Loading/Error/Empty independently. Fix title duplication (ConsolePage now owns the header; hero shows plant/scenario as `meta`), audit-count mismatch (use one source: `overview.audit_events` registry count everywhere), one evidence feed only (remove ConnectorEvidence + AuditObservability + RecentActivity triplication → single `EvidenceFeed` with tone dots + link to /audit). Needs-attention strip: pending approvals (top 3, inline Approve → same confirm Dialog component reused from Task 2.1 via export), blocked workflows (from workflows registry `waiting` state), risk signals (from operations snapshot). Artifact runtime panel: keep, but collapsed into one card with SSO gate messaging only when actually unauthenticated.

Steps:
- [ ] Section tests (needs-attention renders items + actions from mock data; per-section error isolation: one query unavailable → other sections still render). → implement → green.
- [ ] Browser: verify with live API; check empty-approvals renders EmptyPanel. Commit.

### Task 2.3: Phase 2 gate + PR

- [ ] Unit + typecheck + lint + Playwright smoke; update `e2e/smoke.spec.ts` expectations if headers changed. Browser walkthrough (overview → approve flow end-to-end with confirm + audit link). PR "Console redesign phase 2: action-first overview and approvals", merge.

---

# Phase 3 — Agents + Workflows (PR: `redesign/agents-workflows`)

### Task 3.1: Agents — tabbed detail

**Files:** Rewrite `apps/web/components/agent-registry.tsx` → `agent-registry.tsx` + `agents/{agent-detail.tsx,agent-runs.tsx}`. Tests.

List: name, autonomy level (with `<Term k="autonomy_level">`), status, domain. Detail tabs: Overview (owner, boundary plain-language, models) / Permissions & Guardrails / Runs (first-class tab replacing icon-toggle; run list → step rail + linked invocations) / Evidence. Raw fields → InspectDrawer. Filters keep + zero-results EmptyPanel ("No agents match — reset filters" action).

### Task 3.2: Workflows — filters + timeline focus

**Files:** Rewrite `apps/web/components/workflow-console.tsx`. Tests.

Add FilterBar (state, domain). Detail: blocker banner links to `/approvals` (specific approval id when workflow record carries one — check `workflow-demo.ts` types). Timeline table is the visual center; inputs/outputs/context as Collapsible; controls/signals in DetailGrid.

### Task 3.3: Phase 3 gate + PR

- [ ] Tests/typecheck/lint/e2e smoke + browser walkthrough. PR, merge.

---

# Phase 4 — Connectors rebuild + Ontology (PR: `redesign/connectors-ontology`)

### Task 4.1: Connector console decomposition (read surfaces)

**Files:** Delete `apps/web/components/connector-console.tsx`; create `apps/web/components/connector-console/{index.tsx,list.tsx,detail.tsx,governance.tsx,runs.tsx}` and `apps/web/lib/use-connector-registries.ts` (batched queries on shared `useAxisQuery` — one hook call per endpoint actually rendered; drop endpoints whose data only fed deleted invariant tiles). Tests.

index: PageHeader (via ConsolePage) + MetricStrip (exactly: Connectors, Runs, Pending proposals, Egress policies, Evidence issues) + MasterDetail. detail tabs: Overview / Data & Schema (mapping, sample fields) / Runs / Governance & Evidence (credentials handles, leases, egress policies, invariants — DetailGrid + InspectDrawer, no tiles). Distinguish states: registry `connectors: []` → EmptyPanel "No connectors yet — Add your first connector" (opens wizard); fetch failure → ErrorPanel. Remove hardcoded timestamp — show real fetch time.

### Task 4.2: Add Connector wizard

**Files:** Create `connector-console/add-connector-wizard.tsx` (+ test). Uses Dialog, steps: (1) choose type (CSV file / External DB); (2a) CSV: `<input type="file">` → parse client-side row sample → `POST /demo/manufacturing/connectors/file-csv/preview` with `ConnectorCsvPreviewRequest` (read exact request shape from `apps/web/lib/connectors-demo.ts`; it already models this) → show preview table + mapping; (2b) DB: profile-id form → `POST .../external-db/preview`; (3) review → `POST .../connectors/manifests` (201 → toast + refresh registry; 409 → inline "already exists"; 403 → scope explanation via strings.ts). Idempotency: reuse `lib/ids.ts` UUID for manifest revision key if the request type carries one.

### Task 4.3: Test + preview-sync actions

**Files:** `connector-console/runs.tsx` (+ test). "Validate" button re-runs preview endpoint for the selected connector and reports result inline. "Run sync (preview)" → `POST /connectors/runs` (create run record) → `POST /runs/{id}/dispatch` → `POST /runs/{id}/execute-sync`, surfacing each stage as a stepper with statuses from responses; failures show stage-scoped ErrorPanel; success links to created audit events. All three POSTs already exist (verified). OIDC-gated: when unauthenticated, buttons disabled with "Sign in with SSO to run governed syncs".

### Task 4.4: Ontology — slide-over + zoom/pan, metric cleanup

**Files:** Modify `ontology-explorer.tsx` (node-type counts move to legend; remove 8 metric cards), `ontology-graph.tsx` (wheel/pinch zoom + drag pan via viewBox transform, +/- buttons, reset), create `ontology/entity-sheet.tsx` (Sheet rendering existing `ontology-entity-detail` content minus page chrome; full page route stays for deep links). Tests for zoom math + sheet open-from-node.

### Task 4.5: Phase 4 gate + PR

- [ ] Full gate + browser: add a CSV connector end-to-end against live API, run preview sync, check audit events appear. PR, merge.

---

# Phase 5 — Audit + Policies + Simulation + Models (PR: `redesign/governance-pages`)

### Task 5.1: Audit — plain-first integrity + export action

**Files:** Rewrite integrity/export sections of `audit-explorer.tsx`. Integrity panel: "Ledger verified — hash chain intact" style summary lines computed from existing export bundle fields; raw hashes/signature via InspectDrawer. Export: real "Download export bundle" button (serialize fetched bundle JSON → `Blob` download client-side; no new API). Keep filters/deep-link.

### Task 5.2: Simulation — run from UI

**Files:** Modify `simulation-console.tsx` + create `simulation/run-replay-form.tsx`. Form (scope/policy-set/window params — read exact query params of `GET /demo/manufacturing/simulation/replay` from `simulation-demo.ts` request builder) → run → render baseline-vs-simulated comparison view (two-column decision diff, changed outcomes highlighted with status tones). Persisted outputs list stays below.

### Task 5.3: Models — tabs

**Files:** Modify `model-routing-console.tsx`: one PageHeader; Tabs "Reference routing" / "Live invocations"; shared explanation line ("Reference shows the governed routing design; Live shows executed calls."). Unify the three empty-state treatments to EmptyPanel/ErrorPanel.

### Task 5.4: Policies — tabbed detail, single evaluator

**Files:** Modify `policy-detail.tsx`: Tabs Conditions / Revisions (history + compare) / Evaluate (single `policy-evaluation-panel`). Registry: keep create form below list (already good), scope strings plain-first ("You need policy author access" + scope in mono secondary).

### Task 5.5: Phase 5 gate + PR

- [ ] Full gate + browser walkthrough (run a replay, download export, evaluate a policy). Remove `api-required-state.tsx` compatibility wrapper (last usages gone). PR, merge.

---

# Phase 6 — Platform pages + onboarding + demo switch (PR: `redesign/onboarding-demo`)

### Task 6.1: Settings → System status; sessions link

**Files:** Modify `platform-settings-console.tsx`: per-panel queries (kill the 5-way OR collapse), Tabs "Readiness" / "Identity" / "Deployment" / "Support"; each "Action required" pill gains a one-line what-to-do string from strings.ts. Rename page strings to "System status" (nav label Settings stays, header clarifies). Account menu gains "Manage sessions" link (already exists — verify).

### Task 6.2: Onboarding checklist

**Files:** Create `apps/web/components/onboarding-checklist.tsx` (+ test); modify overview index to render it when tenant is empty (all registries zero → derived client-side per spec §6: connectors, ontology nodes, policies, agents, workflow runs counts). Five steps per spec, each: title, one-line why, CTA deep link, done-state derived from its registry count. Progress bar. "Explore with demo data" secondary CTA → Task 6.3 flow.

### Task 6.3: Demo switch

**Files:** Discovery first: `services/api/src/axis_api/demo.py` / `demo_reference.py` / `scripts/` — find the existing seed/bootstrap machinery. Then EITHER (a) if a bootstrap endpoint exists, wire it; OR (b) add `POST /demo/manufacturing/bootstrap` (FastAPI, reuse existing seeding functions, tenant-scoped, idempotent, scope-gated like other demo writes, + API test in `services/api/tests/`). Frontend: `demo-badge.tsx` in topbar shown when overview payload marks scenario/demo bootstrap present; checklist CTA calls the endpoint then refreshes; "Reset demo data" action in the badge dropdown ONLY if the API exposes a safe wipe — otherwise omit reset (do not build destructive endpoints in this pass).

### Task 6.4: Playwright story specs + final sweep

**Files:** Create `apps/web/e2e/{control-room.spec.ts,connectors-flow.spec.ts,onboarding.spec.ts}` (live-API gated like `live-overview.spec.ts` via `AXIS_E2E_LIVE_API`). Final sweep: run full test matrix, browser pass on all 12 pages in light + dark themes, mobile width spot-check (375px) on nav + overview + approvals.

### Task 6.5: Phase 6 PR + docs

- [ ] Update `docs/platform-overview.md` / `docs/platform-connectors.md` / `README.md` console paragraphs to match the new console. PR "Console redesign phase 6: onboarding checklist and demo switch", merge.

---

## Self-review notes

- Spec §4.1–4.5 → Tasks 1.2–1.9; §5.1 → 2.2; §5.2 → 2.1; §5.3 → 4.1–4.3; §5.4 → 3.1–3.2; §5.5 → 4.4; §5.6 → 5.1–5.3; §5.7 → 6.1 (+ tenants alignment happens via shared primitives in 1.9); §6 → 6.2–6.3; §8 phases map 1:1; §9 → 1.1 + per-task tests + 6.4.
- Types referenced (`ConnectorCsvPreviewRequest`, `ApprovalRegistry`, etc.) all exist in `apps/web/lib/*-demo.ts`; tasks instruct reading exact shapes rather than inventing fields.
- Rationale field on approvals: explicitly conditional on existing schema (no API invention).
