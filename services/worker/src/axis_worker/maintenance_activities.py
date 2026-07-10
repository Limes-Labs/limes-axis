"""Temporal activities that execute scheduled maintenance jobs against Postgres.

The worker owns a SQLAlchemy session factory built from the shared
``axis_api.config.Settings`` (the same configuration the API reads) and passes it
to the reusable job functions in ``axis_api.maintenance_jobs``. No business logic
is duplicated here: the activity is a thin adapter that hands the DB session
factory to the shared function (which owns its own transaction boundaries) and
returns its structured, JSON-serializable result to the scheduling workflow.

Activities are registered on the worker with a bound
:class:`MaintenanceActivities` instance, mirroring how integration tests give the
worker DB access via ``axis_api.db.create_session_factory``.
"""

from __future__ import annotations

from axis_api.config import Settings
from axis_api.db import create_session_factory
from axis_api.maintenance_jobs import (
    run_audit_retention_deletion_job,
    run_orphaned_session_sweep_job,
    run_tenant_state_reconciliation_job,
)
from axis_api.telemetry import ATTR_JOB, ATTR_OUTCOME, set_span_attributes
from sqlalchemy.orm import Session, sessionmaker
from temporalio import activity

from axis_worker.telemetry import WorkerTelemetryRuntime, configure_worker_telemetry

AUDIT_RETENTION_ACTIVITY = "run_audit_retention_deletion"
SESSION_SWEEP_ACTIVITY = "run_orphaned_session_sweep"
TENANT_RECONCILIATION_ACTIVITY = "run_tenant_state_reconciliation"


class MaintenanceActivities:
    """DB-owning activity bundle for scheduled maintenance jobs."""

    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session] | None = None,
        telemetry: WorkerTelemetryRuntime | None = None,
    ) -> None:
        self.settings = settings
        self._session_factory = session_factory or create_session_factory(settings)
        # When telemetry is disabled (the default) this is a zero-overhead no-op
        # runtime, so activities stay branch-free.
        self._telemetry = telemetry or configure_worker_telemetry(settings)

    @activity.defn(name=AUDIT_RETENTION_ACTIVITY)
    async def run_audit_retention_deletion(self) -> dict:
        with self._telemetry.activity_span("axis.scheduled_job.audit_retention_deletion") as span:
            result = run_audit_retention_deletion_job(
                self._session_factory, settings=self.settings
            )
            set_span_attributes(span, {ATTR_JOB: result.job, ATTR_OUTCOME: result.status})
            self._telemetry.record_job_run(job=result.job, status=result.status)
            activity.logger.info(
                "audit_retention_deletion job=%s status=%s scanned=%s affected=%s duration_ms=%s",
                result.job,
                result.status,
                result.items_scanned,
                result.items_affected,
                result.duration_ms,
            )
            return result.model_dump(mode="json")

    @activity.defn(name=SESSION_SWEEP_ACTIVITY)
    async def run_orphaned_session_sweep(self) -> dict:
        with self._telemetry.activity_span("axis.scheduled_job.orphaned_session_sweep") as span:
            result = run_orphaned_session_sweep_job(self._session_factory, settings=self.settings)
            set_span_attributes(span, {ATTR_JOB: result.job, ATTR_OUTCOME: result.status})
            self._telemetry.record_job_run(job=result.job, status=result.status)
            activity.logger.info(
                "orphaned_session_sweep job=%s status=%s scanned=%s affected=%s duration_ms=%s",
                result.job,
                result.status,
                result.items_scanned,
                result.items_affected,
                result.duration_ms,
            )
            return result.model_dump(mode="json")

    @activity.defn(name=TENANT_RECONCILIATION_ACTIVITY)
    async def run_tenant_state_reconciliation(self) -> dict:
        with self._telemetry.activity_span(
            "axis.scheduled_job.tenant_state_reconciliation"
        ) as span:
            result = run_tenant_state_reconciliation_job(
                self._session_factory, settings=self.settings
            )
            set_span_attributes(span, {ATTR_JOB: result.job, ATTR_OUTCOME: result.status})
            self._telemetry.record_job_run(job=result.job, status=result.status)
            activity.logger.info(
                "tenant_state_reconciliation job=%s status=%s scanned=%s "
                "affected=%s duration_ms=%s",
                result.job,
                result.status,
                result.items_scanned,
                result.items_affected,
                result.duration_ms,
            )
            return result.model_dump(mode="json")
