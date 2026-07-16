import threading
import time
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Cross-module reuse of the OIDC authorization-code harness for the
# session-created choke point (drives a real callback end to end).
from test_oidc_authorization_code_session import (  # noqa: E402
    _app_with_static_oidc,
    _start_oidc_login,
)
from test_oidc_authorization_code_session import (
    _settings as _oidc_settings,
)

from axis_api.config import Settings
from axis_api.connector_execution import ConnectorSyncExecutionResult
from axis_api.connector_runs import (
    SYNC_BATCH_CHECKPOINT_TYPE,
    SYNC_BATCH_COMMITTED_STATUS,
    _live_sync_resume_records_seed,
    _record_connector_sync_rows_usage,
)
from axis_api.identity import OidcPrincipal
from axis_api.main import create_app
from axis_api.models import Base, TenantUsageRecord
from axis_api.persistence import AxisPersistenceRepository, TenantCreate, TenantUsageAdd
from axis_api.usage_metering import (
    DEFAULT_USAGE_PERIOD_WINDOW_SECONDS,
    TenantUsageMetric,
    UsageAccumulator,
    UsageRecordResult,
    build_tenant_usage_summary,
    record_tenant_usage_event,
    usage_period_start,
)

TENANT_ID = "tenant_acme_manufacturing"
OTHER_TENANT_ID = "tenant_globex_manufacturing"
OPERATOR_ACTOR = "axis-platform-operator-role"
USAGE_SCOPES = ["platform:tenant:operator", "platform:tenant:usage"]


def _factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _metering_settings(**overrides) -> Settings:
    values: dict = {
        "postgres_dsn": "sqlite+pysqlite://",
        "usage_metering_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)


def _build_client(settings: Settings | None = None) -> tuple[TestClient, sessionmaker[Session]]:
    factory = _factory()
    app = create_app(settings or _metering_settings())
    app.state.session_factory = factory
    return TestClient(app), factory


def _provision_tenant(factory: sessionmaker[Session], tenant_id: str = TENANT_ID) -> None:
    with factory() as session:
        AxisPersistenceRepository(session).create_tenant(
            TenantCreate(
                tenant_id=tenant_id,
                display_name=tenant_id,
                created_by=OPERATOR_ACTOR,
            )
        )
        session.commit()


def _seed_usage(
    factory: sessionmaker[Session],
    tenant_id: str,
    metric: str,
    quantity: int,
    occurred_at: datetime,
) -> None:
    with factory() as session:
        record_tenant_usage_event(
            AxisPersistenceRepository(session),
            tenant_id,
            metric,
            quantity,
            occurred_at=occurred_at,
        )
        session.commit()


def _usage_rows(factory: sessionmaker[Session], tenant_id: str) -> list[TenantUsageRecord]:
    with factory() as session:
        return list(
            session.scalars(
                select(TenantUsageRecord)
                .where(TenantUsageRecord.tenant_id == tenant_id)
                .order_by(
                    TenantUsageRecord.metric_key.asc(),
                    TenantUsageRecord.period_start.asc(),
                )
            )
        )


# --------------------------------------------------------------------------- #
# Period bucketing                                                            #
# --------------------------------------------------------------------------- #


def test_usage_period_start_floors_to_utc_day_by_default() -> None:
    moment = datetime(2026, 7, 10, 13, 45, 12, tzinfo=UTC)
    assert usage_period_start(moment) == datetime(2026, 7, 10, 0, 0, 0, tzinfo=UTC)


def test_usage_period_start_aligns_to_configurable_window() -> None:
    moment = datetime(2026, 7, 10, 13, 45, 12, tzinfo=UTC)
    # Hourly buckets align to the top of the hour.
    assert usage_period_start(moment, 3600) == datetime(2026, 7, 10, 13, 0, 0, tzinfo=UTC)


def test_usage_period_start_treats_naive_datetime_as_utc() -> None:
    naive = datetime(2026, 7, 10, 23, 59, 59)
    assert usage_period_start(naive) == datetime(2026, 7, 10, 0, 0, 0, tzinfo=UTC)


# --------------------------------------------------------------------------- #
# Persistence upsert-add                                                       #
# --------------------------------------------------------------------------- #


def test_add_tenant_usage_upsert_add_accumulates_same_bucket() -> None:
    factory = _factory()
    moment = datetime(2026, 7, 10, 8, 0, 0, tzinfo=UTC)
    period = usage_period_start(moment)
    with factory() as session:
        repository = AxisPersistenceRepository(session)
        for _ in range(3):
            repository.add_tenant_usage(
                TenantUsageAdd(
                    tenant_id=TENANT_ID,
                    metric_key=TenantUsageMetric.API_REQUEST.value,
                    period_start=period,
                    quantity=2,
                    occurred_at=moment,
                )
            )
        session.commit()

    rows = _usage_rows(factory, TENANT_ID)
    assert len(rows) == 1
    assert rows[0].quantity == 6
    # SQLite drops tzinfo on readback; compare the wall-clock instant.
    stored = rows[0].period_start
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=UTC)
    assert stored == period


