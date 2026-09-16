"""Governed REST page reader tests over a local HTTP fixture server."""

import contextlib
import gzip
import hashlib
import json
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlsplit

import pytest
from axis_sdk.connector_authoring.contracts import (
    ConnectorError,
    ErrorCode,
    OperationContext,
    ReadRequest,
    ResourceSelection,
)
from pydantic import SecretStr, ValidationError

from axis_api.connector_rest_profiles import parse_rest_source_profile
from axis_api.connector_rest_reader import REST_ADAPTER_NAME, RestPageSource, RestSourceAuthority

JSON_HEADERS = {"Content-Type": "application/json"}
BEARER_SECRET = "bearer-secret-fixture"
CURSOR_PAGE_TWO = "cursor-page-2-sensitive"
PROFILE_REVISION = "e" * 64

PAGE_ONE_ORDERS = [
    {"id": "o-1", "total": 10},
    {"id": "o-2", "total": 20},
    {"id": "o-3", "total": 30},
]


def _page_one_body():
    return json.dumps({"data": {"orders": PAGE_ONE_ORDERS}, "next": CURSOR_PAGE_TWO}).encode()


def _page_two_body():
    return json.dumps({"data": {"orders": [{"id": "o-4", "total": 40}]}, "next": None}).encode()


def _page_two_url(origin):
    return f"{origin[0]}://{origin[1]}:{origin[2]}/v1/accounts/example/orders?after={CURSOR_PAGE_TWO}"


def _base_profile_data():
    return {
        "endpoint_profile_id": "approved-orders-service",
        "endpoint_profile_revision": PROFILE_REVISION,
        "collection_id": "orders",
        "path_template": "/v1/accounts/{account}/orders",
        "query_parameters": [{"name": "status", "value_type": "string", "required": True}],
        "records_path": ["data", "orders"],
        "schema_fingerprint": "a" * 64,
        "pagination": {"kind": "opaque_cursor", "parameter": "after", "next_path": ["next"]},
    }


def _next_link_profile_data():
    return _base_profile_data() | {
        "pagination": {"kind": "next_link", "next_path": ["links", "next"]}
    }


def _send(handler, status, headers, body):
    handler.send_response(status)
    for name, value in headers.items():
        handler.send_header(name, value)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    with contextlib.suppress(BrokenPipeError, ConnectionResetError):
        handler.wfile.write(body)


class FixtureServer:
    """Route-dispatched loopback server recording attempts for assertions."""

    def __init__(self):
        self.routes = {}
        self.requests = []
        handler = self._build_handler()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.server.daemon_threads = True
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @staticmethod
    def _build_handler():
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                pass

            def log_message(self, *args):
                pass

        return Handler

    @property
    def origin(self):
        return ("http", "127.0.0.1", self.server.server_address[1])

    def route(self, path, handler):
        self.routes[path] = handler

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def _record(self, request):
        self.requests.append(
            {
                "method": request.command,
                "path": urlsplit(request.path).path,
                "query": {
                    key: values[0]
                    for key, values in parse_qs(urlsplit(request.path).query).items()
                },
                "authorization_present": bool(request.headers.get("Authorization")),
            }
        )


def _bind(server):
    """Bind a handler class that dispatches through the fixture instance."""

    class BoundHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            server._record(self)
            route = server.routes.get(urlsplit(self.path).path)
            if route is None:
                _send(self, 404, JSON_HEADERS, b'{"error": "no fixture route"}')
                return
            status, headers, body = route(
                {
                    key: values[0]
                    for key, values in parse_qs(urlsplit(self.path).query).items()
                }
            )
            if body == "endless":
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.end_headers()
                try:
                    while True:
                        self.wfile.write(b"4096\r\n" + b"x" * 4096 + b"\r\n")
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                return
            _send(self, status, headers, body)

        def log_message(self, *args):
            pass

    return BoundHandler


def _make_server():
    server = FixtureServer()
    server.server.RequestHandlerClass = _bind(server)
    return server


