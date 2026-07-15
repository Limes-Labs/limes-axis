import asyncio
import os
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from axis_api.rate_limit import RedisRateLimiter

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("AXIS_RUN_INTEGRATION") != "1",
        reason="set AXIS_RUN_INTEGRATION=1 with the local Docker runtime running",
    ),
]


@pytest.mark.asyncio
async def test_two_replicas_share_one_atomic_rate_limit() -> None:
    redis_url = os.getenv("AXIS_REDIS_URL", "redis://127.0.0.1:6379/15")
    first_client = Redis.from_url(redis_url)
    second_client = Redis.from_url(redis_url)
    first = RedisRateLimiter(first_client, window_seconds=5)
    second = RedisRateLimiter(second_client, window_seconds=5)
    key = f"integration:{uuid4()}"
    try:
        decisions = await asyncio.gather(
            *(
                (first if index % 2 == 0 else second).check(key, limit=15)
                for index in range(60)
            )
        )
    finally:
        await first.close()
        await second.close()

    assert sum(decision.allowed for decision in decisions) == 15
    assert sum(not decision.allowed for decision in decisions) == 45
