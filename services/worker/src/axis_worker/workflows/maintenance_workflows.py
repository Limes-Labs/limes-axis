"""Scheduled maintenance workflows triggered by Temporal Schedules.

Each workflow is a thin driver: it invokes the matching DB-owning activity with a
bounded timeout and a retry policy, then returns the activity's structured result.
The real work (and all DB access) lives in the activity so workflow code stays
deterministic and side-effect free.

These workflows are started by Temporal Schedules (see
``axis_worker.schedules``), not by API signals. The schedule's overlap policy
(``SKIP``) guarantees a slow run never overlaps its successor, which — combined
with each job being individually idempotent — makes repeated/overlapping
invocations safe.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from axis_worker.maintenance_activities import (
        AUDIT_RETENTION_ACTIVITY,
        SESSION_SWEEP_ACTIVITY,
        TENANT_RECONCILIATION_ACTIVITY,
    )

_START_TO_CLOSE = timedelta(minutes=10)
_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=3,
)


@workflow.defn
class AuditRetentionDeletionWorkflow:
    @workflow.run
    async def run(self) -> dict:
        return await workflow.execute_activity(
            AUDIT_RETENTION_ACTIVITY,
            start_to_close_timeout=_START_TO_CLOSE,
            retry_policy=_RETRY_POLICY,
        )


@workflow.defn
class OrphanedSessionSweepWorkflow:
    @workflow.run
    async def run(self) -> dict:
        return await workflow.execute_activity(
            SESSION_SWEEP_ACTIVITY,
            start_to_close_timeout=_START_TO_CLOSE,
            retry_policy=_RETRY_POLICY,
        )


@workflow.defn
class TenantStateReconciliationWorkflow:
    @workflow.run
    async def run(self) -> dict:
        return await workflow.execute_activity(
            TENANT_RECONCILIATION_ACTIVITY,
            start_to_close_timeout=_START_TO_CLOSE,
            retry_policy=_RETRY_POLICY,
        )
