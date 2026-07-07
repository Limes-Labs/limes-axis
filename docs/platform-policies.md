# Platform Policy Engine

The Platform policy engine slice introduces a general, tenant-scoped policy
foundation for governed platform behavior beyond connector promotion. It
generalizes the connector promotion policy patterns — typed rule conditions,
append-only revisions, idempotent writes and audit evidence — into a policy
surface that can gate action execution and approval requirements.

Policy evaluation is deterministic: the same tenant, scope and evaluation
context always produce the same decision. Evaluation never calls a model
provider, never performs external egress and never mutates state.

## Current Scope

- `GET /platform/policies` lists tenant-scoped platform policies with optional
  scope and status filters.
- `POST /platform/policies` authors a new policy as revision 1 with
  `platform.policy.authored` audit evidence. Authoring requires the
  `platform:policy:author` scope.
- `GET /platform/policies/{policy_id}` returns the policy with its full
  append-only revision history and the current active revision.
- `POST /platform/policies/{policy_id}/revisions` appends a new revision with
  an idempotency key, supersedes the previous revision and writes
  `platform.policy.revised` audit evidence. Revising requires the
  `platform:policy:revise` scope.
- `POST /platform/policies/evaluate` is a dry-run evaluation endpoint that
  returns the typed `PlatformPolicyDecision` for a tenant, scope and context.
  Evaluation requires the `platform:policy:evaluate` scope.
- Authenticated list and detail reads require the `platform:policy:read` scope
  from the OIDC principal; the authenticated tenant must match the requested
  tenant. In optional local demo mode, unauthenticated reads remain available
  for public-safe walkthroughs.
- When an OIDC bearer token is present, or when auth is required by
  configuration, policy mutations and evaluations derive tenant, actor and
  scopes from the verified principal and reject actor or tenant impersonation
  before persistence.
- In unauthenticated local demo mode (`AXIS_OIDC_AUTH_REQUIRED` disabled and no
  bearer token attached), tenant and actor scopes are self-asserted in the
  request body, matching the existing demo route convention. The policy routes
  are only truly OIDC-bound when authentication is present or required.

## Policy Model

A platform policy declares:

- `policy_id`, `policy_version`, `display_name` and `description`;
- a `scope` that names the governed domain: `action_execution` or
  `approval_requirement` (the enum is extensible for future domains);
- an `effect`: `require_approval`, `deny` or `allow_with_evidence`;
- typed, validated rule conditions.

Rule conditions follow the allowed-values style of connector promotion
policies rather than a new DSL:

- `action_domains`: matching action domains (for example `Operations`);
- `risk_levels`: matching typed action risk levels (`low`, `medium`, `high`,
  `critical`);
- `autonomy_levels`: matching autonomy levels (`L0`–`L4`);
- `requested_amount_at_least`: a numeric threshold that matches when the
  context carries a requested amount greater than or equal to the threshold.
  Amount matching fails closed: if the request carries an amount value that is
  malformed or non-finite (for example `nan`, `1e999` or an unparseable
  string), amount-conditioned policies count as matched so a malformed amount
  can never evade an amount gate. A request without any amount field keeps the
  normal no-match semantics. When the action input schema declares the amount
  field as a `number`, garbage values are already rejected as schema
  violations (`VALIDATION_FAILED`, 422) before the policy engine runs; the
  fail-closed matching stays load-bearing for `string`-declared amount fields,
  which carry string-encoded numbers that only the policy layer parses.

Empty condition lists match any value; a rule must declare at least one
condition. Malformed conditions — unknown fields, unsupported risk or autonomy
levels, negative thresholds or an empty rule — are rejected with
`VALIDATION_FAILED` before any policy row or audit event is written.

## Revisions

Policy revisions are append-only. Each revision is a new row with an
incremented `revision_number`; the previous revision is marked `superseded`
and records `replaced_by_revision_number`. Revision writes require an
idempotency key: replaying the same request returns the persisted revision
with `idempotent_replay=true` and HTTP 200, while reusing the key with a
different payload returns a `POLICY_VIOLATION` conflict. Superseded revisions
stay readable in the policy detail response but are never evaluated.

A partial unique index on `(tenant_id, policy_id)` where `status = 'active'`
enforces the single-active-revision invariant at the database level, and the
evaluator breaks residual ties deterministically by highest revision number.

## Evaluation and Precedence

