"""Temporal activities for scheduled connector live sync.

Follows the same doc-167 seam as ``axis_worker.maintenance_activities``: the
worker owns a SQLAlchemy session factory built from the shared
``axis_api.config.Settings`` and calls the reusable API-side functions in
``axis_api.connector_runs`` (claim / execute / release) directly in process.
No business logic is duplicated here — the activities are thin adapters around
the exact same claim, batch-loop, checkpoint and release code paths the API
exposes, so worker-driven executions produce byte-identical evidence.

Fail-closed posture:

* Everything is gated behind ``AXIS_CONNECTOR_SCHEDULED_LIVE_SYNC_ENABLED``
  plus the existing sync-execution/live-sync flags; with any of them off the
  candidate listing is empty and nothing executes.
* A second worker racing on the same resume checkpoint hits the existing
  single-active-claim semantics (partial unique index from migration 0045)
  and reports ``skipped_claim_conflict`` instead of executing.
* Business validation failures are returned as structured
  ``execution_blocked`` outcomes (never raised), so the workflow always
  reaches its release step.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from axis_api.config import Settings
from axis_api.connector_execution import (
    connector_live_sync_runtime_from_settings,
    connector_sync_execution_runtime_from_settings,
)
from axis_api.connector_runs import (
    SCHEDULED_SYNC_PLAN_MODE,
    SYNC_BATCH_CHECKPOINT_TYPE,
    SYNC_BATCH_COMMITTED_STATUS,
    SYNC_CHECKPOINT_CLAIM_RELEASE_SCOPE,
    SYNC_CHECKPOINT_CLAIM_RENEW_SCOPE,
    SYNC_CHECKPOINT_CLAIM_SCOPE,
    SYNC_EXECUTION_FAILED_STATUS,
    SYNC_EXECUTION_SCOPE,
    ConnectorRunNotFound,
    ConnectorRunPermissionDenied,
    ConnectorRunSyncExecutionConflict,
    ConnectorRunSyncExecutionRequest,
    ConnectorRunValidationError,
    ConnectorSyncCheckpointClaimConflict,
    ConnectorSyncCheckpointClaimReleaseRequest,
    ConnectorSyncCheckpointClaimRenewRequest,
    ConnectorSyncCheckpointClaimRequest,
    claim_connector_sync_checkpoint,
    execute_demo_connector_sync,
    release_connector_sync_checkpoint_claim,
    renew_connector_sync_checkpoint_claim,
)
from axis_api.db import create_session_factory, session_scope
from axis_api.models import utc_now
from axis_api.persistence import AxisPersistenceRepository
from axis_api.telemetry import ATTR_JOB, ATTR_OUTCOME, set_span_attributes
from sqlalchemy.orm import Session, sessionmaker
from temporalio import activity

from axis_worker.telemetry import WorkerTelemetryRuntime, configure_worker_telemetry

LIST_CANDIDATES_ACTIVITY = "list_scheduled_live_sync_candidates"
CLAIM_ACTIVITY = "claim_scheduled_live_sync_checkpoint"
EXECUTE_ACTIVITY = "execute_scheduled_live_sync"
RELEASE_ACTIVITY = "release_scheduled_live_sync_claim"

SCHEDULED_LIVE_SYNC_JOB = "connector_scheduled_live_sync"
SCHEDULED_LIVE_SYNC_WORKER_ACTOR = "axis-scheduled-live-sync-worker"
DISPATCHED_RUN_STATUS = "sync_dispatch_deferred"
CANDIDATE_RUN_STATUSES = frozenset({DISPATCHED_RUN_STATUS, SYNC_EXECUTION_FAILED_STATUS})
CANDIDATE_SCAN_LIMIT = 200
CANDIDATE_LIMIT_PER_TICK = 10
CLAIM_LEASE_DURATION_SECONDS = 900
CLAIM_RENEWAL_GUARD_SECONDS = 300


class ConnectorLiveSyncActivities:
    """DB-owning activity bundle for scheduled connector live sync."""

    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session] | None = None,
        telemetry: WorkerTelemetryRuntime | None = None,
    ) -> None:
        self.settings = settings
        self._session_factory = session_factory or create_session_factory(settings)
        self._telemetry = telemetry or configure_worker_telemetry(settings)

    def _scheduled_live_sync_enabled(self) -> bool:
        return (
            self.settings.connector_scheduled_live_sync_enabled
            and self.settings.connector_sync_execution_enabled
            and self.settings.connector_live_sync_execution_enabled
        )

    @activity.defn(name=LIST_CANDIDATES_ACTIVITY)
    async def list_scheduled_live_sync_candidates(self) -> dict:
        if not self._scheduled_live_sync_enabled():
            return {"status": "scheduled_live_sync_disabled", "candidates": []}
        tenant_id = self.settings.connector_scheduled_live_sync_tenant_id
        candidates: list[dict] = []
        with session_scope(self._session_factory) as session:
            repository = AxisPersistenceRepository(session)
            runs = repository.list_connector_runs(tenant_id, limit=CANDIDATE_SCAN_LIMIT)
            for run in runs:
                if run.execution_mode != SCHEDULED_SYNC_PLAN_MODE:
                    continue
                if run.status not in CANDIDATE_RUN_STATUSES:
                    continue
                if str(run.input_summary.get("live_sync_requested", "false")).lower() != "true":
                    continue
                credential_lease_id = _active_lease_id_for_run(repository, run)
                if credential_lease_id is None:
                    continue
                candidates.append(
                    {
                        "tenant_id": run.tenant_id,
                        "connector_id": run.connector_id,
                        "run_id": run.run_id,
                        "credential_lease_id": credential_lease_id,
                    }
                )
                if len(candidates) >= CANDIDATE_LIMIT_PER_TICK:
                    break
        return {"status": "candidates_listed", "candidates": candidates}

    @activity.defn(name=CLAIM_ACTIVITY)
    async def claim_scheduled_live_sync_checkpoint(self, payload: dict) -> dict:
        tenant_id = str(payload["tenant_id"])
        run_id = str(payload["run_id"])
        attempt_id = str(payload["attempt_id"])
        with session_scope(self._session_factory) as session:
            repository = AxisPersistenceRepository(session)
            latest_batch_checkpoint = repository.get_latest_connector_sync_checkpoint(
                tenant_id,
                run_id=run_id,
                connector_id=str(payload["connector_id"]),
                checkpoint_type=SYNC_BATCH_CHECKPOINT_TYPE,
                status=SYNC_BATCH_COMMITTED_STATUS,
            )
            if latest_batch_checkpoint is None:
                # Fresh runs have no committed batch checkpoint yet; the API-side
                # loop does not require a resume claim for them.
                return {"outcome": "fresh_run_no_claim"}
            try:
                claim, _ = claim_connector_sync_checkpoint(
                    repository,
                    latest_batch_checkpoint.checkpoint_id,
                    ConnectorSyncCheckpointClaimRequest(
                        tenant_id=tenant_id,
                        claim_id=f"claim_sched_{attempt_id}",
                        claimed_by=SCHEDULED_LIVE_SYNC_WORKER_ACTOR,
                        actor_scopes=[SYNC_CHECKPOINT_CLAIM_SCOPE],
                        idempotency_key=f"idem_claim_sched_{attempt_id}",
                        lease_duration_seconds=CLAIM_LEASE_DURATION_SECONDS,
                        notes=["Claimed by the scheduled connector live-sync worker."],
                    ),
                )
            except ConnectorSyncCheckpointClaimConflict as exc:
                # Single-active-claim safety: another worker holds this
                # checkpoint (DB partial unique index backstop); skip the run.
                return {
                    "outcome": "skipped_claim_conflict",
                    "checkpoint_id": latest_batch_checkpoint.checkpoint_id,
                    "active_claim_id": exc.active_claim_id,
                }
        return {
            "outcome": "claimed",
            "checkpoint_id": claim.checkpoint_id,
            "claim_id": claim.claim_id,
            "lease_expires_at": claim.lease_expires_at.isoformat(),
        }

    @activity.defn(name=EXECUTE_ACTIVITY)
    async def execute_scheduled_live_sync(self, payload: dict) -> dict:
        tenant_id = str(payload["tenant_id"])
        run_id = str(payload["run_id"])
        attempt_id = str(payload["attempt_id"])
        checkpoint_claim_id = payload.get("checkpoint_claim_id") or None
        with self._telemetry.activity_span(
            "axis.scheduled_job.connector_live_sync_execution"
        ) as span:
            with session_scope(self._session_factory) as session:
                repository = AxisPersistenceRepository(session)
                claim_renewed = self._renew_claim_near_expiry(repository, payload)
                try:
                    record = execute_demo_connector_sync(
                        repository,
                        run_id,
                        ConnectorRunSyncExecutionRequest(
                            tenant_id=tenant_id,
                            execution_id=f"sched_exec_{attempt_id}",
                            executed_by=SCHEDULED_LIVE_SYNC_WORKER_ACTOR,
                            actor_scopes=[SYNC_EXECUTION_SCOPE],
                            credential_lease_id=str(payload["credential_lease_id"]),
                            checkpoint_claim_id=checkpoint_claim_id,
                            idempotency_key=f"idem_sched_exec_{attempt_id}",
                            notes=["Executed by the scheduled connector live-sync worker."],
                        ),
                        sync_execution_runtime=connector_sync_execution_runtime_from_settings(
                            self.settings
                        ),
                        live_sync_runtime=connector_live_sync_runtime_from_settings(
                            self.settings
                        ),
                        usage_metering_enabled=self.settings.usage_metering_enabled,
                        usage_window_seconds=(
                            self.settings.usage_metering_aggregation_window_seconds
                        ),
                    )
                except (
                    ConnectorRunNotFound,
                    ConnectorRunPermissionDenied,
                    ConnectorRunSyncExecutionConflict,
                    ConnectorRunValidationError,
                ) as exc:
                    outcome = {
                        "status": "execution_blocked",
                        "reason": getattr(exc, "reason", exc.__class__.__name__),
                        "claim_renewed": claim_renewed,
                    }
                    self._record_outcome(span, outcome["status"])
                    return outcome
            summary = record.result_summary
            outcome = {
                "status": record.status,
                "claim_renewed": claim_renewed,
                "records_read": str(summary.get("records_read", "0")),
                "sync_batches_committed": str(summary.get("sync_batches_committed", "0")),
                "sync_error_code": str(summary.get("sync_error_code", "")),
            }
            self._record_outcome(span, record.status)
            return outcome

    @activity.defn(name=RELEASE_ACTIVITY)
    async def release_scheduled_live_sync_claim(self, payload: dict) -> dict:
        tenant_id = str(payload["tenant_id"])
        checkpoint_id = str(payload["checkpoint_id"])
        claim_id = str(payload["claim_id"])
        with session_scope(self._session_factory) as session:
            repository = AxisPersistenceRepository(session)
            try:
                released = release_connector_sync_checkpoint_claim(
                    repository,
                    checkpoint_id,
                    claim_id,
                    ConnectorSyncCheckpointClaimReleaseRequest(
                        tenant_id=tenant_id,
                        released_by=SCHEDULED_LIVE_SYNC_WORKER_ACTOR,
                        actor_scopes=[SYNC_CHECKPOINT_CLAIM_RELEASE_SCOPE],
                        release_reason=str(payload["release_reason"]),
                        notes=["Released by the scheduled connector live-sync worker."],
                    ),
                )
            except (ConnectorRunNotFound, ConnectorRunValidationError) as exc:
                return {
                    "outcome": "release_skipped",
                    "reason": getattr(exc, "reason", exc.__class__.__name__),
                }
        return {"outcome": "released", "claim_id": released.claim_id}

    def _renew_claim_near_expiry(
        self,
        repository: AxisPersistenceRepository,
        payload: dict,
    ) -> bool:
        """Renew the resume claim when its lease is inside the renewal guard.

        Keeps the claim alive for the whole batch loop of this attempt so a
        long execution never loses single-worker ownership mid-run.
        """
        checkpoint_claim_id = payload.get("checkpoint_claim_id") or None
        claim_checkpoint_id = payload.get("claim_checkpoint_id") or None
        lease_expires_at = payload.get("claim_lease_expires_at") or None
        if not checkpoint_claim_id or not claim_checkpoint_id or not lease_expires_at:
            return False
        expires_at = datetime.fromisoformat(str(lease_expires_at))
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        renewal_deadline = utc_now() + timedelta(seconds=CLAIM_RENEWAL_GUARD_SECONDS)
        if expires_at > renewal_deadline:
            return False
        renew_connector_sync_checkpoint_claim(
            repository,
            str(claim_checkpoint_id),
            str(checkpoint_claim_id),
            ConnectorSyncCheckpointClaimRenewRequest(
                tenant_id=str(payload["tenant_id"]),
                renewed_by=SCHEDULED_LIVE_SYNC_WORKER_ACTOR,
                actor_scopes=[SYNC_CHECKPOINT_CLAIM_RENEW_SCOPE],
                lease_duration_seconds=CLAIM_LEASE_DURATION_SECONDS,
                renewal_reason="scheduled_live_sync_execution_window",
            ),
        )
        return True

    def _record_outcome(self, span, status: str) -> None:
        set_span_attributes(span, {ATTR_JOB: SCHEDULED_LIVE_SYNC_JOB, ATTR_OUTCOME: status})
        self._telemetry.record_job_run(job=SCHEDULED_LIVE_SYNC_JOB, status=status)
        activity.logger.info(
            "connector_scheduled_live_sync job=%s status=%s",
            SCHEDULED_LIVE_SYNC_JOB,
            status,
        )


def _active_lease_id_for_run(
    repository: AxisPersistenceRepository,
    run,
) -> str | None:
    leases = repository.list_connector_credential_leases(
        tenant_id=run.tenant_id,
        connector_id=run.connector_id,
        status="active",
    )
    now = utc_now()
    for lease in leases:
        if lease.handle_id not in (run.credential_handle_ids or []):
            continue
        expires_at = lease.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=now.tzinfo)
        if expires_at <= now:
            continue
        return lease.lease_id
    return None
