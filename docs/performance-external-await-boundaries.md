# External-Await Transaction Boundaries

This document inventories every API request path that awaits an external
runtime — a model provider or the workflow runtime — and records whether that
path holds a database transaction while it waits. It is the measurement
inventory for [issue #362](https://github.com/Limes-Labs/limes-axis/issues/362)
and the reference for the phase contract described below.

Holding a transaction across an external call couples database pool occupancy
to a third party's latency and leaves the request's own evidence uncommitted
for the whole call. The second effect matters more than the first: a record
that carries an idempotency key is not durable until it is committed, so a
process that dies mid-call loses the only proof that the call was ever issued.

## Phase Contract

A request that awaits an external runtime runs in three phases:

1. **Prepare and commit.** Evaluate permissions, policy, routing and egress,
   write the record that carries the idempotency key and the decision evidence,
   then commit. The transaction ends and the pooled connection is returned.
2. **External await.** Call the provider or workflow runtime with no open
   transaction and no lazy attribute load.
3. **Idempotent finalize.** Open a new transaction and record the outcome
   against the committed record. If this phase never commits, the record stays
   in its non-terminal state, which is the fail-closed position: a later
   delivery of the same idempotency key replays that record instead of issuing
   a second external call.

Phase 1 commits the whole request session. A caller may therefore only take
this contract when it owns the request transaction and the session holds
nothing but its own prepared work. A path that embeds an external call inside a
larger unit of work — an agent run, for example — must not commit, because it
would also commit its own partial state.

## Inventory

Seven request handlers in `services/api/src/axis_api/main.py` are `async def`
and take the synchronous `PersistenceRepository`.

| Request handler | External await | Owner | Written before the await | Phase contract |
| --- | --- | --- | --- | --- |
| `manufacturing_agent_run` | Model provider and workflow signal | `agent_runs.py` | Agent run row and context-read audit events | Not applied |
| `manufacturing_connector_evidence_invariant_snapshot_export_request_decision` | Workflow signal | `connector_evidence_invariants.py` | Approval decision record | Not applied |
| `manufacturing_connector_manual_import_decision` | Workflow signal | `connector_manual_imports.py` | Approval decision record | Not applied |
| `manufacturing_action_run` | Workflow signal | `action_runs.py` | Action run row | Not applied |
| `manufacturing_action_run_outcome` | None | `action_runs.py` | Not applicable | Not applicable |
| `manufacturing_approval_decision` | Workflow signal, unless `AXIS_APPROVAL_DECISION_OUTBOX_ENABLED` is set | `approval_decisions.py` | Decision record, and the outbox row when enabled | Superseded by the outbox |
| `platform_model_invocation_create` | Model provider | `model_invocations.py` | Requested invocation row | **Applied** |

Two entries need explanation.

`manufacturing_action_run_outcome` is `async def` for interface symmetry with
the other action-run handlers and awaits nothing external. It is listed so that
a future reader does not re-derive the same conclusion.

`manufacturing_approval_decision` already has the stronger remedy. With
`AXIS_APPROVAL_DECISION_OUTBOX_ENABLED`, the decision and its delivery
intent are written in one transaction and a dispatcher performs the signal, so
no external call happens inside the request at all. See
[the approval decision outbox](./approval-decision-outbox.md). An outbox suits
a fire-and-forget signal; it does not suit a model invocation, whose caller
waits for the provider response in the same request.

## Applied Path: Model Invocation

`POST /platform/models/invocations` commits the requested invocation before the
provider call. Two behaviours follow from that commit and are contract, not
side effects:

- A duplicate delivery that arrives while the first call is in flight now finds
  the committed record and replays it, so at most one provider call is issued
  per idempotency key. Previously both deliveries called the provider and one
  of them failed on the uniqueness constraint at the end of the request.
- A replayed record whose provider call has not yet been recorded is returned
  with status `requested` and a note stating that no result is available and
  that no second call was issued. Callers must not read `requested` as failure.

A record left in `requested` by an interrupted process is never finalized
automatically, because the outcome of the provider call is unknown and Axis
does not fabricate one. Recovering or expiring those records is operator work
today; automating it is follow-up scope, not part of this contract.

Browser session refresh already runs the same shape — it commits an atomic
`active` -> `refreshing` claim before the IdP token exchange and reaps stale
claims in `run_orphaned_session_sweep_job` — so the sweep pattern exists in the
repository. It is not reused here as-is: a stale session claim can be resolved
by revoking the session, while an invocation left `requested` cannot be
resolved without knowing whether the provider ran.

## Verification

| Property | Evidence |
| --- | --- |
| No transaction is open during the provider call | `test_invoke_model_holds_no_transaction_across_the_provider_call` |
| Pool occupancy during the provider call is 0, against a measured baseline of 1 | `test_provider_call_occupies_no_pooled_connection` and `test_provider_call_occupies_a_pooled_connection_for_embedded_callers` |
| An interrupted provider call leaves the idempotency key durable | `test_interrupted_provider_call_keeps_the_requested_row_durable` |
| A retry after an interruption issues no second provider call | `test_retry_after_an_interrupted_call_does_not_call_the_provider_again` |
| A concurrent duplicate replays instead of failing | `test_concurrent_duplicate_delivery_replays_instead_of_failing` |
| A concurrent duplicate with a different payload still conflicts | `test_concurrent_duplicate_with_a_different_payload_still_conflicts` |
| HTTP handler releases the pool before dispatch | `test_http_invocation_releases_pool_before_provider` |
| Overlapping deliveries see the committed in-flight claim | `test_overlapping_deliveries_replay_the_committed_in_flight_claim` |
| Prepare and finalize commit failures preserve dispatch and metering boundaries | `test_commit_failure_never_reissues_a_provider_call` |
| Embedded callers keep their transaction semantics | `test_invoke_model_keeps_the_caller_transaction_when_not_the_owner` |

All of the above live in `services/api/tests/test_model_invocations.py`.

## Measured Pool Occupancy Under Load

The structural tests above prove that no transaction is open across the provider
call. This section measures what that is worth under arrivals, using the
[versioned workload contract](./performance-baseline.md) delivered by
[issue #361](https://github.com/Limes-Labs/limes-axis/issues/361).

The evidence is the retained
[performance-v1 baseline](./benchmarks/performance-v1/README.md). It was captured
on 2026-09-07, after this contract was applied to the model-invocation handler,
so its `model-invocation` journey already exercises the phase split. No new
capture is needed to read it.

Two of the four journeys await an external runtime inside the request, and they
sit on opposite sides of this contract:

- `workflow-signal` awaits a synthetic workflow acknowledgement of 20 ms with
  its transaction still open. It is one of the handlers listed as *Not applied*
  in the inventory above.
- `model-invocation` awaits a synthetic provider response of 50 ms under the
  phase contract.

Both stay at `pool_peak` 1 in every trial of both shapes, so for these two the
mean checked-out time per request divided by the median request latency is
exactly the fraction of the request during which a connection was held. That
reading does not hold for `console`, which reaches 3-5 concurrent connections in
the enterprise shape; it is used here only for the two journeys that never
exceed one.

Values are medians of the three per-trial figures in the retained batches.

| Shape | Journey | External wait | p50 / p95 / p99 ms | Connection held per request | Fraction of request holding a connection |
| --- | --- | ---: | ---: | ---: | ---: |
| SME | `workflow-signal` | 20 ms | 38.92 / 42.00 / 42.33 | 30.14 ms | 77.5% |
| SME | `model-invocation` | 50 ms | 70.59 / 72.96 / 75.45 | 10.74 ms | 15.2% |
| Enterprise | `workflow-signal` | 20 ms | 29.06 / 33.38 / 36.51 | 25.88 ms | 89.1% |
| Enterprise | `model-invocation` | 50 ms | 60.95 / 61.90 / 67.98 | 5.11 ms | 8.4% |

The comparison is not a controlled experiment: the two journeys persist different
state and issue different statements, so the absolute figures are not
attributable to the transaction boundary alone. The *direction* is what the
measurement settles. `model-invocation` waits on an external runtime for two and
a half times as long as `workflow-signal` and holds a connection for a fifth to a
tenth as much of its request. If a connection were held across the await, the
journey with the longer wait would hold one for the larger share of its request.
It holds one for the smaller share, by five to ten times.

The five-minute
[enterprise model soak](./benchmarks/performance-v1/soak-enterprise-model.json.gz)
agrees over a longer window: 1,200 of 1,200 arrivals successful, p95 73.89 ms,
p99 75.61 ms, 14.72 connection-seconds for the batch — 12.3 ms per request
against a 70.05 ms median — and peak and final checked-out connections of 1 and
0.

An independent re-run on different hardware and a later date reproduces the
shape: three trials per profile of the `model-invocation` journey, 360 and 720
arrivals, every trial `PASS`, `pool_peak` 1, `pool_at_end` 0, and 10.4% (SME)
and 11.5% (enterprise) of request time holding a connection. That run is
corroboration, not a retained artifact: its host was not idle, and the numbers
above come from the committed baseline instead so that any reader can reproduce
this reading from the repository alone. Its scheduler lag stayed at p95 1.6 ms.

`NOT RUN`: an attribution comparison isolating this contract. The only runtime
without it is twenty commits and twenty-seven API files back, and
[the measurement contract](./performance-baseline.md) forbids modifying
production code to manufacture a baseline. The figures above therefore establish
the journey's absolute tail latency and pool behaviour, not a measured speedup.

`NOT RUN`: PostgreSQL pool contention, real provider latency and hosted capacity.
This is a single process on SQLite with fake identity and external ports, per
[ADR 0016](./adr/0016-performance-measurement-contract.md). Connection-pool
behaviour under a real driver and a shared database is a different measurement.

`NOT RUN`: the phase contract for the four remaining external-await handlers.
Each writes state that belongs to a larger unit of work and needs its own
analysis of what may become durable before the await.

The synchronous repository still runs on the event loop inside these
`async def` handlers. That is a separate concern from transaction scope and is
not addressed here.
