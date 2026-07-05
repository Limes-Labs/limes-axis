"""Header and tenant-context propagation tests against the real app."""

from __future__ import annotations

import pytest
from conftest import TENANT_ID, RecordingTransport, SyncASGITransport
from fastapi import FastAPI

from axis_sdk import USER_AGENT, AxisClient, NotFoundError
from axis_sdk._version import SDK_VERSION

BASE_URL = "http://axis-api.test"


def recording_client(app: FastAPI, **kwargs) -> tuple[AxisClient, RecordingTransport]:
    recording = RecordingTransport(SyncASGITransport(app))
    return AxisClient(BASE_URL, transport=recording, **kwargs), recording


def test_user_agent_identifies_sdk_and_version(app: FastAPI) -> None:
    client, recording = recording_client(app)
    with client:
        client.system.health()

    user_agent = recording.requests[0].headers["User-Agent"]
    assert user_agent == USER_AGENT
    assert SDK_VERSION in user_agent


def test_static_token_is_sent_as_bearer(app: FastAPI) -> None:
    client, recording = recording_client(app, token="static-token")
    with client:
        client.system.health()

    assert recording.requests[0].headers["Authorization"] == "Bearer static-token"


def test_token_provider_is_called_per_request(app: FastAPI) -> None:
    tokens = iter(["token-1", "token-2"])
    client, recording = recording_client(app, token_provider=lambda: next(tokens))
    with client:
        client.system.health()
        client.system.ready()

    assert recording.requests[0].headers["Authorization"] == "Bearer token-1"
    assert recording.requests[1].headers["Authorization"] == "Bearer token-2"


def test_no_authorization_header_without_token(app: FastAPI) -> None:
    client, recording = recording_client(app)
    with client:
        client.system.health()

    assert "Authorization" not in recording.requests[0].headers


def test_request_ids_are_sent_and_unique(app: FastAPI) -> None:
    client, recording = recording_client(app)
    with client:
        client.system.health()
        client.system.ready()

    request_ids = [request.headers["X-Request-Id"] for request in recording.requests]
    assert all(request_id.startswith("req_") for request_id in request_ids)
    assert len(set(request_ids)) == len(request_ids)


def test_error_surfaces_the_request_id_that_was_sent(app: FastAPI) -> None:
    client, recording = recording_client(app, tenant_id=TENANT_ID)
    with client, pytest.raises(NotFoundError) as excinfo:
        client.ontology.entity("node_does_not_exist")

    sent_request_id = recording.requests[-1].headers["X-Request-Id"]
    assert excinfo.value.request_id == sent_request_id


def test_configured_tenant_is_injected_as_query_parameter(app: FastAPI) -> None:
    client, recording = recording_client(app, tenant_id=TENANT_ID)
    with client:
        client.approvals.list()

    assert recording.requests[0].url.params["tenant_id"] == TENANT_ID


def test_explicit_tenant_overrides_configured_tenant(app: FastAPI) -> None:
    client, recording = recording_client(app, tenant_id="tenant_configured")
    with client, pytest.raises(NotFoundError):
        # The override tenant has no seeded reference records.
        client.approvals.list("tenant_other")

    assert recording.requests[0].url.params["tenant_id"] == "tenant_other"


def test_unscoped_system_routes_send_no_tenant_parameter(app: FastAPI) -> None:
    client, recording = recording_client(app, tenant_id=TENANT_ID)
    with client:
        client.system.health()

    assert "tenant_id" not in recording.requests[0].url.params
