"""Fake Microsoft Graph provider tests for the bounded M365 discovery adapter."""

import contextlib
import gzip
import hashlib
import json
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest
from axis_sdk.connector_authoring.contracts import (
    ConnectorError,
    ErrorCode,
    OperationContext,
)
from pydantic import SecretStr, ValidationError

from axis_api.connector_m365_discovery import (
    M365LibraryDiscovery,
    M365LibrarySelection,
    M365SetupState,
    M365SourceAuthority,
)

BEARER = "m365-bearer-secret-fixture"
PROFILE_MODE = "selected_resource_grant"
TENANT = "12345678-1234-1234-1234-123456789012"
DRIVE = "drive-1"

ITEM_USER_FILE = {
    "id": "item-1",
    "name": "quarterly-report-sentinel.docx",
    "eTag": "etag-1",
    "cTag": "ctag-1",
    "file": {"mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    "parentReference": {"id": "root"},
}
ITEM_GROUP_FILE = {
    "id": "item-2",
    "name": "team-notes.txt",
    "eTag": "etag-2",
    "file": {"mimeType": "text/plain"},
    "parentReference": {"id": "root"},
}
ITEM_APP_FILE = {
    "id": "item-3",
    "name": "service-only.pdf",
    "eTag": "etag-3",
    "file": {"mimeType": "application/pdf"},
    "parentReference": {"id": "root"},
}
ITEM_LINK_FILE = {
    "id": "item-4",
    "name": "org-wide.xlsx",
    "eTag": "etag-4",
    "file": {"mimeType": "application/vnd.ms-excel"},
    "parentReference": {"id": "root"},
}
ITEM_FOLDER = {
    "id": "folder-1",
    "name": "shared-folder",
    "eTag": "etag-f",
    "folder": {"childCount": 0},
    "parentReference": {"id": "root"},
}


def _user_permission(user_id, *, inherited=None):
    permission = {"id": "perm-user", "grantedToV2": {"user": {"id": user_id}}, "roles": ["read"]}
    if inherited:
        permission["inheritedFrom"] = {"id": inherited, "path": "/drive/root:/x"}
    return permission


def _group_permission(group_id):
    return {"id": "perm-group", "grantedToV2": {"group": {"id": group_id}}, "roles": ["read"]}


def _app_permission():
    return {
        "id": "perm-app",
        "grantedToV2": {"application": {"id": "svc-principal"}},
        "roles": ["full"],
    }


def _org_link_permission():
    return {"id": "perm-link", "link": {"scope": "organization", "type": "edit"}, "shareId": "s-id"}


def _permissions_for(item_id):
    if item_id == ITEM_USER_FILE["id"]:
        return [_user_permission("user-a")]
    if item_id == ITEM_GROUP_FILE["id"]:
        return [_user_permission("user-b"), _group_permission("group-a")]
    if item_id == ITEM_APP_FILE["id"]:
        return [_app_permission()]
    if item_id == ITEM_LINK_FILE["id"]:
        return [_org_link_permission()]
    return []


class GraphFixture:
    """Loopback Graph provider recording request paths; JSON and raw routes."""

    def __init__(self):
        self.routes: dict[str, object] = {}
        self.raw_routes: dict[str, object] = {}
        self.requests: list[str] = []
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                fixture.serve(self)

            def log_message(self, *args) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def origin(self) -> tuple[str, str, int]:
        return ("http", "127.0.0.1", self.server.server_address[1])

    def route(self, path: str, handler) -> None:
        self.routes[path] = handler

    def raw_route(self, path: str, handler) -> None:
        self.raw_routes[path] = handler

    def serve(self, handler) -> None:
        path = urlsplit(handler.path).path
        self.requests.append(path)
        raw = self.raw_routes.get(path)
        if raw is not None:
            raw(handler)
            return
        route = self.routes.get(path)
        if route is None:
            _send_json(
                handler, 404, {"error": {"code": "itemNotFound", "message": "internal detail"}}
            )
            return
        status, payload = route(urlsplit(handler.path).query)
        _send_json(handler, status, payload)

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def _send_json(handler, status, payload):
    body = json.dumps(payload).encode()
    _send_raw(handler, status=status, headers={"Content-Type": "application/json"}, body=body)


def _send_raw(handler, *, status=200, headers=None, body=b""):
    handler.send_response(status)
    for name, value in (headers or {}).items():
        handler.send_header(name, value)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    with contextlib.suppress(BrokenPipeError, ConnectionResetError):
        handler.wfile.write(body)


def _children_payload(*items, next_url=None):
    payload = {"value": list(items)}
    if next_url:
        payload["@odata.nextLink"] = next_url
    return payload


def _page_url(server, path):
    return f"http://127.0.0.1:{server.origin[2]}{path}"


def _install_library(server, items):
    server.route(
        f"/v1.0/drives/{DRIVE}/root/children",
        lambda query: (200, _children_payload(*items)),
    )
    for item in items:
        server.route(
            f"/v1.0/drives/{DRIVE}/items/{item['id']}/permissions",
            lambda query, item_id=item["id"]: (200, {"value": _permissions_for(item_id)}),
        )


@pytest.fixture
def server():
    server = GraphFixture()
    _install_library(server, (ITEM_USER_FILE, ITEM_GROUP_FILE, ITEM_FOLDER))
    yield server
    server.close()


def build_selection(**overrides):
    return M365LibrarySelection.model_validate(
        {
            "tenant_id": "tenant-a",
            "connector_id": "m365-docs",
            "org_tenant_id": TENANT,
            "site_id": "site-1",
            "drive_id": DRIVE,
            "permission_mode": PROFILE_MODE,
        }
        | overrides
    )


def build_authority(server, **overrides):
    origin = server.origin
    return M365SourceAuthority.model_validate(
        {
            "tenant_id": "tenant-a",
            "connector_id": "m365-docs",
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
            "permission_mode": PROFILE_MODE,
        }
        | overrides
    )


def build_discovery(server, selection=None, authority=None):
    return M365LibraryDiscovery(
        selection=selection or build_selection(),
        authority=authority or build_authority(server),
        credential_bearer=SecretStr(BEARER),
    )


def context():
    return OperationContext(
        tenant_id="tenant-a",
        connector_id="m365-docs",
        actor_id="operator",
        operation_id="run-1",
    )


# --- One allowed library, bounded metadata, explicit truncation ---


def test_enumerates_only_the_selected_library_with_bounded_metadata(server):
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())

    assert outcome.setup_state == M365SetupState.READY
    assert not outcome.truncated
    names = [item.snapshot.display_name for item in outcome.items]
    assert "quarterly-report-sentinel.docx" in names
    assert all(item.identity.container_id == DRIVE for item in outcome.items)
    assert all(item.identity.account_id == TENANT for item in outcome.items)
    assert server.requests
    assert all(path.startswith(f"/v1.0/drives/{DRIVE}/") for path in server.requests)
    evidence = outcome.evidence()
    assert "quarterly-report-sentinel" not in json.dumps(evidence)
    assert evidence["item_count"] == 3
    assert evidence["file_count"] == 2
    assert evidence["folder_count"] == 1
    assert evidence["permission_surface_available"] is True