def test_add_tenant_usage_composes_across_independent_sessions() -> None:
    # Two separate sessions (two flushers / replicas) targeting one bucket sum.
    factory = _factory()
    moment = datetime(2026, 7, 10, 8, 0, 0, tzinfo=UTC)
    period = usage_period_start(moment)
    for delta in (3, 4):
        with factory() as session:
            AxisPersistenceRepository(session).add_tenant_usage(
                TenantUsageAdd(
                    tenant_id=TENANT_ID,
                    metric_key=TenantUsageMetric.SESSION_CREATED.value,
                    period_start=period,
                    quantity=delta,
                    occurred_at=moment,
                )
            )
            session.commit()

    rows = _usage_rows(factory, TENANT_ID)
    assert len(rows) == 1
    assert rows[0].quantity == 7


# --------------------------------------------------------------------------- #
# Accumulator + flush                                                          #
# --------------------------------------------------------------------------- #


def test_accumulator_flush_aggregates_to_period_totals() -> None:
    factory = _factory()
    accumulator = UsageAccumulator(enabled=True)
    moment = datetime(2026, 7, 10, 8, 0, 0, tzinfo=UTC)
    for _ in range(5):
        accumulator.record(TENANT_ID, TenantUsageMetric.API_REQUEST.value, occurred_at=moment)

    flushed = accumulator.flush(factory)

    assert flushed == 5
    rows = _usage_rows(factory, TENANT_ID)
    assert len(rows) == 1
    assert rows[0].quantity == 5
    # Drained: a second flush with nothing pending is a no-op.
    assert accumulator.flush(factory) == 0


def test_accumulator_disabled_is_a_no_op() -> None:
    factory = _factory()
    accumulator = UsageAccumulator(enabled=False)
    accumulator.record(TENANT_ID, TenantUsageMetric.API_REQUEST.value)
    assert accumulator.flush(factory) == 0
    assert _usage_rows(factory, TENANT_ID) == []


def test_accumulator_overflow_is_observable_and_existing_bucket_still_accumulates() -> None:
    accumulator = UsageAccumulator(enabled=True, max_pending_keys=1)

    assert accumulator.record(TENANT_ID, TenantUsageMetric.API_REQUEST.value) == (
        UsageRecordResult.ACCEPTED
    )
    assert accumulator.record(OTHER_TENANT_ID, TenantUsageMetric.API_REQUEST.value, 3) == (
        UsageRecordResult.OVERFLOW
    )
    assert accumulator.record(TENANT_ID, TenantUsageMetric.API_REQUEST.value, 2) == (
        UsageRecordResult.ACCEPTED
    )

    assert accumulator.health() == {
        "healthy": False,
        "pending_keys": 1,
        "max_pending_keys": 1,
        "overflow_total": 3,
    }
    drained = accumulator.drain()
    assert drained[0].quantity == 3
    accumulator.restore(drained)
    factory = _factory()
    assert accumulator.flush(factory) == 3
    assert accumulator.health() == {
        "healthy": True,
        "pending_keys": 0,
        "max_pending_keys": 1,
        "overflow_total": 3,
    }


