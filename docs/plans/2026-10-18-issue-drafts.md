# Issue Drafts — North Star Phasing (2026-10-18)

Status: drafts, ready to paste into GitHub issues.
Context: [North star and market phasing](./2026-10-18-north-star-phasing.md).

These drafts are not filed yet. The GitHub integration used to prepare them was
refused write access to issues (HTTP 403). Issue numbers refer to
`Limes-Labs/limes-axis`. Labels: `enhancement`, `operate`.

| Draft | Proposed title | Proposed parent |
| --- | --- | --- |
| A | Product north star: one European operational platform, phased SME/enterprise → regulated → public sector | none (top level) |
| B | Delivery: drain the stalled PR queue in phase order | A |
| C | Public sector: Italian and EU readiness (ACN, procurement, SPID/CIE/eIDAS, PDND, accessibility) | #440 |
| D | Connectors: enterprise system packs, with the first ERP/CRM targets chosen by the pilot | #277 |
| E | Pilot kit: a repeatable paid pilot with in-product value evidence | #353 |

Comments for existing issues are at the end of this file.

## Draft A — Product north star

Use the body of
[the north star and market phasing plan](./2026-10-18-north-star-phasing.md)
from "Why this plan exists" to the end. When you paste it, replace the
draft-file links with the issue numbers you filed for B–E.

## Draft B — Delivery: drain the stalled PR queue in phase order

**Phase:** 1 (delivery hygiene). **Parent:** A.

### Problem

`main` last moved on 2026-09-16, with the merge of PR #891. On 2026-10-18 there
were 26 open non-dependabot PRs and 8 dependabot PRs. Several umbrellas have
every slice open at the same time. For example, portability 1/4–4/4 are all
open, and so are assurance 1/3–3/3. Each stacked slice drifts further from
`main` and from the slices it depends on. The work is done, but none of it is
usable yet.

The CI and mergeable state of each PR was **not** checked when this draft was
written. Re-check them before acting.

### Order of work

1. **Unblock CI first.**
   - [ ] PR #900: fix the flaky approval-history E2E test (#898), which turns
         CI red on unrelated PRs.
