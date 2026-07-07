"""Worker runtime entry point: connect to Temporal, register schedules, poll.

This is the process that ``make`` / docker-compose runs. On startup it:

1. builds the shared ``axis_api.config.Settings`` (same env the API reads);
2. connects to Temporal;
3. idempotently creates/updates the maintenance Schedules (paused unless
   ``AXIS_SCHEDULED_JOBS_ENABLED`` is true);
4. runs a Temporal :class:`~temporalio.worker.Worker` on the ``axis-foundation``
   task queue hosting the approval workflow plus the scheduled maintenance
   workflows and their DB-owning activities.

Kept import-light and side-effect free at module load so tests can import the
pieces without connecting to Temporal.
"""

from __future__ import annotations

import asyncio
import logging

from axis_api.config import Settings
from temporalio.client import Client
from temporalio.worker import Worker

from axis_worker.maintenance_activities import MaintenanceActivities
from axis_worker.schedules import register_maintenance_schedules
from axis_worker.temporal_adapter import TemporalAdapterConfig
from axis_worker.workflows.approval_workflow import ApprovalWorkflow
from axis_worker.workflows.maintenance_workflows import (
    AuditRetentionDeletionWorkflow,
    OrphanedSessionSweepWorkflow,
    TenantStateReconciliationWorkflow,
)

logger = logging.getLogger("axis_worker.runtime")

WORKFLOWS = [
    ApprovalWorkflow,
    AuditRetentionDeletionWorkflow,
    OrphanedSessionSweepWorkflow,
    TenantStateReconciliationWorkflow,
]


def adapter_config_from_settings(settings: Settings) -> TemporalAdapterConfig:
    return TemporalAdapterConfig(
        address=settings.temporal_address,
        namespace=settings.temporal_namespace,
    )


async def run_worker(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    config = adapter_config_from_settings(settings)
    client = await Client.connect(config.address, namespace=config.namespace)

    outcomes = await register_maintenance_schedules(
        client, settings, task_queue=config.task_queue
    )
    logger.info(
        "scheduled maintenance schedules reconciled enabled=%s outcomes=%s",
        settings.scheduled_jobs_enabled,
        outcomes,
    )

    activities = MaintenanceActivities(settings)
    worker = Worker(
        client,
        task_queue=config.task_queue,
        workflows=WORKFLOWS,
        activities=[
            activities.run_audit_retention_deletion,
            activities.run_orphaned_session_sweep,
            activities.run_tenant_state_reconciliation,
        ],
    )
    logger.info("axis-worker started task_queue=%s", config.task_queue)
    await worker.run()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
