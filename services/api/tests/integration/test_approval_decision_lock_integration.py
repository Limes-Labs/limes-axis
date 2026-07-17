import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.persistence import AxisPersistenceRepository

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("AXIS_RUN_INTEGRATION") != "1",
        reason="set AXIS_RUN_INTEGRATION=1 with the local Docker runtime running",
    ),
]


def test_postgres_approval_lock_serializes_same_approval_only() -> None:
    engine = create_engine(Settings().postgres_dsn, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    first = factory()
    executor = ThreadPoolExecutor(max_workers=2)
    same_approval_acquired = Event()
    other_approval_acquired = Event()

    def acquire(approval_id: str, acquired: Event) -> None:
        with session_scope(factory) as session:
            AxisPersistenceRepository(session).acquire_approval_decision_lock(
                "tenant_lock_integration", approval_id
            )
            acquired.set()

    try:
        first.begin()
        AxisPersistenceRepository(first).acquire_approval_decision_lock(
            "tenant_lock_integration", "approval_shared"
        )
        same_future = executor.submit(acquire, "approval_shared", same_approval_acquired)
        other_future = executor.submit(acquire, "approval_other", other_approval_acquired)

        assert other_approval_acquired.wait(timeout=2)
        assert not same_approval_acquired.wait(timeout=0.25)
        first.commit()
        assert same_approval_acquired.wait(timeout=2)
        same_future.result()
        other_future.result()
    finally:
        if first.in_transaction():
            first.rollback()
        first.close()
        executor.shutdown(wait=True, cancel_futures=True)
        engine.dispose()
