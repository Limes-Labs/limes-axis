from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.audit import AuditEventCreate
from axis_api.config import Settings
from axis_api.maintenance_jobs import (
    AUDIT_RETENTION_JOB_EVENT_TYPE,
    OIDC_SESSION_REVOKED_EVENT_TYPE,
    SESSION_SWEEP_JOB_EVENT_TYPE,
    TENANT_RECONCILIATION_JOB_EVENT_TYPE,
    run_audit_retention_deletion_job,
    run_orphaned_session_sweep_job,
    run_tenant_state_reconciliation_job,
)
from axis_api.models import AuditEvent, Base, OidcBrowserSession
from axis_api.persistence import AxisPersistenceRepository, TenantCreate, TenantQuotaUpsert


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


def _settings(**overrides) -> Settings:
    base = {
        "AXIS_SCHEDULED_AUDIT_RETENTION_DAYS": "30",
        "AXIS_SCHEDULED_AUDIT_RETENTION_DRY_RUN": "false",
        "AXIS_OIDC_SESSION_IDLE_TIMEOUT_SECONDS": "1800",
        "AXIS_OIDC_REFRESH_CLAIM_STALENESS_SECONDS": "120",
    }
    base.update(overrides)
    return Settings(**base)


def _seed_tenant(repository: AxisPersistenceRepository, tenant_id: str, status: str = "active"):
    return repository.create_tenant(
        TenantCreate(
            tenant_id=tenant_id,
            display_name=tenant_id,
            status=status,
            created_by="test",
        )
    )