@pytest.fixture
def server():
    server = _make_server()
    server.route(
        "/v1/accounts/example/orders",
        lambda query: (
            (200, JSON_HEADERS, _page_one_body())
            if query.get("after") != CURSOR_PAGE_TWO
            else (200, JSON_HEADERS, _page_two_body())
        ),
    )
    yield server
    server.close()


@pytest.fixture
def profile():
    return parse_rest_source_profile(_base_profile_data())


def build_authority(server, **overrides):
    origin = server.origin
    defaults = {
        "tenant_id": "tenant-a",
        "connector_id": "rest-a",
        "credential_lease_id": "lease-1",
        "egress_policy_id": "policy-1",
        "lease_status": "lease_executed",
        "lease_ref": "provider-lease-ref-1",
        "lease_secret_material_returned": "false",
        "lease_expires_at": datetime.now(UTC) + timedelta(minutes=5),
        "egress_mode": "approved_private_endpoint",
        "egress_endpoint_target_sha256": hashlib.sha256(
            f"{origin[1]}:{origin[2]}".encode()
        ).hexdigest(),
        "pinned_origin": origin,
        "allow_insecure_local": True,
        "registered_endpoint_profile_revision": PROFILE_REVISION,
    }
    return RestSourceAuthority.model_validate(defaults | overrides)


def build_source(profile, authority, **overrides):
    return RestPageSource(
        profile=profile,
        authority=authority,
        credential_bearer=SecretStr(BEARER_SECRET),
        path_values={"account": "example"},
        query_values={"status": "open"},
        **overrides,
    )


def read_request(server, **overrides):
    defaults = {
        "context": OperationContext(
            tenant_id="tenant-a", connector_id="rest-a", actor_id="operator", operation_id="run-a"
        ),
        "resource": ResourceSelection(
            resource_id="orders", schema_fingerprint="a" * 64, source_revision="b" * 64
        ),
    }
    return ReadRequest.model_validate(defaults | overrides)


class FakeClock:
    def __init__(self, *values):
        self.values = list(values)
        self.index = 0

    def __call__(self):
        value = self.values[min(self.index, len(self.values) - 1)]
        self.index += 1
        return value


# --- One bounded page with an advancing, context-bound candidate checkpoint ---


def test_three_record_fixture_returns_bounded_page_and_candidate_checkpoint(server, profile):
    authority = build_authority(server)
    with build_source(profile, authority) as source:
        batch = source.read(read_request(server))
    assert [record["id"] for record in batch.records] == ["o-1", "o-2", "o-3"]
    assert batch.completion == "more"
    request = read_request(server)
    assert batch.checkpoint.matches(request.context, request.resource)
    assert source.progress.evidence() == {
        "adapter": REST_ADAPTER_NAME,
        "credential_lease_id": "lease-1",
        "egress_policy_id": "policy-1",
        "egress_target_validated": True,
        "records_read": 3,
        "wire_bytes": len(_page_one_body()),
        "decoded_bytes": len(_page_one_body()),
        "completion": "more",
        "checkpoint_present": True,
        "auth_failure": False,
        "retry_after_seconds": None,
    }


def test_advancing_cursor_resumes_the_traversal(server, profile):
    authority = build_authority(server)
    with build_source(profile, authority) as source:
        first = source.read(read_request(server))
        resumed = ReadRequest.model_validate(
            {
                "context": OperationContext(
                    tenant_id="tenant-a",
                    connector_id="rest-a",
                    actor_id="operator",
                    operation_id="run-b",
                ),
                "resource": ResourceSelection(
                    resource_id="orders", schema_fingerprint="a" * 64, source_revision="b" * 64
                ),
                "checkpoint": first.checkpoint,
            }
        )
        second = source.read(resumed)
    assert second.completion == "complete"
    assert [record["id"] for record in second.records] == ["o-4"]
    assert second.checkpoint is None
    queries = [entry["query"] for entry in server.requests]
    assert queries[0] == {"status": "open"}
    assert queries[1] == {"status": "open", "after": CURSOR_PAGE_TWO}


