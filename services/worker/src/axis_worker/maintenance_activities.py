"""Temporal activities that execute scheduled maintenance jobs against Postgres.

The worker owns a SQLAlchemy session factory built from the shared
``axis_api.config.Settings`` (the same configuration the API reads) and calls the
reusable job functions in ``axis_api.maintenance_jobs``. No business logic is
duplicated here: the activity is a thin, DB-owning adapter that opens a
transactional session, invokes the shared function and returns its structured,
JSON-serializable result to the scheduling workflow.

Activities are registered on the worker with a bound
:class:`MaintenanceActivities` instance, mirroring how integration tests give the
worker DB access via ``axis_api.db.create_session_factory``.
"""

from __future__ import annotations

from axis_api.config import Settings
from axis_api.db import create_session_factory, session_scope
from axis_api.maintenance_jobs import (
    run_audit_retention_deletion_job,
    run_orphaned_session_sweep_job,
    run_tenant_state_reconciliation_job,
)
from axis_api.persistence import AxisPersistenceRepository
from sqlalchemy.orm import Session, sessionmaker
from temporalio import activity

AUDIT_RETENTION_ACTIVITY = "run_audit_retention_deletion"
SESSION_SWEEP_ACTIVITY = "run_orphaned_session_sweep"
TENANT_RECONCILIATION_ACTIVITY = "run_tenant_state_reconciliation"


class MaintenanceActivities:
    """DB-owning activity bundle for scheduled maintenance jobs."""

    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        self.settings = settings
        self._session_factory = session_factory or create_session_factory(settings)

    @activity.defn(name=AUDIT_RETENTION_ACTIVITY)
    async def run_audit_retention_deletion(self) -> dict:
        with session_scope(self._session_factory) as session:
            repository = AxisPersistenceRepository(session)
            result = run_audit_retention_deletion_job(repository, settings=self.settings)
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
        with session_scope(self._session_factory) as session:
            repository = AxisPersistenceRepository(session)
            result = run_orphaned_session_sweep_job(repository, settings=self.settings)
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
        with session_scope(self._session_factory) as session:
            repository = AxisPersistenceRepository(session)
            result = run_tenant_state_reconciliation_job(repository, settings=self.settings)
        activity.logger.info(
            "tenant_state_reconciliation job=%s status=%s scanned=%s affected=%s duration_ms=%s",
            result.job,
            result.status,
            result.items_scanned,
            result.items_affected,
            result.duration_ms,
        )
        return result.model_dump(mode="json")
