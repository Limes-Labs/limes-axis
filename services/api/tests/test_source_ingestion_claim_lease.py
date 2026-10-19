"""Claim-lease behaviour of the source ingestion dispatcher (issue #942).

Extraction that outlives its claim lease used to be fenced at completion
without any transition, so the expired row was reclaimed with a higher
``attempt_count`` on every pass and re-read its source forever. These tests
drive the dispatcher with a controllable clock and fake source runtimes.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.config import Settings
from axis_api.connector_source_ingestion import (
    INGESTION_FAILED_EVENT,
    SourceIngestionOutboxDispatcher,
    SourceIngestionValidationOutcome,
)
from axis_api.db import session_scope
from axis_api.models import AuditEvent, Base, ConnectorSourceIngestionRequest
from axis_api.s3_source_profile import S3_SOURCE_CONNECTOR_ID

T0 = datetime(2026, 10, 19, 6, 0, tzinfo=UTC)
CLAIM_TIMEOUT = 120
TENANT = "tenant-lease"


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


class AlwaysValid:
    def validate_selection(self, **_kwargs: object) -> SourceIngestionValidationOutcome:
        return SourceIngestionValidationOutcome(ok=True)


class SlowSourceRuntime:
    """Each read advances the clock; commits are recorded, never performed."""

    def __init__(self, clock: Clock, seconds_per_read: float, on_read=None) -> None:
        self.clock = clock
        self.seconds_per_read = seconds_per_read
        self.on_read = on_read
        self.reads: list[str] = []
        self.commits: list[str] = []

    def prepare_selection(self, _repository, *, binding_id: str, resource_name: str, **_kw):
        return SimpleNamespace(
            binding_id=binding_id,
            profile=SimpleNamespace(resource_name=resource_name),
        )

    def extract_prepared(self, prepared, progress=None):
        self.reads.append(prepared.binding_id)
        if progress is not None:
            progress.source_dial_performed = True
            progress.extraction_performed = True
        self.clock.advance(self.seconds_per_read)
        if self.on_read is not None:
            self.on_read(prepared.binding_id)
        return SimpleNamespace(
            batch_key=f"batch:{prepared.binding_id}",
            prepared=prepared,
            outcome=SimpleNamespace(
                row_count=1,
                truncated=False,
                digest_sha256="0" * 64,
                stored={"storage_uri": f"memory://{prepared.binding_id}"},
            ),
        )

    def commit(self, _repository, result) -> None:
        self.commits.append(result.batch_key)


@pytest.fixture
def factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


def _settings(max_attempts: int = 3) -> Settings:
    return Settings(
        _env_file=None,
        source_ingestion_dispatch_enabled=True,
        source_ingestion_extraction_enabled=True,
        source_ingestion_claim_timeout_seconds=CLAIM_TIMEOUT,
        source_ingestion_max_attempts=max_attempts,
        source_ingestion_retry_base_seconds=0,
    )


def _enqueue(factory: sessionmaker[Session], bindings: list[str], **values: object) -> None:
    with session_scope(factory) as session:
        session.add(
            ConnectorSourceIngestionRequest(
                tenant_id=TENANT,
                connector_id=S3_SOURCE_CONNECTOR_ID,
                request_id="request",
                requested_by="test",
                reason="lease fixture",
                stage="extract",
                selections=[
                    {
                        "binding_id": binding,
                        "resource_name": f"resource-{binding}",
                        "schema_fingerprint": "f" * 64,
                    }
                    for binding in bindings
                ],
                available_at=T0,
                audit_event_id=uuid4(),
                audit_event_type="connector.source.ingestion.requested",
                **values,
            )
        )


def _row(factory: sessionmaker[Session]) -> ConnectorSourceIngestionRequest:
    with factory() as session:
        row = session.scalar(select(ConnectorSourceIngestionRequest))
        assert row is not None
        session.expunge(row)
        return row


def _dispatcher(factory, clock, source) -> SourceIngestionOutboxDispatcher:
    return SourceIngestionOutboxDispatcher(
        settings=_settings(),
        session_factory=factory,
        runtime=AlwaysValid(),
        s3_runtime=source,
        clock=clock,
        random_uniform=lambda low, _high: low,
    )


def test_extraction_outliving_its_lease_dead_letters_at_max_attempts(factory) -> None:
    clock = Clock()
    source = SlowSourceRuntime(clock, seconds_per_read=CLAIM_TIMEOUT + 1)
    _enqueue(factory, ["b1"])
    dispatcher = _dispatcher(factory, clock, source)

    results = []
    for _ in range(6):
        results.append(asyncio.run(dispatcher.run_once()))
        clock.advance(1)

    row = _row(factory)
    assert row.status == "failed"
    assert row.dead_lettered_at is not None
    assert row.attempt_count == 3
    assert row.last_error == "claim_lease_expired"
    # The source is read once per counted attempt, never past max_attempts.
    assert source.reads == ["b1"] * 3
    assert source.commits == []
    assert [result.claimed for result in results] == [1, 1, 1, 0, 0, 0]
    assert [result.retried for result in results[:3]] == [1, 1, 0]
    assert results[2].dead_lettered == 1
    assert [entry["outcome"] for entry in row.evidence["attempts"]] == [
        "retried",
        "retried",
        "dead_lettered",
    ]
    with factory() as session:
        failures = session.scalars(
            select(AuditEvent).where(AuditEvent.event_type == INGESTION_FAILED_EVENT)
        ).all()
    assert len(failures) == 1
    assert failures[0].payload["error_code"] == "claim_lease_expired"


def test_lease_is_renewed_between_selections(factory) -> None:
    clock = Clock()
    # Two selections each take 75% of the lease: together they outlive it.
    source = SlowSourceRuntime(clock, seconds_per_read=CLAIM_TIMEOUT * 0.75)
    _enqueue(factory, ["b1", "b2"])

    result = asyncio.run(_dispatcher(factory, clock, source).run_once())

    assert result.completed == 1
    assert source.reads == ["b1", "b2"]
    assert source.commits == ["batch:b1", "batch:b2"]
    row = _row(factory)
    assert row.status == "completed"
    assert row.attempt_count == 1


def test_lost_claim_stops_before_reading_the_next_selection(factory) -> None:
    clock = Clock()

    def steal_claim(binding_id: str) -> None:
        if binding_id == "b1":
            with session_scope(factory) as session:
                row = session.scalar(select(ConnectorSourceIngestionRequest))
                row.claim_token = uuid4()

    source = SlowSourceRuntime(clock, seconds_per_read=1, on_read=steal_claim)
    _enqueue(factory, ["b1", "b2"])

    result = asyncio.run(_dispatcher(factory, clock, source).run_once())

    assert result.fenced == 1
    assert source.reads == ["b1"]
    assert source.commits == []
    assert _row(factory).status == "dispatching"


def test_expired_reclaim_past_max_attempts_dead_letters_without_reading(factory) -> None:
    clock = Clock()
    source = SlowSourceRuntime(clock, seconds_per_read=1)
    # A worker died holding the request at its final attempt.
    _enqueue(
        factory,
        ["b1"],
        status="dispatching",
        attempt_count=3,
        claim_token=uuid4(),
        claimed_at=T0 - timedelta(seconds=CLAIM_TIMEOUT + 5),
        lease_expires_at=T0 - timedelta(seconds=5),
    )

    result = asyncio.run(_dispatcher(factory, clock, source).run_once())

    assert result.dead_lettered == 1
    assert source.reads == []
    row = _row(factory)
    assert row.status == "failed"
    assert row.attempt_count == 4
    assert row.last_error == "claim_lease_expired"
