# Portability conformance: operational portability with the source disconnected

[#879](https://github.com/Limes-Labs/limes-axis/issues/879) (parent #476,
depends on #876/#877/#878 and the #324 export producer) is delivered here as
one orchestration module:
[`services/api/src/axis_api/portability_conformance.py`](../services/api/src/axis_api/portability_conformance.py).
It demonstrates **operational** portability — the destination uses the
declared restored profile with independent local identity and storage while
the source instance is unavailable — by running the real #877 validator and
the real #878 restore runner in two isolated deployment facades and
publishing one machine-readable report. It implements no restore or
validation logic of its own, and no new export/restore format.

## The bounded scenario

`run_conformance_scenario` is the one reproducible runbook entrypoint:

1. **Seed** the source deployment facade (synthetic identities, policies,
   approved ontology records, object artifacts and a representative audit
   trail, only where export/restore handlers exist).
2. **Export** at the declared consistency point (#324 producer role): the
   signed #876 manifest plus per-component payload records.
3. **Disconnect** the source — permanently. From here the destination view
   refuses any read while a source path exists (`source_deployment_reachable`),
   so AC "zero runtime access to source credentials, database, identity,
   object store or application service" is enforced by construction, not
   asserted after the fact.
4. **Restore** into a clean, independently initialized destination through
   the real #877 `validate_bundle` → `acknowledge_restore_plan` → #878
   `start_restore_run`/`claim_step`/`complete_step` path on the
   destination's own database. Components without a destination handler
   stay #878 blocked steps (`missing_handler`), never fabricated successes.
5. **Evaluate** the restored destination against the approved plan and
   **publish** the report.

## What the report compares (and what it refuses to claim)

- **Logical identities, not deployment UUIDs**: only principals the operator
  explicitly mapped resolve on the destination; unmapped principals gain no
  access (the check resolves one and requires the refusal).
- **Payload digests, not narrative**: every restored component is re-digested
  with the #876 canonical digest and compared to the declared inventory.
- **Effective permissions** from the restored policy store, compared per
  principal against the plan.
- **Audit attribution**: imported evidence keeps its `source_history` origin;
  the activated destination flow appends `destination_action` evidence, so
  source history and new actions stay separately attributable forever.
- **One activated flow** plus the #878 suspended-operations list proving
  pre-export notifications/writeback/schedules remain inert.
- **Search is rebuilt, never imported**: the report carries the outcome the
  caller passes in from the #875 rebuild owner (its dedicated conformance
  lives in PR #908). Without that outcome the row is NOT RUN with the exact
  reason — missing infrastructure is never a silent skip.

### Outcome honesty (AC 6)

| Situation | Outcome |
| --- | --- |
| All rows PASS on a supported profile with no exclusions | `portable` |
| Any FAIL row (digest drift, permission drift, flow failure, validation failure) | `not_portable` with the exact reason |
| Missing destination handlers, blocked rows, NOT RUN rows, or planned export exclusions | `partially_portable` |
| Nothing evaluated (only infrastructure probes ran) | `not_evaluated` |

A minimal profile therefore **passes narrowly**: `excluded_components` are
listed in the report and keep the outcome strictly below a full #476
portability claim. Corrupt bundles and incompatible profile versions are
`not_portable` rows carrying the exact #877 reason
(`incompatible_source_axis_version`, payload digest mismatch), never crashes
and never successes.

## Report shape (AC 5)

```json
{
  "format": "axis.portability-conformance-report",
  "version": [1, 0],
  "profile": "canonical-1.0",
  "release": "1.14.0",
  "plan_digest": "…", "bundle_digest": "…",
  "profile_supported": true,
  "outcome": "portable | partially_portable | not_portable | not_evaluated",
  "missing_handlers": [], "excluded_components": [],
  "restored_components": ["…"],
  "rows": [{"check": "…", "state": "PASS|FAIL|BLOCKED|NOT RUN",
            "owner": "…", "reason": "…"}],
  "summary": {"pass": 10, "fail": 0, "blocked": 0, "not_run": 0}
}
```

Every row names the owner that decided the outcome (the #877 validator, the
#878 runner, the #876 digest, or the #875 rebuild owner), so the report is
suitable for later assurance references (#883 family).

## Non-goals respected

No guarantee for arbitrary historic versions (same-version profile only; the
adjacent-version fixture waits for its handlers), no copied credentials or
private signing keys (rebinding references stay `fresh_local_resolution_required`),
no restoration-from-mocks claim (the restore path is the real #878 runner on
a real database), and missing infrastructure is NOT RUN with a reason, never
a skip and never a destructive test.

## Tests

`services/api/tests/test_portability_conformance.py` — 20 tests mapping the
acceptance criteria: enforced source disconnect, plan matching (identities,
digests, permissions), tampering detection, audit attribution, activated
flow + inert effects, search-owner row semantics, the negative matrix
(unsupported version, missing handlers, partial restore) and reproducibility
(identical digests and rows across runs).
