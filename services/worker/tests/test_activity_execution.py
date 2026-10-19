"""Blocking activity work runs off the worker event loop and heartbeats (#942).

The maintenance and live-sync activities are ``async def`` but call synchronous
DB and connector code. Run inline, that work blocked the event loop shared with
the Temporal pollers and the outbox loops, and with no heartbeat a stuck
activity was only noticed at its 10-minute start-to-close timeout.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from axis_api.config import Settings
from axis_api.maintenance_jobs import JobRunResult
from temporalio.testing import ActivityEnvironment

import axis_worker.activity_execution as activity_execution
import axis_worker.maintenance_activities as maintenance_module
from axis_worker.connector_live_sync_activities import ConnectorLiveSyncActivities
from axis_worker.maintenance_activities import MaintenanceActivities
from axis_worker.workflows import connector_live_sync_workflows, maintenance_workflows

pytestmark = pytest.mark.asyncio

BLOCK_SECONDS = 0.3


def _slow_job(*_args: object, **_kwargs: object) -> JobRunResult:
    time.sleep(BLOCK_SECONDS)
    return JobRunResult(job="audit_retention_deletion", status="completed")


@pytest.fixture
def slow_maintenance(monkeypatch: pytest.MonkeyPatch) -> MaintenanceActivities:
    monkeypatch.setattr(maintenance_module, "run_audit_retention_deletion_job", _slow_job)
    return MaintenanceActivities(Settings(_env_file=None), session_factory=object())  # type: ignore[arg-type]


async def test_blocking_maintenance_work_leaves_the_event_loop_responsive(
    slow_maintenance: MaintenanceActivities,
) -> None:
    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    task = asyncio.create_task(ticker())
    await asyncio.sleep(0)
    result = await slow_maintenance.run_audit_retention_deletion()
    observed = ticks
    task.cancel()

    assert result["status"] == "completed"
    # The poller-sharing loop kept running while the job blocked its thread.
    assert observed >= 10


async def test_blocking_maintenance_work_heartbeats(
    slow_maintenance: MaintenanceActivities, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(activity_execution, "HEARTBEAT_INTERVAL_SECONDS", 0.05)
    heartbeats: list[tuple] = []
    environment = ActivityEnvironment()
    environment.on_heartbeat = lambda *details: heartbeats.append(details)

    result = await environment.run(slow_maintenance.run_audit_retention_deletion)

    assert result["status"] == "completed"
    assert len(heartbeats) >= 3


async def test_live_sync_listing_runs_off_the_event_loop(monkeypatch) -> None:
    activities = ConnectorLiveSyncActivities(
        Settings(_env_file=None), session_factory=object()  # type: ignore[arg-type]
    )
    threads: list[bool] = []

    def blocking_enabled() -> bool:
        threads.append(_on_loop_thread())
        return False

    monkeypatch.setattr(activities, "_scheduled_live_sync_enabled", blocking_enabled)

    result = await activities.list_scheduled_live_sync_candidates()

    assert result["status"] == "scheduled_live_sync_disabled"
    assert threads == [False]


def _on_loop_thread() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


async def test_workflows_schedule_db_activities_with_a_heartbeat_timeout() -> None:
    for options in (
        maintenance_workflows.ACTIVITY_OPTIONS,
        connector_live_sync_workflows.ACTIVITY_OPTIONS,
    ):
        heartbeat = options["heartbeat_timeout"]
        assert heartbeat == activity_execution.ACTIVITY_HEARTBEAT_TIMEOUT
        assert heartbeat.total_seconds() > 3 * activity_execution.HEARTBEAT_INTERVAL_SECONDS
        assert options["start_to_close_timeout"] > heartbeat
