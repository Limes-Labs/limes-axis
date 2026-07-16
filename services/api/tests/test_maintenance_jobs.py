from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.audit import AuditEventCreate
from axis_api.config import Settings
from axis_api.db import session_scope
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


def _seed_tenant(factory, tenant_id: str, status: str = "active") -> None:
    with session_scope(factory) as session:
        AxisPersistenceRepository(session).create_tenant(
            TenantCreate(
                tenant_id=tenant_id,
                display_name=tenant_id,
                status=status,
                created_by="test",
            )
        )


def _seed_old_event(factory, tenant_id: str, event_type: str = "demo.old") -> None:
    with session_scope(factory) as session:
        repo = AxisPersistenceRepository(session)
        evt = repo.append_audit_event(
            AuditEventCreate(tenant_id=tenant_id, actor_id="a", event_type=event_type, payload={})
        )
        evt.created_at = datetime.now(UTC) - timedelta(days=400)


def _seed_session(
    factory,
    *,
    hash_prefix: str,
    tenant_id: str,
    status: str = "active",
    expires_at: datetime | None = None,
    absolute_expires_at: datetime | None = None,
    last_seen_at: datetime | None = None,
    updated_at: datetime | None = None,
):
    with session_scope(factory) as session:
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
        return row.id


def _events(factory, event_type: str) -> list[AuditEvent]:
    with session_scope(factory) as session:
        return list(
            session.scalars(select(AuditEvent).where(AuditEvent.event_type == event_type))
        )


def _session_status(factory, row_id):
    with session_scope(factory) as session:
        return session.get(OidcBrowserSession, row_id).status


def _count_events(factory, event_type: str) -> int:
    return len(_events(factory, event_type))


# ---------------------------------------------------------------------------
# Audit retention deletion job
# ---------------------------------------------------------------------------


def test_audit_retention_job_deletes_old_events_and_is_idempotent(session_factory) -> None:
    settings = _settings()
    _seed_tenant(session_factory, "tenant_a")
    _seed_old_event(session_factory, "tenant_a")
    with session_scope(session_factory) as session:
        AxisPersistenceRepository(session).append_audit_event(
            AuditEventCreate(
                tenant_id="tenant_a", actor_id="a", event_type="demo.fresh", payload={}
            )
        )

    result = run_audit_retention_deletion_job(session_factory, settings=settings)

    assert result.job == "audit_retention_deletion"
    assert result.status == "completed"
    assert result.items_affected == 1
    assert result.tenants_scanned == 1
    assert _events(session_factory, AUDIT_RETENTION_JOB_EVENT_TYPE)

    rerun = run_audit_retention_deletion_job(session_factory, settings=settings)
    assert rerun.items_affected == 0


def test_audit_retention_job_dry_run_deletes_nothing(session_factory) -> None:
    settings = _settings(AXIS_SCHEDULED_AUDIT_RETENTION_DRY_RUN="true")
    _seed_tenant(session_factory, "tenant_a")
    _seed_old_event(session_factory, "tenant_a")

    result = run_audit_retention_deletion_job(session_factory, settings=settings)

    assert result.items_scanned == 1
    assert result.items_affected == 0
    assert result.details["dry_run"] is True


def test_audit_retention_job_is_tenant_scoped(session_factory) -> None:
    settings = _settings()
    _seed_tenant(session_factory, "tenant_a")
    _seed_tenant(session_factory, "tenant_b")
    _seed_old_event(session_factory, "tenant_a")
    _seed_old_event(session_factory, "tenant_b")

    result = run_audit_retention_deletion_job(
        session_factory, settings=settings, tenant_ids=["tenant_a"]
    )

    assert result.tenants_scanned == 1
    assert result.items_affected == 1
    with session_scope(session_factory) as session:
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
    _seed_tenant(session_factory, "tenant_a")

    result = run_audit_retention_deletion_job(session_factory, settings=settings)

    assert result.items_scanned == 0
    assert result.items_affected == 0
    assert result.status == "completed"


