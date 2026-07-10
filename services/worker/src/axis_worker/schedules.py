"""Idempotent Temporal Schedule registration for scheduled maintenance jobs.

Uses the modern Temporal Python SDK Schedule API (``temporalio>=1.24`` ships it;
the repo pins 1.29). Each maintenance job maps to one Schedule whose interval is
read from the shared ``axis_api.config.Settings`` and whose overlap policy is
``SKIP`` — a slow run never overlaps its successor, which, combined with each
job's own idempotency, makes repeated/overlapping invocations safe.

``register_maintenance_schedules`` is create-or-update idempotent: on first run it
creates each Schedule; on subsequent runs it updates the existing Schedule in
place (interval/overlap/paused) without creating duplicates. The Temporal client
is used behind a narrow :class:`ScheduleClientPort` protocol so tests can drive a
thin in-memory fake and never require a live Temporal.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from axis_api.config import Settings
from temporalio.client import (
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleAlreadyRunningError,
    ScheduleHandle,
    ScheduleIntervalSpec,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleState,
    ScheduleUpdate,
    ScheduleUpdateInput,
)

from axis_worker.workflows.connector_live_sync_workflows import (
    ConnectorScheduledLiveSyncWorkflow,
)
from axis_worker.workflows.maintenance_workflows import (
    AuditRetentionDeletionWorkflow,
    OrphanedSessionSweepWorkflow,
    TenantStateReconciliationWorkflow,
)

AUDIT_RETENTION_SCHEDULE_ID = "axis-audit-retention-deletion"
SESSION_SWEEP_SCHEDULE_ID = "axis-orphaned-session-sweep"
TENANT_RECONCILIATION_SCHEDULE_ID = "axis-tenant-state-reconciliation"
CONNECTOR_LIVE_SYNC_SCHEDULE_ID = "axis-connector-scheduled-live-sync"


class ScheduleClientPort(Protocol):
    """Narrow slice of ``temporalio.client.Client`` used for schedule registration."""

    async def create_schedule(self, id: str, schedule: Schedule) -> ScheduleHandle: ...

    def get_schedule_handle(self, id: str) -> ScheduleHandle: ...


@dataclass(frozen=True)
class ScheduledJobSpec:
    schedule_id: str
    workflow: Callable[..., Awaitable[object]]
    workflow_id: str
    interval_seconds: int


def build_scheduled_job_specs(settings: Settings) -> list[ScheduledJobSpec]:
    specs = [
        ScheduledJobSpec(
            schedule_id=AUDIT_RETENTION_SCHEDULE_ID,
            workflow=AuditRetentionDeletionWorkflow.run,
            workflow_id="axis-audit-retention-deletion-run",
            interval_seconds=settings.scheduled_audit_retention_interval_seconds,
        ),
        ScheduledJobSpec(
            schedule_id=SESSION_SWEEP_SCHEDULE_ID,
            workflow=OrphanedSessionSweepWorkflow.run,
            workflow_id="axis-orphaned-session-sweep-run",
            interval_seconds=settings.scheduled_session_sweep_interval_seconds,
        ),
        ScheduledJobSpec(
            schedule_id=TENANT_RECONCILIATION_SCHEDULE_ID,
            workflow=TenantStateReconciliationWorkflow.run,
            workflow_id="axis-tenant-state-reconciliation-run",
            interval_seconds=settings.scheduled_tenant_reconciliation_interval_seconds,
        ),
    ]
    if settings.connector_scheduled_live_sync_enabled:
        # Registered only behind the worker flag so flag-off deployments keep
        # today's exact schedule set (no new paused schedule appears).
        specs.append(
            ScheduledJobSpec(
                schedule_id=CONNECTOR_LIVE_SYNC_SCHEDULE_ID,
                workflow=ConnectorScheduledLiveSyncWorkflow.run,
                workflow_id="axis-connector-scheduled-live-sync-run",
                interval_seconds=settings.connector_scheduled_live_sync_interval_seconds,
            )
        )
    return specs


def _build_schedule(spec: ScheduledJobSpec, *, task_queue: str, paused: bool) -> Schedule:
    return Schedule(
        action=ScheduleActionStartWorkflow(
            spec.workflow,
            id=spec.workflow_id,
            task_queue=task_queue,
        ),
        spec=ScheduleSpec(
            intervals=[ScheduleIntervalSpec(every=timedelta(seconds=spec.interval_seconds))],
        ),
        policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
        state=ScheduleState(
            note="Managed by axis-worker scheduled maintenance bootstrap.",
            paused=paused,
        ),
    )


async def _create_or_update_schedule(
    client: ScheduleClientPort,
    spec: ScheduledJobSpec,
    *,
    task_queue: str,
    created_paused: bool,
) -> str:
    """Create the schedule, or update its definition in place if it exists.

    Returns ``"created"`` or ``"updated"``. Idempotent: repeated calls converge
    the persisted schedule's action/interval/overlap without ever creating a
    duplicate.

    On CREATE the paused state is seeded from ``created_paused`` (derived from the
    enable flag). On UPDATE the operator's current paused state is PRESERVED: a
    manual unpause (or pause) in the Temporal UI survives worker restarts, so the
    reconciliation only owns the schedule definition, not the operator's runtime
    pause intent.
    """
    try:
        await client.create_schedule(
            spec.schedule_id,
            _build_schedule(spec, task_queue=task_queue, paused=created_paused),
        )
        return "created"
    except ScheduleAlreadyRunningError:
        handle = client.get_schedule_handle(spec.schedule_id)

        async def _updater(schedule_input: ScheduleUpdateInput) -> ScheduleUpdate:
            existing_paused = schedule_input.description.schedule.state.paused
            return ScheduleUpdate(
                schedule=_build_schedule(
                    spec, task_queue=task_queue, paused=existing_paused
                )
            )

        await handle.update(_updater)
        return "updated"


async def register_maintenance_schedules(
    client: ScheduleClientPort,
    settings: Settings,
    *,
    task_queue: str,
) -> dict[str, str]:
    """Create/update every maintenance schedule idempotently.

    When ``AXIS_SCHEDULED_JOBS_ENABLED`` is false a newly created schedule is
    seeded in the ``paused`` state, so existing deployments/tests are unaffected
    by default. The flag governs only the initial (created) state: once a schedule
    exists, an operator's pause/unpause in the Temporal UI is preserved across
    worker restarts (the update path does not clobber it).
    """
    created_paused = not settings.scheduled_jobs_enabled
    outcomes: dict[str, str] = {}
    for spec in build_scheduled_job_specs(settings):
        outcomes[spec.schedule_id] = await _create_or_update_schedule(
            client, spec, task_queue=task_queue, created_paused=created_paused
        )
    return outcomes