def test_operator_item_cap_reports_explicit_truncation(server):
    items = [
        {
            "id": f"item-{index}",
            "name": f"doc-{index}.txt",
            "eTag": f"etag-{index}",
            "file": {"mimeType": "text/plain"},
            "parentReference": {"id": "root"},
        }
        for index in range(6)
    ]
    _install_library(server, items)
    selection = build_selection(max_items=4, max_pages=5)
    with build_discovery(server, selection=selection) as discovery:
        outcome = discovery.discover(context())
    assert outcome.setup_state == M365SetupState.READY
    assert outcome.truncated is True
    assert outcome.evidence()["item_count"] == 4


def test_page_cap_exhausted_with_pending_next_link_is_truncated(server):
    next_url = _page_url(server, f"/v1.0/drives/{DRIVE}/root/children?page=2")
    server.route(
        f"/v1.0/drives/{DRIVE}/root/children",
        lambda query: (200, _children_payload(ITEM_USER_FILE, next_url=next_url)),
    )
    selection = build_selection(max_pages=1)
    with build_discovery(server, selection=selection) as discovery:
        outcome = discovery.discover(context())
    assert outcome.setup_state == M365SetupState.READY
    assert outcome.truncated is True
    assert outcome.evidence()["item_count"] == 1


def test_follows_next_link_inside_the_selected_scope(server):
    second_page = _page_url(server, f"/v1.0/drives/{DRIVE}/root/children?page=2")

    def children(query):
        if parse_qs(query).get("page") == ["2"]:
            return 200, _children_payload(ITEM_FOLDER)
        return 200, _children_payload(ITEM_USER_FILE, next_url=second_page)

    server.route(f"/v1.0/drives/{DRIVE}/root/children", children)
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    assert outcome.setup_state == M365SetupState.READY
    assert not outcome.truncated
    assert outcome.evidence()["item_count"] == 2


# --- Distinct safe setup states; no auto-escalation ---


def test_insufficient_consent_on_enumeration_is_a_distinct_state(server):
    server.route(
        f"/v1.0/drives/{DRIVE}/root/children",
        lambda query: (403, {"error": {"code": "consentRequired", "message": "internal detail"}}),
    )
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    assert outcome.setup_state == M365SetupState.INSUFFICIENT_CONSENT
    assert outcome.items == ()
    assert "internal detail" not in json.dumps(outcome.evidence())