def test_audit_retention_job_pages_through_all_tenants(session_factory) -> None:
    # More tenants than a single _TENANT_PAGE_SIZE (500) page.
    settings = _settings()
    for i in range(600):
        _seed_tenant(session_factory, f"tenant_{i:04d}")
    # Seed an old event only on a tenant that falls on the second page.
    _seed_old_event(session_factory, "tenant_0555")

    result = run_audit_retention_deletion_job(session_factory, settings=settings)

    assert result.tenants_scanned == 600
    assert result.items_affected == 1
    assert result.details["tenant_cap_reached"] is False


def test_audit_retention_job_records_partial_failure_and_keeps_successes(
    session_factory, monkeypatch
) -> None:
    settings = _settings()
    _seed_tenant(session_factory, "tenant_ok")
    _seed_tenant(session_factory, "tenant_bad")
    _seed_old_event(session_factory, "tenant_ok")
    _seed_old_event(session_factory, "tenant_bad")

    import axis_api.maintenance_jobs as mod

    real = mod.execute_audit_retention_deletion

    def flaky(repository, request):
        if request.tenant_id == "tenant_bad":
            raise RuntimeError("boom")
        return real(repository, request)

    monkeypatch.setattr(mod, "execute_audit_retention_deletion", flaky)

    result = run_audit_retention_deletion_job(session_factory, settings=settings)

    assert result.status == "partial_failure"
    assert any("tenant_bad" in e for e in result.errors)
    # tenant_ok's deletion committed despite tenant_bad failing.
    assert result.items_affected == 1
    with session_scope(session_factory) as session:
        ok_remaining = list(
            session.scalars(
                select(AuditEvent).where(
                    AuditEvent.tenant_id == "tenant_ok", AuditEvent.event_type == "demo.old"
                )
            )
        )
        bad_remaining = list(
            session.scalars(
                select(AuditEvent).where(
                    AuditEvent.tenant_id == "tenant_bad", AuditEvent.event_type == "demo.old"
                )
            )
        )
    assert ok_remaining == []
    assert len(bad_remaining) == 1
    # The summary evidence is still written despite the failure.
    assert _events(session_factory, AUDIT_RETENTION_JOB_EVENT_TYPE)


# ---------------------------------------------------------------------------
# Orphaned / expired session sweep job
# ---------------------------------------------------------------------------


def test_session_sweep_revokes_stale_refreshing_and_expired(session_factory) -> None:
    settings = _settings()
    now = datetime.now(UTC)
    _seed_session(
        session_factory,
        hash_prefix="a",
        tenant_id="tenant_a",
        status="refreshing",
        updated_at=now - timedelta(seconds=600),
    )
    _seed_session(
        session_factory,
        hash_prefix="b",
        tenant_id="tenant_a",
        status="active",
        expires_at=now + timedelta(hours=1),
        absolute_expires_at=now - timedelta(minutes=1),
    )
    _seed_session(
        session_factory,
        hash_prefix="c",
        tenant_id="tenant_a",
        status="active",
        last_seen_at=now - timedelta(hours=2),
    )
    fresh_id = _seed_session(
        session_factory,
        hash_prefix="d",
        tenant_id="tenant_a",
        status="active",
        last_seen_at=now,
    )
    recent_id = _seed_session(
        session_factory,
        hash_prefix="e",
        tenant_id="tenant_a",
        status="refreshing",
        updated_at=now - timedelta(seconds=5),
    )

    result = run_orphaned_session_sweep_job(session_factory, settings=settings, now=now)

    assert result.status == "completed"
    assert result.items_affected == 3
    assert result.details["orphaned_revoked"] == 1
    assert result.details["expired_revoked"] == 2
    assert _session_status(session_factory, fresh_id) == "active"
    assert _session_status(session_factory, recent_id) == "refreshing"
    assert _count_events(session_factory, OIDC_SESSION_REVOKED_EVENT_TYPE) == 3
    assert _events(session_factory, SESSION_SWEEP_JOB_EVENT_TYPE)