2. **Phase 1. Review and merge in dependency order, rebasing each PR after its
   predecessor lands.**
   - [ ] REST pull: PR #892 (#860), then PR #915 (#861), then PR #916 (#862).
   - [ ] Full-text search: PR #896 (#873), then PR #907 (#874), then PR #908
         (#875).
   - [ ] Document sources: PR #894 (Microsoft 365 discovery, #864) and PR #897
         (Google Drive discovery, #866). Merge only the provider that the first
         pilot needs. Keep the other open.
   - [ ] Writeback contract: PR #917 (#510).
   - [ ] Connector runtime recovery: PR #923. It comes from an external fork, so
         confirm ownership, CLA and scope before review.
3. **Phase 2. Keep these open and rebase them after phase 1. Do not grow them.**
   - [ ] Zero-egress: PR #893 (#869), then PR #913 (#870), then PR #914 (#871).
   - [ ] Portability: PR #895 (#876), then PR #905 (#877), then PR #906 (#878),
         then PR #911 (#879).
   - [ ] Assurance packs: PR #904 (#883), then PR #909 (#884), then PR #910
         (#885).
4. **Phase 3, off by default.**
   - [ ] PR #929 (GovCore context). Merge only after the verification required by
         #930 is reported as PASS/FAIL/NOT RUN.
5. **Deferred. Convert these to draft PRs, with a comment linking A.**
   - [ ] PR #899 (open data), PR #901 (document studio), PR #902 (workbook) and
         PR #903 (clean rooms).
6. **Dependabot.**
   - [ ] Merge the minor/patch groups once CI is green: PRs #922, #926, #927,
         #932 and #933.
   - [ ] Review the major bumps one by one, each with its own verification: PR #919
         (eslint 10), PR #920 (jest-dom 7) and PR #928 (valkey 9).

### Acceptance

- [ ] No phase-1 PR is older than 14 days without a review decision.
- [ ] Each umbrella has at most one in-flight PR.
- [ ] Every merged PR reports which verification ran, with PASS/FAIL/NOT RUN,
      as [AGENTS.md](../../AGENTS.md) requires.

## Draft C — Italian and EU public-sector readiness (ACN, procurement, SPID/CIE/eIDAS, PDND, accessibility)

**Phase:** 3 (starts in parallel at the end of phase 2). **Parent:** #440.

### Problem

#440 covers the *capabilities* that the public sector needs: markings,
disconnected operation, investigations and federation. It does not cover the
*conditions of entry* that decide whether an Italian or EU administration can
buy and use Axis at all. A search of issue titles and repository docs on
2026-10-18 found no owner for ACN qualification, MePA/Consip procurement,
CAD reuse obligations, SPID/CIE login for operators, PDND interoperability or a
public-sector accessibility statement.

This issue is a readiness tracker. It does **not** claim any qualification,
certification or eligibility. Legal applicability stays with #372 and qualified
owners.

### Workstreams

1. **Cloud qualification for the hosted service (non-code first).**
   - [ ] Determine the ACN qualification level that the target use case's data
         classification requires (ordinary, critical or strategic data).
         Record which Axis profile (hosted, dedicated or customer-operated)
         falls under which obligation.
   - [ ] Map the existing evidence (#371–#375, #728, #733) to the ACN
         requirements. List the gaps with owners.
   - [ ] For deployments run on the administration's own infrastructure, record
         what changes. Do not assume the hosted qualification transfers.
2. **Procurement and IP model (non-code).**
   - [ ] Decide the route: MePA/Consip listing (check the current calls for
         innovative startups and their eligibility), a delivery partner already
         under framework agreements, or both.
   - [ ] Write down a licensing and IP position covering the CAD obligations:
         the art. 68 comparative assessment and art. 69 reuse/open release of
         software that the administration owns. Separate the pre-existing
         platform license from customer-funded customizations, so contracts do
         not transfer the core by accident. Review it with counsel.
   - [ ] Decide whether and how to list reusable components on Developers Italia.
3. **Identity for public-sector operators.**
   - [ ] Add a documented identity-broker profile (Keycloak) for SPID and CIE
         OIDC federation. Axis stays OIDC-first, so this is configuration plus
         a conformance test, not new auth code in the API.
   - [ ] Track eIDAS 2 / EUDI wallet acceptance as a later item, not an
         immediate one.
   - [ ] Non-goal: automating or bypassing a citizen's SPID/CIE authentication.
4. **PDND interoperability.**
   - [ ] Add a read-only REST source profile for consuming a PDND e-service. It
         uses the ModI security patterns (voucher, signed requests) on top of
         #336 and the credential/egress gates. Use it only under an existing,
         authorized purpose (finalità) of the administration.
   - [ ] Add fixture-based conformance tests. Live calls are NOT RUN unless
         authorized credentials exist.
   - [ ] Non-goal: scraping authenticated public-sector portals.
5. **Accessibility and language.**
   - [ ] Run automated accessibility checks (WCAG 2.1 AA / EN 301 549) on the
         console's operator paths in Playwright. Make manual review a release
         step.
   - [ ] Prepare an accessibility statement (dichiarazione di accessibilità)
         template.
   - [ ] Complete the Italian localization under #282 for the operator paths that
         a pilot uses.
6. **Institutional context.**
   - [ ] Optional GovCore lookup (#930, PR #929), off by default, with the
         non-overwrite verification that #930 requires.

### Acceptance

- [ ] Each workstream has a named owner and records `PASS`, `GAP` or `NOT RUN`
      with evidence links.
- [ ] No public material claims ACN qualification, MePA listing or
      accessibility conformance before the evidence exists.
- [ ] All code items stay in packs or profiles. Shared transport, authorization
      and ontology carry no public-sector-specific behavior.

## Draft D — Enterprise system packs: first ERP/CRM targets chosen by the pilot

**Phase:** 1. **Parent:** #277. **Edition row:** `ENTERPRISE-PREMIUM-CONNECTORS`
(Planned) in [the edition matrix](../editions-matrix.md).

### Problem

SMEs and enterprises buy outcomes on top of the systems they already run. Axis
ships generic CSV, PostgreSQL and S3 paths, and REST pull is in review. No issue
owns a supported pack for the ERP/CRM systems that a first customer actually
uses. The edition matrix lists maintained ERP, MES and CRM packs as Planned,
with `plan.md` as the only evidence.

### Scope

Build **one** pack, then a second, and only for systems a signed or committed
pilot uses (#353). Candidates, to be confirmed by discovery rather than built
upfront:

- SAP S/4HANA (OData) or SAP Business One (Service Layer)
- Microsoft Dynamics 365 / Business Central (OData/REST)
- Odoo (external API)
- Italian SME ERPs such as TeamSystem or Zucchetti. Verify API availability and
  partner terms first.
- Salesforce or HubSpot for CRM.

Each pack contains:

- [ ] A REST source profile on the #336 contract (see
      [REST source profiles](../rest-source-profiles.md)), with incremental
      cursors and rate-limit handling. It is read-only first.
- [ ] An ontology mapping to a small typed model, for example customer,
      supplier, order, invoice and item. The mapping is reviewed through the
      existing promotion policies.
- [ ] Optional writeback, only through #513 (#880–#882) and only for the
      operations the pilot approves.
- [ ] A recorded-fixture conformance scenario, in the style of #862. Live-system
      runs are reported as NOT RUN unless a sanctioned test tenant exists.
- [ ] Supported-version and limitation notes in the connector docs.

### Non-goals

- Connector-count parity.
- Vendor-specific code in shared core modules.
- Storing raw vendor credentials outside the credential-handle and lease path.

## Draft E — Pilot kit: a repeatable paid pilot with in-product value evidence

**Phase:** 1. **Parent:** #353. Related: #284 and #322 (prospect sandbox) and
#351 (onboarding).

### Problem

#353 defines a good pilot boundary:
`2–3 sources → small ontology → one workspace → one reviewed decision → auditable result`.
No deliverable makes that boundary repeatable, so every pilot would be rebuilt by
hand. The prospect sandbox covers pre-sales with synthetic data. It does not
cover a paid pilot on customer data.

### Deliverables

- [ ] **Pilot playbook** (doc): scope template, data-access checklist,
      deployment choice (hosted single-tenant or a single-node profile on the
      customer's VM), roles, a timeline from kickoff to the first governed
      decision in at most 10 working days, and an exit/conversion step.
- [ ] **Acceptance metrics template:** baseline and target for cycle time,
      manual steps, errors/rework and the share of decisions reviewed. Record
      these with the buyer before the build starts, as #353 requires.
- [ ] **In-product value evidence:** a tenant-scoped report derived only from
      existing audit and workflow evidence. It covers decisions proposed,
      approved, rejected and executed, plus time-to-decision. The report makes
      no estimates beyond what was measured, and adds no new collection of
      personal data.
- [ ] **Install path:** one-command install of the supported single-node
      profile, with a readiness check that separates `/health`, `/ready` and
      route checks.
- [ ] **Conversion path:** from pilot tenant to production tenant through the
      tenant export (#324), without re-entering data.

### Non-goals

- Customer names, data or prices in the repository.
- ROI claims that the measured evidence does not support.

## Comments for existing issues

### On #285 (Operate umbrella)

> Phase ordering for this umbrella and for the portfolios created after it
> (#440–#930) is proposed in `docs/plans/2026-10-18-north-star-phasing.md` and
> in the north-star issue (A). The umbrellas #441–#930 are not yet in this
> checklist; the plan assigns each one to phase 1, phase 2, phase 3 or
> deferred. Suggest adding one line here: "Phase and gate ordering: see A."

### On #440 (Gov/regulated readiness)

> Proposed new child: the Italian and EU public-sector readiness issue (C).
> It covers the conditions of entry that this umbrella does not own: ACN
> qualification, MePA/CAD procurement and IP, SPID/CIE operator identity,
> PDND interoperability, and accessibility. The north-star plan (A) also adds
> an explicit gate from phase 2 to phase 3. Gov work starts only after at least
> one regulated customer has accepted Axis through its own security review and
> the external pentest (#332) is closed. This matches the sequencing already
> stated here and in #353 Stage C.

### On #353 (beachhead discovery)

> Two deliverables are proposed to make Stage A repeatable: the pilot kit (E)
> and the enterprise ERP/CRM packs (D), each built only for systems a committed
> pilot uses. The north-star plan (A) turns Stages A, B and C into explicit exit
> gates.