def test_missing_selected_resource_grant_is_distinct_from_consent(server):
    server.route(
        f"/v1.0/drives/{DRIVE}/root/children",
        lambda query: (403, {"error": {"code": "accessDenied", "message": "internal detail"}}),
    )
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    assert outcome.setup_state == M365SetupState.MISSING_SELECTED_RESOURCE_GRANT

    with build_discovery(
        server,
        selection=build_selection(permission_mode="application_consent"),
        authority=build_authority(server, permission_mode="application_consent"),
    ) as discovery:
        application_outcome = discovery.discover(context())
    assert application_outcome.setup_state == M365SetupState.INSUFFICIENT_CONSENT


def test_token_rejected_and_not_found_are_distinct_states(server):
    server.route(
        f"/v1.0/drives/{DRIVE}/root/children",
        lambda query: (
            401,
            {"error": {"code": "InvalidAuthenticationToken", "message": "internal"}},
        ),
    )
    with build_discovery(server) as discovery:
        assert discovery.discover(context()).setup_state == M365SetupState.TOKEN_REJECTED

    server.route(
        f"/v1.0/drives/{DRIVE}/root/children",
        lambda query: (404, {"error": {"code": "itemNotFound", "message": "internal"}}),
    )
    with build_discovery(server) as discovery:
        assert (
            discovery.discover(context()).setup_state == M365SetupState.SELECTED_RESOURCE_NOT_FOUND
        )


def test_unsupported_permission_surface_is_a_distinct_state(server):
    server.route(
        f"/v1.0/drives/{DRIVE}/items/item-1/permissions",
        lambda query: (400, {"error": {"code": "invalidRequest", "message": "internal"}}),
    )
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    assert outcome.setup_state == M365SetupState.UNSUPPORTED_PERMISSION_MODE
    assert outcome.items == ()


def test_unreachable_graph_is_a_safe_state(server):
    server.route(
        f"/v1.0/drives/{DRIVE}/root/children",
        lambda query: (503, {"error": {"code": "serviceUnavailable", "message": "internal"}}),
    )
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    assert outcome.setup_state == M365SetupState.SOURCE_UNREACHABLE
    assert outcome.items == ()


def test_permission_surface_blocked_for_mode_leaves_unavailable_evidence(server):
    server.route(
        f"/v1.0/drives/{DRIVE}/items/item-1/permissions",
        lambda query: (403, {"error": {"code": "accessDenied", "message": "internal"}}),
    )
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    assert outcome.setup_state == M365SetupState.READY
    item = next(o for o in outcome.items if o.identity.item_id == "item-1")
    assert item.snapshot.acl.completeness == "unavailable"
    assert item.snapshot.acl.grants == ()
    assert outcome.permission_surface_available is False
    assert outcome.evidence()["acl_unavailable_count"] == 1


# --- Grant normalization without universal authorization ---


def test_direct_inherited_user_and_group_grants_are_normalized(server):
    server.route(
        f"/v1.0/drives/{DRIVE}/items/item-1/permissions",
        lambda query: (
            200,
            {
                "value": [
                    _user_permission("user-a"),
                    _user_permission("user-b", inherited="folder-9"),
                    _group_permission("group-a"),
                ]
            },
        ),
    )
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    item = next(o for o in outcome.items if o.identity.item_id == "item-1")
    assert item.snapshot.acl.completeness == "complete"
    kinds = {
        (grant.principal_kind, grant.inherited_from_item_id) for grant in item.snapshot.acl.grants
    }
    assert ("user", None) in kinds
    assert ("user", "folder-9") in kinds
    assert ("group", None) in kinds
    assert all(grant.source_account_id == TENANT for grant in item.snapshot.acl.grants)
    assert all(grant.mapping_ref is None for grant in item.snapshot.acl.grants)


def test_application_principal_and_organizational_link_stay_unreadable(server):
    _install_library(
        server, (ITEM_USER_FILE, ITEM_GROUP_FILE, ITEM_APP_FILE, ITEM_LINK_FILE, ITEM_FOLDER)
    )
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())

    app_item = next(o for o in outcome.items if o.identity.item_id == "item-3")
    assert app_item.snapshot.acl.completeness == "partial"
    assert app_item.snapshot.acl.grants == ()
    link_item = next(o for o in outcome.items if o.identity.item_id == "item-4")
    assert link_item.snapshot.acl.completeness == "complete"
    assert [grant.principal_kind for grant in link_item.snapshot.acl.grants] == ["domain"]
    # Link and application evidence is never a universal end-user entitlement.
    now = datetime.now(UTC)
    assert not app_item.snapshot.acl.ready_for_authorization(now)
    assert not link_item.snapshot.acl.ready_for_authorization(now)