def test_session_sweep_is_idempotent(session_factory) -> None:
    settings = _settings()
    now = datetime.now(UTC)
    _seed_session(
        session_factory,
        hash_prefix="a",
        tenant_id="tenant_a",
        status="refreshing",
        updated_at=now - timedelta(seconds=600),
    )

    first = run_orphaned_session_sweep_job(session_factory, settings=settings, now=now)
    assert first.items_affected == 1

    second = run_orphaned_session_sweep_job(session_factory, settings=settings, now=now)
    assert second.items_affected == 0
    assert second.status == "completed"


def test_session_sweep_is_tenant_scoped(session_factory) -> None:
    settings = _settings()
    now = datetime.now(UTC)
    _seed_session(
        session_factory,
        hash_prefix="a",
        tenant_id="tenant_a",
        status="refreshing",
        updated_at=now - timedelta(seconds=600),
    )
    b_id = _seed_session(
        session_factory,
        hash_prefix="b",
        tenant_id="tenant_b",
        status="refreshing",
        updated_at=now - timedelta(seconds=600),
    )

    result = run_orphaned_session_sweep_job(
        session_factory, settings=settings, tenant_id="tenant_a", now=now
    )

    assert result.items_affected == 1
    assert result.tenants_scanned == 1
    assert _session_status(session_factory, b_id) == "refreshing"


def test_session_sweep_no_op_records_completed(session_factory) -> None:
    settings = _settings()
    result = run_orphaned_session_sweep_job(session_factory, settings=settings)
    assert result.items_scanned == 0
    assert result.items_affected == 0
    assert result.status == "completed"
    assert _events(session_factory, SESSION_SWEEP_JOB_EVENT_TYPE)


def test_session_sweep_boundary_matches_request_path(session_factory) -> None:
    """A session exactly at the staleness threshold is treated by the sweep
    identically to the request path (browser_session_lifecycle_failure).

    Both use inclusive ``<= now`` comparisons at the boundary. A refreshing row
    whose updated_at equals now-staleness (the claim deadline) is swept and is
    classified by the request-path helper as an orphaned revocation; a row one
    second fresher is preserved by the sweep.
    """
    from axis_api.session_lifecycle import browser_session_lifecycle_failure

    settings = _settings()
    now = datetime.now(UTC)
    staleness = settings.oidc_refresh_claim_staleness_seconds

    at_boundary_id = _seed_session(
        session_factory,
        hash_prefix="a",
        tenant_id="tenant_a",
        status="refreshing",
        updated_at=now - timedelta(seconds=staleness),
    )
    fresher_id = _seed_session(
        session_factory,
        hash_prefix="b",
        tenant_id="tenant_a",
        status="refreshing",
        updated_at=now - timedelta(seconds=staleness - 1),
    )

    with session_scope(session_factory) as session:
        repo = AxisPersistenceRepository(session)
        at_boundary_row = repo.get_oidc_browser_session_by_row_id(at_boundary_id)
        fresher_row = repo.get_oidc_browser_session_by_row_id(fresher_id)
        # Request-path verdict for the boundary row: orphaned revocation.
        boundary_failure = browser_session_lifecycle_failure(at_boundary_row, settings)
        assert at_boundary_row.status == "refreshing"
        assert fresher_row.status == "refreshing"

    assert boundary_failure is not None
    assert boundary_failure[0] == "revoked_session_cookie"
    assert boundary_failure[1] == "refresh_claim_orphaned"

    result = run_orphaned_session_sweep_job(session_factory, settings=settings, now=now)

    # The boundary session is swept; the fresher one is preserved.
    assert _session_status(session_factory, at_boundary_id) == "revoked"
    assert _session_status(session_factory, fresher_id) == "refreshing"
    assert result.details["orphaned_revoked"] == 1


