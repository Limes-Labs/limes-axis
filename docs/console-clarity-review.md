# Console clarity review — issue #433

The console should help an operations team move from connected business data to a reviewable decision and its recorded outcome. This delivery revises presentation across the existing console; it does not establish new execution, deployment, compliance, or market capabilities.

## Design references

Reviewed the supplied eight dashboard images and public previews from [Board UI](https://www.boardui.com/components) and [Efferd dashboards](https://efferd.com/blocks/dashboard). No commercial component source or new library is imported.

- Board UI bar list: directly label categories, counts and shares; use one visible denominator. Applied to the returned audit window.
- Board UI revenue, funnel, heatmap and combo previews: select a visual only when the underlying measures justify it. Axis has no complete revenue series, conversion cohort or hourly activity matrix in this view; these graphics would imply unsupported business measurements here.
- Efferd dashboard 6: put attention items and their next action ahead of supporting detail. Keep cards aligned and use whitespace to separate tasks.
- The [Palantir application-building documentation](https://www.palantir.com/docs/foundry/app-building/overview/) connects data exploration with operational applications and actions. [Quantexa supply-chain intelligence](https://www.quantexa.com/solutions/supply-chain-intelligence/) emphasizes connected supplier context; [ChapsVision manufacturing](https://www.chapsvision.com/fr/secteurs/industrie-manufacturiere/) emphasizes connected industrial data. Our design inference is to prioritize business objects, decisions and traceability for SME/enterprise operators. These sources do not establish feature parity or substantiate the supplied European contract estimates.

## Page-by-page decisions

All 17 routes below were reviewed at 1440 × 1000 and 390 × 844 in the in-app browser against an isolated local PostgreSQL/API fixture. Shared page headers now state the page's purpose once; the decorative topbar slogan and repeated navigation category are removed. The API, demo and data-source indicators remain. The dark theme keeps the Axis navy palette with a plain background so decorative dots and glow no longer show through data cards.

| Page | Before | After | Why |
| --- | --- | --- | --- |
| Overview | Large scenario hero and setup preceded decisions; radar encoded statuses as arbitrary numbers; unlabeled category sparkbars | Compact persisted counts, attention alongside labeled category bars, setup below decisions, one recent-event list | Show the next decision early and make quantities interpretable |
| Approvals | Long header; flex metrics stretched the final card | Short purpose statement; equal-width metric columns | Preserve the decision, risks, evidence, permission gate and external-executor boundary |
| Workflows | Verbose purpose statement; empty runtime state | Short purpose statement; retain the accurate empty state | Reference scenarios must not become invented workflow runs |
| Agents | Agent registry and action catalog competed on one page | Agent registry first; action catalog and registry notes expandable | Operators can inspect an agent before opening technical action definitions |
| Data | Sidebar destination returned 404 | Route renders the existing tenant-bound catalog; narrow ignore exception tracks the source file | Make the existing capability reachable without changing its contract |
| Connectors | Manifest JSON import above the registry | Registry first; advanced import below it in an explicit disclosure | Standard connection and monitoring remain the primary path |
| Ontology | Generic title, graph labels shrank on phones, adapter identifiers displayed as headings | Business-object title, mobile object cards by default and optional full-size scrollable graph with 13px labels; sources/access details expandable | Keep relationships readable and technical inspection available |
| Entity detail | Dense but relevant business attributes and relationships | Short purpose and object summary before metrics; preserve relationship and history detail | These facts explain the selected object and its evidence |
| Models | Verbose purpose; monitoring implementation named as a main section | Short purpose; expandable monitoring details | Preserve example/live distinction, cost basis and routing boundaries |
| Policies | Creation form always open below the registry | Explicit create-policy disclosure; registry remains first | Reading and authoring are separate tasks; evaluation semantics remain available |
| Policy detail | Revision, conditions and comparison | Short purpose; preserve revision and comparison controls | Rules and historical differences are necessary to assess a change |
| Audit | Database engine and replay capability presented as numeric KPIs | Operational event metrics only; keep filters, raw inspection and replay/export details | Backend implementation is not an operational measurement |
| Simulation | Long header plus empty replay history | Short purpose; retain accurate empty history | Do not manufacture comparison results |
| Tenants | Provisioning form always open | Explicit create-organization disclosure below registry | Keep lifecycle status and operator scope visible before authoring |
| Tenant detail | Lifecycle, quotas and terminology controls | Short purpose; preserve controls and permission explanations | These settings describe real administrative effects |
| Settings | Repeated category header; guidance mixed with raw check messages | Action guidance remains visible; technical check details expand on demand | Make remediation readable while retaining support evidence |
| Sessions | Access gate and session management | Shared header cleanup; preserve sign-in/scope gate | A simpler page must not imply session-management permission |

## Measurement and access rules

The category bars count every event in the returned audit window, with a maximum requested size of 25; this is neither lifetime activity nor a time trend. Visible text exposes counts and rounded percentages independently of decorative bars. The source pill preserves live/reference provenance. Empty and unavailable sources have different states. The removed radar also inferred connector health from event presence, which cannot establish service health.

Native disclosures retain form drafts while collapsed and remain keyboard-operable. Their children keep existing identity/tenant/query and mutation gates. The graph has a bounded scroll region so its full-size content does not overflow the page; mouse view navigation and explicit zoom controls remain. Keyboard focus includes disclosure summaries and focusable regions. No schema, authentication, transaction, egress or backend execution behavior changes.

## Validation

The pull request records final local, browser and CI results separately. Local `make verify` passed: API 2,560 passed / 43 skipped, worker 64 passed / 3 skipped, SDK 278 passed, web 992 passed, schema and repository contract gates passed. The skipped integration lanes require their own live services. Browser fixtures are synthetic and local; they are not hosted deployment proof. Workflow and simulation were reviewed in their empty runtime states, sessions in the unauthenticated gate, and policies/tenant/entity detail with seeded records.