# --- Gate failures never reach the transport ---


@pytest.mark.parametrize(
    "overrides",
    [
        {"lease_status": "lease_revoked"},
        {"lease_secret_material_returned": "true"},
        {"lease_ref": ""},
        {"egress_mode": "approved_public_endpoint"},
        {"egress_endpoint_target_sha256": "f" * 64},
    ],
)
def test_inactive_lease_or_denied_endpoint_fails_closed_before_any_io(server, overrides):
    with pytest.raises(ValidationError):
        build_authority(server, **overrides)
    assert server.requests == []


def test_expired_lease_causes_zero_transport_calls(server, profile):
    authority = build_authority(
        server, lease_expires_at=datetime.now(UTC) - timedelta(seconds=1)
    )
    with build_source(profile, authority) as source, pytest.raises(ConnectorError) as error:
        source.read(read_request(server))
    assert error.value.code == ErrorCode.CONTEXT_MISMATCH
    assert server.requests == []


def test_wrong_tenant_context_causes_zero_transport_calls(server, profile):
    authority = build_authority(server)
    request = ReadRequest.model_validate(
        {
            "context": OperationContext(
                tenant_id="tenant-b",
                connector_id="rest-a",
                actor_id="operator",
                operation_id="run-a",
            ),
            "resource": ResourceSelection(
                resource_id="orders", schema_fingerprint="a" * 64, source_revision="b" * 64
            ),
        }
    )
    with build_source(profile, authority) as source, pytest.raises(ConnectorError) as error:
        source.read(request)
    assert error.value.code == ErrorCode.CONTEXT_MISMATCH
    assert server.requests == []


def test_profile_revision_mismatch_is_rejected_before_io(server, profile):
    authority = build_authority(server, registered_endpoint_profile_revision="f" * 64)
    with pytest.raises(ConnectorError) as error:
        build_source(profile, authority)
    assert error.value.code == ErrorCode.RESOURCE_MISMATCH
    assert server.requests == []


def test_cross_tenant_cursor_reuse_is_rejected_without_io(server, profile):
    authority = build_authority(server)
    with build_source(profile, authority) as source:
        batch = source.read(read_request(server))
    assert len(server.requests) == 1
    with pytest.raises(ValidationError):
        ReadRequest.model_validate(
            {
                "context": OperationContext(
                    tenant_id="tenant-b",
                    connector_id="rest-a",
                    actor_id="operator",
                    operation_id="run-c",
                ),
                "resource": ResourceSelection(
                    resource_id="orders", schema_fingerprint="a" * 64, source_revision="b" * 64
                ),
                "checkpoint": batch.checkpoint,
            }
        )
    assert len(server.requests) == 1


# --- Redirects and pagination origins never receive credentials ---


def test_disallowed_redirect_is_never_dialed_and_returns_fixed_error(server, profile):
    evil = _make_server()
    try:
        server.route(
            "/v1/accounts/example/orders",
            lambda query: (
                302,
                {"Location": f"{evil.origin[0]}://{evil.origin[1]}:{evil.origin[2]}/evil"},
                b"",
            ),
        )
        authority = build_authority(server)
        with build_source(profile, authority) as source, pytest.raises(ConnectorError) as error:
            source.read(read_request(server))
        assert error.value.code == ErrorCode.RESOURCE_MISMATCH
        assert evil.requests == []
        assert len(server.requests) == 1
        assert CURSOR_PAGE_TWO not in str(error.value)
    finally:
        evil.close()


