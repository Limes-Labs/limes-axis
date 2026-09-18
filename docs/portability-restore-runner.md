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

- **Isolated suspended target only.** `start_restore_run` refuses non-suspended
  targets (`restore_target_not_suspended`) and re-checks operator rights
  through an injected callback at start and at every claim
  (`restore_operator_not_authorized`, fail-closed).
- **Acknowledgement carried forward.** The run records the #877
  `PlanAcknowledgement` identity; a mismatched plan digest or acknowledging
  operator is a construction failure (`plan_acknowledgement_mismatch`).
- **Persisted state machine.** Runs (`pending → running →
  suspended_quarantined | completed | aborted`) and steps (`pending →
  in_progress → completed | failed | blocked`) live in dedicated tables
  (migration `0067`), so a crash leaves resumable or quarantined state — never
  a partially activated tenant.
- **Fenced execution.** `claim_step` takes the run row lock, sets an explicit
  fencing flag and the current step; a second worker on the same run is
  refused (`restore_run_fenced_by_other_worker`).
- **Idempotent retries.** Deterministic handlers make re-execution safe;
  `complete_step` is a no-op for an already-completed step and records the
  exact evidence digest. Completed steps are never re-claimed.
- **Quarantine and resume.** `fail_step` quarantines the run with the
  component failure code; re-issuing `start_restore_run` with the same
  bundle/plan digests resumes the identical run (only retryable failures go
  back to pending). Changed digests always open a new generation — resume
  without identity is impossible.
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
