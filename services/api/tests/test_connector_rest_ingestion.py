"""REST host adoption: fenced cursor commits, resumable rate limits, containment.

These tests drive the real ingestion outbox and the real #860 reader with an
injected transport. They cover the six acceptance groups of #861 against SQLite
owners. Where a claim about live providers or PostgreSQL row locks is not
provable here, the test says so explicitly instead of implying coverage.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from axis_sdk.connector_authoring.contracts import ProtocolRange, ReadLimits
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from axis_api.config import Settings
from axis_api.connector_rest_ingestion import (
    RestCheckpointConflict,
    RestIngestionRuntime,
    record_rest_declared_observation,
)
from axis_api.connector_rest_profiles import (
    OpaqueCursorPagination,
    RestParameter,
    RestSourceLimits,
    RestSourceProfile,
)
from axis_api.connector_secret_resolution import EnvLeaseScopedSecretResolver
from axis_api.connector_source_activation import (
    SOURCE_ACTIVATION_SCOPE,
    ConnectorSourceActivationRequest,
    record_connector_source_activation,
)
from axis_api.connector_source_ingestion import (
    SOURCE_INGESTION_SCOPE,
    ConnectorSourceIngestionSubmission,
    ObservationFreshnessIngestionRuntime,
    SourceIngestionOutboxDispatcher,
    record_connector_source_ingestion_request,
)
from axis_api.db import session_scope
from axis_api.models import (
    Base,
    ConnectorSourceExtractionBatch,
    ConnectorSourceIngestionRequest,
)
from axis_api.object_storage import LocalObjectStore
from axis_api.persistence import (
    AxisPersistenceRepository,
    ConnectorCredentialHandleCreate,
    ConnectorCredentialLeaseCreate,
    ConnectorEgressPolicyCreate,
    ConnectorManifestCreate,
    TenantCreate,
)
from axis_api.rest_source_profile import REST_SOURCE_CONNECTOR_ID, RestHostProfile

TENANT_ENDPOINT = "https://api.example.internal"
BEARER = "fixture-bearer-token"


def endpoint_target_sha256() -> str:
    return hashlib.sha256(b"api.example.internal:443").hexdigest()


def build_profile(tenant_id: str, profile_id: str = "profile_rest_orders") -> RestHostProfile:
    return RestHostProfile(
        tenant_id=tenant_id,
        profile_id=profile_id,
        endpoint=TENANT_ENDPOINT,
        source=RestSourceProfile(
            endpoint_profile_id="endpoint_rest_orders",
            endpoint_profile_revision="a" * 64,
            collection_id="rest_orders",
            path_template="/v1/orders/{account}",
            query_parameters=(
                RestParameter(name="status", value_type="string", required=True),
            ),
            records_path=("data", "orders"),
            schema_fingerprint="b" * 64,
            pagination=OpaqueCursorPagination(parameter="cursor", next_path=("paging", "next")),
            limits=RestSourceLimits(
                page=ReadLimits(max_records=5, max_bytes=100_000, time_budget_seconds=30),
                max_pages=3,
            ),
        ),
        path_values={"account": "acct-1"},
        query_values={"status": "open"},
        credential_secret_ref="env://REST_FIXTURE_CREDENTIALS",
        private_endpoint_ref="private-endpoint://tenant/rest-readonly",
    )


class FakeResponse:
    def __init__(self, body, *, status=200, headers=None):
        self.status = status
        self.headers = headers or {"Content-Type": "application/json"}
        self._body = json.dumps(body).encode() if isinstance(body, (dict, list)) else body
        self._offset = 0
        self.closed = False

    def read(self, size, decode_content=False):
        chunk = self._body[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk

    def close(self):
        self.closed = True

    def release_conn(self):
        pass


class ScriptedTransport:
    """Deterministic response queue that also proves no SQL is held mid-read."""

    def __init__(self, engine, origin):
        self.engine = engine
        self.origin = origin
        self.responses: list = []
        self.urls: list[str] = []

    def queue(self, *responses):
        self.responses.extend(responses)

    def get(self, url, *, headers, timeout):
        # The host must never hold a database connection across network I/O.
        assert self.engine.pool.checkedout() == 0
        self.urls.append(url)
        if not self.responses:
            raise AssertionError("unexpected extra REST request")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def close(self):
        pass


def page(rows, *, next_token=None):
    body = {"data": {"orders": rows}}
    if next_token is not None:
        body["paging"] = {"next": next_token}
    return FakeResponse(body)


@pytest.fixture
def host(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'host.sqlite'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, autoflush=False, expire_on_commit=False)
    profile = build_profile(f"rest-{uuid4().hex}")
    connector = REST_SOURCE_CONNECTOR_ID
    settings = Settings(
        connector_sync_execution_enabled=True,
        source_ingestion_dispatch_enabled=True,
        source_ingestion_extraction_enabled=True,
        rest_source_ingestion_enabled=True,
        rest_source_profiles=[profile],
    )
    transport = ScriptedTransport(engine, profile.pinned_origin)
    store = LocalObjectStore(tmp_path / "payloads")
    runtime = RestIngestionRuntime(
        settings,
        store,
        transport_factory=lambda origin: transport,
        resolver=EnvLeaseScopedSecretResolver(
            {"REST_FIXTURE_CREDENTIALS": json.dumps({"bearer_token": BEARER})}
        ),
    )
    with session_scope(factory) as session:
        repo = AxisPersistenceRepository(session)
        repo.create_tenant(
            TenantCreate(
                tenant_id=profile.tenant_id,
                display_name="REST fixture",
                description="Isolated",
                created_by="test",
            )
        )
        repo.create_connector_manifest(
            ConnectorManifestCreate(
                tenant_id=profile.tenant_id,
                connector_id=connector,
                revision_number=1,
                display_name="REST fixture",
                connector_type="rest_api",
                source_type="rest",
                version="1.0",
                status="active_live",
                registered_by="test",
                runtime_policy={"allowed_operations": ["live_query", "external_egress"]},
            )
        )
        repo.create_connector_credential_handle(
            ConnectorCredentialHandleCreate(
                tenant_id=profile.tenant_id,
                connector_id=connector,
                handle_id="handle",
                display_name="Fixture",
                secret_provider="env",
                secret_ref=profile.credential_secret_ref,
                purpose="source_ingestion",
                rotation_interval_days=1,
                created_by="test",
            )
        )
        now = datetime.now(UTC)
        repo.create_connector_credential_lease(
            ConnectorCredentialLeaseCreate(
                tenant_id=profile.tenant_id,
                connector_id=connector,
                handle_id="handle",
                lease_id="lease",
                requested_by="test",
                lease_purpose="source_ingestion",
                secret_provider="env",
                secret_ref=profile.credential_secret_ref,
                permission_decision={"allowed": True, "reason": "fixture"},
                lease_result={
                    "status": "lease_executed",
                    "provider_lease_ref": "fixture://lease",
                    "secret_material_returned": "false",
                },
                granted_at=now,
                expires_at=now + timedelta(hours=1),
                renewal_due_at=now + timedelta(minutes=30),
            )
        )
        repo.create_connector_egress_policy(
            ConnectorEgressPolicyCreate(
                tenant_id=profile.tenant_id,
                connector_id=connector,
                policy_id="policy",
                display_name="Fixture",
                connection_profile_id=profile.profile_id,
                egress_boundary="approved_private_endpoint",
                policy_mode="approved_private_endpoint",
                runtime_boundary="axis-egress-policy-enforcer",
                private_endpoint_ref=profile.private_endpoint_ref,
                created_by="test",
                policy_document={"approved_endpoint_target_sha256": endpoint_target_sha256()},
            )
        )
        record_rest_declared_observation(repo, profile, observed_by="test")
    with session_scope(factory) as session:
        record_connector_source_activation(
            AxisPersistenceRepository(session),
            request=ConnectorSourceActivationRequest(
                tenant_id=profile.tenant_id,
                connector_id=connector,
                activation_id="activate",
                requested_by="test",
                connection_profile_id=profile.profile_id,
                credential_lease_id="lease",
                egress_policy_id="policy",
                activation_reason="Read the declared REST collection",
                selections=[
                    {
                        "binding_id": "binding",
                        "resource_name": profile.resource_name,
                        "expected_schema_fingerprint": profile.source.schema_fingerprint,
                    }
                ],
            ),
            principal_scopes=[SOURCE_ACTIVATION_SCOPE],
            max_selections=20,
        )
    yield SimpleNamespace(
        factory=factory,
        engine=engine,
        settings=settings,
        runtime=runtime,
        transport=transport,
        store=store,
        profile=profile,
        binding_id="binding",
        tmp_path=tmp_path,
    )
    engine.dispose()


def submit(host, request_id="request", *, stage="extract", binding_id=None):
    with session_scope(host.factory) as session:
        return record_connector_source_ingestion_request(
            AxisPersistenceRepository(session),
            submission=ConnectorSourceIngestionSubmission(
                tenant_id=host.profile.tenant_id,
                connector_id=REST_SOURCE_CONNECTOR_ID,
                request_id=request_id,
                requested_by="test",
                reason="REST page",
                stage=stage,
                selections=[{"binding_id": binding_id or host.binding_id}],
            ),
            principal_scopes=[SOURCE_INGESTION_SCOPE],
            max_selections=20,
            settings=host.settings,
        )


_UNSET = object()


def build_dispatcher(host, *, rest_runtime=_UNSET, extraction_runtime=None):
    return SourceIngestionOutboxDispatcher(
        settings=host.settings,
        session_factory=host.factory,
        runtime=ObservationFreshnessIngestionRuntime(),
        extraction_runtime=extraction_runtime,
        rest_runtime=host.runtime if rest_runtime is _UNSET else rest_runtime,
        random_uniform=lambda low, high: low,
    )


def dispatch(host, **kwargs):
    return asyncio.run(build_dispatcher(host, **kwargs).run_once())


def state(host):
    with session_scope(host.factory) as session:
        repo = AxisPersistenceRepository(session)
        binding = repo.get_connector_source_binding(host.profile.tenant_id, host.binding_id)
        batches = list(session.scalars(select(ConnectorSourceExtractionBatch)).all())
        return binding.source_checkpoint_revision, binding.source_checkpoint, batches


def request_row(host, request_id="request"):
    with session_scope(host.factory) as session:
        return AxisPersistenceRepository(session).get_connector_source_ingestion_request(
            host.profile.tenant_id, request_id
        )


def make_available(host, request_id="request"):
    with session_scope(host.factory) as session:
        row = session.scalar(
            select(ConnectorSourceIngestionRequest).where(
                ConnectorSourceIngestionRequest.request_id == request_id
            )
        )
        row.available_at = datetime.now(UTC) - timedelta(seconds=1)
        row.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)


def payloads(host):
    return [json.loads(path.read_text()) for path in host.store.root.rglob("*.json")]


# --------------------------------------------------------------------------
# Acceptance group 1: durable envelope, then fenced commit; replay is safe.
# --------------------------------------------------------------------------


def test_three_page_traversal_commits_one_page_per_fenced_request(host):
    host.transport.queue(
        page([{"id": 1}], next_token="cursor-2"),
        page([{"id": 2}], next_token="cursor-3"),
        page([{"id": 3}]),
    )
    for index in range(3):
        submit(host, f"request-{index}")
        assert dispatch(host).completed == 1
    revision, checkpoint, batches = state(host)
    assert revision == 3
    assert checkpoint["traversal"] == "complete"
    assert checkpoint["cursor"] is None
    assert [batch.row_count for batch in batches] == [1, 1, 1]
    assert batch_keys_unique(batches)
    # The opaque provider cursor never appears in persisted batch metadata.
    assert "cursor-2" not in json.dumps([batch.cursor_watermark for batch in batches])


def batch_keys_unique(batches):
    keys = [batch.batch_key for batch in batches]
    return len(keys) == len(set(keys))


def test_interrupt_after_upload_before_sql_commit_replays_same_object(host):
    replay = page([{"id": 1}], next_token="cursor-2")
    host.transport.queue(replay, page([{"id": 1}], next_token="cursor-2"))
    submit(host)
    original_commit = host.runtime.commit
    calls = {"count": 0}

    def failing_commit(repository, result):
        calls["count"] += 1
        raise OSError("simulated crash after upload, before SQL commit")

    host.runtime.commit = failing_commit
    assert dispatch(host).retried == 1
    revision, checkpoint, batches = state(host)
    # Uploaded bytes alone must never advance the cursor or record a batch.
    assert revision == 0 and checkpoint is None and batches == []
    assert len(payloads(host)) == 1

    host.runtime.commit = original_commit
    make_available(host)
    assert dispatch(host).completed == 1
    revision, checkpoint, batches = state(host)
    assert revision == 1 and len(batches) == 1
    # The retry overwrote the same deterministic object instead of duplicating.
    assert len(payloads(host)) == 1
    assert calls["count"] == 1


def test_interrupt_before_upload_commits_nothing(host):
    host.transport.queue(
        page([{"id": 1}], next_token="cursor-2"),
        page([{"id": 1}], next_token="cursor-2"),
    )
    submit(host)
    original = host.store.put_json

    def fail_before_store(*_args):
        raise OSError("simulated crash before upload")

    host.store.put_json = fail_before_store
    assert dispatch(host).retried == 1
    assert state(host) == (0, None, []) and payloads(host) == []
    host.store.put_json = original
    make_available(host)
    assert dispatch(host).completed == 1
    assert state(host)[0] == 1 and len(state(host)[2]) == 1


def test_interrupt_after_commit_before_acknowledgement_keeps_committed_page(host):
    host.transport.queue(page([{"id": 1}], next_token="cursor-2"))
    submit(host)
    assert dispatch(host).completed == 1
    assert state(host)[0] == 1
    transport_calls = len(host.transport.urls)
    # A lost acknowledgement must not cause a re-read or a checkpoint retreat.
    assert dispatch(host).claimed == 0
    assert state(host)[0] == 1
    assert len(host.transport.urls) == transport_calls


# --------------------------------------------------------------------------
# Acceptance group 2: competing and expired workers cannot advance a generation.
# --------------------------------------------------------------------------


def test_stale_claim_token_cannot_advance_the_checkpoint(host):
    host.transport.queue(page([{"id": 1}], next_token="cursor-2"))
    submit(host)
    original = host.store.put_json

    def steal_claim(key, payload):
        with session_scope(host.factory) as session:
            row = session.scalar(select(ConnectorSourceIngestionRequest))
            row.claim_token = uuid4()
        return original(key, payload)

    host.store.put_json = steal_claim
    assert dispatch(host).fenced == 1
    revision, checkpoint, batches = state(host)
    assert revision == 0 and checkpoint is None and batches == []


def test_expired_claim_lease_cannot_advance_the_checkpoint(host):
    host.transport.queue(page([{"id": 1}], next_token="cursor-2"))
    submit(host)
    original = host.store.put_json

    def expire_claim(key, payload):
        with session_scope(host.factory) as session:
            row = session.scalar(select(ConnectorSourceIngestionRequest))
            row.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        return original(key, payload)

    host.store.put_json = expire_claim
    assert dispatch(host).fenced == 1
    assert state(host) == (0, None, [])


def test_two_prepared_results_cannot_both_advance_one_generation(host):
    host.transport.queue(page([{"id": 1}], next_token="cursor-2"))
    submit(host)
    with session_scope(host.factory) as session:
        prepared = host.runtime.prepare_selection(
            AxisPersistenceRepository(session),
            tenant_id=host.profile.tenant_id,
            connector_id=REST_SOURCE_CONNECTOR_ID,
            request_id="request",
            binding_id=host.binding_id,
            resource_name=host.profile.resource_name,
            pinned_schema_fingerprint=host.profile.source.schema_fingerprint,
            executed_by="test",
        )
    first = host.runtime.extract_prepared(prepared)
    with session_scope(host.factory) as session:
        host.runtime.commit(AxisPersistenceRepository(session), first)
    assert state(host)[0] == 1
    # The second result was prepared at generation 0; committing it now must
    # lose the compare-and-swap instead of advancing twice.
    with session_scope(host.factory) as session, pytest.raises(RestCheckpointConflict):
        host.runtime.commit(AxisPersistenceRepository(session), first)
    assert state(host)[0] == 1 and len(state(host)[2]) == 1


# --------------------------------------------------------------------------
# Acceptance group 3: 429 defers durably; exhaustion dead-letters.
# --------------------------------------------------------------------------


def rate_limited(retry_after="120"):
    return FakeResponse(
        {"error": "slow down"},
        status=429,
        headers={"Content-Type": "application/json", "Retry-After": retry_after},
    )


def test_rate_limit_schedules_durable_retry_and_keeps_committed_cursor(host):
    host.transport.queue(rate_limited())
    submit(host)
    assert dispatch(host).retried == 1
    row = request_row(host)
    assert row.last_error == "rate_limited"
    expected_floor = datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=60)
    assert row.available_at >= expected_floor
    assert state(host) == (0, None, [])
    # A fresh dispatcher (restart) still sees the durable retry state.
    assert dispatch(host).claimed == 0
    host.transport.queue(page([{"id": 1}]))
    make_available(host)
    assert dispatch(host).completed == 1
    revision, _, batches = state(host)
    assert revision == 1 and len(batches) == 1


def test_retry_exhaustion_dead_letters_through_existing_evidence(host):
    host.settings.source_ingestion_max_attempts = 2
    host.transport.queue(rate_limited(), rate_limited())
    submit(host)
    assert dispatch(host).retried == 1
    make_available(host)
    assert dispatch(host).dead_lettered == 1
    row = request_row(host)
    assert row.status == "failed" and row.dead_lettered_at is not None
    assert row.last_error == "rate_limited"
    assert state(host) == (0, None, [])


def test_retry_after_is_bounded_by_configuration(host):
    host.settings.source_ingestion_retry_after_max_seconds = 30
    host.transport.queue(rate_limited("3600"))
    submit(host)
    assert dispatch(host).retried == 1
    row = request_row(host)
    assert row.available_at <= datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=35)


# --------------------------------------------------------------------------
# Acceptance group 4: expired cursor / changed profile / revoked lease stop.
# --------------------------------------------------------------------------


def test_completed_traversal_never_silently_restarts_at_page_one(host):
    host.transport.queue(page([{"id": 1}]))
    submit(host, "first")
    assert dispatch(host).completed == 1
    assert state(host)[1]["traversal"] == "complete"
    submit(host, "second")
    assert dispatch(host).dead_lettered == 1
    row = request_row(host, "second")
    assert row.last_error == "invalid_checkpoint"
    assert len(host.transport.urls) == 1


def test_expired_or_tampered_cursor_is_terminal_and_not_retried(host):
    host.transport.queue(page([{"id": 1}], next_token="cursor-2"))
    submit(host, "first")
    assert dispatch(host).completed == 1
    with session_scope(host.factory) as session:
        binding = AxisPersistenceRepository(session).get_connector_source_binding(
            host.profile.tenant_id, host.binding_id
        )
        checkpoint = dict(binding.source_checkpoint)
        checkpoint["cursor"] = {
            **checkpoint["cursor"],
            "cursor": "tampered-envelope",
            "cursor_sha256": "0" * 64,
        }
        binding.source_checkpoint = checkpoint
    submit(host, "second")
    assert dispatch(host).dead_lettered == 1
    assert request_row(host, "second").last_error == "invalid_checkpoint"
    assert state(host)[0] == 1


def test_revoked_lease_blocks_before_any_read(host):
    submit(host)
    with session_scope(host.factory) as session:
        repo = AxisPersistenceRepository(session)
        repo.get_connector_credential_lease(host.profile.tenant_id, "lease").status = "revoked"
    assert dispatch(host).dead_lettered == 1
    assert host.transport.urls == []
    assert state(host) == (0, None, [])


def test_changed_profile_revision_or_schema_blocks_before_any_read(host):
    submit(host)
    with session_scope(host.factory) as session:
        repo = AxisPersistenceRepository(session)
        repo.get_data_resource_observation(
            host.profile.tenant_id, REST_SOURCE_CONNECTOR_ID, host.profile.resource_name
        ).schema_fingerprint = "c" * 64
    assert dispatch(host).dead_lettered == 1
    assert host.transport.urls == []
    assert state(host) == (0, None, [])


def test_repeated_cursor_is_a_terminal_protocol_error(host):
    host.transport.queue(
        page([{"id": 1}], next_token="A"),
        page([{"id": 2}], next_token="B"),
        page([{"id": 3}], next_token="A"),
    )
    for index in range(2):
        submit(host, f"request-{index}")
        assert dispatch(host).completed == 1
    submit(host, "request-2")
    assert dispatch(host).dead_lettered == 1
    assert request_row(host, "request-2").last_error == "no_progress"
    # The looping page was rejected before it was ever stored.
    assert state(host)[0] == 2 and len(state(host)[2]) == 2


def test_truncated_page_is_never_committed_as_progress(host):
    host.transport.queue(page([{"id": index} for index in range(10)]))
    submit(host)
    assert dispatch(host).dead_lettered == 1
    assert request_row(host).last_error == "limit_exceeded"
    assert state(host) == (0, None, []) and payloads(host) == []


def test_incompatible_declared_protocol_fails_before_any_client(host):
    from axis_sdk.connector_authoring.contracts import ConnectorError

    incompatible = ProtocolRange(major=2, min_minor=0, max_minor=0)
    with pytest.raises(ConnectorError) as failure:
        host.runtime.negotiate(host.profile.model_copy(update={"protocol": incompatible}))
    assert failure.value.code.value == "incompatible_protocol"
    # The deployment's declared 1.0 range still negotiates successfully.
    assert host.runtime.negotiate(host.profile).minor == 0
    assert host.transport.urls == []


# --------------------------------------------------------------------------
# Acceptance group 5: tenant substitution and secret containment.
# --------------------------------------------------------------------------


def test_cross_tenant_binding_identity_is_rejected(host):
    from axis_sdk.connector_authoring.contracts import ConnectorError

    with session_scope(host.factory) as session, pytest.raises(ConnectorError):
        host.runtime.prepare_selection(
            AxisPersistenceRepository(session),
            tenant_id="other-tenant",
            connector_id=REST_SOURCE_CONNECTOR_ID,
            request_id="other",
            binding_id=host.binding_id,
            resource_name=host.profile.resource_name,
            pinned_schema_fingerprint=host.profile.source.schema_fingerprint,
            executed_by="test",
        )


def test_cross_tenant_cursor_is_rejected_on_resume(host):
    host.transport.queue(page([{"id": 1}], next_token="cursor-2"))
    submit(host, "first")
    assert dispatch(host).completed == 1
    with session_scope(host.factory) as session:
        repo = AxisPersistenceRepository(session)
        binding = repo.get_connector_source_binding(host.profile.tenant_id, host.binding_id)
        foreign = dict(binding.source_checkpoint)
        foreign["cursor"] = {**foreign["cursor"], "tenant_id": "other-tenant"}
    with session_scope(host.factory) as session:
        prepared = host.runtime.prepare_selection(
            AxisPersistenceRepository(session),
            tenant_id=host.profile.tenant_id,
            connector_id=REST_SOURCE_CONNECTOR_ID,
            request_id="second",
            binding_id=host.binding_id,
            resource_name=host.profile.resource_name,
            pinned_schema_fingerprint=host.profile.source.schema_fingerprint,
            executed_by="test",
            lock_current=False,
        )
    tampered = replace(prepared, checkpoint_state=foreign)
    from axis_api.connector_rest_ingestion import RestSourceFailure

    calls_before = len(host.transport.urls)
    with pytest.raises(RestSourceFailure) as failure:
        host.runtime.extract_prepared(tampered)
    assert failure.value.code.value == "invalid_checkpoint"
    # A foreign cursor is rejected before any request is dialed.
    assert len(host.transport.urls) == calls_before


def test_secrets_and_rows_never_enter_sql_or_evidence(host):
    host.transport.queue(page([{"secret_row": "private-row-value"}], next_token="cursor-2"))
    submit(host)
    assert dispatch(host).completed == 1
    row = request_row(host)
    serialized = json.dumps(row.evidence, default=str)
    assert BEARER not in serialized
    assert "private-row-value" not in serialized
    assert "cursor-2" not in serialized
    database_bytes = (host.tmp_path / "host.sqlite").read_bytes()
    for forbidden in (BEARER.encode(), b"private-row-value"):
        assert forbidden not in database_bytes
    # The payload store is the one place raw rows live.
    assert payloads(host)[0]["rows"] == [{"secret_row": "private-row-value"}]


def test_operation_context_binds_lease_and_policy_evidence(host):
    with session_scope(host.factory) as session:
        prepared = host.runtime.prepare_selection(
            AxisPersistenceRepository(session),
            tenant_id=host.profile.tenant_id,
            connector_id=REST_SOURCE_CONNECTOR_ID,
            request_id="request",
            binding_id=host.binding_id,
            resource_name=host.profile.resource_name,
            pinned_schema_fingerprint=host.profile.source.schema_fingerprint,
            executed_by="test",
        )
    context = host.runtime.context(prepared)
    assert context.credential_lease_id == "lease"
    assert context.egress_policy_id == "policy"
    assert context.tenant_id == host.profile.tenant_id


# --------------------------------------------------------------------------
# Acceptance group 6: REST is default-off and does not disturb other paths.
# --------------------------------------------------------------------------


def test_rest_disabled_never_dials_and_dead_letters(host):
    host.settings.rest_source_ingestion_enabled = False
    submit(host)
    assert dispatch(host).dead_lettered == 1
    assert request_row(host).last_error == "unsupported_capability"
    assert host.transport.urls == []
    assert state(host) == (0, None, [])


def test_missing_rest_runtime_dead_letters_without_dialing(host):
    submit(host)
    result = dispatch(host, rest_runtime=None, extraction_runtime=object())
    assert result.dead_lettered == 1
    assert request_row(host).last_error == "rest_source_disabled"
    assert host.transport.urls == []
    assert state(host) == (0, None, [])


def test_rest_disabled_keeps_validation_only_path_unchanged(host):
    host.settings.rest_source_ingestion_enabled = False
    submit(host, stage="validate")
    result = dispatch(host)
    assert result.completed == 1
    row = request_row(host)
    assert row.evidence["source_dial_performed"] is False
    assert row.evidence["extraction_performed"] is False
    assert host.transport.urls == []


def test_gate_off_refuses_profile_lookup(host):
    from axis_sdk.connector_authoring.contracts import ConnectorError

    host.settings.rest_source_ingestion_enabled = False
    runtime = RestIngestionRuntime(host.settings, object_store=None)
    with pytest.raises(ConnectorError):
        runtime.profile(host.profile.tenant_id, host.profile.profile_id)


def test_reconciliation_boundary_documents_orphan_objects(host):
    # Upload succeeds, SQL commit fails repeatedly, then the request is
    # dead-lettered: the object is orphaned on purpose and operators reconcile
    # by listing the tenant-scoped prefix. This test pins that documented
    # behaviour instead of pretending the two stores are atomic.
    host.transport.queue(page([{"id": 1}]))
    submit(host)

    def failing_commit(repository, result):
        raise OSError("store/db boundary")

    host.runtime.commit = failing_commit
    assert dispatch(host).retried == 1
    assert state(host) == (0, None, [])
    assert len(payloads(host)) == 1