Evaluation loads the active revisions for the tenant and scope, matches each
policy's conditions against the typed context (action id, action domain, risk
level, autonomy level, requested amount) and returns a decision containing the
winning policy, its revision, the effect and an evidence payload with the
matched constraints.

When no policy matches, the decision effect is `allow` (default allow). When
multiple policies match, the winner is selected by the deterministic
precedence rule `effect_severity_then_policy_id`:

1. `deny` beats `require_approval`, which beats `allow_with_evidence`;
2. ties on effect are broken by the lexicographically smallest `policy_id`.

All matched policies are reported in the decision so reviewers can see which
gates applied beyond the winning one.

## Enforcement Model

The `action_execution` scope is enforced at three lifecycle points. Every
denial appends a `platform.policy.enforcement.denied` audit event with the
full decision payload and an `enforcement_point` marker, and returns a
`POLICY_VIOLATION` error.

Action run creation (`enforcement_point=action_run_creation`):

- `deny` → the run is rejected and no action run row is written.
- `require_approval` → the run is forced into the existing approval-gated
  path: it persists with `approval_required` status and reuses the existing
  approval mechanics, including the outcome-recording block until approval.
- `allow_with_evidence` → the run proceeds and the decision is recorded in the
  action-run audit payload.
- No matching policy → existing behavior is unchanged (default allow); the
  audit payload records no policy decision.

Approval decision transition (`enforcement_point=approval_decision_transition`),
which can create or advance approval-gated action runs to
`approved_for_execution`:

- The evaluation context is enriched from the persisted action registry
  (domain, risk level, autonomy ceiling) and from the linked action-run payload
  (requested amount) when they exist, so autonomy- and amount-conditioned
  policies block at the approval transition, not only at the outcome check.
- `deny` → an `approve` decision is rejected before any approval, workflow or
  action-run state is written; only the denial audit evidence persists.
  `reject` and `request_changes` decisions are not execution-advancing and stay
  available, so reviewers can still close out denied proposals.
- `require_approval` → satisfied by the approval being decided; the decision
  proceeds normally and the matched policy is recorded in the
  `approval.decision.recorded` audit payload and response.
- `allow_with_evidence` → the decision proceeds and the matched policy is
  recorded as evidence in the approval audit payload.

Action run outcome recording (`enforcement_point=action_run_outcome`), which
advances runs into terminal states:

- `deny` policies are re-evaluated before the execution-advancing outcomes
  `dry_run_completed` and `execution_completed`, so a policy authored after run
  creation still blocks completion. `execution_failed` and `execution_blocked`
  remain recordable as failure evidence.
- Degraded context fails closed: when the enforcement context cannot be
  derived because the action is missing from the persisted registry, any
  active deny policy for the tenant and scope blocks the execution-advancing
  outcome, and the denial evidence carries `context_degraded=true` with a
  `fail_closed` decision. When no deny policies exist, the outcome proceeds
  and the `action.run.outcome.recorded` audit payload is marked with
  `platform_policy_context_degraded=true` for review.
- `require_approval` is not re-evaluated at this point: it was satisfied at
  creation or approval time and must not loop.

Idempotent replays of already-persisted records return the stored record
without re-evaluating policy, so replays never mutate state under a newer
policy.

## Console

The governance console exposes the policy engine — reads, dry-run evaluation
and authoring — under the `Policies` navigation section:

- `/policies` lists the tenant-scoped policy registry through
  `GET /platform/policies` with scope and status filters, effect and status
  signals, summarized typed conditions and revision markers. When the API is
  unreachable the page shows the standard API-required state; there are no
  browser-local fallback policy records.
- `/policies/{policy_id}` reads `GET /platform/policies/{policy_id}` and shows
  the full active definition, the typed rule conditions (action domains, risk
  levels, autonomy levels, amount threshold), the deterministic precedence
  explanation (`deny` beats `require_approval` beats `allow_with_evidence`,
  ties broken by smallest policy id, default allow without a match) and the
  append-only revision history with authorship, timestamps and superseded
  markers.
- The detail page includes a dry-run evaluation panel that composes a typed
  evaluation context (scope, action domain, risk level, autonomy level,
  requested amount) and posts it to `POST /platform/policies/evaluate`. The
  returned decision — effect, matched policies with revisions, evaluated
  policy count, precedence rule and evidence payload — is rendered inline and
  clearly labeled as a dry run that never mutates state.

