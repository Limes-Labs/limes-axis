"""Retry policy tests with a flaky transport in front of the real app."""

from __future__ import annotations

import pytest
from conftest import TENANT_ID, FlakyTransport, SyncASGITransport
from fastapi import FastAPI

from axis_sdk import AxisClient, AxisConnectionError, RetryConfig, ServerError

BASE_URL = "http://axis-api.test"

NO_BACKOFF = RetryConfig(backoff_initial_seconds=0.0, backoff_max_seconds=0.0)


def make_client(app: FastAPI, transport, retry: RetryConfig = NO_BACKOFF) -> AxisClient:
    return AxisClient(BASE_URL, tenant_id=TENANT_ID, transport=transport, retry=retry)


def test_get_retries_connect_errors_then_succeeds(app: FastAPI) -> None:
    flaky = FlakyTransport(SyncASGITransport(app), failures=2)
    with make_client(app, flaky) as client:
        health = client.system.health()

    assert health.status == "ok"
    assert flaky.attempts == 3


def test_get_retries_retryable_status_then_succeeds(app: FastAPI) -> None:
    flaky = FlakyTransport(SyncASGITransport(app), failures=1, mode="status")
    with make_client(app, flaky) as client:
        inbox = client.approvals.list()

    assert inbox.approvals
    assert flaky.attempts == 2


def test_get_retries_exhaust_into_connection_error(app: FastAPI) -> None:
    flaky = FlakyTransport(SyncASGITransport(app), failures=10)
    with make_client(app, flaky) as client, pytest.raises(AxisConnectionError):
        client.system.health()

    assert flaky.attempts == 1 + NO_BACKOFF.max_retries


def test_get_retries_exhaust_into_server_error_for_5xx(app: FastAPI) -> None:
    flaky = FlakyTransport(SyncASGITransport(app), failures=10, mode="status")
    with make_client(app, flaky) as client, pytest.raises(ServerError) as excinfo:
        client.system.health()

    assert excinfo.value.status_code == 503
    assert flaky.attempts == 1 + NO_BACKOFF.max_retries


def test_post_without_idempotency_key_is_never_retried(app: FastAPI) -> None:
    flaky = FlakyTransport(SyncASGITransport(app), failures=1)
    with make_client(app, flaky) as client, pytest.raises(AxisConnectionError):
        client.approvals.decide(
            "appr_expedite_supplier_batch",
            decision="approve",
            actor_id="plant-operations-owner-role",
            actor_scopes=["approvals:supply:decide"],
        )

    assert flaky.attempts == 1


def test_keyless_action_run_create_is_never_retried(app: FastAPI) -> None:
    flaky = FlakyTransport(SyncASGITransport(app), failures=1)
    with make_client(app, flaky) as client, pytest.raises(AxisConnectionError):
        client.actions.create_run(
            "request_supplier_expedite",
            actor_id="agent_supply_risk",
            actor_scopes=["supply:read", "approvals:supply:request"],
            payload={
                "supplier_batch_id": "asset_motors_batch",
                "target_arrival": "2026-06-22T08:00:00+02:00",
                "reason": "Line 2 packaging risk",
                "cost_ceiling_eur": "1200",
            },
        )

    assert flaky.attempts == 1


def test_idempotency_keyed_action_run_create_is_retried(app: FastAPI) -> None:
    flaky = FlakyTransport(SyncASGITransport(app), failures=1)
    with make_client(app, flaky) as client:
        result = client.actions.create_run(
            "request_supplier_expedite",
            actor_id="agent_supply_risk",
            actor_scopes=["supply:read", "approvals:supply:request"],
            idempotency_key="sdk-retry-keyed-run",
            payload={
                "supplier_batch_id": "asset_motors_batch",
                "target_arrival": "2026-06-22T08:00:00+02:00",
                "reason": "Line 2 packaging risk",
                "cost_ceiling_eur": "1200",
            },
        )

    assert result.idempotency_key == "sdk-retry-keyed-run"
    assert flaky.attempts == 2


def test_retry_after_header_paces_the_retry(app: FastAPI, monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("axis_sdk.client.time.sleep", sleeps.append)
    flaky = FlakyTransport(
        SyncASGITransport(app), failures=1, mode="status", retry_after="2"
    )
    retry = RetryConfig(backoff_initial_seconds=0.0, backoff_max_seconds=5.0)
    with make_client(app, flaky, retry=retry) as client:
        health = client.system.health()

    assert health.status == "ok"
    assert sleeps == [2.0]


def test_retry_after_header_is_capped_by_max_backoff(app: FastAPI, monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("axis_sdk.client.time.sleep", sleeps.append)
    flaky = FlakyTransport(
        SyncASGITransport(app), failures=1, mode="status", retry_after="60"
    )
    retry = RetryConfig(backoff_initial_seconds=0.0, backoff_max_seconds=3.0)
    with make_client(app, flaky, retry=retry) as client:
        health = client.system.health()

    assert health.status == "ok"
    assert sleeps == [3.0]


def test_retries_can_be_disabled(app: FastAPI) -> None:
    flaky = FlakyTransport(SyncASGITransport(app), failures=1)
    retry = RetryConfig(enabled=False)
    with make_client(app, flaky, retry=retry) as client, pytest.raises(AxisConnectionError):
        client.system.health()

    assert flaky.attempts == 1


def test_4xx_responses_are_not_retried_even_when_status_configured(app: FastAPI) -> None:
    # A 404 is not in retry_statuses by default and must never be added
    # implicitly: FlakyTransport passthrough hits the real app once.
    flaky = FlakyTransport(SyncASGITransport(app), failures=0)
    with make_client(app, flaky) as client, pytest.raises(Exception) as excinfo:
        client.ontology.entity("node_does_not_exist")

    assert flaky.attempts == 1
    assert getattr(excinfo.value, "status_code", None) == 404