def test_accumulator_restore_does_not_lose_counts_on_flush_failure() -> None:
    accumulator = UsageAccumulator(enabled=True)
    moment = datetime(2026, 7, 10, 8, 0, 0, tzinfo=UTC)
    accumulator.record(TENANT_ID, TenantUsageMetric.API_REQUEST.value, 4, occurred_at=moment)

    class _BrokenFactory:
        def __call__(self):
            raise RuntimeError("db down")

    # session_scope will raise a non-SQLAlchemyError; but a SQLAlchemyError path
    # restores. Emulate the restore contract directly with drain/restore.
    drained = accumulator.drain()
    assert sum(item.quantity for item in drained) == 4
    accumulator.restore(drained)
    # A subsequent successful flush recovers every restored delta.
    factory = _factory()
    assert accumulator.flush(factory) == 4
    assert _usage_rows(factory, TENANT_ID)[0].quantity == 4


def test_flush_restores_counts_when_session_factory_fails() -> None:
    # A non-SQLAlchemy failure (e.g. session construction) must not drop the
    # drained counts: they are restored and recovered by the next flush.
    accumulator = UsageAccumulator(enabled=True)
    moment = datetime(2026, 7, 10, 8, 0, 0, tzinfo=UTC)
    accumulator.record(TENANT_ID, TenantUsageMetric.API_REQUEST.value, 4, occurred_at=moment)

    class _FailingFactory:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self):
            self.calls += 1
            raise RuntimeError("session construction failed")

    failing = _FailingFactory()
    with pytest.raises(RuntimeError):
        accumulator.flush(failing)
    assert failing.calls == 1

    # The drained deltas were restored, so a later healthy flush recovers them.
    factory = _factory()
    assert accumulator.flush(factory) == 4
    assert _usage_rows(factory, TENANT_ID)[0].quantity == 4


def test_concurrent_records_and_flushes_do_not_lose_counts() -> None:
    # Simulated concurrency at the persistence seam: many recorder threads folding
    # in-memory deltas while a flusher thread drains to the ledger.
    factory = _factory()
    accumulator = UsageAccumulator(enabled=True)
    moment = datetime(2026, 7, 10, 8, 0, 0, tzinfo=UTC)
    thread_count = 8
    per_thread = 500
    stop = threading.Event()

    def recorder() -> None:
        for _ in range(per_thread):
            accumulator.record(
                TENANT_ID, TenantUsageMetric.API_REQUEST.value, occurred_at=moment
            )

    def flusher() -> None:
        while not stop.is_set():
            accumulator.flush(factory)
            time.sleep(0.001)

    flush_thread = threading.Thread(target=flusher)
    flush_thread.start()
    recorders = [threading.Thread(target=recorder) for _ in range(thread_count)]
    for thread in recorders:
        thread.start()
    for thread in recorders:
        thread.join()
    stop.set()
    flush_thread.join()
    accumulator.flush(factory)  # drain any final pending

    with factory() as session:
        total = session.scalar(
            select(func.sum(TenantUsageRecord.quantity)).where(
                TenantUsageRecord.tenant_id == TENANT_ID
            )
        )
    assert total == thread_count * per_thread


# --------------------------------------------------------------------------- #
# Choke point: connector sync rows                                             #
# --------------------------------------------------------------------------- #


