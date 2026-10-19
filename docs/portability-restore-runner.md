# Portability restore runner: resumable plan execution

[#878](https://github.com/Limes-Labs/limes-axis/issues/878) (parent #476) is
delivered here as slice 3/4, stacked on the #876 manifest contract (PR #895)
and the #877 offline validator (PR #905):
[`services/api/src/axis_api/portability_restore_runner.py`](../services/api/src/axis_api/portability_restore_runner.py).

## What the runner is

The runner executes a **validated** #877 restore plan into an isolated target
tenant through **versioned component restore ports** — never SQL or scripts
supplied by the archive. It persists a complete per-component outcome before
any application access is possible; activation of the target tenant stays out
of scope (#879 verifies, operators enable).

## Guarantees

- **Isolated suspended target only.** The runner reads the persisted
  `tenants` row under lock — never a caller-supplied status — and refuses a
  missing or non-suspended target (`restore_target_not_suspended`) at start
  and at every claim, so a tenant reactivated mid-restore receives no further
  writes. A target is bound to one bundle: a different bundle, or a different
  plan while an earlier run is unfinished, is refused
  (`restore_target_bound_to_other_restore`) rather than overwriting it by an
  implicit id match. Operator rights are re-checked through an injected
  callback at start and at every claim (`restore_operator_not_authorized`,
  fail-closed). The runner does not admit or create the target tenant.
- **Acknowledgement and plan carried forward.** The run records the #877
  `PlanAcknowledgement` identity; a mismatched plan digest, acknowledging
  operator, or a manifest whose digest is not the plan's is a construction
  failure (`plan_acknowledgement_mismatch`). Plans that are not `supported`
  (blocked rebinding) are refused (`restore_plan_unsupported`).
- **Persisted state machine.** Runs (`pending → running →
  suspended_quarantined | completed | aborted`) and steps (`pending →
  in_progress → completed | failed | blocked`) live in dedicated tables
  (migration `0067`), so a crash leaves resumable or quarantined state — never
  a partially activated tenant.
- **Fenced execution.** `claim_step` takes the run row lock, sets an explicit
  fencing flag, its owner (`fenced_by`) and the current step; any other
  worker — on another step or the same one — is refused
  (`restore_run_fenced_by_other_worker`). Only the fencing worker may re-claim
  its interrupted step; there is no lease expiry, so a crashed worker's step
  is retried under the same worker identity.
- **Idempotent retries.** Deterministic handlers make re-execution safe;
  `complete_step` is a no-op for an already-completed step and records the
  exact evidence digest (a 64-hex digest, else
  `restore_step_evidence_invalid`). Only a claimed (`in_progress`) step can
  complete or fail, so pending or blocked steps can never be marked restored
  without running their handler. Completed steps are never re-claimed and an
  identical completed run is returned instead of re-executed.
- **Quarantine and resume.** `fail_step` quarantines the run with the
  component failure code; re-issuing `start_restore_run` with the same
  bundle/plan digests resumes the identical run (only retryable failures go
  back to pending). Changed digests open a separate run (subject to the
  target binding above) — resume without identity is impossible.
- **Missing handlers are blocked, never fabricated.** Components without a
  registered handler stay `blocked` (`missing_handler`); `complete_step` never
  completes a run with blocked steps outstanding.
- **Activation blockers as data.** `activation_blockers` returns the exact
  reasons the target may not be enabled yet: incomplete run state, incomplete
  or blocked steps, missing evidence.

## Out of scope (by slice design)

- Object-store writes and SQL step records are deliberately not one
  distributed transaction: handlers must be idempotent and step boundaries
  are the reconciliation points.
- No admission, no tenant activation, no post-restore verification — #879.
- Network, credentials, and destination admission are #877/#876 concerns; the
  runner inherits their conclusions through the validated plan.
