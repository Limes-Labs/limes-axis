"""Worker maintenance-activity tests against a real DB session (no live Temporal).

These verify the DB-owning activity adapter opens a transactional session, invokes
the shared ``axis_api.maintenance_jobs`` function and returns its structured,
JSON-serializable result. The heavy business-logic coverage lives in the API
suite (``test_maintenance_jobs.py``); here we assert the worker seam works and
commits its work.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from axis_api.audit import AuditEventCreate
from axis_api.config import Settings
from axis_api.models import AuditEvent, Base, OidcBrowserSession
from axis_api.persistence import AxisPersistenceRepository, TenantCreate
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_worker.maintenance_activities import MaintenanceActivities

pytestmark = pytest.mark.asyncio


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


def _settings() -> Settings:
    return Settings(
        AXIS_SCHEDULED_AUDIT_RETENTION_DAYS="30",
        AXIS_SCHEDULED_AUDIT_RETENTION_DRY_RUN="false",
    )


async def test_audit_retention_activity_commits_and_returns_result(session_factory) -> None:
    with session_factory() as session:
        repo = AxisPersistenceRepository(session)
        repo.create_tenant(
            TenantCreate(tenant_id="tenant_a", display_name="A", created_by="test")
        )
        old = repo.append_audit_event(
            AuditEventCreate(tenant_id="tenant_a", actor_id="a", event_type="demo.old", payload={})
        )
        old.created_at = datetime.now(UTC) - timedelta(days=400)
        session.commit()

    activities = MaintenanceActivities(_settings(), session_factory=session_factory)
    result = await activities.run_audit_retention_deletion()

    assert result["job"] == "audit_retention_deletion"
    assert result["status"] == "completed"
    assert result["items_affected"] == 1
    # Work was committed by the activity's session_scope.
    with session_factory() as session:
        surviving = list(
            session.scalars(select(AuditEvent).where(AuditEvent.event_type == "demo.old"))
        )
        assert surviving == []


async def test_session_sweep_activity_revokes_and_commits(session_factory) -> None:
    now = datetime.now(UTC)
    with session_factory() as session:
        row = OidcBrowserSession(
            session_id_hash="a" * 64,
            tenant_id="tenant_a",
            actor_id="actor",
            status="refreshing",
            scopes=[],
            expires_at=now + timedelta(hours=1),
            refresh_token_ciphertext="cipher",
        )
        session.add(row)
        session.flush()
        row.updated_at = now - timedelta(seconds=600)
        row_id = row.id
        session.commit()

    activities = MaintenanceActivities(_settings(), session_factory=session_factory)
    result = await activities.run_orphaned_session_sweep()

    assert result["job"] == "orphaned_session_sweep"
    assert result["items_affected"] == 1
    with session_factory() as session:
        assert session.get(OidcBrowserSession, row_id).status == "revoked"


async def test_tenant_reconciliation_activity_returns_result(session_factory) -> None:
    with session_factory() as session:
        repo = AxisPersistenceRepository(session)
        repo.create_tenant(
            TenantCreate(tenant_id="tenant_a", display_name="A", created_by="test")
        )
        session.commit()

    activities = MaintenanceActivities(_settings(), session_factory=session_factory)
    result = await activities.run_tenant_state_reconciliation()

    assert result["job"] == "tenant_state_reconciliation"
    assert result["status"] == "completed"
    assert result["tenants_scanned"] == 1