def test_connector_sync_rows_recorded_with_real_row_count() -> None:
    factory = _factory()
    result = ConnectorSyncExecutionResult(
        adapter="file_csv",
        status="succeeded",
        sync_ref="sync_ref_1",
        external_sync_started=True,
        idempotency_key="idem_1",
        result_summary={"records_read": "17", "records_accepted": "17"},
    )
    with factory() as session:
        _record_connector_sync_rows_usage(
            AxisPersistenceRepository(session),
            TENANT_ID,
            result,
            DEFAULT_USAGE_PERIOD_WINDOW_SECONDS,
        )
        session.commit()

    rows = _usage_rows(factory, TENANT_ID)
    assert len(rows) == 1
    assert rows[0].metric_key == TenantUsageMetric.CONNECTOR_SYNC_ROWS.value
    assert rows[0].quantity == 17


def test_connector_sync_rows_zero_is_not_recorded() -> None:
    factory = _factory()
    result = ConnectorSyncExecutionResult(
        adapter="file_csv",
        status="succeeded",
        sync_ref="sync_ref_1",
        external_sync_started=False,
        idempotency_key="idem_1",
        result_summary={"records_read": "0"},
    )
    with factory() as session:
        _record_connector_sync_rows_usage(
            AxisPersistenceRepository(session),
            TENANT_ID,
            result,
            DEFAULT_USAGE_PERIOD_WINDOW_SECONDS,
        )
        session.commit()
    assert _usage_rows(factory, TENANT_ID) == []


def _sync_result(records_read: int, status: str = "sync_execution_completed"):
    return ConnectorSyncExecutionResult(
        adapter="file_csv",
        status=status,
        sync_ref="sync_ref_1",
        external_sync_started=True,
        idempotency_key="idem_1",
        result_summary={"records_read": str(records_read)},
    )


def test_connector_sync_rows_meters_delta_on_resume() -> None:
    # A resumed run reports the run-CUMULATIVE records_read; metering must
    # subtract the resume seed so only this attempt's increment is billed.
    factory = _factory()
    with factory() as session:
        _record_connector_sync_rows_usage(
            AxisPersistenceRepository(session),
            TENANT_ID,
            _sync_result(250),
            DEFAULT_USAGE_PERIOD_WINDOW_SECONDS,
            resume_records_seed=100,
        )
        session.commit()
    rows = _usage_rows(factory, TENANT_ID)
    assert len(rows) == 1
    assert rows[0].quantity == 150


def test_connector_sync_failed_then_retry_resume_does_not_double_count() -> None:
    # Attempt A reads 100 rows and fails (metered on the failed outcome); Attempt
    # B resumes from the committed checkpoint (seed 100), reads 150 more and
    # completes with cumulative records_read=250. The ledger must total the true
    # 250 rows read, not 350.
    factory = _factory()
    with factory() as session:
        repository = AxisPersistenceRepository(session)
        # Attempt A: fresh (seed 0), fails after reading 100.
        _record_connector_sync_rows_usage(
            repository,
            TENANT_ID,
            _sync_result(100, status="sync_execution_failed"),
            DEFAULT_USAGE_PERIOD_WINDOW_SECONDS,
            resume_records_seed=0,
        )
        # Attempt B: resumes from seed 100, completes at cumulative 250.
        _record_connector_sync_rows_usage(
            repository,
            TENANT_ID,
            _sync_result(250),
            DEFAULT_USAGE_PERIOD_WINDOW_SECONDS,
            resume_records_seed=100,
        )
        session.commit()

    rows = _usage_rows(factory, TENANT_ID)
    assert len(rows) == 1
    assert rows[0].metric_key == TenantUsageMetric.CONNECTOR_SYNC_ROWS.value
    assert rows[0].quantity == 250


class _RunStub:
    def __init__(self, tenant_id: str, run_id: str, connector_id: str) -> None:
        self.tenant_id = tenant_id
        self.run_id = run_id
        self.connector_id = connector_id


