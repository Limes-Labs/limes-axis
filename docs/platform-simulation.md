# Platform Replay And Simulation

The replay and simulation foundation turns existing workflow history and audit
evidence into public-safe replay preview artifacts and governed policy-set
version diff previews.

It is intentionally limited. The slice does not execute Temporal deterministic
replay, mutate workflow state, compare arbitrary policies, persist simulation
outputs or expose raw action payloads. It creates a first inspectable contract
for future replay, wider policy diffing and audit-backed simulation.

## Demo Endpoint

```text
GET /demo/manufacturing/simulation/replay
```

The endpoint derives replay artifacts from existing Postgres records:

- `workflow_runs`;
- `workflow_timeline_events`;
- `audit_events`.

Query filters:

- `tenant_id`;
- `workflow_id`;
- `limit`.

The response includes:

- simulation status and metrics;
- replay artifact id, workflow id, workflow name and audit scope;
- replay mode and determinism status;
- timeline event count and audit event count;
- redacted audit evidence;
- deterministic policy preview results;
- governed connector policy-set version diff previews;
- public-safe simulation notes.

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
the replay response or console fallback seed.

Future Platform work should connect this contract to:

- Temporal deterministic replay;
- arbitrary policy comparison over historical events;
- retention-aware replay windows;
- simulation results persisted as governed audit artifacts.

## Verification

The slice is covered by:

- API unit tests for tenant-scoped artifact construction;
- API unit tests for workflow filter behavior;
- API unit tests for policy-set version diff preview construction;
- API endpoint and OpenAPI exposure tests;
- web unit tests for fallback artifacts, policy-set diffs and persisted-data
  selection;
- Playwright smoke tests for `/simulation` rendering, including policy-set diff
  metadata.
