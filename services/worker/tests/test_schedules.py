"""Schedule-registration bootstrap tests with a thin in-memory fake Temporal client.

These tests never require a live Temporal (they run in the default suite). They
verify the create-or-update bootstrap is idempotent: a first pass creates each
schedule, a second pass updates in place with no duplicates, and the enable flag
controls the paused state.
"""

from __future__ import annotations

import pytest
from axis_api.config import Settings
from temporalio.client import Schedule, ScheduleAlreadyRunningError

from axis_worker.schedules import (
    AUDIT_RETENTION_SCHEDULE_ID,
    SESSION_SWEEP_SCHEDULE_ID,
    TENANT_RECONCILIATION_SCHEDULE_ID,
    register_maintenance_schedules,
)

pytestmark = pytest.mark.asyncio


class FakeScheduleHandle:
    def __init__(self, store: dict[str, Schedule], schedule_id: str) -> None:
        self._store = store
        self._schedule_id = schedule_id
        self.update_calls = 0

    async def update(self, updater) -> None:
        self.update_calls += 1
        update = await updater(_FakeUpdateInput(self._store[self._schedule_id]))
        self._store[self._schedule_id] = update.schedule


class _FakeUpdateInput:
    def __init__(self, description) -> None:
        self.description = description


class FakeScheduleClient:
    """In-memory stand-in for the schedule slice of ``temporalio.client.Client``."""

    def __init__(self) -> None:
        self.schedules: dict[str, Schedule] = {}
        self.create_calls: list[str] = []
        self.handles: dict[str, FakeScheduleHandle] = {}

    async def create_schedule(self, id: str, schedule: Schedule):
        self.create_calls.append(id)
        if id in self.schedules:
            raise ScheduleAlreadyRunningError()
        self.schedules[id] = schedule
        return self.get_schedule_handle(id)

    def get_schedule_handle(self, id: str) -> FakeScheduleHandle:
        handle = FakeScheduleHandle(self.schedules, id)
        self.handles[id] = handle
        return handle


def _settings(**overrides) -> Settings:
    return Settings(**overrides)


ALL_IDS = {
    AUDIT_RETENTION_SCHEDULE_ID,
    SESSION_SWEEP_SCHEDULE_ID,
    TENANT_RECONCILIATION_SCHEDULE_ID,
}


async def test_register_creates_all_schedules_first_run() -> None:
    client = FakeScheduleClient()
    outcomes = await register_maintenance_schedules(
        client, _settings(), task_queue="axis-foundation"
    )

    assert set(outcomes) == ALL_IDS
    assert all(outcome == "created" for outcome in outcomes.values())
    assert set(client.schedules) == ALL_IDS


async def test_register_is_idempotent_updates_in_place_no_duplicates() -> None:
    client = FakeScheduleClient()
    settings = _settings()

    first = await register_maintenance_schedules(client, settings, task_queue="axis-foundation")
    assert all(outcome == "created" for outcome in first.values())

    second = await register_maintenance_schedules(client, settings, task_queue="axis-foundation")

    assert all(outcome == "updated" for outcome in second.values())
    # Still exactly one schedule per id: no duplicates were created.
    assert set(client.schedules) == ALL_IDS
    assert len(client.schedules) == 3
    # Each existing schedule was updated in place exactly once on the second pass.
    for schedule_id in ALL_IDS:
        assert client.handles[schedule_id].update_calls == 1


async def test_schedules_paused_when_disabled_and_active_when_enabled() -> None:
    disabled_client = FakeScheduleClient()
    await register_maintenance_schedules(
        disabled_client,
        _settings(AXIS_SCHEDULED_JOBS_ENABLED="false"),
        task_queue="axis-foundation",
    )
    assert all(
        schedule.state.paused for schedule in disabled_client.schedules.values()
    )

    enabled_client = FakeScheduleClient()
    await register_maintenance_schedules(
        enabled_client,
        _settings(AXIS_SCHEDULED_JOBS_ENABLED="true"),
        task_queue="axis-foundation",
    )
    assert all(
        not schedule.state.paused for schedule in enabled_client.schedules.values()
    )


async def test_schedule_intervals_read_from_settings() -> None:
    client = FakeScheduleClient()
    settings = _settings(
        AXIS_SCHEDULED_AUDIT_RETENTION_INTERVAL_SECONDS="1000",
        AXIS_SCHEDULED_SESSION_SWEEP_INTERVAL_SECONDS="200",
        AXIS_SCHEDULED_TENANT_RECONCILIATION_INTERVAL_SECONDS="300",
    )
    await register_maintenance_schedules(client, settings, task_queue="axis-foundation")

    audit = client.schedules[AUDIT_RETENTION_SCHEDULE_ID]
    assert audit.spec.intervals[0].every.total_seconds() == 1000
    sweep = client.schedules[SESSION_SWEEP_SCHEDULE_ID]
    assert sweep.spec.intervals[0].every.total_seconds() == 200
