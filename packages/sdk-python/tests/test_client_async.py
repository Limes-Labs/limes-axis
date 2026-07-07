"""End-to-end tests: the async SDK client against the real FastAPI app."""

from __future__ import annotations

import httpx
import pytest
from conftest import TENANT_ID, AsyncFlakyTransport, AsyncRecordingTransport, build_app
from fastapi import FastAPI

from axis_sdk import (
    AsyncAxisClient,
    AuthRequiredError,
    AxisConnectionError,
    NotFoundError,
    RetryConfig,
)
from axis_sdk.models import ApprovalDecision

BASE_URL = "http://axis-api.test"

NO_BACKOFF = RetryConfig(backoff_initial_seconds=0.0, backoff_max_seconds=0.0)


def make_client(app: FastAPI, **kwargs) -> AsyncAxisClient:
    kwargs.setdefault("tenant_id", TENANT_ID)
    kwargs.setdefault("transport", httpx.ASGITransport(app=app))
    return AsyncAxisClient(BASE_URL, **kwargs)


async def test_async_health_and_readiness(app: FastAPI) -> None:
    async with make_client(app) as client:
        health = await client.system.health()
        ready = await client.system.ready()

    assert health.status == "ok"
    assert ready.status == "ready"


async def test_async_governed_surface_happy_paths(app: FastAPI) -> None:
    async with make_client(app) as client:
        inbox = await client.approvals.list()
        catalog = await client.actions.catalog()
        console = await client.workflows.console()
        explorer = await client.audit.explorer()
        graph = await client.ontology.graph()
        agents = await client.agents.registry()

    assert inbox.approvals
    assert catalog.actions
    assert console.workflow_runs
    assert explorer.events
    assert graph.nodes
    assert agents.agents


async def test_async_decision_and_persisted_run_round_trip(app: FastAPI) -> None:
    async with make_client(app) as client:
        decision = await client.approvals.decide(
            "appr_expedite_supplier_batch",
            decision=ApprovalDecision.APPROVE,
            actor_id="plant-operations-owner-role",
            actor_scopes=["approvals:supply:decide"],
        )
        run = await client.workflows.get_run(decision.workflow_id)
        events = await client.audit.query_events(event_type="approval.decision.recorded")

    assert decision.persisted is True
    assert run.workflow_id == decision.workflow_id
    assert events.events


async def test_async_action_run_idempotency_key_propagates(app: FastAPI) -> None:
    async with make_client(app) as client:
        result = await client.actions.create_run(
            "request_supplier_expedite",
            actor_id="agent_supply_risk",
            actor_scopes=["supply:read", "approvals:supply:request"],
            idempotency_key="sdk-async-run-1",
            payload={
                "supplier_batch_id": "asset_motors_batch",
                "target_arrival": "2026-06-22T08:00:00+02:00",
                "reason": "Line 2 packaging risk",
                "cost_ceiling_eur": "1200",
            },
        )

    assert result.idempotency_key == "sdk-async-run-1"
    assert result.persisted is True


async def test_async_error_mapping(session_factory) -> None:
    app = build_app(session_factory, oidc_auth_required=True)
    async with make_client(app) as client:
        with pytest.raises(AuthRequiredError):
            await client.approvals.decide(
                "appr_expedite_supplier_batch",
                decision="approve",
                actor_id="plant-operations-owner-role",
            )

    open_app = build_app(session_factory)
    async with make_client(open_app) as client:
        with pytest.raises(NotFoundError):
            await client.ontology.entity("node_does_not_exist")


async def test_async_get_retries_transport_failures(app: FastAPI) -> None:
    flaky = AsyncFlakyTransport(httpx.ASGITransport(app=app), failures=1)
    async with make_client(app, transport=flaky, retry=NO_BACKOFF) as client:
        health = await client.system.health()

    assert health.status == "ok"
    assert flaky.attempts == 2


async def test_async_retries_exhaust_into_connection_error(app: FastAPI) -> None:
    flaky = AsyncFlakyTransport(httpx.ASGITransport(app=app), failures=5)
    async with make_client(app, transport=flaky, retry=NO_BACKOFF) as client:
        with pytest.raises(AxisConnectionError):
            await client.system.health()

    assert flaky.attempts == 1 + NO_BACKOFF.max_retries


async def test_async_request_id_header_is_sent(app: FastAPI) -> None:
    recording = AsyncRecordingTransport(httpx.ASGITransport(app=app))
    async with make_client(app, transport=recording) as client:
        await client.system.health()

    assert recording.requests[0].headers["X-Request-Id"].startswith("req_")