# ---------------------------------------------------------------------------
# Tenant state reconciliation job
# ---------------------------------------------------------------------------


def test_reconciliation_flags_unknown_quota_key(session_factory) -> None:
    settings = _settings()
    _seed_tenant(session_factory, "tenant_a")
    with session_scope(session_factory) as session:
        AxisPersistenceRepository(session).upsert_tenant_quota(
            TenantQuotaUpsert(
                tenant_id="tenant_a",
                quota_key="bogus_quota",
                quota_value=10,
                updated_by="test",
            )
        )

    result = run_tenant_state_reconciliation_job(session_factory, settings=settings)

    assert result.tenants_scanned == 1
    assert result.items_affected >= 1
    findings = result.details["tenants"]["tenant_a"]["findings"]
    assert any("unknown_quota_key" in f for f in findings)
    assert _events(session_factory, TENANT_RECONCILIATION_JOB_EVENT_TYPE)


def test_reconciliation_revokes_sessions_on_suspended_tenant(session_factory) -> None:
    settings = _settings()
    now = datetime.now(UTC)
    _seed_tenant(session_factory, "tenant_a", status="suspended")
    active_id = _seed_session(
        session_factory,
        hash_prefix="a",
        tenant_id="tenant_a",
        status="active",
        last_seen_at=now,
    )

    result = run_tenant_state_reconciliation_job(session_factory, settings=settings, now=now)

    assert result.details["sessions_revoked"] == 1
    assert _session_status(session_factory, active_id) == "revoked"
    assert _events(session_factory, OIDC_SESSION_REVOKED_EVENT_TYPE)


def test_reconciliation_clean_tenant_is_no_op_and_idempotent(session_factory) -> None:
    settings = _settings()
    _seed_tenant(session_factory, "tenant_a")

    first = run_tenant_state_reconciliation_job(session_factory, settings=settings)
    assert first.items_affected == 0
    assert first.details["tenants"]["tenant_a"]["findings"] == []

    second = run_tenant_state_reconciliation_job(session_factory, settings=settings)
    assert second.items_affected == 0
    assert second.status == "completed"


def test_reconciliation_is_tenant_scoped(session_factory) -> None:
    settings = _settings()
    _seed_tenant(session_factory, "tenant_a")
    _seed_tenant(session_factory, "tenant_b")

    result = run_tenant_state_reconciliation_job(
        session_factory, settings=settings, tenant_ids=["tenant_a"]
    )

    assert result.tenants_scanned == 1
    assert "tenant_a" in result.details["tenants"]
    assert "tenant_b" not in result.details["tenants"]


def test_reconciliation_records_partial_failure_and_keeps_successes(
    session_factory, monkeypatch
) -> None:
    settings = _settings()
    _seed_tenant(session_factory, "tenant_ok")
    _seed_tenant(session_factory, "tenant_bad")
    with session_scope(session_factory) as session:
        AxisPersistenceRepository(session).upsert_tenant_quota(
            TenantQuotaUpsert(
                tenant_id="tenant_ok",
                quota_key="bogus_quota",
                quota_value=1,
                updated_by="test",
            )
        )

    import axis_api.maintenance_jobs as mod

    real = mod._reconcile_one_tenant

    def flaky(factory, tenant_id, *, settings, now):
        if tenant_id == "tenant_bad":
            raise RuntimeError("boom")
        return real(factory, tenant_id, settings=settings, now=now)

    monkeypatch.setattr(mod, "_reconcile_one_tenant", flaky)

    result = run_tenant_state_reconciliation_job(session_factory, settings=settings)

    assert result.status == "partial_failure"
    assert any("tenant_bad" in e for e in result.errors)
    # tenant_ok's finding evidence still committed.
    assert result.details["tenants"]["tenant_ok"]["findings"]
    assert _events(session_factory, TENANT_RECONCILIATION_JOB_EVENT_TYPE)
