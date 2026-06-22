# Platform Replay And Simulation

The replay and simulation foundation turns existing workflow history and audit
evidence into public-safe replay preview artifacts and governed policy-set
version diff previews. Replay outputs can also be persisted as governed audit
artifacts for later inspection, and replay responses enforce retention-aware
query windows before returning history or persisted output records.

It is intentionally limited. The slice does not execute Temporal deterministic
replay, mutate workflow state, compare arbitrary policies or expose raw action
payloads. It creates a first inspectable contract for future replay, wider
policy diffing and audit-backed simulation.

## Demo Endpoint

```text
GET /demo/manufacturing/simulation/replay
POST /demo/manufacturing/simulation/replay/outputs
```

The endpoint derives replay artifacts from existing Postgres records:

- `workflow_runs`;
- `workflow_timeline_events`;
- `audit_events`.

Query filters:

- `tenant_id`;
- `workflow_id`;
- `limit`.
- `retention_days`;
- `legal_hold`.

The response includes:

- simulation status and metrics;
- replay retention policy, window start, legal-hold state and excluded counts;
- replay artifact id, workflow id, workflow name and audit scope;
- replay mode and determinism status;
- timeline event count and audit event count;
- redacted audit evidence;
- deterministic policy preview results;
- governed connector policy-set version diff previews;
- persisted replay output records when present;
- public-safe simulation notes.

`POST /demo/manufacturing/simulation/replay/outputs` persists one derived
artifact for a workflow. The request requires:

- `simulation_output_id`;
- `workflow_id`;
- `idempotency_key`;
- `requested_by`;
- `actor_scopes` containing `simulation:replay:persist`;
- `reason`;
- `retention_window_days`.

The write creates `simulation.replay_output.persisted` audit evidence, stores a
SHA-256 `output_hash`, persists the redacted artifact payload and returns `200`
on idempotent replay without writing duplicate audit events.

Replay query retention is enforced before artifacts and outputs are returned:

- timeline events are filtered by event occurrence time;
- audit events are filtered by ledger creation time;
- persisted outputs use the stricter of the query `retention_days` value and
  each output's own `retention_window_days`;
- `legal_hold=true` suspends exclusion and marks the response as not retention
  enforced;
- excluded timeline, audit and output counts are returned in `retention_window`.

This is query-time retention enforcement only. It does not delete records,
operate a production legal-hold workflow or claim immutable archive hardening.

## Console Behavior

The `/simulation` page first loads
`/demo/manufacturing/simulation/replay`. If no persisted artifacts are
available, or the API is unavailable, it falls back to the local synthetic
manufacturing replay seed.

The page lets an operator inspect:

- replay artifacts by workflow;
- policy preview outcomes;
- baseline versus simulated decision;
- baseline versus candidate policy-set version decisions;
- persisted output hash, retention and audit evidence;
- replay retention window and excluded record counts;
- timeline evidence;
- audit event types and evidence references.

The page is read-only. It does not trigger live workflow replay, action
execution, connector mutation or policy rollout.

## Governance Boundary

The first policy preview is `human-approval-required`. It checks whether the
historical workflow and audit evidence should stay blocked until the required
owner approval signal is present.

The first policy-set diff preview compares the governed connector policy set
`policy_set_connector_asset_required_20260622_v2` with the rollback candidate
`policy_set_connector_asset_required_20260622_rollback` over each artifact's
historical timeline and audit events. It reports changed policy ids, baseline
and candidate decisions, `changed_outcome_detected` status and the synthetic
audit event type `connector.promotion_policy_set.simulated_diff`. It does not
activate a policy set or execute connector mutation.

Artifacts expose redacted metadata only. Raw action payloads are not returned in
the replay response, and the console requires API-backed replay artifacts.

Future Platform work should connect this contract to:

- Temporal deterministic replay;
- arbitrary policy comparison over historical events;
- physical retention deletion jobs and production legal-hold workflows.

## Verification

The slice is covered by:

- API unit tests for tenant-scoped artifact construction;
- API unit tests for workflow filter behavior;
- API unit tests for policy-set version diff preview construction;
- API unit tests for persisted output write, permission and idempotency;
- API unit tests for replay retention filtering and legal-hold bypass;
- API endpoint and OpenAPI exposure tests;
- web unit tests for replay artifacts, persisted outputs, policy-set diffs and
  persisted-data selection;
- Playwright smoke tests for `/simulation` API-required behavior.
