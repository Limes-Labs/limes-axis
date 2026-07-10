# LimesAxis Console Redesign — Design Spec

Date: 2026-07-10
Status: Approved by Francesco (this session)
Scope: `apps/web` (full console), plus targeted API work in `services/api` for missing flows.

## 1. Problem

The governance console is feature-complete as a data surface but fails as a product:

- Pages are telemetry dumps, not workspaces. Of 12 pages, only two have a real user action (approve/reject, dry-run), and both bury it below 6–8 metadata sections.
- First-time users cannot tell what a page is for or what to do. Internal engineering vocabulary (`integrity_chain_tip_sha256`, `policy_boundary`, raw IAM scopes, "lease evidence invariants") is the primary UI copy.
- The connector console (2,556 lines) opens with ~40 metric tiles of internal invariants, promises management ("Connector intake") but offers no way to add, test, or sync a connector; its CSV preview is dead code and it renders a hardcoded timestamp.
- Loading state renders the "API required" error card on 5 of 10 pages — every navigation flashes "broken".
- Three incompatible empty-state visual languages; blank table bodies when lists are empty; the overview and settings pages collapse entirely if any one of their 4–5 backing endpoints fails.
- Navigation is a flat list of 12 equal items, duplicate icons, no pending-work badges; Cmd+K has no keyboard navigation.
- Every page renders two stacked near-identical headers (ConsolePage wrapper + component's own header card).
- There is no onboarding, no demo mode in the product (demo = externally pre-seeded tenant), and no designed "empty new customer" experience.

Full audit findings live in the session transcript; file:line specifics are preserved in the implementation plan.

## 2. Decisions (locked with Francesco)

| Decision | Choice |
|---|---|
| Primary audience | CTO / developer eyes first; must remain legible to ops managers and compliance officers |
| Scope | Frontend redesign + build the key missing flows (incl. API work) |
| Onboarding | Guided setup checklist on the overview for empty tenants |
| Demo data | First-class demo switch: empty-tenant checklist offers "Explore with demo data" (provisions the manufacturing scenario, badged Demo, wipeable) vs "Start fresh" |
| Missing flows in scope | Add + test connector; trigger preview sync; approval flow hardening; run simulation from UI |
| Navigation | Keep all pages, group into 4 sections with badges |
| Copy strategy | Plain-first: plain-language purpose/status leads; raw technical fields move to an always-available Inspect drawer |
| UI stack | shadcn/ui + Radix, restyled with existing tokens (Signal Blue, navy, Geist, status pills) |
| Overview job | Action-first control room; becomes the setup checklist when the tenant is empty |
| Language | English only, but all copy in a centralized strings layer (i18n-ready) |
| Delivery | Incremental PRs in demo-story order; main stays demoable at every merge |

## 3. North star

Every page answers in five seconds: **what is this, what's its state, what do I do next.** Technical depth never disappears — it moves one click away. Demo tenant and empty tenant are two states of the same product.

## 4. Foundation layer

Everything else builds on this; it ships first.

### 4.1 Component primitives
- Adopt shadcn/ui + Radix: Dialog, Sheet (drawer), Tabs, Tooltip, Command, Table, Toast, Collapsible, DropdownMenu, Badge.
- Restyle with existing tokens from `globals.css` — the visual language (one accent, navy dark theme, eyebrow labels, status pills) is retained deliberately.
- New shared scaffold components:
  - `PageHeader` — single header per page; the `ConsolePage` wrapper's duplicate header is removed.
  - `MetricStrip` — max ~5 metrics per page; metrics must describe user-relevant state, not internal invariants.
  - `FilterBar` — consistent across all list pages (Workflows and Simulation gain filters).
  - `MasterDetail` — shared list/detail layout.
  - `DetailGrid` / `KeyValueRow` — replaces hundreds of duplicated Tailwind grid strings.
  - `InspectDrawer` — per-record drawer exposing raw fields (scopes, hashes, snake_case identifiers, JSON payloads). This is where technical depth lives.

### 4.2 State system (one visual language)
- **Loading** → skeleton, always. The current "loading renders the API-required error card" bug is eliminated everywhere.
- **API unavailable** → error card with plain copy; endpoint paths and technical details demoted into an expandable details section.
- **Empty data** → purposeful empty state: one sentence of purpose + one CTA (e.g. "No connectors yet — Add your first connector").
- The three current vocabularies (ApiRequiredState, ad-hoc "Flag-Gated" blocks, bespoke not-found cards) are unified.
- Blank table bodies are banned: every list renders an explicit empty row/state.

### 4.3 Data layer
- Extend `useAxisQuery` to support per-panel independent queries; remove all-or-nothing `Promise.all` gates (overview, settings). One failing endpoint degrades one panel, never the page.
- Stale-while-revalidate on refresh; global `triggerRefresh` bus retained.
- Connector console migrates from its 16 hand-rolled fetches to the shared layer.
- `getApiBaseUrl()` localhost fallback: when the default is in use, surface it explicitly in API-down states ("Console is pointing at http://localhost:8000 — set NEXT_PUBLIC_AXIS_API_BASE_URL").

### 4.4 Navigation & chrome
- Sidebar grouped into 4 sections:
  - **Operate**: Overview, Approvals, Workflows, Agents
  - **Data & Models**: Ontology, Connectors, Models
  - **Governance**: Policies, Audit, Simulation
  - **Platform**: Tenants, Settings
- Pending-approvals count badge on Approvals nav item. Unique icon per item.
- Cmd+K: arrow-key/Enter navigation, entity search (workflows, agents, policies, tenants, connectors) in addition to page navigation.
- Topbar decomposition: notifications, help, and account panels split into separate components. Account popover simplified; the raw bearer-token paste flow is demoted into a clearly-labeled Developer section, visually subordinate to SSO.

### 4.5 Copy layer
- Centralized strings module (i18n-ready, English only). All page copy rewritten plain-first during page migration.
- Glossary tooltip component for platform terms: ontology, autonomy level, egress, evidence, dry-run, replay, idempotency.
- Raw snake_case identifiers and IAM scopes never appear as primary copy; they appear in Inspect drawers and as secondary mono details.

## 5. Page designs

### 5.1 Overview — action-first control room
Non-empty tenant, top to bottom:
1. **Needs attention** strip: pending approvals (inline approve → confirm dialog), blocked workflows, risk signals. Direct actions, deep links.
2. **Posture cards** (~5): agents, workflows, connectors, policies, models — each with one status, one number, one link.
3. **One** evidence/activity feed (replacing the current three overlapping audit views).
4. Right rail: system health, quick actions.
- Fixes: duplicated "Operations Plant Operations Cockpit" title; conflicting counts (hero 25 vs card 128 audit events); per-panel degradation on endpoint failure.
- Empty tenant: the page becomes the **guided setup checklist** (§6).

### 5.2 Approvals — hero flow
- Decision-first layout: the decision block sits at the top of the detail panel, not below 8 sections.
- Consequence text always visible (currently hidden in a hover `title` tooltip).
- Confirm dialog with optional rationale before persisting.
- After deciding: inline success with a direct link to the created audit event.
- Metadata organized into collapsible sections; raw permissions/policy strings in the Inspect drawer.

### 5.3 Connectors — full rebuild (largest item)
Task-oriented structure:
- **Connector list** with real status (source, last sync, health) + **Add Connector wizard**:
  - CSV: actual file input → upload → preview rows → mapping → save manifest.
  - External DB: profile-id based registration → metadata-only validation.
- **Validate/Test** action per connector.
- **Run sync (preview)** action producing real run records, checkpoints and audit events.
- Per-connector detail in tabs: Overview / Data & Schema / Governance & Evidence (the current ~40 invariant tiles compress into this tab + Inspect drawers) / Runs.
- Fixes: hardcoded fake timestamp removed; "no connectors yet" (empty + CTA) distinguished from "API down"; dead CSV-preview code removed or wired to the wizard.
- API work in `services/api`: connector registration, CSV upload/preview, validation, preview-sync trigger endpoints. Exact contracts defined in the implementation plan after reading the existing connector service code.

### 5.4 Agents & Workflows
- Agents: scannable list; autonomy level explained inline (glossary); detail in tabs — Overview / Permissions & Guardrails / Runs / Evidence. Runs promoted from the current icon-only toggle to a first-class tab.
- Workflows: gains a filter bar; timeline is the centerpiece; blocker banner links directly to the blocking approval.

### 5.5 Ontology
- Graph stays (best-crafted piece, good a11y) and gains zoom/pan.
- Entity detail opens as a slide-over (Sheet) preserving graph state; full page remains for deep links.
- The 8 redundant "Mapped demo ontology nodes" metric cards are removed; node-type counts move into the graph legend.

### 5.6 Audit, Simulation, Models
- Audit: plain-first integrity panel ("Ledger verified — hash chain intact"; raw hashes in Inspect), an actual Export action for the export bundle, filters retained.
- Simulation: **Run simulation** from the UI (new API endpoint); results presented as baseline-vs-simulated comparison; replay trace retained.
- Models: the two stacked consoles (Reference vs Live) become tabs under one header that explains the distinction.

### 5.7 Platform pages
- Settings renamed to reflect reality (System status / diagnostics), organized into tabs; "Action required" pills contextualized with what to do.
- Sessions console linked from the account menu; revoke interactions unified.
- Tenants: keep current flows (already the best-designed pages); align to new primitives.

## 6. Onboarding & demo machinery

- **Empty tenant** → Overview renders the setup checklist:
  1. Connect a system (→ Connectors wizard)
  2. Import ontology entities (→ Ontology)
  3. Define a policy (→ Policies create)
  4. Register an agent (→ Agents)
  5. Run a governed workflow (→ Workflows)
  - Each step deep-links to its page, which shows its designed empty state with one CTA. Checklist progress is derived client-side from the existing registry endpoints (connectors, ontology, policies, agents, workflows counts); a dedicated setup-state endpoint is only added if derivation proves insufficient during implementation.
- **"Explore with demo data"**: alternative checklist path that provisions the manufacturing scenario for the tenant (reusing the existing seeded-bootstrap machinery), sets a visible **Demo** badge in the topbar, and offers a wipe/reset. Demo and onboarding share the same machinery.

## 7. Non-goals

- No i18n translations (infrastructure-lite only: centralized strings).
- No live connector execution beyond governed preview sync.
- No configurable/draggable dashboard.
- No visual rebrand — existing tokens, typography and status language are kept.
- No changes to auth flows beyond UI reorganization (SSO/bearer logic unchanged).

## 8. Delivery plan (phases = PR groups)

1. **Foundation**: shadcn setup, scaffold primitives, state system, data-layer changes, nav groups, topbar decomposition, copy layer. Main visual identity unchanged.
2. **Overview + Approvals** (control-room story) incl. approval hardening.
3. **Agents + Workflows**.
4. **Connectors rebuild + Ontology** (incl. API endpoints for connector flows).
5. **Audit + Policies + Simulation + Models** (incl. simulation-run endpoint).
6. **Platform pages + onboarding checklist + demo switch**.

Each phase: component tests for new primitives, a Playwright walkthrough of that phase's demo path, and a demoable main branch at merge.

## 9. Testing

- Component tests (first in the repo) for the shared primitives: states, InspectDrawer, MetricStrip, nav.
- Playwright: one spec per demo-story segment (control room → approve → evidence; add connector → preview sync; empty tenant → checklist → demo data).
- Existing `lib/*` unit-test discipline retained for new data-layer code.