def test_every_observation_is_non_readable_evidence_for_the_trust_layer(server):
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    now = datetime.now(UTC)
    for item in outcome.items:
        assert item.snapshot.acl.ready_for_authorization(now) is False


# --- Failed gates: zero transport, zero leakage ---


def test_expired_lease_produces_zero_calls(server):
    authority = build_authority(server, lease_expires_at=datetime.now(UTC) - timedelta(seconds=1))
    with (
        build_discovery(server, authority=authority) as discovery,
        pytest.raises(ConnectorError) as error,
    ):
        discovery.discover(context())
    assert error.value.code == ErrorCode.CONTEXT_MISMATCH
    assert server.requests == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"lease_status": "lease_revoked"},
        {"lease_secret_material_returned": "true"},
        {"egress_mode": "approved_public_endpoint"},
        {"egress_endpoint_target_sha256": "f" * 64},
        {"permission_mode": "user_delegated_site"},
        {"pinned_origin": ("https", "graph.microsoft.com", 443)},
    ],
)
def test_invalid_authority_fails_closed_before_io(server, overrides):
    with pytest.raises(ValidationError):
        build_authority(server, **overrides)
    assert server.requests == []


def test_permission_mode_mismatch_between_selection_and_authority_is_rejected(server):
    with pytest.raises(ConnectorError) as error:
        build_discovery(
            server,
            selection=build_selection(permission_mode=PROFILE_MODE),
            authority=build_authority(server, permission_mode="application_consent"),
        )
    assert error.value.code == ErrorCode.RESOURCE_MISMATCH
    assert server.requests == []


def test_wrong_tenant_context_is_rejected_without_io(server):
    request = OperationContext(
        tenant_id="tenant-b",
        connector_id="m365-docs",
        actor_id="operator",
        operation_id="run-1",
    )
    with build_discovery(server) as discovery, pytest.raises(ConnectorError) as error:
        discovery.discover(request)
    assert error.value.code == ErrorCode.CONTEXT_MISMATCH
    assert server.requests == []


def test_scope_escaping_continuation_is_never_dialed(server):
    evil = GraphFixture()
    try:
        escaped = f"http://127.0.0.1:{evil.origin[2]}/v1.0/drives/{DRIVE}/root/children"
        server.route(
            f"/v1.0/drives/{DRIVE}/root/children",
            lambda query: (200, _children_payload(ITEM_USER_FILE, next_url=escaped)),
        )
        with build_discovery(server) as discovery, pytest.raises(ConnectorError) as error:
            discovery.discover(context())
        assert error.value.code == ErrorCode.RESOURCE_MISMATCH
        assert evil.requests == []
    finally:
        evil.close()


def test_continuation_outside_the_selected_drive_is_never_dialed(server):
    other_drive = _page_url(server, "/v1.0/drives/other-drive/root/children")
    server.route(
        f"/v1.0/drives/{DRIVE}/root/children",
        lambda query: (200, _children_payload(ITEM_USER_FILE, next_url=other_drive)),
    )
    with build_discovery(server) as discovery, pytest.raises(ConnectorError) as error:
        discovery.discover(context())
    assert error.value.code == ErrorCode.RESOURCE_MISMATCH
    assert all("/drives/other-drive/" not in path for path in server.requests)


def test_non_json_body_is_a_fixed_error(server):
    server.raw_route(
        f"/v1.0/drives/{DRIVE}/root/children",
        lambda handler: _send_raw(
            handler, headers={"Content-Type": "text/plain"}, body=b"not json"
        ),
    )
    with build_discovery(server) as discovery, pytest.raises(ConnectorError) as error:
        discovery.discover(context())
    assert error.value.code == ErrorCode.RESOURCE_MISMATCH


def test_gzip_bomb_is_capped(server):
    bomb = gzip.compress(b"x" * (12 * 1024 * 1024))
    server.raw_route(
        f"/v1.0/drives/{DRIVE}/root/children",
        lambda handler: _send_raw(
            handler,
            headers={"Content-Type": "application/json", "Content-Encoding": "gzip"},
            body=bomb,
        ),
    )
    with build_discovery(server) as discovery, pytest.raises(ConnectorError) as error:
        discovery.discover(context())
    assert error.value.code == ErrorCode.LIMIT_EXCEEDED


def test_error_bodies_and_bearer_never_reach_evidence(server):
    server.route(
        f"/v1.0/drives/{DRIVE}/root/children",
        lambda query: (403, {"error": {"code": "accessDenied", "message": "tenant secret detail"}}),
    )
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    serialized = json.dumps(outcome.evidence())
    assert "tenant secret detail" not in serialized
    assert BEARER not in serialized
    assert "accessDenied" not in serialized
    assert BEARER not in repr(discovery)