- `/policies` also carries the authoring form. It creates revision 1 through
  `POST /platform/policies` with typed condition builders (multi-select risk
  and autonomy levels, comma-separated action domains, a numeric amount
  threshold) and mirrors the server rules client-side before anything is sent:
  the `^[a-z0-9][a-z0-9_-]*$` policy id pattern, required-field lengths, the
  at-least-one-condition rule and the finite non-negative amount check. Server
  rejections are surfaced inline — 409 duplicate ids on the policy id field,
  `VALIDATION_FAILED` condition errors on the condition builders and 403
  permission denials with the required authoring scope. An advisory preview
  runs the dry-run evaluate endpoint for the drafted scope against the
  policies already persisted for the tenant, plus a client-side check of
  whether the drafted conditions would match the sampled context; the draft
  itself is never evaluated by the API until it is authored.
- `/policies/{policy_id}` carries a revise form pre-filled from the current
  revision. It appends through
  `POST /platform/policies/{policy_id}/revisions` with a client-generated
  idempotency key (`crypto.randomUUID`), distinguishes a 201 new revision from
  a 200 idempotent replay ("revision already applied") and explains 409
  idempotency-key conflicts, rotating to a fresh key since a conflicted key
  can never succeed. Successful writes refetch the registry and detail
  through the standard console refresh path.
- The revision history offers a lightweight compare: any superseded revision
  can be diffed against the current one field by field (name, description,
  version, effect, each typed condition, notes) with changed, added and
  removed values marked inline — no diff dependency involved.

All console reads and writes go through the shared Axis API fetch layer, so
OIDC bearer sessions, API-owned session cookies and the CSRF double-submit
header attach the same way as on every other console surface. The authoring
affordances render optimistically like the rest of the console's action
surfaces (for example approval decisions): the forms are always visible and
the API enforces the `platform:policy:author` / `platform:policy:revise`
scopes, with 403 denials surfaced inline. No policy capability remains
API-only for a single policy's lifecycle; only bulk or cross-policy tooling
(such as policy simulation over historical events) stays outside the console.

## Boundaries

The engine is a foundation slice. It does not yet include:

- enforcement points beyond action run creation, approval decision transitions
  and action run outcome recording;
- policy simulation over historical events for platform policies;
- approval-workflow-gated policy enablement or rollback bundles like the
  connector promotion policy sets.

Those capabilities remain Platform work and should be implemented behind the
typed policy scopes, the append-only revision store and the existing approval
and audit boundaries.

## Acceptance Notes

- API tests cover policy authoring, duplicate conflicts, permission denial,
  malformed condition rejection with `VALIDATION_FAILED`, revision append,
  idempotent replay, idempotency conflicts and tenant isolation for list,
  detail, evaluation and enforcement paths.
- Evaluation tests cover determinism (same input, same decision), default
  allow without matching policies, deterministic multi-match precedence,
  amount-threshold matching and superseded-revision exclusion.
- Enforcement tests cover the deny, forced-approval and allow-with-evidence
  paths on action run creation, including audit evidence and the unchanged
  default behavior without policies.
- Lifecycle enforcement tests cover deny blocking on approval decision
  transitions (with reject decisions still available), require-approval
  satisfaction on approval paths without looping, deny re-evaluation on
  execution-advancing outcome recording and non-finite requested-amount
  hardening for payloads, evaluation contexts and rule conditions.
- Fail-closed tests cover malformed-amount matching against amount-conditioned
  deny policies (and unchanged behavior without them), degraded-context denial
  and audit marking on outcome recording, and autonomy-conditioned denial at
  the approval transition through registry-enriched context.
- A storage test proves the single-active-revision partial unique index
  rejects a second active revision of the same policy.
- OIDC binding tests cover actor and tenant impersonation rejection and
  read-scope enforcement for authenticated requests.
- The OpenAPI contract is regenerated and checked; migration identifier tests
  cover the `platform_policies` schema.
- Console tests cover the authoring slice: unit tests for the client-side
  mirror of the server validation rules, the exact create and revise payload
  shapes, the 201/200-replay/409/422/403 result mapping and the revision
  compare logic, plus route-mocked browser smoke tests for the validation
  gate, the create round-trip with the CSRF header and the revise and compare
  surfaces on the detail page.
- Public documentation avoids customer data, personal names, contacts,
  pricing, credentials and deployment secrets.
