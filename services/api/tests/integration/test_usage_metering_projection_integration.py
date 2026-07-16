import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from alembic.command import upgrade
from alembic.config import Config
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.models import TenantUsageEvent, TenantUsageRecord
from axis_api.persistence import AxisPersistenceRepository, TenantUsageEventAppend
from axis_api.usage_metering import (
    DEFAULT_USAGE_PERIOD_WINDOW_SECONDS,
    TenantUsageMetric,
    UsageEventProjector,
    usage_period_start,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("AXIS_RUN_INTEGRATION") != "1",
        reason="set AXIS_RUN_INTEGRATION=1 with the local Docker runtime running",
    ),
]


def test_postgres_projectors_claim_disjoint_batches_and_preserve_exact_total() -> None:
    upgrade(Config("alembic.ini"), "head")
    engine = create_engine(Settings().postgres_dsn, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    tenant_id = f"tenant_usage_projection_{uuid4().hex}"
    occurred_at = datetime.now(UTC)
    event_count = 100
    try:
        with session_scope(factory) as session:
            repository = AxisPersistenceRepository(session)
            for index in range(event_count):
                repository.append_tenant_usage_event(
                    TenantUsageEventAppend(
                        tenant_id=tenant_id,
                        metric_key=TenantUsageMetric.API_REQUEST,
                        source_type="integration_admission",
                        source_id=str(index),
                        period_start=usage_period_start(occurred_at),
                        period_window_seconds=DEFAULT_USAGE_PERIOD_WINDOW_SECONDS,
                        quantity=1,
                        occurred_at=occurred_at,
                    ),
                    project_immediately=False,
                )

        projectors = [
            UsageEventProjector(failure_threshold=3, max_backlog_age_seconds=60)
            for _ in range(2)
        ]
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    projector.project_available,
                    factory,
                    batch_size=10,
                    max_batches=20,
                )
                for projector in projectors
            ]
        results = [future.result() for future in futures]

        assert sum(result.events_projected for result in results) == event_count
        with factory() as session:
            pending = session.scalar(
                select(func.count())
                .select_from(TenantUsageEvent)
                .where(
                    TenantUsageEvent.tenant_id == tenant_id,
                    TenantUsageEvent.projected_at.is_(None),
                )
            )
            total = session.scalar(
                select(TenantUsageRecord.quantity).where(
                    TenantUsageRecord.tenant_id == tenant_id,
                    TenantUsageRecord.metric_key == TenantUsageMetric.API_REQUEST,
                )
            )
        assert pending == 0
        assert total == event_count
    finally:
        with Session(engine) as session:
            session.execute(
                delete(TenantUsageEvent).where(TenantUsageEvent.tenant_id == tenant_id)
            )
            session.execute(
                delete(TenantUsageRecord).where(TenantUsageRecord.tenant_id == tenant_id)
            )
            session.commit()
        engine.dispose()
