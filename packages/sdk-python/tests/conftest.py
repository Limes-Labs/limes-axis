"""End-to-end fixtures: the SDK runs against the real FastAPI app in-process.

``limes-axis-api`` is a dev-only dependency of the SDK: it is used here to
build the actual application (with an in-memory SQLite persistence layer
seeded from the real Alembic bootstrap payloads) and to serve it through
``httpx.ASGITransport``. The SDK runtime itself never imports ``axis_api``.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from runpy import run_path

import axis_api
import httpx
import pytest
from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.identity import OidcAuthenticationError, OidcPrincipal
from axis_api.main import create_app
from axis_api.models import Base
from axis_api.persistence import (
    AxisPersistenceRepository,
    DemoReferenceRecordCreate,
    WorkflowRunCreate,
    WorkflowTimelineEventCreate,
)
from axis_api.runtime_readiness import static_runtime_readiness_service
from axis_api.workflow_runtime import WorkflowSignalResult
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

TENANT_ID = "tenant_demo_manufacturing"

API_ROOT = Path(axis_api.__file__).resolve().parents[2]
MIGRATIONS = API_ROOT / "migrations" / "versions"

_REFERENCE_SEEDS = [
    ("overview", "manufacturing-overview", "0022_demo_reference_records.py", (
        "MANUFACTURING_OVERVIEW_PAYLOAD"
    )),
    ("agents", "manufacturing-agent-registry", "0024_agent_registry_reference.py", (
        "AGENT_REGISTRY_PAYLOAD"
    )),
    ("actions", "manufacturing-action-registry", "0025_action_registry_reference.py", (
        "ACTION_REGISTRY_PAYLOAD"
    )),
    ("workflows", "manufacturing-workflow-console", "0026_workflow_console_reference.py", (
        "WORKFLOW_CONSOLE_PAYLOAD"
    )),
    ("approvals", "manufacturing-approval-inbox", "0027_approval_inbox_reference.py", (
        "APPROVAL_INBOX_PAYLOAD"
    )),
    ("audit", "manufacturing-audit-explorer", "0028_audit_explorer_reference.py", (
        "AUDIT_EXPLORER_PAYLOAD"
    )),
    ("ontology", "manufacturing-ontology", "0030_ontology_reference.py", (
        "ONTOLOGY_PAYLOAD"
    )),
]


_PAYLOAD_CACHE: dict[str, dict] = {}


def _reference_payload(migration_file: str, symbol: str) -> dict:
    if migration_file not in _PAYLOAD_CACHE:
        migration = run_path(str(MIGRATIONS / migration_file))
        _PAYLOAD_CACHE[migration_file] = migration[symbol]
    return deepcopy(_PAYLOAD_CACHE[migration_file])


def _seed_supplier_delay_workflow(repository: AxisPersistenceRepository) -> None:
    started_at = datetime(2026, 6, 21, 14, 5, tzinfo=UTC)
    repository.create_workflow_run(
        WorkflowRunCreate(
            tenant_id=TENANT_ID,
            workflow_id="wf_supplier_delay_review",
            name="Supplier Delay Review",
            domain="Supply",
            state="waiting_for_approval",
            status="action_required",
            owner_role="plant-operations-owner",
            runtime="Temporal OSS",
            adapter="axis-temporal-adapter",
            autonomy_level="L2",
            started_at=started_at,
            eta="Today 18:00",
            blocker="Approve expedite action or adjust production schedule",
            objective="Resolve a delayed supplier batch before it blocks Line 2.",
            current_step="Approval gate",
            related_risk="risk_supplier_delay",
            related_assets=["asset_motors_batch", "asset_line_2_packaging"],
            inputs=["Supplier portal delay signal", "Line 2 packaging schedule"],
            proposed_outputs=["Expedite supplier batch action payload"],
            pending_signals=[
                {
                    "signal": "approval.decision",
                    "required_role": "plant-operations-owner",
                    "status": "waiting",
                    "approval_id": "appr_expedite_supplier_batch",
                }
            ],
            controls=["approvals:supply:decide", "append-only-audit-required"],
            audit_scope="wf_supplier_delay_review",
            replay_ready=False,
        )
    )
    repository.append_workflow_timeline_event(
        WorkflowTimelineEventCreate(
            tenant_id=TENANT_ID,
            workflow_id="wf_supplier_delay_review",
            sequence=1,
            event="workflow.started",
            occurred_at=started_at,
            actor="workflow-runtime",
            result="started",
            summary="Supplier delay workflow created from the supply risk signal.",
        )
    )


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        for surface, reference_id, migration_file, symbol in _REFERENCE_SEEDS:
            payload = _reference_payload(migration_file, symbol)
            repository.upsert_demo_reference_record(
                DemoReferenceRecordCreate(
                    tenant_id=TENANT_ID,
                    surface=surface,
                    reference_id=reference_id,
                    status="active",
                    source="bootstrap",
                    version=str(payload.get("schema_version", "sdk-test")),
                    payload=payload,
                )
            )
        _seed_supplier_delay_workflow(repository)
    yield factory
    engine.dispose()


class RecordingWorkflowRuntime:
    """Records workflow signals instead of talking to Temporal."""

    def __init__(self) -> None:
        self.requests: list[object] = []

    async def signal_approval_decision(self, request):
        self.requests.append(request)
        return WorkflowSignalResult(
            workflow_id=request.workflow_id,
            status="approval_signaled",
            adapter="axis-sdk-test-adapter",
            signal_name=request.signal_name,
            payload={
                "approval_id": request.approval_id,
                "approved": request.approved,
                "decision": request.decision.value,
            },
        )

    async def signal_action_run(self, request):
        self.requests.append(request)
        return WorkflowSignalResult(
            workflow_id=request.workflow_id,
            status="action_signal_requested",
            adapter="axis-sdk-test-adapter",
            signal_name=request.signal_name,
            payload={
                "action_id": request.action_id,
                "action_run_id": str(request.action_run_id),
                "idempotency_key": request.idempotency_key,
            },
        )


class StaticIdentityVerifier:
    """Accepts exactly one bearer token and returns a fixed principal."""

    def __init__(self, principal: OidcPrincipal, token: str = "sdk-test-token") -> None:
        self.principal = principal
        self.token = token

    def verify_authorization_header(self, authorization: str | None) -> OidcPrincipal:
        if authorization != f"Bearer {self.token}":
            raise OidcAuthenticationError("invalid_token")
        return self.principal


def build_app(
    session_factory: sessionmaker[Session],
    *,
    oidc_auth_required: bool = False,
    principal: OidcPrincipal | None = None,
) -> FastAPI:
    app = create_app(
        Settings(postgres_dsn="sqlite+pysqlite://", oidc_auth_required=oidc_auth_required),
        readiness_service=static_runtime_readiness_service(
            {
                "postgres": (False, None),
                "typedb": (False, None),
                "temporal": (False, None),
                "usage_metering": (False, None),
            }
        ),
    )
    app.state.session_factory = session_factory
    app.state.workflow_runtime = RecordingWorkflowRuntime()
    if principal is not None:
        app.state.identity_verifier = StaticIdentityVerifier(principal)
    return app


@pytest.fixture
def app(session_factory: sessionmaker[Session]) -> FastAPI:
    return build_app(session_factory)


class SyncASGITransport(httpx.BaseTransport):
    """Serve an ASGI app to the blocking SDK client in tests."""

    def __init__(self, app: FastAPI) -> None:
        self._transport = httpx.ASGITransport(app=app)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        async def _dispatch() -> httpx.Response:
            response = await self._transport.handle_async_request(request)
            await response.aread()
            return response

        response = asyncio.run(_dispatch())
        # Rebuild the response around a sync byte stream for httpx.Client.
        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=response.content,
            request=request,
        )


class RecordingTransport(httpx.BaseTransport):
    """Wraps a transport and records every outgoing request."""

    def __init__(self, inner: httpx.BaseTransport) -> None:
        self.inner = inner
        self.requests: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.inner.handle_request(request)


class FlakyTransport(httpx.BaseTransport):
    """Fails a configurable number of times before delegating."""

    def __init__(
        self,
        inner: httpx.BaseTransport,
        *,
        failures: int,
        mode: str = "connect_error",
        retry_after: str | None = None,
    ) -> None:
        self.inner = inner
        self.remaining_failures = failures
        self.mode = mode
        self.retry_after = retry_after
        self.attempts = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.attempts += 1
        if self.remaining_failures > 0:
            self.remaining_failures -= 1
            if self.mode == "connect_error":
                raise httpx.ConnectError("synthetic connection failure", request=request)
            headers = {"Retry-After": self.retry_after} if self.retry_after is not None else {}
            return httpx.Response(
                503, json={"detail": "synthetic upstream failure"}, headers=headers
            )
        return self.inner.handle_request(request)


class AsyncRecordingTransport(httpx.AsyncBaseTransport):
    """Async variant of :class:`RecordingTransport`."""

    def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
        self.inner = inner
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return await self.inner.handle_async_request(request)


class AsyncFlakyTransport(httpx.AsyncBaseTransport):
    """Async variant of :class:`FlakyTransport`."""

    def __init__(
        self,
        inner: httpx.AsyncBaseTransport,
        *,
        failures: int,
        mode: str = "connect_error",
    ) -> None:
        self.inner = inner
        self.remaining_failures = failures
        self.mode = mode
        self.attempts = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.attempts += 1
        if self.remaining_failures > 0:
            self.remaining_failures -= 1
            if self.mode == "connect_error":
                raise httpx.ConnectError("synthetic connection failure", request=request)
            return httpx.Response(503, json={"detail": "synthetic upstream failure"})
        return await self.inner.handle_async_request(request)