def test_cross_origin_next_link_never_receives_credentials(server):
    profile = parse_rest_source_profile(_next_link_profile_data())
    evil = _make_server()
    try:
        link = f"{evil.origin[0]}://{evil.origin[1]}:{evil.origin[2]}/evil?after=x"
        server.route(
            "/v1/accounts/example/orders",
            lambda query: (
                200,
                JSON_HEADERS,
                json.dumps(
                    {"data": {"orders": PAGE_ONE_ORDERS}, "links": {"next": link}}
                ).encode(),
            ),
        )
        authority = build_authority(server)
        with build_source(profile, authority) as source, pytest.raises(ConnectorError) as error:
            source.read(read_request(server))
        assert error.value.code == ErrorCode.RESOURCE_MISMATCH
        assert evil.requests == []
        assert len(server.requests) == 1
    finally:
        evil.close()


def test_next_link_pagination_follows_only_same_origin_links(server):
    profile = parse_rest_source_profile(_next_link_profile_data())
    server.route(
        "/v1/accounts/example/orders",
        lambda query: (
            (200, JSON_HEADERS, _page_two_body())
            if query.get("after") == CURSOR_PAGE_TWO
            else (
                200,
                JSON_HEADERS,
                json.dumps(
                    {
                        "data": {"orders": PAGE_ONE_ORDERS},
                        "links": {"next": _page_two_url(server.origin)},
                    }
                ).encode(),
            )
        ),
    )
    authority = build_authority(server)
    with build_source(profile, authority) as source:
        first = source.read(read_request(server))
        assert first.completion == "more"
        second = source.read(
            ReadRequest.model_validate(
                {
                    "context": OperationContext(
                        tenant_id="tenant-a",
                        connector_id="rest-a",
                        actor_id="operator",
                        operation_id="run-b",
                    ),
                    "resource": ResourceSelection(
                        resource_id="orders", schema_fingerprint="a" * 64, source_revision="b" * 64
                    ),
                    "checkpoint": first.checkpoint,
                }
            )
        )
    assert second.completion == "complete"
    assert [record["id"] for record in second.records] == ["o-4"]
    assert all(entry["method"] == "GET" for entry in server.requests)
    assert all(entry["authorization_present"] for entry in server.requests)


# --- Payload bounds survive compression, endlessness and corruption ---


def test_oversized_wire_body_is_capped(server):
    profile = parse_rest_source_profile(_base_profile_data() | {"limits": {"max_wire_bytes": 128}})
    server.route(
        "/v1/accounts/example/orders",
        lambda query: (200, JSON_HEADERS, b"[" + b'"x",' * 200 + b"]"),
    )
    authority = build_authority(server)
    with build_source(profile, authority) as source, pytest.raises(ConnectorError) as error:
        source.read(read_request(server))
    assert error.value.code == ErrorCode.LIMIT_EXCEEDED
    assert source.progress.wire_bytes <= 128


def test_gzip_bomb_is_capped_by_decoded_budget(server):
    profile = parse_rest_source_profile(
        _base_profile_data() | {"limits": {"max_decoded_bytes": 64}}
    )
    gzipped = gzip.compress(b"x" * 8192)
    server.route(
        "/v1/accounts/example/orders",
        lambda query: (200, JSON_HEADERS | {"Content-Encoding": "gzip"}, gzipped),
    )
    authority = build_authority(server)
    with build_source(profile, authority) as source, pytest.raises(ConnectorError) as error:
        source.read(read_request(server))
    assert error.value.code == ErrorCode.LIMIT_EXCEEDED


def test_endless_response_is_capped(server):
    profile = parse_rest_source_profile(_base_profile_data() | {"limits": {"max_wire_bytes": 4096}})
    server.route("/v1/accounts/example/orders", lambda query: (200, JSON_HEADERS, "endless"))
    authority = build_authority(server)
    with build_source(profile, authority) as source, pytest.raises(ConnectorError) as error:
        source.read(read_request(server))
    assert error.value.code == ErrorCode.LIMIT_EXCEEDED
    assert source.progress.wire_bytes == 4096