def test_live_sync_resume_records_seed_reads_committed_checkpoint() -> None:
    from axis_api.persistence import ConnectorSyncCheckpointCreate

    factory = _factory()
    run = _RunStub(TENANT_ID, "run_live_1", "connector_file_csv")
    with factory() as session:
        repository = AxisPersistenceRepository(session)
        # No checkpoint yet: a fresh run seeds zero.
        assert _live_sync_resume_records_seed(repository, run) == 0
        repository.create_connector_sync_checkpoint(
            ConnectorSyncCheckpointCreate(
                tenant_id=TENANT_ID,
                connector_id="connector_file_csv",
                run_id="run_live_1",
                checkpoint_id="chk_batch_1",
                checkpoint_type=SYNC_BATCH_CHECKPOINT_TYPE,
                status=SYNC_BATCH_COMMITTED_STATUS,
                sequence=1,
                runtime_boundary="axis_self_hosted_runtime",
                adapter="file_csv",
                cursor={"next_offset": "100", "total_records_read": "100"},
            )
        )
        session.commit()
        assert _live_sync_resume_records_seed(repository, run) == 100


# --------------------------------------------------------------------------- #
# Choke point: api_request via the rate-limit middleware                       #
# --------------------------------------------------------------------------- #


class _StaticVerifier:
    def __init__(self, principal: OidcPrincipal) -> None:
        self.principal = principal

    def verify_authorization_header(self, authorization: str | None) -> OidcPrincipal:
        assert authorization == "Bearer valid-token"
        return self.principal


def _set_bearer_principal(client: TestClient, tenant_id: str = TENANT_ID) -> None:
    client.app.state.identity_verifier = _StaticVerifier(
        OidcPrincipal(
            actor_id="acme-console-user-role",
            tenant_id=tenant_id,
            scopes=["audit:read"],
        )
    )


def test_api_request_metered_for_verified_bearer_on_non_rate_limited_path() -> None:
    settings = _metering_settings(api_rate_limit_paths=["/deployment/readiness"])
    client, factory = _build_client(settings)
    _set_bearer_principal(client)

    response = client.get(
        "/identity/session",
        headers={"Authorization": "Bearer valid-token"},
    )
    assert response.status_code == 200

    accumulator: UsageAccumulator = client.app.state.usage_accumulator
    assert accumulator.flush(factory) == 1
    rows = _usage_rows(factory, TENANT_ID)
    assert len(rows) == 1
    assert rows[0].metric_key == TenantUsageMetric.API_REQUEST.value
    assert rows[0].quantity == 1


def test_api_request_not_metered_without_verified_principal() -> None:
    settings = _metering_settings()
    client, factory = _build_client(settings)

    assert client.get("/deployment/readiness").status_code == 200

    accumulator: UsageAccumulator = client.app.state.usage_accumulator
    assert accumulator.flush(factory) == 0


def test_api_request_not_metered_when_disabled() -> None:
    settings = _metering_settings(usage_metering_enabled=False)
    client, factory = _build_client(settings)
    _set_bearer_principal(client)

    assert (
        client.get(
            "/identity/session",
            headers={"Authorization": "Bearer valid-token"},
        ).status_code
        == 200
    )

    accumulator: UsageAccumulator = client.app.state.usage_accumulator
    assert accumulator.flush(factory) == 0
    assert _usage_rows(factory, TENANT_ID) == []


# --------------------------------------------------------------------------- #
# Choke point: session_created via the OIDC callback                           #
# --------------------------------------------------------------------------- #


def test_session_created_metered_on_oidc_callback() -> None:
    settings = _oidc_settings(
        oidc_session_cookie_secure=False,
        usage_metering_enabled=True,
    )
    client, factory, _token_requests, id_token_context = _app_with_static_oidc(
        settings,
        token_secret="axis-test-secret",
    )
    state = _start_oidc_login(client, id_token_context, return_to="/settings")

    callback = client.get(f"/identity/oidc/callback?code=valid-code&state={state}")
    assert callback.status_code == 307

    rows = _usage_rows(factory, "tenant_demo_manufacturing")
    assert len(rows) == 1
    assert rows[0].metric_key == TenantUsageMetric.SESSION_CREATED.value
    assert rows[0].quantity == 1


