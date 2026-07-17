from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import pytest

from axis_worker.approval_outbox_loop import run_approval_decision_outbox_loop


@dataclass(frozen=True)
class _Result:
    claimed: int


class _ScriptedDispatcher:
    def __init__(self, outcomes: list[_Result | Exception]) -> None:
        self._outcomes = iter(outcomes)
        self.calls = 0
        self.exhausted = asyncio.Event()

    async def run_once(self) -> _Result:
        self.calls += 1
        try:
            outcome = next(self._outcomes)
        except StopIteration:
            self.exhausted.set()
            return _Result(claimed=0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.mark.asyncio
async def test_loop_immediately_drains_claimed_batches_then_waits() -> None:
    dispatcher = _ScriptedDispatcher([_Result(claimed=3), _Result(claimed=1)])
    task = asyncio.create_task(run_approval_decision_outbox_loop(dispatcher, interval_seconds=60))

    await asyncio.wait_for(dispatcher.exhausted.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert dispatcher.calls == 3


@pytest.mark.asyncio
async def test_loop_logs_and_retries_dispatch_failures(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dispatcher = _ScriptedDispatcher([RuntimeError("database unavailable")])
    caplog.set_level(logging.ERROR, logger="axis_worker.approval_outbox_loop")
    task = asyncio.create_task(
        run_approval_decision_outbox_loop(dispatcher, interval_seconds=0.001)
    )

    await asyncio.wait_for(dispatcher.exhausted.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert dispatcher.calls == 2
    assert "dispatch failed; retrying" in caplog.text
    assert "database unavailable" in caplog.text


@pytest.mark.asyncio
async def test_loop_retries_invalid_dispatch_results(
    caplog: pytest.LogCaptureFixture,
) -> None:
    dispatcher = _ScriptedDispatcher([_Result(claimed=-1)])
    caplog.set_level(logging.ERROR, logger="axis_worker.approval_outbox_loop")
    task = asyncio.create_task(
        run_approval_decision_outbox_loop(dispatcher, interval_seconds=0.001)
    )

    await asyncio.wait_for(dispatcher.exhausted.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert dispatcher.calls == 2
    assert "non-negative integer claimed count" in caplog.text


@pytest.mark.asyncio
async def test_loop_propagates_cancellation_during_dispatch() -> None:
    started = asyncio.Event()
    cancelled = asyncio.Event()

    class BlockingDispatcher:
        async def run_once(self) -> _Result:
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
            return _Result(claimed=0)

    task = asyncio.create_task(
        run_approval_decision_outbox_loop(
            BlockingDispatcher(),
            interval_seconds=60,
        )
    )
    await asyncio.wait_for(started.wait(), timeout=1)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_loop_rejects_non_positive_interval() -> None:
    dispatcher = _ScriptedDispatcher([])

    with pytest.raises(ValueError, match="greater than zero"):
        await run_approval_decision_outbox_loop(dispatcher, interval_seconds=0)
    assert dispatcher.calls == 0