def test_invalid_json_is_a_fixed_error(server, profile):
    server.route(
        "/v1/accounts/example/orders", lambda query: (200, JSON_HEADERS, b"not json at all")
    )
    authority = build_authority(server)
    with build_source(profile, authority) as source, pytest.raises(ConnectorError) as error:
        source.read(read_request(server))
    assert error.value.code == ErrorCode.RESOURCE_MISMATCH


def test_non_json_constant_is_rejected(server, profile):
    body = b'{"data": {"orders": [{"id": NaN}]}, "next": null}'
    server.route("/v1/accounts/example/orders", lambda query: (200, JSON_HEADERS, body))
    authority = build_authority(server)
    with build_source(profile, authority) as source, pytest.raises(ConnectorError) as error:
        source.read(read_request(server))
    assert error.value.code == ErrorCode.RESOURCE_MISMATCH


def test_wrong_mime_type_is_rejected(server, profile):
    server.route(
        "/v1/accounts/example/orders",
        lambda query: (200, {"Content-Type": "text/plain"}, _page_one_body()),
    )
    authority = build_authority(server)
    with build_source(profile, authority) as source, pytest.raises(ConnectorError) as error:
        source.read(read_request(server))
    assert error.value.code == ErrorCode.RESOURCE_MISMATCH


def test_time_expiry_is_enforced_before_the_transport(server, profile):
    server.route(
        "/v1/accounts/example/orders",
        lambda query: pytest.fail("transport must not be dialed after time expiry"),
    )
    authority = build_authority(server)
    clock = FakeClock(0, 5)
    with build_source(
        profile, authority, clock=clock
    ) as source, pytest.raises(ConnectorError) as error:
        source.read(read_request(server, limits={"time_budget_seconds": 1}))
    assert error.value.code == ErrorCode.TIME_BUDGET_EXCEEDED
    assert server.requests == []


# --- Bounded status handling with retry hints, never retries ---


def test_unauthorized_is_terminal_with_auth_failure_evidence(server, profile):
    server.route(
        "/v1/accounts/example/orders",
        lambda query: (401, JSON_HEADERS, b'{"error": "bad token"}'),
    )
    authority = build_authority(server)
    with build_source(profile, authority) as source, pytest.raises(ConnectorError) as error:
        source.read(read_request(server))
    assert error.value.code == ErrorCode.SOURCE_UNAVAILABLE
    evidence = json.dumps(source.progress.evidence())
    assert source.progress.evidence()["auth_failure"] is True
    assert "bad token" not in evidence
    assert BEARER_SECRET not in evidence
    assert len(server.requests) == 1


@pytest.mark.parametrize(
    ("status", "retry_after", "expected_code", "expected_hint"),
    [
        (429, "12", ErrorCode.RATE_LIMITED, 12),
        (429, "later", ErrorCode.RATE_LIMITED, None),
        (429, "99999", ErrorCode.RATE_LIMITED, None),
        (500, "7", ErrorCode.SOURCE_UNAVAILABLE, 7),
        (503, None, ErrorCode.SOURCE_UNAVAILABLE, None),
        (404, None, ErrorCode.RESOURCE_MISMATCH, None),
    ],
)
def test_failure_statuses_map_to_fixed_codes_with_bounded_hints(
    server, profile, status, retry_after, expected_code, expected_hint
):
    headers = dict(JSON_HEADERS)
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    server.route(
        "/v1/accounts/example/orders", lambda query: (status, headers, b'{"error": "x"}')
    )
    authority = build_authority(server)
    with build_source(profile, authority) as source, pytest.raises(ConnectorError) as error:
        source.read(read_request(server))
    assert error.value.code == expected_code
    assert source.progress.evidence()["retry_after_seconds"] == expected_hint
    assert len(server.requests) == 1  # the adapter itself never retries


# --- Honest truncation and record-shape failures ---


def test_page_exceeding_record_cap_is_truncated_without_checkpoint(server, profile):
    request = read_request(server, limits={"max_records": 2})
    authority = build_authority(server)
    with build_source(profile, authority) as source:
        batch = source.read(request)
    assert batch.completion == "truncated"
    assert batch.records == ()
    assert batch.checkpoint is None


