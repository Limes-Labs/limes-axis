"""Run blocking activity work off the worker event loop, with heartbeats.

The DB-owning activities call synchronous SQLAlchemy and connector code. The
worker's event loop also runs the Temporal pollers and the outbox dispatch
loops, so that code must not run inline on it. ``run_blocking`` moves it to a
thread (``asyncio.to_thread`` copies the context, so telemetry spans and the
activity context still apply) and heartbeats from the loop while it runs, so a
worker that dies mid-activity is noticed within ``ACTIVITY_HEARTBEAT_TIMEOUT``
instead of at the start-to-close timeout.

Cancellation cannot interrupt the thread: it finishes its current transaction,
which each job owns, and its result is discarded. The jobs are idempotent and
lease-fenced, so a retry after a heartbeat timeout is safe.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta

from temporalio import activity

HEARTBEAT_INTERVAL_SECONDS = 10.0
ACTIVITY_HEARTBEAT_TIMEOUT = timedelta(seconds=60)


async def run_blocking[T](
    function: Callable[..., T], /, *args: object, **kwargs: object
) -> T:
    task = asyncio.ensure_future(asyncio.to_thread(function, *args, **kwargs))
    while True:
        done, _pending = await asyncio.wait({task}, timeout=HEARTBEAT_INTERVAL_SECONDS)
        if done:
            return task.result()
        if activity.in_activity():
            activity.heartbeat()
