import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.models import OidcBrowserSession
from axis_api.persistence import AxisPersistenceRepository, OidcBrowserSessionRevocation

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("AXIS_RUN_INTEGRATION") != "1",
        reason="set AXIS_RUN_INTEGRATION=1 with the local Docker runtime running",
    ),
]


def test_postgres_oidc_admission_lock_serializes_same_principal_only() -> None:
    engine = create_engine(Settings().postgres_dsn, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    first = factory()
    executor = ThreadPoolExecutor(max_workers=2)
    same_principal_acquired = Event()
    other_principal_acquired = Event()

    def acquire_same_principal() -> None:
        with session_scope(factory) as session:
            AxisPersistenceRepository(session).acquire_oidc_session_admission_lock(
                tenant_id="tenant_lock_integration",
                actor_id="shared-actor",
            )
            same_principal_acquired.set()

    def acquire_other_principal() -> None:
        with session_scope(factory) as session:
            AxisPersistenceRepository(session).acquire_oidc_session_admission_lock(
                tenant_id="tenant_lock_integration",
                actor_id="other-actor",
            )
            other_principal_acquired.set()

    try:
        first.begin()
        AxisPersistenceRepository(first).acquire_oidc_session_admission_lock(
            tenant_id="tenant_lock_integration",
            actor_id="shared-actor",
        )
        same_future = executor.submit(acquire_same_principal)
        other_future = executor.submit(acquire_other_principal)

        assert other_principal_acquired.wait(timeout=2)
        assert not same_principal_acquired.wait(timeout=0.25)
        first.commit()
        assert same_principal_acquired.wait(timeout=2)
        same_future.result()
        other_future.result()
    finally:
        if first.in_transaction():
            first.rollback()
        first.close()
        executor.shutdown(wait=True, cancel_futures=True)
        engine.dispose()


def test_postgres_reference_revocation_wins_against_waiting_refresh() -> None:
    engine = create_engine(Settings().postgres_dsn, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session_hash = uuid4().hex + uuid4().hex
    replacement_hash = uuid4().hex + uuid4().hex
    tenant_id = "tenant_lock_integration"
    refresh_finished = Event()
    refresh_results: list[bool] = []

    with session_scope(factory) as session:
        stored = OidcBrowserSession(
            session_id_hash=session_hash,
            tenant_id=tenant_id,
            actor_id="shared-actor",
            status="refreshing",
            scopes=[],
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        session.add(stored)
        session.flush()
        session_ref = stored.id

    first = factory()
    executor = ThreadPoolExecutor(max_workers=1)

    def finalize_refresh() -> None:
        try:
            with session_scope(factory) as session:
                refresh_results.append(
                    AxisPersistenceRepository(session).finalize_oidc_browser_session_refresh(
                        session_id_hash=session_hash,
                        rotated_to_session_id_hash=replacement_hash,
                    )
                )
        finally:
            refresh_finished.set()

    try:
        first.begin()
        repository = AxisPersistenceRepository(first)
        locked = repository.get_oidc_browser_session_for_update(tenant_id, session_ref)
        assert locked is not None
        refresh_future = executor.submit(finalize_refresh)

        assert not refresh_finished.wait(timeout=0.25)
        repository.revoke_oidc_browser_session(
            OidcBrowserSessionRevocation(
                session_id_hash=session_hash,
                revoked_by="identity-admin-role",
                revocation_reason="admin_revocation",
            )
        )
        first.commit()

        assert refresh_finished.wait(timeout=2)
        refresh_future.result()
        assert refresh_results == [False]
        with factory() as verification:
            stored = verification.scalar(
                select(OidcBrowserSession).where(OidcBrowserSession.session_id_hash == session_hash)
            )
            assert stored is not None
            assert stored.status == "revoked"
            assert stored.rotated_to_session_id_hash is None
    finally:
        if first.in_transaction():
            first.rollback()
        first.close()
        executor.shutdown(wait=True, cancel_futures=True)
        with session_scope(factory) as cleanup:
            stored = cleanup.scalar(
                select(OidcBrowserSession).where(OidcBrowserSession.session_id_hash == session_hash)
            )
            if stored is not None:
                cleanup.delete(stored)
        engine.dispose()
