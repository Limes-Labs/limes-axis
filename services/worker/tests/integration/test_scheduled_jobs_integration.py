import os
from uuid import uuid4

import pytest
from axis_api.config import Settings
from axis_api.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from axis_worker.maintenance_activities import MaintenanceActivities
from axis_worker.workflows.maintenance_workflows import OrphanedSessionSweepWorkflow

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("AXIS_RUN_INTEGRATION") != "1",
        reason="set AXIS_RUN_INTEGRATION=1 with the local Docker runtime running",
    ),
]


async def test_scheduled_workflow_drives_activity_end_to_end() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    activities = MaintenanceActivities(Settings(), session_factory=factory)

    task_queue = f"axis-scheduled-{uuid4().hex}"
    async with await WorkflowEnvironment.start_time_skipping() as env, Worker(
        env.client,
        task_queue=task_queue,
        workflows=[OrphanedSessionSweepWorkflow],
        activities=[activities.run_orphaned_session_sweep],
    ):
        result = await env.client.execute_workflow(
            OrphanedSessionSweepWorkflow.run,
            id=f"axis-sweep-{uuid4().hex}",
            task_queue=task_queue,
        )

    assert result["job"] == "orphaned_session_sweep"
    assert result["status"] == "completed"
    engine.dispose()
