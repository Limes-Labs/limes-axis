# Writeback contracts: mapping a typed action onto one governed external mutation

[#510](https://github.com/Limes-Labs/limes-axis/issues/510) (parent
[#509](https://github.com/Limes-Labs/limes-axis/issues/509)) is delivered here as
one contract module:
[`services/api/src/axis_api/writeback_contracts.py`](../services/api/src/axis_api/writeback_contracts.py).
It is vocabulary plus **fail-closed resolution**: a registered adapter profile
for a schema-bound REST mutation, the mapping from a typed Axis action input to
one remote request with a typed normalized response, an immutable tenant-bound
registry, and an adapter conformance interface.

It performs no I/O. It owns no retry, outbox, conflict resolution or
reconciliation state machine (those are
[#511](https://github.com/Limes-Labs/limes-axis/issues/511) and
[#512](https://github.com/Limes-Labs/limes-axis/issues/512)), no vendor business
schema, no release process and no browser-facing write endpoint.

## An enabled target grants nothing

Enabling a writeback target does **not** authorize invoking any action. The
registry answers *where* an already-approved typed action may write; the
action's own approval, risk and permission rules
([`axis_api/actions.py`](../services/api/src/axis_api/actions.py),
[`docs/platform-actions.md`](platform-actions.md)) remain the authority on
*whether* it may run. Resolution rechecks the host facts on every attempt rather
than caching a decision:

| Fact | Owner | Failure code |
| --- | --- | --- |
| Tenant binding of registry, target and context | this contract | `tenant_mismatch` |
| Target enabled for this tenant | this contract | `target_disabled`, `target_unknown` |
| Adapter registered, writeback-capable and currently ready | adapter registration | `adapter_not_ready`, `adapter_not_writeback_capable` |
| Credential **handle** reference matches the target | credential-handle owner | `credential_reference_mismatch` |
| Lease present at execution time | [`connector_credential_leases.py`](../services/api/src/axis_api/connector_credential_leases.py) | `credential_lease_required` |
| Egress evaluated against the **resolved** authority under **this** policy | [`connector_egress_policies.py`](../services/api/src/axis_api/connector_egress_policies.py) | `egress_not_evaluated`, `egress_target_mismatch` |
| Mapping schema still matches the action input schema | this contract | `mapping_schema_mismatch` |
| Operation and precondition supported by the adapter | this contract | `unsupported_operation`, `unsupported_precondition` |
| Exact approved payload digest | approval owner; the contract only compares | `approval_payload_mismatch` |
| Request within the declared byte bound | this contract | `request_too_large` |

Every one of those failures happens **before** any transport exists, because the
module has none. Resolution returns either one complete
`WritebackRequestPlan` or a fixed
[`WritebackErrorCode`](../services/api/src/axis_api/writeback_contracts.py)
that never echoes a payload, endpoint or credential.

## Credentials are referenced, never copied

`WritebackTargetSpec` carries an opaque `credential_handle_ref` and
`egress_policy_ref`; the lease is supplied by the host at execution time as
`credential_lease_ref`. References are validated as opaque identifiers: a URL,
a query string, a whitespace-separated value or a credential-looking word
(`password`, `token`, `api_key`, `bearer`) is rejected at construction, so secret
material cannot be smuggled into a target record or into the audit projection.
`WritebackRemoteRequest` marks authority, path and body as `repr=False`, and
`WritebackEvidence` (the audit-safe projection) contains only identifiers,
versions, digests, operation kind, idempotency mode and a byte count.

## Mapping is narrow on purpose

`WritebackOperationMapping` binds typed action input fields to declared remote
fields for exactly one operation, with:

- one allowlisted method (`PUT`, `PATCH`, `POST`, `DELETE`) and an **absolute
  relative path template** with no traversal or query component;
- placeholders that must name a declared remote field, substituted only from
  typed input and only when each value matches a single safe path segment;
- protected headers from a fixed allowlist whose values are **host-derived**
  (`credential_lease`, `approval_digest`, `idempotency_key`, `correlation_id`,
  `contract_version`) — a caller cannot inject a header name or a header value;
- bindings that cannot name transport or raw payload fields (`raw_body`, `body`,
  `sql`, `query`, `url`, `host`, `authority`, `headers`, `method`, `path`);
- a bounded response projection that keeps the remote id, version, receipt,
  correlation and reason-code fields and a declared maximum response size;
- delete mappings that may only bind path parameters, and a request model that
  refuses a replacement body on `DELETE`.

Provided action input must be a subset of both the action's declared schema
properties and the mapping's bound fields: an unbound field is rejected rather
than silently dropped, because the approval covers the whole payload.

## Remote request, acknowledgement, result, verification

The contract keeps four things apart, because conflating them is how a
mutation gets repeated destructively:

| Concept | Model | Meaning |
| --- | --- | --- |
| Remote request | `WritebackRequestPlan.request` | What was approved and is about to be sent |
| Acknowledgement | `WritebackAcknowledgement` | The remote accepted or refused to process it (`accepted`) |
| Business result | `WritebackBusinessResult.state` | `succeeded`, `rejected`, `conflict`, `outcome_unknown`, `not_sent` |
| Source-of-truth verification | `WritebackSourceVerification` | A later observation that the remote change is actually visible |

`normalize_remote_outcome` maps one observed `RemoteOutcome` (status plus
digested body, never the body) onto those states: `2xx` is `succeeded`, `4xx` is
`rejected`, `409`/`412` is `conflict` with `WritebackConflictEvidence`, and
`408`/`425`/`429`/`5xx` is `outcome_unknown`. A request that was never sent is
`not_sent` with `accepted = False`. Acknowledgement is never promoted into
verification: a decided verification result requires its own timestamp and
observation reference, and an unresolved state cannot be `confirmed`.

## Idempotency is stated, not assumed

`WritebackIdempotencyPlan` reports `mode`, whether the key comes from a
host-derived digest, `repeat_safe`, `exactly_once` and
`outcome_unknown_after_timeout`. Only an adapter that declares
`native_idempotency: supported` **and** declares an `idempotency-key` protected
header earns `repeat_safe`/`exactly_once`, and resolution refuses the claim
without that mechanism (`invalid_operation_mapping`). An adapter with
unsupported or unknown native idempotency yields `mode: none`, no exactly-once
claim, and a timeout after send is explicitly `outcome_unknown` — never
"failed and safe to repeat".

## Registry semantics

`WritebackTargetRegistry` is bound to one tenant at construction:

- `register_adapter` records the capability, readiness and the conformance scope
  the adapter actually earned; a second registration for the same type/version is
  refused, and a capability that does not claim `writeback` cannot be declared at
  all, so a read-only source profile cannot become a mutation target.
- `register_target` appends an immutable, monotonically versioned target record
  (version 1, 2, ...) and requires the registered adapter's capability digest to
  match. Existing versions are never rewritten.
- `set_enabled` is the only mutating operation, and it changes activation state
  alone — not the definition, not the digest. Enabling version 1 after
  registering version 2 leaves version 2 unactivated, and `catalog()` with no
  enabled target is empty rather than silently falling back to another version.
- `register_mapping` is append-only per `(mapping_ref, version)`, and
  `register_action_binding` refuses a binding whose declared action-input-schema
  digest does not match the mapping, or whose action does not match the mapping's
  action id.
- `catalog()` is the public-safe authoring projection: connector, resource kind,
  adapter type/version, display name, operations, acknowledgement kind, native
  idempotency, preconditions and readiness. It exposes no endpoint, path or
  credential reference.

The plan digest is computed by `compute_plan_digest` over the canonical contract
version, tenant, actor, action, approval, target ref and version, spec and
mapping digests, operation kind, resource, precondition, method, path and body
digest. Changing the payload, the mapping version, the target version or the
precondition changes the digest, so an approval can never be replayed against a
different operation.

## Adapter conformance

`run_adapter_conformance` checks an adapter's **declared** claims against its
registration and mapping: writeback capability, idempotency declaration,
precondition support, bounded response mapping, result mapping and error
taxonomy. Statements that were not exercised are reported as `not_run` — an
empty observation set cannot earn a clean report — and the report carries the
scope its owner claims (`contract_only`, `local_wire_level`,
`provider_verified`). Findings carry fixed codes, never payload or endpoint
detail.

## What is implemented, and what is not

Implemented and tested here: target, mapping, capability, readiness, request and
normalized-response schemas; the tenant-bound versioned registry with explicit
activation; credential/egress reference binding; typed-action resolution; plan
digests; outcome normalization with conflict evidence; and the adapter
conformance report.

Not implemented here, by design:

- **No transport.** Nothing in this module contacts a remote system, so the
  contract cannot be used to reach an arbitrary endpoint.
- **No retries, outbox or reconciliation.** [#511](https://github.com/Limes-Labs/limes-axis/issues/511)
  owns durable retries and remote idempotency; [#512](https://github.com/Limes-Labs/limes-axis/issues/512)
  owns conflict resolution. This contract only names the conflict.
- **No vendor semantics.** ERP/CRM business schemas stay in packs, resolved by
  the vendor extension contract.
- **No HTTP authoring route yet.** The public-safe projection (`catalog()`,
  `WritebackTargetPublicMetadata`) and its tests are here, but exposing it over
  the operations API needs a configuration source for the registry, which
  belongs to [#880](https://github.com/Limes-Labs/limes-axis/issues/880) — the
  slice that registers real schema-bound REST mutation adapters and targets.
  Registering an endpoint over an always-empty in-process registry would be a
  decorative surface, and
  [#509](https://github.com/Limes-Labs/limes-axis/issues/509) explicitly rules
  out an arbitrary direct write endpoint. The console/app/workflow authoring
  surfaces consume `catalog()` once that source exists; the acceptance criterion
  for that exposure is tracked by the adapter slices, not satisfied by a route
  that can never return a target.
- **No production claim.** Tests run against local schemas only: no live
  ERP/CRM write, no asynchronous callback receiver, no second approval or
  idempotency service, no vendor catalog and no readiness claim.