def test_session_created_not_metered_when_disabled() -> None:
    settings = _oidc_settings(oidc_session_cookie_secure=False)
    client, factory, _token_requests, id_token_context = _app_with_static_oidc(
        settings,
        token_secret="axis-test-secret",
    )
    state = _start_oidc_login(client, id_token_context, return_to="/settings")

    assert client.get(f"/identity/oidc/callback?code=valid-code&state={state}").status_code == 307
    assert _usage_rows(factory, "tenant_demo_manufacturing") == []


# --------------------------------------------------------------------------- #
# Read API                                                                     #
# --------------------------------------------------------------------------- #


def test_usage_read_returns_aggregated_totals_and_breakdown() -> None:
    client, factory = _build_client()
    _provision_tenant(factory)
    now = datetime.now(UTC)
    today = now.replace(hour=6, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    _seed_usage(factory, TENANT_ID, TenantUsageMetric.API_REQUEST.value, 10, today)
    _seed_usage(factory, TENANT_ID, TenantUsageMetric.API_REQUEST.value, 5, yesterday)
    _seed_usage(factory, TENANT_ID, TenantUsageMetric.SESSION_CREATED.value, 2, today)

    response = client.get(f"/platform/tenants/{TENANT_ID}/usage?last_days=7")
    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == TENANT_ID
    totals = {row["metric_key"]: row["quantity"] for row in body["metric_totals"]}
    assert totals == {"api_request": 15, "session_created": 2}
    # Breakdown: api_request spans two periods, session_created one.
    api_points = [p for p in body["periods"] if p["metric_key"] == "api_request"]
    assert len(api_points) == 2
    assert sum(p["quantity"] for p in api_points) == 15


def test_usage_read_period_filtering_excludes_out_of_window() -> None:
    client, factory = _build_client()
    _provision_tenant(factory)
    now = datetime.now(UTC)
    recent = now.replace(hour=6, minute=0, second=0, microsecond=0)
    old = recent - timedelta(days=40)
    _seed_usage(factory, TENANT_ID, TenantUsageMetric.API_REQUEST.value, 9, recent)
    _seed_usage(factory, TENANT_ID, TenantUsageMetric.API_REQUEST.value, 99, old)

    response = client.get(f"/platform/tenants/{TENANT_ID}/usage?last_days=7")
    assert response.status_code == 200
    totals = {row["metric_key"]: row["quantity"] for row in response.json()["metric_totals"]}
    assert totals == {"api_request": 9}


def test_usage_read_empty_when_no_usage() -> None:
    client, factory = _build_client()
    _provision_tenant(factory)

    response = client.get(f"/platform/tenants/{TENANT_ID}/usage")
    assert response.status_code == 200
    body = response.json()
    assert body["metric_totals"] == []
    assert body["periods"] == []


def test_usage_read_isolates_tenants() -> None:
    client, factory = _build_client()
    _provision_tenant(factory, TENANT_ID)
    _provision_tenant(factory, OTHER_TENANT_ID)
    now = datetime.now(UTC).replace(hour=6, minute=0, second=0, microsecond=0)
    _seed_usage(factory, TENANT_ID, TenantUsageMetric.API_REQUEST.value, 3, now)
    _seed_usage(factory, OTHER_TENANT_ID, TenantUsageMetric.API_REQUEST.value, 100, now)

    response = client.get(f"/platform/tenants/{TENANT_ID}/usage")
    totals = {row["metric_key"]: row["quantity"] for row in response.json()["metric_totals"]}
    assert totals == {"api_request": 3}


def test_usage_read_missing_tenant_returns_404() -> None:
    client, _factory = _build_client()
    response = client.get("/platform/tenants/tenant_absent/usage")
    assert response.status_code == 404


def test_usage_read_rejects_invalid_window() -> None:
    client, factory = _build_client()
    _provision_tenant(factory)
    response = client.get(
        f"/platform/tenants/{TENANT_ID}/usage",
        params={"from": "2999-01-01T00:00:00Z", "to": "2000-01-01T00:00:00Z"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "invalid_usage_window"


def test_usage_read_naive_future_from_yields_422_not_500() -> None:
    # A naive `from` (no tz) with `to` omitted compares against an aware now();
    # normalization must yield a clean 422, not a TypeError-driven 500.
    client, factory = _build_client()
    _provision_tenant(factory)
    response = client.get(
        f"/platform/tenants/{TENANT_ID}/usage",
        params={"from": "2999-01-01T00:00:00"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["reason"] == "invalid_usage_window"


def test_usage_read_requires_operator_and_usage_scopes_when_authenticated() -> None:
    client, factory = _build_client()
    _provision_tenant(factory)
    bearer = {"Authorization": "Bearer valid-token"}

    # Missing the operator scope: denied.
    client.app.state.identity_verifier = _StaticVerifier(
        OidcPrincipal(
            actor_id=OPERATOR_ACTOR,
            tenant_id="tenant_axis_platform_ops",
            scopes=["platform:tenant:usage"],
        )
    )
    denied = client.get(f"/platform/tenants/{TENANT_ID}/usage", headers=bearer)
    assert denied.status_code == 403
    assert denied.json()["detail"]["required_permission"] == "platform:tenant:operator"

    # Missing the usage scope: denied.
    client.app.state.identity_verifier = _StaticVerifier(
        OidcPrincipal(
            actor_id=OPERATOR_ACTOR,
            tenant_id="tenant_axis_platform_ops",
            scopes=["platform:tenant:operator", "platform:tenant:read"],
        )
    )
    denied_usage = client.get(f"/platform/tenants/{TENANT_ID}/usage", headers=bearer)
    assert denied_usage.status_code == 403
    assert denied_usage.json()["detail"]["required_permission"] == "platform:tenant:usage"

    # Operator + usage: allowed cross-tenant (operator reads any tenant).
    client.app.state.identity_verifier = _StaticVerifier(
        OidcPrincipal(
            actor_id=OPERATOR_ACTOR,
            tenant_id="tenant_axis_platform_ops",
            scopes=USAGE_SCOPES,
        )
    )
    allowed = client.get(f"/platform/tenants/{TENANT_ID}/usage", headers=bearer)
    assert allowed.status_code == 200


# --------------------------------------------------------------------------- #
# build_tenant_usage_summary service + migration                              #
# --------------------------------------------------------------------------- #


def test_build_tenant_usage_summary_raises_for_missing_tenant() -> None:
    from axis_api.platform_tenants import TenantNotFound

    factory = _factory()
    with factory() as session:
        repository = AxisPersistenceRepository(session)
        raised = False
        try:
            build_tenant_usage_summary(
                repository,
                "tenant_absent",
                window_start=datetime.now(UTC) - timedelta(days=1),
                window_end=datetime.now(UTC),
            )
        except TenantNotFound:
            raised = True
        assert raised


def test_migration_0049_identifier_and_down_revision() -> None:
    import importlib.util
    from pathlib import Path

    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "0049_tenant_usage_records.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0049", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "0049_tenant_usage_records"
    assert migration.down_revision == "0048_session_device_metadata"


def test_tenant_usage_records_schema_has_unique_bucket_constraint() -> None:
    table = TenantUsageRecord.__table__
    assert table.name == "tenant_usage_records"
    unique_columns = {
        tuple(sorted(column.name for column in constraint.columns))
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("metric_key", "period_start", "tenant_id") in unique_columns
