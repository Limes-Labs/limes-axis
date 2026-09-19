"""Local wire-level conformance for the REST collection host (#862).

Run the whole scenario with one documented command:

```sh
make test-api PYTEST_ARGS='tests/test_rest_connector_conformance.py -q'
```

It uses a real loopback HTTP service, the real #860 reader transport and the
real ingestion outbox over an isolated SQLite database and local object-store
directory under pytest's ``tmp_path`` (removed automatically; nothing outside
that directory or the ephemeral loopback port is touched).

Substituted components are labelled honestly: SQLite stands in for PostgreSQL
and the loopback service stands in for a provider, so this evidence is
``local_wire_level`` — never ``provider_verified``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from uuid import uuid4

import pytest
from axis_sdk.connector_authoring.contracts import ReadLimits
from axis_sdk.connector_authoring.health import HealthBudgets
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from axis_api.config import Settings
from axis_api.connector_rest_ingestion import (
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
from axis_api.models import Base, ConnectorSourceExtractionBatch
from axis_api.object_storage import LocalObjectStore
from axis_api.persistence import (
    AxisPersistenceRepository,
    ConnectorCredentialHandleCreate,
    ConnectorCredentialLeaseCreate,
    ConnectorEgressPolicyCreate,
    ConnectorManifestCreate,
    TenantCreate,
)
from axis_api.rest_connector_support_evidence import (
    LOCAL_ONLY_VERIFICATION,
    NO_COMMITTED_EVIDENCE,
    PROVIDER_NOT_VERIFIED,
    VerificationScope,
    build_rest_support_evidence,
    project_rest_health,
)
from axis_api.rest_source_profile import REST_SOURCE_CONNECTOR_ID, RestHostProfile

BEARER = "conformance-bearer-token"
ORDER_IDS = ["order-0001", "order-0002", "order-0003"]


class ScriptedRestService:
    """A real loopback HTTP service with a deterministic response queue."""

    def __init__(self) -> None:
        self.responses: list[tuple[int, dict, bytes]] = []
        self.requests: list[str] = []
        service = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):  # noqa: N802 - stdlib hook name
                service.requests.append(self.path)
                status, headers, body = (
                    service.responses.pop(0) if service.responses else (500, {}, b"{}")
                )
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):  # noqa: ARG002 - silence test output
                return

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def queue_json(self, body, *, status=200, headers=None):
        encoded = body if isinstance(body, bytes) else json.dumps(body).encode()
        merged = {"Content-Type": "application/json", **(headers or {})}
        self.responses.append((status, merged, encoded))

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def build_profile(tenant_id: str, endpoint: str) -> RestHostProfile:
    return RestHostProfile(
        tenant_id=tenant_id,
        profile_id="profile_rest_orders",
        endpoint=endpoint,
        source=RestSourceProfile(
            endpoint_profile_id="endpoint_rest_orders",
            endpoint_profile_revision="a" * 64,
            collection_id="rest_orders",
            path_template="/v1/orders/{account}",
            query_parameters=(RestParameter(name="status", value_type="string", required=True),),
            records_path=("data", "orders"),
            schema_fingerprint="b" * 64,
            pagination=OpaqueCursorPagination(parameter="cursor", next_path=("paging", "next")),
            limits=RestSourceLimits(
                page=ReadLimits(max_records=10, max_bytes=100_000, time_budget_seconds=30),
                max_pages=10,
            ),
        ),
        path_values={"account": "acct-1"},
        query_values={"status": "open"},
        credential_secret_ref="env://REST_CONFORMANCE_CREDENTIALS",
        private_endpoint_ref="private-endpoint://tenant/rest-readonly",
        allow_insecure_local=True,
    )


@pytest.fixture
def service():
    service = ScriptedRestService()
    yield service
    service.stop()


@pytest.fixture
def host(tmp_path, service):
    """Real outbox + real reader over an isolated database and payload store."""

    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'conformance.sqlite'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, autoflush=False, expire_on_commit=False)
    profile = build_profile(f"rest-conf-{uuid4().hex}", service.endpoint)
    connector = REST_SOURCE_CONNECTOR_ID
    settings = Settings(
        connector_sync_execution_enabled=True,
        source_ingestion_dispatch_enabled=True,
        source_ingestion_extraction_enabled=True,
        rest_source_ingestion_enabled=True,
        rest_source_profiles=[profile],
    )
    store = LocalObjectStore(tmp_path / "payloads")
    runtime = RestIngestionRuntime(
        settings,
        store,
        resolver=EnvLeaseScopedSecretResolver(
            {"REST_CONFORMANCE_CREDENTIALS": json.dumps({"bearer_token": BEARER})}
        ),
    )
    with session_scope(factory) as session:
        repo = AxisPersistenceRepository(session)
        repo.create_tenant(
            TenantCreate(
                tenant_id=profile.tenant_id,
                display_name="REST conformance",
                description="Isolated",
                created_by="test",
            )
        )
        repo.create_connector_manifest(
            ConnectorManifestCreate(
                tenant_id=profile.tenant_id,
                connector_id=connector,
                revision_number=1,
                display_name="REST conformance",
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
                permission_decision={"allowed": True, "reason": "conformance"},
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
                display_name="Loopback conformance service",
                connection_profile_id=profile.profile_id,
                egress_boundary="approved_private_endpoint",
                policy_mode="approved_private_endpoint",
                runtime_boundary="axis-egress-policy-enforcer",
                private_endpoint_ref=profile.private_endpoint_ref,
                created_by="test",
                policy_document={"approved_endpoint_target_sha256": profile.endpoint_target_sha256},
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
                activation_reason="Bind the declared REST collection for conformance",
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
        store=store,
        profile=profile,
        service=service,
        binding_id="binding",
        tmp_path=tmp_path,
    )
    engine.dispose()


def submit(host, request_id="request", *, stage="extract"):
    with session_scope(host.factory) as session:
        return record_connector_source_ingestion_request(
            AxisPersistenceRepository(session),
            submission=ConnectorSourceIngestionSubmission(
                tenant_id=host.profile.tenant_id,
                connector_id=REST_SOURCE_CONNECTOR_ID,
                request_id=request_id,
                requested_by="test",
                reason="REST conformance page",
                stage=stage,
                selections=[{"binding_id": host.binding_id}],
            ),
            principal_scopes=[SOURCE_INGESTION_SCOPE],
            max_selections=20,
            settings=host.settings,
        )


_UNSET = object()


def dispatch(host, *, rest_runtime=_UNSET):
    runtime = host.runtime if rest_runtime is _UNSET else rest_runtime
    return asyncio.run(
        SourceIngestionOutboxDispatcher(
            settings=host.settings,
            session_factory=host.factory,
            runtime=ObservationFreshnessIngestionRuntime(),
            rest_runtime=runtime,
            random_uniform=lambda low, high: low,
        ).run_once()
    )


def page(rows, *, next_token=None):
    body = {"data": {"orders": [{"order_id": value} for value in rows]}}
    if next_token is not None:
        body["paging"] = {"next": next_token}
    return body


def binding_state(host):
    with session_scope(host.factory) as session:
        return AxisPersistenceRepository(session).get_connector_source_binding(
            host.profile.tenant_id, host.binding_id
        )


def envelope_digests(host):
    return [
        json.loads(path.read_text())
        for path in sorted((host.tmp_path / "payloads").rglob("*.json"))
    ]


def evidence_for(host, request_id, scope):
    with session_scope(host.factory) as session:
        return build_rest_support_evidence(
            AxisPersistenceRepository(session),
            tenant_id=host.profile.tenant_id,
            connector_id=REST_SOURCE_CONNECTOR_ID,
            binding_id=host.binding_id,
            request_id=request_id,
            scope=scope,
        )


# --------------------------------------------------------------------------
# Scenario: successful traversal over the real wire, committed durably.
# --------------------------------------------------------------------------


def test_full_traversal_commits_bounded_payloads_and_reports_completion(host):
    host.service.queue_json(page(ORDER_IDS[:1], next_token="cursor-2"))
    host.service.queue_json(page(ORDER_IDS[1:2], next_token="cursor-3"))
    host.service.queue_json(page(ORDER_IDS[2:]))
    for index in range(3):
        submit(host, f"request-{index}")
        assert dispatch(host).completed == 1

    binding = binding_state(host)
    assert binding.source_checkpoint_revision == 3
    assert binding.source_checkpoint["traversal"] == "complete"
    assert binding.source_checkpoint["cursor"] is None

    envelopes = envelope_digests(host)
    assert len(envelopes) == 3
    observed = [row for envelope in envelopes for row in envelope["rows"]]
    assert sorted(row["order_id"] for row in observed) == ORDER_IDS
    for envelope in envelopes:
        assert envelope["completion"] in {"more", "complete"}
        assert envelope["ordering_mode"] == "none"
    # The declared consistency is a mutable traversal: no snapshot or CDC claim.
    assert host.profile.source.consistency == "mutable_traversal"
    assert len(host.service.requests) == 3
    assert all(path.startswith("/v1/orders/acct-1?status=open") for path in host.service.requests)

    with session_scope(host.factory) as session:
        batches = list(session.scalars(select(ConnectorSourceExtractionBatch)).all())
    assert len(batches) == 3
    serialized = json.dumps([batch.cursor_watermark for batch in batches]) + json.dumps(
        [batch.provenance for batch in batches]
    )
    for secret in ("order-0001", "cursor-2", BEARER):
        assert secret not in serialized


def test_metadata_evidence_is_public_safe_and_scope_is_local(host):
    host.service.queue_json(page(ORDER_IDS))
    submit(host)
    assert dispatch(host).completed == 1
    evidence = evidence_for(host, "request", VerificationScope.LOCAL_WIRE_LEVEL)
    assert evidence.has_committed_evidence
    assert evidence.record_count == len(ORDER_IDS)
    assert evidence.completion == "complete"
    assert evidence.scope == VerificationScope.LOCAL_WIRE_LEVEL
    assert LOCAL_ONLY_VERIFICATION in evidence.reasons
    assert PROVIDER_NOT_VERIFIED in evidence.reasons
    serialized = evidence.model_dump_json()
    for secret in ("order-0001", "cursor-", BEARER):
        assert secret not in serialized


# --------------------------------------------------------------------------
# Recovery cases against the same real service.
# --------------------------------------------------------------------------


def test_throttle_retries_durably_then_completes(host):
    host.service.queue_json({"error": "slow down"}, status=429, headers={"Retry-After": "1"})
    host.service.queue_json(page(ORDER_IDS))
    submit(host)
    assert dispatch(host).retried == 1
    with session_scope(host.factory) as session:
        row = AxisPersistenceRepository(session).get_connector_source_ingestion_request(
            host.profile.tenant_id, "request"
        )
        assert row.last_error == "rate_limited"
        row.available_at = datetime.now(UTC) - timedelta(seconds=1)
    assert dispatch(host).completed == 1
    assert binding_state(host).source_checkpoint_revision == 1


def test_repeated_cursor_is_terminal_without_storing_the_loop(host):
    host.service.queue_json(page(ORDER_IDS[:1], next_token="A"))
    host.service.queue_json(page(ORDER_IDS[1:2], next_token="A"))
    submit(host, "request-0")
    assert dispatch(host).completed == 1
    submit(host, "request-1")
    assert dispatch(host).dead_lettered == 1
    with session_scope(host.factory) as session:
        row = AxisPersistenceRepository(session).get_connector_source_ingestion_request(
            host.profile.tenant_id, "request-1"
        )
        assert row.last_error == "no_progress"
    assert binding_state(host).source_checkpoint_revision == 1


def test_malformed_json_dead_letters_without_advancing(host):
    host.service.queue_json(b"not-json", headers={"Content-Type": "application/json"})
    submit(host)
    assert dispatch(host).dead_lettered == 1
    with session_scope(host.factory) as session:
        row = AxisPersistenceRepository(session).get_connector_source_ingestion_request(
            host.profile.tenant_id, "request"
        )
        assert row.last_error == "resource_mismatch"
    assert binding_state(host).source_checkpoint_revision == 0


def test_schema_change_blocks_before_any_request(host):
    submit(host)
    with session_scope(host.factory) as session:
        AxisPersistenceRepository(session).get_data_resource_observation(
            host.profile.tenant_id, REST_SOURCE_CONNECTOR_ID, host.profile.resource_name
        ).schema_fingerprint = "c" * 64
    assert dispatch(host).dead_lettered == 1
    assert host.service.requests == []


def test_interrupted_acceptance_replays_without_advancing(host):
    host.service.queue_json(page(ORDER_IDS))
    host.service.queue_json(page(ORDER_IDS))
    submit(host)
    original = host.store.put_json
    host.store.put_json = lambda *args: (_ for _ in ()).throw(OSError("interrupted"))
    assert dispatch(host).retried == 1
    assert binding_state(host).source_checkpoint_revision == 0
    host.store.put_json = original
    with session_scope(host.factory) as session:
        row = AxisPersistenceRepository(session).get_connector_source_ingestion_request(
            host.profile.tenant_id, "request"
        )
        row.available_at = datetime.now(UTC) - timedelta(seconds=1)
    assert dispatch(host).completed == 1
    assert binding_state(host).source_checkpoint_revision == 1
    assert len(envelope_digests(host)) == 1


def test_disabled_gates_prove_zero_source_io(host):
    host.settings.rest_source_ingestion_enabled = False
    host.service.queue_json(page(ORDER_IDS))
    submit(host)
    assert dispatch(host).dead_lettered == 1
    assert host.service.requests == []
    assert host.service.responses  # nothing consumed
    assert binding_state(host).source_checkpoint_revision == 0


# --------------------------------------------------------------------------
# Verification scope and health: what the evidence does and does not certify.
# --------------------------------------------------------------------------


def test_provider_scope_requires_provider_evidence_and_contract_scope_is_batch_free(host):
    from axis_api.rest_connector_support_evidence import RestSupportEvidence

    with pytest.raises(ValueError):
        RestSupportEvidence(
            tenant_id=host.profile.tenant_id,
            connector_id=REST_SOURCE_CONNECTOR_ID,
            binding_id=host.binding_id,
            resource_name=host.profile.resource_name,
            scope=VerificationScope.PROVIDER_VERIFIED,
        )
    host.service.queue_json(page(ORDER_IDS))
    submit(host)
    assert dispatch(host).completed == 1
    with pytest.raises(ValueError):
        evidence_for(host, "request", VerificationScope.CONTRACT_ONLY)


def test_health_distinguishes_never_tested_from_fresh_and_stale(host):
    budgets = HealthBudgets(
        max_freshness_seconds=300, max_lag_seconds=300, max_checkpoint_age_seconds=300
    )
    # Never tested: no committed evidence, no freshness, no certified availability.
    never = evidence_for(host, None, VerificationScope.LOCAL_WIRE_LEVEL)
    assert NO_COMMITTED_EVIDENCE in never.reasons
    never_health = project_rest_health(never, observed_at=datetime.now(UTC), budgets=budgets)
    assert never_health.status == "unknown"
    assert "freshness_unknown" in never_health.reasons

    host.service.queue_json(page(ORDER_IDS))
    submit(host)
    assert dispatch(host).completed == 1
    fresh = evidence_for(host, "request", VerificationScope.LOCAL_WIRE_LEVEL)
    observed_now = datetime.now(UTC)
    # Without a caller-supplied live probe the source head is unknown, so the
    # evidence cannot certify readiness and the SDK says lag_unknown.
    unprobed = project_rest_health(fresh, observed_at=observed_now, budgets=budgets)
    assert unprobed.status == "unknown" and "lag_unknown" in unprobed.reasons
    # With a live probe at the observation time, a fresh success is ready.
    probed = project_rest_health(
        fresh,
        observed_at=observed_now,
        budgets=budgets,
        source_head_at=observed_now,
        source_watermark_at=fresh.last_committed_at,
    )
    assert probed.status == "ready"
    # A past green run does not certify current availability: beyond the
    # freshness budget the same evidence is stale.
    stale_at = observed_now + timedelta(seconds=budgets.max_freshness_seconds + 1)
    stale = project_rest_health(
        fresh,
        observed_at=stale_at,
        budgets=budgets,
        source_head_at=stale_at,
        source_watermark_at=fresh.last_committed_at,
    )
    assert stale.status != "ready"
    assert "stale" in stale.reasons


def test_health_reports_scheduled_retry_as_degraded_not_ready(host):
    budgets = HealthBudgets(
        max_freshness_seconds=3600, max_lag_seconds=3600, max_checkpoint_age_seconds=3600
    )
    host.service.queue_json({"error": "slow down"}, status=429, headers={"Retry-After": "2"})
    submit(host)
    assert dispatch(host).retried == 1
    evidence = evidence_for(host, "request", VerificationScope.LOCAL_WIRE_LEVEL)
    assert evidence.retry_state == "scheduled"
    health = project_rest_health(evidence, observed_at=datetime.now(UTC), budgets=budgets)
    assert health.status == "degraded"
    assert "throttled" in health.reasons


def test_loopback_endpoint_digest_binds_the_actual_origin(host):
    expected = hashlib.sha256(f"127.0.0.1:{host.service.port}".encode()).hexdigest()
    assert host.profile.endpoint_target_sha256 == expected
    assert host.profile.pinned_origin[:2] == ("http", "127.0.0.1")
