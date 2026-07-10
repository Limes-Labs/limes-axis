"""Scheduled connector live-sync workflow triggered by a Temporal Schedule.

The workflow is a deterministic driver over four DB-owning activities:

1. ``list_scheduled_live_sync_candidates`` — flag-gated discovery of dispatched
   (or failed-resumable) governed live-sync runs;
2. ``claim_scheduled_live_sync_checkpoint`` — single-worker checkpoint claim on
   the latest committed batch checkpoint (resume runs only). A racing worker
   receives the existing claim-conflict semantics and the run is skipped;
3. ``execute_scheduled_live_sync`` — the existing API-side sync-execution loop,
   which reads source batches and persists one committed checkpoint per batch;
4. ``release_scheduled_live_sync_claim`` — always releases a held claim, with a
   completion or failure reason, so the next scheduled tick can resume.

The orchestration logic lives in :func:`orchestrate_scheduled_live_sync`,
parameterized over a narrow activity port, so worker tests can drive the exact
same lifecycle with in-memory fakes (or the real activities on SQLite) without
a live Temporal server. The schedule's ``SKIP`` overlap policy plus the
checkpoint claim plus per-attempt idempotency keys make repeated and racing
invocations safe.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Protocol

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from axis_worker.connector_live_sync_activities import (
        CLAIM_ACTIVITY,
        EXECUTE_ACTIVITY,
        LIST_CANDIDATES_ACTIVITY,
        RELEASE_ACTIVITY,
    )

_START_TO_CLOSE = timedelta(minutes=10)
_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=3,
)

COMPLETED_EXECUTION_STATUS = "sync_execution_completed"
RELEASE_REASON_COMPLETED = "scheduled_live_sync_completed"
RELEASE_REASON_FAILED = "scheduled_live_sync_failed"
EXECUTION_ERROR_OUTCOME = "execution_error"


class ScheduledLiveSyncActivityPort(Protocol):
    """Narrow activity-invocation seam so tests can drive the lifecycle in memory."""

    async def run(self, activity_name: str, payload: dict | None = None) -> dict:
        ...


async def orchestrate_scheduled_live_sync(
    activities: ScheduledLiveSyncActivityPort,
    *,
    attempt_seed: str,
) -> dict:
    """Claim → execute (batch loop with per-batch checkpoints) → release."""
    listing = await activities.run(LIST_CANDIDATES_ACTIVITY)
    outcomes: list[dict] = []
    for index, candidate in enumerate(listing.get("candidates", [])):
        attempt_id = f"{attempt_seed}_{index}"
        claim = await activities.run(
            CLAIM_ACTIVITY,
            {**candidate, "attempt_id": attempt_id},
        )
        if claim.get("outcome") == "skipped_claim_conflict":
            # Another worker holds the active claim for this run's checkpoint:
            # single-active-claim safety, skip without executing.
            outcomes.append(
                {
                    "run_id": candidate["run_id"],
                    "outcome": "skipped_claim_conflict",
                    "active_claim_id": str(claim.get("active_claim_id", "")),
                }
            )
            continue
        claim_held = claim.get("outcome") == "claimed"
        execute_payload = {**candidate, "attempt_id": attempt_id}
        if claim_held:
            execute_payload.update(
                {
                    "checkpoint_claim_id": claim["claim_id"],
                    "claim_checkpoint_id": claim["checkpoint_id"],
                    "claim_lease_expires_at": str(claim.get("lease_expires_at", "")),
                }
            )
        execution_status = EXECUTION_ERROR_OUTCOME
        try:
            execution = await activities.run(EXECUTE_ACTIVITY, execute_payload)
            execution_status = str(execution.get("status", EXECUTION_ERROR_OUTCOME))
        except ActivityError:
            # Infra-level activity failure after retries: fall through to the
            # release step so the claim never leaks, then record the outcome.
            pass
        if claim_held:
            release_reason = (
                RELEASE_REASON_COMPLETED
                if execution_status == COMPLETED_EXECUTION_STATUS
                else RELEASE_REASON_FAILED
            )
            await activities.run(
                RELEASE_ACTIVITY,
                {
                    "tenant_id": candidate["tenant_id"],
                    "checkpoint_id": claim["checkpoint_id"],
                    "claim_id": claim["claim_id"],
                    "release_reason": release_reason,
                },
            )
        outcomes.append({"run_id": candidate["run_id"], "outcome": execution_status})
    return {"status": listing.get("status", "candidates_listed"), "outcomes": outcomes}


class _TemporalActivityPort:
    async def run(self, activity_name: str, payload: dict | None = None) -> dict:
        args = [payload] if payload is not None else []
        return await workflow.execute_activity(
            activity_name,
            *args,
            start_to_close_timeout=_START_TO_CLOSE,
            retry_policy=_RETRY_POLICY,
        )


@workflow.defn
class ConnectorScheduledLiveSyncWorkflow:
    @workflow.run
    async def run(self) -> dict:
        attempt_seed = f"w{workflow.info().run_id.lower().replace('-', '')[:12]}"
        return await orchestrate_scheduled_live_sync(
            _TemporalActivityPort(),
            attempt_seed=attempt_seed,
        )