def test_complete_page_without_continuation_is_complete(server, profile):
    body = json.dumps({"data": {"orders": PAGE_ONE_ORDERS}}).encode()
    server.route("/v1/accounts/example/orders", lambda query: (200, JSON_HEADERS, body))
    authority = build_authority(server)
    with build_source(profile, authority) as source:
        batch = source.read(read_request(server))
    assert batch.completion == "complete"
    assert batch.checkpoint is None


def test_oversized_single_record_is_record_too_large(server, profile):
    server.route(
        "/v1/accounts/example/orders",
        lambda query: (
            200,
            JSON_HEADERS,
            json.dumps({"data": {"orders": [{"blob": "y" * 4096}]}}).encode(),
        ),
    )
    request = read_request(server, limits={"max_bytes": 512})
    authority = build_authority(server)
    with build_source(profile, authority) as source, pytest.raises(ConnectorError) as error:
        source.read(request)
    assert error.value.code == ErrorCode.RECORD_TOO_LARGE


@pytest.mark.parametrize(
    "body",
    [
        b'{"data": {"orders": {"id": 1}}}',
        b'{"data": {"orders": ["not-an-object"]}}',
        b'{"data": {"orders": 7}}',
        b'{"unexpected": []}',
        b"[1, 2, 3]",
    ],
)
def test_unexpected_document_shapes_are_fixed_errors(server, profile, body):
    server.route("/v1/accounts/example/orders", lambda query: (200, JSON_HEADERS, body))
    authority = build_authority(server)
    with build_source(profile, authority) as source, pytest.raises(ConnectorError) as error:
        source.read(read_request(server))
    assert error.value.code == ErrorCode.RESOURCE_MISMATCH


def test_non_string_continuation_is_rejected(server, profile):
    body = json.dumps({"data": {"orders": PAGE_ONE_ORDERS}, "next": 7}).encode()
    server.route("/v1/accounts/example/orders", lambda query: (200, JSON_HEADERS, body))
    authority = build_authority(server)
    with build_source(profile, authority) as source, pytest.raises(ConnectorError) as error:
        source.read(read_request(server))
    assert error.value.code == ErrorCode.RESOURCE_MISMATCH


# --- No authorization header, token, cursor or row values leak ---


def test_derived_surfaces_never_contain_secrets_or_rows(server, profile):
    authority = build_authority(server)
    with build_source(profile, authority) as source:
        batch = source.read(read_request(server))
    evidence = json.dumps(source.progress.evidence())
    assert BEARER_SECRET not in evidence
    assert CURSOR_PAGE_TWO not in evidence
    assert "o-1" not in evidence
    assert "Authorization" not in evidence
    batch_evidence = json.dumps(batch.evidence().model_dump())
    assert CURSOR_PAGE_TWO not in batch_evidence
    assert BEARER_SECRET not in batch_evidence
    assert BEARER_SECRET not in repr(source)


def test_credentials_reach_only_the_approved_origin(server, profile):
    authority = build_authority(server)
    with build_source(profile, authority) as source:
        source.read(read_request(server))
    assert len(server.requests) == 1
    assert server.requests[0]["method"] == "GET"
    assert server.requests[0]["authorization_present"] is True


def test_blocked_continuation_never_dials_a_second_destination(server):
    profile = parse_rest_source_profile(_next_link_profile_data())
    server.route(
        "/v1/accounts/example/orders",
        lambda query: (
            200,
            JSON_HEADERS,
            json.dumps(
                {
                    "data": {"orders": PAGE_ONE_ORDERS},
                    "links": {"next": "ftp://127.0.0.1/next"},
                }
            ).encode(),
        ),
    )
    authority = build_authority(server)
    with build_source(profile, authority) as source, pytest.raises(ConnectorError):
        source.read(read_request(server))
    assert len(server.requests) == 1
    assert server.requests[0]["authorization_present"] is True