def _seed_session(
    session: Session,
    *,
    hash_prefix: str,
    tenant_id: str,
    status: str = "active",
    expires_at: datetime | None = None,
    absolute_expires_at: datetime | None = None,
    last_seen_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> OidcBrowserSession:
    now = datetime.now(UTC)
    row = OidcBrowserSession(
        session_id_hash=hash_prefix * 64,
        tenant_id=tenant_id,
        actor_id=f"actor-{hash_prefix}",
        status=status,
        scopes=[],
        expires_at=expires_at or now + timedelta(hours=1),
        absolute_expires_at=absolute_expires_at,
        last_seen_at=last_seen_at,
        refresh_token_ciphertext="cipher",
    )
    session.add(row)
    session.flush()
    if updated_at is not None:
        row.updated_at = updated_at
        session.flush()
    return row


def _events(session: Session, event_type: str) -> list[AuditEvent]:
    return list(
        session.scalars(select(AuditEvent).where(AuditEvent.event_type == event_type))
    )


# ---------------------------------------------------------------------------
# Audit retention deletion job
# ---------------------------------------------------------------------------


def test_audit_retention_job_deletes_old_events_and_is_idempotent(session_factory) -> None:
    settings = _settings()
    with session_factory() as session:
        repo = AxisPersistenceRepository(session)
        _seed_tenant(repo, "tenant_a")
        old = repo.append_audit_event(
            AuditEventCreate(tenant_id="tenant_a", actor_id="a", event_type="demo.old", payload={})
        )
        old.created_at = datetime.now(UTC) - timedelta(days=400)
        repo.append_audit_event(
            AuditEventCreate(
                tenant_id="tenant_a", actor_id="a", event_type="demo.fresh", payload={}
            )
        )
        session.commit()

        result = run_audit_retention_deletion_job(repo, settings=settings)
        session.commit()

        assert result.job == "audit_retention_deletion"
        assert result.status == "completed"
        assert result.items_affected == 1
        assert result.tenants_scanned == 1
        # Summary evidence event is appended.
        assert _events(session, AUDIT_RETENTION_JOB_EVENT_TYPE)

        # Idempotent re-run: nothing eligible remains.
        rerun = run_audit_retention_deletion_job(repo, settings=settings)
        session.commit()
        assert rerun.items_affected == 0


def test_audit_retention_job_dry_run_deletes_nothing(session_factory) -> None:
    settings = _settings(AXIS_SCHEDULED_AUDIT_RETENTION_DRY_RUN="true")
    with session_factory() as session:
        repo = AxisPersistenceRepository(session)
        _seed_tenant(repo, "tenant_a")
        old = repo.append_audit_event(
            AuditEventCreate(tenant_id="tenant_a", actor_id="a", event_type="demo.old", payload={})
        )
        old.created_at = datetime.now(UTC) - timedelta(days=400)
        session.commit()

        result = run_audit_retention_deletion_job(repo, settings=settings)
        session.commit()

        assert result.items_scanned == 1
        assert result.items_affected == 0
        assert result.details["dry_run"] is True


def test_audit_retention_job_is_tenant_scoped(session_factory) -> None:
    settings = _settings()
    with session_factory() as session:
        repo = AxisPersistenceRepository(session)
        _seed_tenant(repo, "tenant_a")
        _seed_tenant(repo, "tenant_b")
        for tenant in ("tenant_a", "tenant_b"):
            evt = repo.append_audit_event(
                AuditEventCreate(tenant_id=tenant, actor_id="a", event_type="demo.old", payload={})
            )
            evt.created_at = datetime.now(UTC) - timedelta(days=400)
        session.commit()

        result = run_audit_retention_deletion_job(
            repo, settings=settings, tenant_ids=["tenant_a"]
        )
        session.commit()

        assert result.tenants_scanned == 1
        assert result.items_affected == 1
        # tenant_b's old event survives because it was out of scope.
        remaining = list(
            session.scalars(
                select(AuditEvent).where(
                    AuditEvent.tenant_id == "tenant_b", AuditEvent.event_type == "demo.old"
                )
            )
        )
        assert len(remaining) == 1


def test_audit_retention_job_no_op_when_no_events(session_factory) -> None:
    settings = _settings()
    with session_factory() as session:
        repo = AxisPersistenceRepository(session)
        _seed_tenant(repo, "tenant_a")
        session.commit()

        result = run_audit_retention_deletion_job(repo, settings=settings)
        session.commit()

        assert result.items_scanned == 0
        assert result.items_affected == 0
        assert result.status == "completed"


# ---------------------------------------------------------------------------
# Orphaned / expired session sweep job
# ---------------------------------------------------------------------------


def test_session_sweep_revokes_stale_refreshing_and_expired(session_factory) -> None:
    settings = _settings()
    now = datetime.now(UTC)
    with session_factory() as session:
        repo = AxisPersistenceRepository(session)
        # Orphaned refreshing (updated_at older than staleness window).
        _seed_session(
            session,
            hash_prefix="a",
            tenant_id="tenant_a",
            status="refreshing",
            updated_at=now - timedelta(seconds=600),
        )
        # Expired active (absolute timeout passed).
        _seed_session(
            session,
            hash_prefix="b",
            tenant_id="tenant_a",
            status="active",
            expires_at=now + timedelta(hours=1),
            absolute_expires_at=now - timedelta(minutes=1),
        )
        # Idle active (last_seen older than idle timeout).
        _seed_session(
            session,
            hash_prefix="c",
            tenant_id="tenant_a",
            status="active",
            last_seen_at=now - timedelta(hours=2),
        )
        # Fresh active (must be preserved).
        fresh = _seed_session(
            session,
            hash_prefix="d",
            tenant_id="tenant_a",
            status="active",
            last_seen_at=now,
        )
        # Fresh refreshing (recently claimed, must be preserved).
        recent_refreshing = _seed_session(
            session,
            hash_prefix="e",
            tenant_id="tenant_a",
            status="refreshing",
            updated_at=now - timedelta(seconds=5),
        )
        session.commit()
        fresh_id, recent_id = fresh.id, recent_refreshing.id

        result = run_orphaned_session_sweep_job(repo, settings=settings, now=now)
        session.commit()

        assert result.status == "completed"
        assert result.items_affected == 3
        assert result.details["orphaned_revoked"] == 1
        assert result.details["expired_revoked"] == 2

        assert session.get(OidcBrowserSession, fresh_id).status == "active"
        assert session.get(OidcBrowserSession, recent_id).status == "refreshing"

        # Reuses the request-path revoke audit event.
        revoked_events = _events(session, OIDC_SESSION_REVOKED_EVENT_TYPE)
        assert len(revoked_events) == 3
        assert _events(session, SESSION_SWEEP_JOB_EVENT_TYPE)


def test_session_sweep_is_idempotent(session_factory) -> None:
    settings = _settings()
    now = datetime.now(UTC)
    with session_factory() as session:
        repo = AxisPersistenceRepository(session)
        _seed_session(
            session,
            hash_prefix="a",
            tenant_id="tenant_a",
            status="refreshing",
            updated_at=now - timedelta(seconds=600),
        )
        session.commit()

        first = run_orphaned_session_sweep_job(repo, settings=settings, now=now)
        session.commit()
        assert first.items_affected == 1

        second = run_orphaned_session_sweep_job(repo, settings=settings, now=now)
        session.commit()
        assert second.items_affected == 0
        assert second.status == "completed"


def test_session_sweep_is_tenant_scoped(session_factory) -> None:
    settings = _settings()
    now = datetime.now(UTC)
    with session_factory() as session:
        repo = AxisPersistenceRepository(session)
        _seed_session(
            session,
            hash_prefix="a",
            tenant_id="tenant_a",
            status="refreshing",
            updated_at=now - timedelta(seconds=600),
        )
        b = _seed_session(
            session,
            hash_prefix="b",
            tenant_id="tenant_b",
            status="refreshing",
            updated_at=now - timedelta(seconds=600),
        )
        session.commit()
        b_id = b.id

        result = run_orphaned_session_sweep_job(
            repo, settings=settings, tenant_id="tenant_a", now=now
        )
        session.commit()

        assert result.items_affected == 1
        assert result.tenants_scanned == 1
        assert session.get(OidcBrowserSession, b_id).status == "refreshing"


def test_session_sweep_no_op_records_completed(session_factory) -> None:
    settings = _settings()
    with session_factory() as session:
        repo = AxisPersistenceRepository(session)
        result = run_orphaned_session_sweep_job(repo, settings=settings)
        session.commit()
        assert result.items_scanned == 0
        assert result.items_affected == 0
        assert result.status == "completed"
        assert _events(session, SESSION_SWEEP_JOB_EVENT_TYPE)


# ---------------------------------------------------------------------------
# Tenant state reconciliation job
# ---------------------------------------------------------------------------


def test_reconciliation_flags_unknown_quota_key(session_factory) -> None:
    settings = _settings()
    with session_factory() as session:
        repo = AxisPersistenceRepository(session)
        _seed_tenant(repo, "tenant_a")
        repo.upsert_tenant_quota(
            TenantQuotaUpsert(
                tenant_id="tenant_a",
                quota_key="bogus_quota",
                quota_value=10,
                updated_by="test",
            )
        )
        session.commit()

        result = run_tenant_state_reconciliation_job(repo, settings=settings)
        session.commit()

        assert result.tenants_scanned == 1
        assert result.items_affected >= 1
        findings = result.details["tenants"]["tenant_a"]["findings"]
        assert any("unknown_quota_key" in f for f in findings)
        assert _events(session, TENANT_RECONCILIATION_JOB_EVENT_TYPE)


def test_reconciliation_revokes_sessions_on_suspended_tenant(session_factory) -> None:
    settings = _settings()
    now = datetime.now(UTC)
    with session_factory() as session:
        repo = AxisPersistenceRepository(session)
        _seed_tenant(repo, "tenant_a", status="suspended")
        active = _seed_session(
            session,
            hash_prefix="a",
            tenant_id="tenant_a",
            status="active",
            last_seen_at=now,
        )
        session.commit()
        active_id = active.id

        result = run_tenant_state_reconciliation_job(repo, settings=settings, now=now)
        session.commit()

        assert result.details["sessions_revoked"] == 1
        assert session.get(OidcBrowserSession, active_id).status == "revoked"
        assert _events(session, OIDC_SESSION_REVOKED_EVENT_TYPE)


def test_reconciliation_clean_tenant_is_no_op_and_idempotent(session_factory) -> None:
    settings = _settings()
    with session_factory() as session:
        repo = AxisPersistenceRepository(session)
        _seed_tenant(repo, "tenant_a")
        session.commit()

        first = run_tenant_state_reconciliation_job(repo, settings=settings)
        session.commit()
        assert first.items_affected == 0
        # Only the summary event, no per-tenant finding event.
        assert first.details["tenants"]["tenant_a"]["findings"] == []

        second = run_tenant_state_reconciliation_job(repo, settings=settings)
        session.commit()
        assert second.items_affected == 0
        assert second.status == "completed"


def test_reconciliation_is_tenant_scoped(session_factory) -> None:
    settings = _settings()
    with session_factory() as session:
        repo = AxisPersistenceRepository(session)
        _seed_tenant(repo, "tenant_a")
        _seed_tenant(repo, "tenant_b")
        session.commit()

        result = run_tenant_state_reconciliation_job(
            repo, settings=settings, tenant_ids=["tenant_a"]
        )
        session.commit()

        assert result.tenants_scanned == 1
        assert "tenant_a" in result.details["tenants"]
        assert "tenant_b" not in result.details["tenants"]
