# Limes Axis — North Star and Market Phasing

Last updated: 2026-10-18
Status: proposed
Tracking: proposed as a new top-level issue above #285, #353, #376 and #440.
Issue numbers below refer to `Limes-Labs/limes-axis`.

## Why this plan exists

The backlog holds about 490 open issues and about 60 capability umbrellas
(#441–#930). Together they already cover most of what a Palantir-class
platform does. Axis does not need more capability issues. It needs **one ordered
map**:

- which umbrella serves which market phase;
- what is deliberately deferred;
- what evidence lets Axis move from one phase to the next.

Without that map, work spreads across many parallel slices. On 2026-10-18 there
were 26 open non-dependabot PRs, and `main` had not changed since 2026-09-16
(see [the PR-queue triage draft](./2026-10-18-issue-drafts.md#draft-b--delivery-drain-the-stalled-pr-queue-in-phase-order)).

This plan is the ordering layer above #285 (the Operate umbrella), #353
(beachhead discovery), #376 (the capability radar) and #440 (Gov and regulated
readiness). It does not replace those issues or change any security invariant
in [AGENTS.md](../../AGENTS.md).

## Target

Axis becomes **one** European operational platform with a single shared core.
It is sold in three successive phases:

1. **SMEs and enterprises:** the first revenue. Each customer gets one paid,
   repeatable operational workflow.
2. **Regulated enterprises:** energy, utilities, finance, healthcare and large
   industry, including buyers subject to NIS2, DORA or the AI Act. The core stays
   the same and the assurance gets stronger.
3. **Public sector and Gov:** the largest long-term opportunity. The core stays
   the same, with public-sector modules added on top. Axis enters through a
   concrete, eligible procurement route, never through a fork.

There is no separate SME or Gov codebase. Vertical and public-sector specifics
live in packs, deployment profiles and optional modules.

## Capability map: Axis families and the Palantir reference

Use the Palantir names to *explain* scope internally. Externally, describe what
Axis does (see [Positioning](#positioning)). The family names are only a
positioning proposal; nothing is renamed in code.

| Axis family (proposal) | Closest reference | Existing owners |
| --- | --- | --- |
| **Axis Operate**: data, ontology, apps, workflows, actions | Foundry | #277, #441, #586, #641, #655, #713, #752, #766, #787, #523, #447, #516, #509, #280, #530, #537, #773, #780, #803, #616, #828, #847 |
| **Axis AI**: search, assistant, agents, models, evaluation | AIP | #278, #279, #366, #598, #818, #449, #448, #544, #580 |
| **Axis Deploy**: sovereign deployment, fleet, reliability | Apollo | #283, #445, #627, #574, #656, #634, #810, #667, #552 |
| **Axis Intelligence**: entity fusion, investigations, markings, federation | Gotham-class, for civil and public-sector use | #440, #442, #443, #444, #446, #450, #559, #648, #759, #567 |
| Cross-cutting trust and compliance | — | #371, #609, #682, #675, #795, #720, #705, #697, #735, #728, #743, #690, #837, #854 |

## Phase 1 — SMEs and enterprises: the minimal Operate + AI loop

**Goal:** sell this loop as a pilot, then as a subscription:
`2–3 approved sources → typed ontology → authorized search → assistant proposal → human approval → writeback → audit`.

Promote the work in this order:

- [ ] Merge or close the stalled phase-1 PRs: REST pull, full-text search,
      document discovery, the writeback contract and connector recovery.
- [ ] Sources: #336 (#859–#862), one provider of #338 chosen by the first pilot,
      and the enterprise ERP/CRM pack ([draft D](./2026-10-18-issue-drafts.md#draft-d--enterprise-system-packs-first-erpcrm-targets-chosen-by-the-pilot)).
- [ ] Search and answers: #343 (#873–#875), then #345, then #346.
- [ ] Actions: #510–#512, then #513 (#880–#882). Build these only when the pilot
      needs external writes.
- [ ] Enterprise modules with immediate demand: the entity-resolution baseline
      #455 (customer and supplier deduplication), and rules and alerts
      (#466 and #471).
- [ ] Commercial basics: SSO #330, SCIM #727, billing-grade metering #326 and
      tenant export #324.
- [ ] Experience: #276, #351 and Italian localization under #282.
- [ ] Repeatable delivery: the pilot kit
      ([draft E](./2026-10-18-issue-drafts.md#draft-e--pilot-kit-a-repeatable-paid-pilot-with-in-product-value-evidence)).

**Exit gate from phase 1 to phase 2.** Close every item with evidence, not
demos:

- [ ] At least two paying customers run the core loop on real sources that the
      customer approved.
- [ ] A second, independently deployed supported instance exists, and the
      backup/restore drill (#328) passes.
- [ ] Each customer has a measured before/after outcome, recorded as #353
      requires.

## Phase 2 — Regulated enterprises

**Goal:** pass a real customer security review without bespoke forks.

- [ ] Hardening #327–#332, including the external pentest #332.
- [ ] Compliance evidence #371–#375: the ISO 27001 path (#374) and AI Act and
      NIS2 controls (#375).
- [ ] Zero-egress #473 (#869–#872) and portability #476 (#876–#879).
- [ ] Assurance packs #733 (#883–#885), secrets #735, access governance #682
      and the policy studio #609.
- [ ] AI governance: the model gateway #818 (BYOM #827 first), AI assurance #449
      and decision lineage #580.
- [ ] Private connectivity #810, where a customer network requires it.

**Exit gate from phase 2 to phase 3:**

- [ ] At least one regulated customer has run its own security review and
      accepted Axis.
- [ ] The external pentest is closed, and ISO 27001 certification is in
      progress with a named owner.
- [ ] Evidence from the disconnected rehearsal and the independent restore is
      published as bounded results.

## Phase 3 — Public sector and Gov

**Goal:** enter through a specific, eligible use case and procurement route,
directly or with a delivery partner, on the same core.

- [ ] Readiness for the Italian and EU public sector: ACN, procurement,
      SPID/CIE/eIDAS, PDND and accessibility
      ([draft C](./2026-10-18-issue-drafts.md#draft-c--italian-and-eu-public-sector-readiness-acn-procurement-spidcieeidas-pdnd-accessibility)).
- [ ] The trust plane: markings, purpose and controlled release (#446).
- [ ] Full entity intelligence #442, investigations #443, geospatial #648,
      external and open data #559, records #697, and open-data publishing #837.
- [ ] Federation across administrations #450.
- [ ] Optional institutional context through GovCore (#930 and PR #929),
      off by default.
- [ ] Later, and only for an eligible security buyer: CTI #759, edge #552 and
      field operations #567.

The rules in #376 still apply. Classify every Gov signal as `policy signal`,
`active contract`, `review/option`, `published tender`, `awarded` or
`confirmed termination`. Criticism of an incumbent is not an open tender.
Defence and classified workloads stay out of scope until a specific
accreditation path exists.

## Deferred until a named buyer asks

- Clean rooms #854
- Workbook studio #847
- Preview environments #667
- Test data #690
- Notebooks #551
- Optimization #537
- Process mining #530
- Resource management #634
- Package registry #627, beyond basic signed bundles

Their open PRs (#899, #901, #902 and #903) should be parked as drafts, not
merged ahead of phase-1 work.

## Working rules

- Every new umbrella or slice states its phase (1, 2, 3 or deferred) in the first
  line of its body.
- At most **one** PR per umbrella is in flight at a time. A stacked slice opens
  only after its predecessor merges.
- A phase-3 capability may land early only when a phase-1 or phase-2 customer
  needs it, and it must reuse the shared core.
- These invariants do not change: tenant binding, fail-closed gates, secret
  redaction, append-only evidence, outbox recovery and idempotency.

## Positioning

> Limes Axis is a European operational platform. It connects a company's
> existing systems and turns them into a shared operational model that people and
> AI can work with. Every decision and action runs under permissions, human
> approval and audit. Axis is self-hostable, including in isolated environments.

Use "a European alternative to Palantir" only as an informal reference. Public
claims must match behavior that has shipped and been verified.

## Definition of done

- [ ] #285 and #440 reference this map, and every umbrella has a phase.
- [ ] The phase-1 loop runs end to end for a paying customer.
- [ ] Each gate is closed by linked evidence, not by a checkbox.
