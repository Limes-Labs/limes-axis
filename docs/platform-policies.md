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

Action run creation consults the policy engine for the `action_execution`
scope before persisting a new run:

- `deny` → the run is rejected with a `POLICY_VIOLATION` error, no action run
  row is written and a `platform.policy.enforcement.denied` audit event is
  appended with the full decision payload.
- `require_approval` → the run is forced into the existing approval-gated
  path: it persists with `approval_required` status and reuses the existing
  approval mechanics, including the outcome-recording block until approval.
- `allow_with_evidence` → the run proceeds and the decision is recorded in the
  action-run audit payload.
- No matching policy → existing behavior is unchanged (default allow); the
  audit payload records no policy decision.

Idempotent action-run replays return the previously persisted record without
re-evaluating policy, so replays never mutate state under a newer policy.

## Boundaries

The engine is a foundation slice. It does not yet include:

- a policy console UI;
- enforcement points beyond action run creation;
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
- OIDC binding tests cover actor and tenant impersonation rejection and
  read-scope enforcement for authenticated requests.
- The OpenAPI contract is regenerated and checked; migration identifier tests
  cover the `platform_policies` schema.
- Public documentation avoids customer data, personal names, contacts,
  pricing, credentials and deployment secrets.
