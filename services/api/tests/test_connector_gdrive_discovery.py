"""Fake Google Drive provider tests for the bounded Drive discovery adapter."""

import contextlib
import gzip
import hashlib
import json
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlsplit

import pytest
from axis_sdk.connector_authoring.contracts import (
    ConnectorError,
    ErrorCode,
    OperationContext,
)
from pydantic import SecretStr, ValidationError

from axis_api.connector_gdrive_discovery import (
    GDriveCorpusDiscovery,
    GDriveSelection,
    GDriveSetupState,
    GDriveSourceAuthority,
)

BEARER = "gdrive-bearer-secret-fixture"
CREDENTIAL_MODE = "selected_resource_grant"
TENANT = "tenant-a"
DRIVE = "1AbCdEfGhIjKlMnOpQrStUv"  # shared-drive-shaped ID, distinct from any item ID
ROOT = "1RootZxYwVuTsRqPoNmLkJi"
ACCOUNT = "docs-bot@tenant-projects.iam.gserviceaccount.com"

FILE_IN_SCOPE = {
    "id": "1FileAAaaAAaaAAaaAAaaAA",
    "name": "quarterly-report-sentinel.docx",
    "mimeType": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
    "parentReference": {"id": ROOT, "driveId": DRIVE},
    "version": "17",
}
FOLDER_IN_SCOPE = {
    "id": "1FoldBBbbBBbbBBbbBBbbBB",
    "name": "shared-folder",
    "mimeType": "application/vnd.google-apps.folder",
    "parentReference": {"id": ROOT, "driveId": DRIVE},
    "version": "3",
}
SHORTCUT_IN_SCOPE = {
    "id": "1ShrtCCccCCccCCccCCccCC",
    "name": "pointer-to-folder",
    "mimeType": "application/vnd.google-apps.shortcut",
    "parentReference": {"id": ROOT, "driveId": DRIVE},
    "version": "1",
    "shortcutDetails": {"targetId": FOLDER_IN_SCOPE["id"], "targetMimeType": "folder"},
}
SHORTCUT_OUT_OF_SCOPE = {
    "id": "1ShrtDDddDDddDDddDDddDD",
    "name": "pointer-elsewhere",
    "mimeType": "application/vnd.google-apps.shortcut",
    "parentReference": {"id": ROOT, "driveId": DRIVE},
    "version": "1",
    "shortcutDetails": {"targetId": "1TgtEEEEEEEEEEEEEEEEEEEE", "targetMimeType": "folder"},
}
SAME_ID_IN_MY_DRIVE = {
    # AC 1: My Drive and shared-drive identities stay distinct even when the
    # local item identifiers collide.
    "id": FILE_IN_SCOPE["id"],
    "name": "my-drive-twin.txt",
    "mimeType": "text/plain",
    "parentReference": {"id": ROOT},
    "version": "2",
}


def _user_permission(user_email, *, permission_id="perm-user-1"):
    return {
        "id": permission_id,
        "type": "user",
        "emailAddress": user_email,
        "role": "reader",
    }


def _group_permission(group_email):
    return {
        "id": "perm-group-1",
        "type": "group",
        "emailAddress": group_email,
        "role": "reader",
    }


def _domain_permission(domain):
    return {"id": "perm-domain-1", "type": "domain", "domain": domain, "role": "reader"}


def _anyone_with_link_permission():
    return {"id": "perm-link-1", "type": "anyoneWithLink", "role": "reader"}


def _unknown_shape_permission():
    return {"id": "perm-unknown-1", "type": "futurePrincipalType", "role": "reader"}


_PERMISSIONS = {
    FILE_IN_SCOPE["id"]: [
        _user_permission("user.a@example.com"),
        _group_permission("eng@example.com"),
    ],
    FOLDER_IN_SCOPE["id"]: [_domain_permission("example.com")],
    SHORTCUT_IN_SCOPE["id"]: [_anyone_with_link_permission()],
    SHORTCUT_OUT_OF_SCOPE["id"]: [_unknown_shape_permission()],
}


class DriveFixture:
    """Loopback Drive provider recording request paths; JSON and raw routes."""

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
        self.requests.append(handler.path)
        raw = self.raw_routes.get(path)
        if raw is not None:
            raw(handler)
            return
        route = self.routes.get(path)
        if route is None:
            _send_json(handler, 404, {"error": {"code": 404, "message": "internal detail"}})
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


def _files_payload(*items, next_token=None):
    payload = {"files": list(items), "kind": "drive#fileList"}
    if next_token:
        payload["nextPageToken"] = next_token
    return payload


def _install_drive(server, items, *, drive_id=DRIVE, root=ROOT, permissions=None):
    table = _PERMISSIONS if permissions is None else permissions
    server.route(
        "/drive/v3/files",
        lambda q: (200, _files_payload(*items)),
    )
    for item in items:
        server.route(
            f"/drive/v3/files/{item['id']}/permissions",
            lambda q, item_id=item["id"]: (200, {"permissions": table.get(item_id, [])}),
        )


def _assert_selection_params(server, drive_kind="shared_drive"):
    """Capture the first files.list query for scope-parameter assertions."""

    captured = {}
    original = server.routes.get("/drive/v3/files")

    def capture(query):
        captured.update(parse_qs(query))
        return original(query)

    server.routes["/drive/v3/files"] = capture
    return captured


@pytest.fixture
def server():
    server = DriveFixture()
    _install_drive(
        server,
        (FILE_IN_SCOPE, FOLDER_IN_SCOPE, SHORTCUT_IN_SCOPE, SHORTCUT_OUT_OF_SCOPE),
    )
    yield server
    server.close()


def build_selection(**overrides):
    return GDriveSelection.model_validate(
        {
            "tenant_id": TENANT,
            "connector_id": "gdrive-docs",
            "provider_account_id": ACCOUNT,
            "credential_mode": CREDENTIAL_MODE,
            "drive_kind": "shared_drive",
            "drive_id": DRIVE,
            "root_item_id": ROOT,
        }
        | overrides
    )


def build_authority(server, **overrides):
    origin = server.origin
    return GDriveSourceAuthority.model_validate(
        {
            "tenant_id": TENANT,
            "connector_id": "gdrive-docs",
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
            "credential_mode": CREDENTIAL_MODE,
        }
        | overrides
    )


def build_discovery(server, selection=None, authority=None):
    return GDriveCorpusDiscovery(
        selection=selection or build_selection(),
        authority=authority or build_authority(server),
        credential_bearer=SecretStr(BEARER),
    )


def context():
    return OperationContext(
        tenant_id=TENANT,
        connector_id="gdrive-docs",
        actor_id="operator",
        operation_id="run-1",
    )


def item_by_id(outcome, item_id):
    return next(o for o in outcome.items if o.identity.item_id == item_id)


# --- AC 1: My Drive vs shared drive identity; explicit scope parameters ---


def test_shared_drive_selection_pins_the_drive_scoped_query(server):
    captured = _assert_selection_params(server)
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    assert outcome.setup_state == GDriveSetupState.READY
    assert captured["corpora"] == ["drive"]
    assert captured["driveId"] == [DRIVE]
    assert captured["includeItemsFromAllDrives"] == ["true"]
    assert captured["supportsAllDrives"] == ["true"]


def test_my_drive_selection_omits_shared_drive_parameters(server):
    server.routes.clear()
    _install_drive(server, (SAME_ID_IN_MY_DRIVE,))
    captured = _assert_selection_params(server)
    selection = build_selection(drive_kind="my_drive")
    with build_discovery(server, selection=selection) as discovery:
        outcome = discovery.discover(context())
    assert outcome.setup_state == GDriveSetupState.READY
    assert "corpora" not in captured
    assert "driveId" not in captured
    # AC 1: the same local item identifier under a different drive kind is a
    # different #863 identity.
    item = item_by_id(outcome, SAME_ID_IN_MY_DRIVE["id"])
    assert item.identity.container_id == DRIVE
    assert item.identity.account_id == ACCOUNT
    assert item.snapshot.display_name == "my-drive-twin.txt"


def test_my_drive_and_shared_drive_fixtures_do_not_merge(server):
    shared_outcome = _discover(server)
    my_drive_id = "1MyDaaaaaaaaaaaaaaaDrive"
    server.routes.clear()
    _install_drive(server, (SAME_ID_IN_MY_DRIVE,))
    selection = build_selection(drive_kind="my_drive", drive_id=my_drive_id)
    my_drive_outcome = _discover(server, selection)
    shared_item = item_by_id(shared_outcome, FILE_IN_SCOPE["id"])
    my_drive_item = item_by_id(my_drive_outcome, SAME_ID_IN_MY_DRIVE["id"])
    # AC 1: the same local item identifier under a different drive is a
    # different #863 identity; the two fixtures never merge.
    assert shared_item.identity.container_id == DRIVE
    assert my_drive_item.identity.container_id == my_drive_id
    assert shared_item.snapshot.display_name != my_drive_item.snapshot.display_name


# --- AC 2: bounded listing inside the approved root; explicit truncation ---


def test_listing_stays_inside_the_approved_root(server):
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    assert outcome.setup_state == GDriveSetupState.READY
    assert all("/drive/v3/files" in path for path in server.requests)
    listing_queries = [
        urlsplit(path).query
        for path in server.requests
        if urlsplit(path).path == "/drive/v3/files"
    ]
    assert listing_queries
    assert all(quote(f"'{ROOT}' in parents", safe="") in query for query in listing_queries)
    assert all(item.identity.container_id == DRIVE for item in outcome.items)


def test_operator_item_cap_reports_explicit_truncation(server):
    items = [
        {
            "id": f"1Cap{i:016d}xxxxxx",
            "name": f"doc-{i}.txt",
            "mimeType": "text/plain",
            "parentReference": {"id": ROOT, "driveId": DRIVE},
            "version": str(i),
        }
        for i in range(6)
    ]
    server.routes.clear()
    _install_drive(server, items)
    selection = build_selection(max_items=4, max_pages=5)
    with build_discovery(server, selection=selection) as discovery:
        outcome = discovery.discover(context())
    assert outcome.setup_state == GDriveSetupState.READY
    assert outcome.truncated is True
    assert outcome.evidence()["item_count"] == 4


def test_page_cap_exhausted_with_pending_token_is_truncated(server):
    server.routes.clear()
    _install_drive(server, (FILE_IN_SCOPE,))
    original = server.routes["/drive/v3/files"]
    server.routes["/drive/v3/files"] = lambda q: (
        (200, _files_payload(FILE_IN_SCOPE, next_token="page-2-token"))
        if parse_qs(q).get("pageToken") != ["page-2-token"]
        else original(q)
    )
    selection = build_selection(max_pages=1)
    with build_discovery(server, selection=selection) as discovery:
        outcome = discovery.discover(context())
    assert outcome.setup_state == GDriveSetupState.READY
    assert outcome.truncated is True
    assert outcome.evidence()["item_count"] == 1


def test_follows_page_tokens_inside_the_same_scope(server):
    server.routes.clear()
    _install_drive(server, (FILE_IN_SCOPE, FOLDER_IN_SCOPE))

    def listing(query):
        if parse_qs(query).get("pageToken") == ["page-2-token"]:
            return 200, _files_payload(FOLDER_IN_SCOPE)
        return 200, _files_payload(FILE_IN_SCOPE, next_token="page-2-token")

    server.routes["/drive/v3/files"] = listing
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    assert outcome.setup_state == GDriveSetupState.READY
    assert not outcome.truncated
    assert outcome.evidence()["item_count"] == 2
    assert all("/drive/v3/files" in path for path in server.requests)


def test_malformed_page_token_is_a_fixed_error_never_a_fetch(server):
    server.routes.clear()
    _install_drive(server, (FILE_IN_SCOPE,))

    def listing(query):
        if parse_qs(query).get("pageToken") == ["bad token"]:
            return 200, _files_payload(FOLDER_IN_SCOPE)
        return 200, _files_payload(FILE_IN_SCOPE, next_token="bad token")

    server.routes["/drive/v3/files"] = listing
    with build_discovery(server) as discovery, pytest.raises(ConnectorError) as error:
        discovery.discover(context())
    assert error.value.code == ErrorCode.RESOURCE_MISMATCH
    assert all("bad+token" not in path for path in server.requests)


def test_truncation_never_implies_deletion(server):
    # The outcome carries no tombstones: a bounded enumeration reports
    # truncation, never a removal basis.
    items = [
        {
            "id": f"1Tru{i:016d}xxxxxx",
            "name": f"doc-{i}.txt",
            "mimeType": "text/plain",
            "parentReference": {"id": ROOT, "driveId": DRIVE},
            "version": str(i),
        }
        for i in range(3)
    ]
    server.routes.clear()
    _install_drive(server, items)
    selection = build_selection(max_items=1)
    with build_discovery(server, selection=selection) as discovery:
        outcome = discovery.discover(context())
    assert outcome.truncated is True
    assert all(item.snapshot is not None for item in outcome.items)


# --- AC 3: supported grants normalized; link/domain never Axis entitlements ---


def test_direct_user_and_group_grants_are_normalized(server):
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    item = item_by_id(outcome, FILE_IN_SCOPE["id"])
    assert item.snapshot.acl.completeness == "complete"
    kinds = {grant.principal_kind for grant in item.snapshot.acl.grants}
    assert kinds == {"user", "group"}
    assert all(grant.source_account_id == ACCOUNT for grant in item.snapshot.acl.grants)
    assert all(grant.mapping_ref is None for grant in item.snapshot.acl.grants)


def test_domain_and_link_access_stays_non_authorizing(server):
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    folder = item_by_id(outcome, FOLDER_IN_SCOPE["id"])
    assert [grant.principal_kind for grant in folder.snapshot.acl.grants] == ["domain"]
    shortcut = item_by_id(outcome, SHORTCUT_IN_SCOPE["id"])
    assert [grant.principal_kind for grant in shortcut.snapshot.acl.grants] == ["link"]
    now = datetime.now(UTC)
    # Link and domain evidence is never a universal end-user entitlement.
    assert not folder.snapshot.acl.ready_for_authorization(now)
    assert not shortcut.snapshot.acl.ready_for_authorization(now)


def test_every_observation_is_non_readable_evidence_for_the_trust_layer(server):
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    now = datetime.now(UTC)
    for item in outcome.items:
        assert item.snapshot.acl.ready_for_authorization(now) is False


def test_unknown_permission_shapes_leave_the_observation_partial(server):
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    item = item_by_id(outcome, SHORTCUT_OUT_OF_SCOPE["id"])
    assert item.snapshot.acl.completeness == "partial"
    assert item.snapshot.acl.grants == ()


def test_group_membership_is_never_resolved_by_the_adapter(server):
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    item = item_by_id(outcome, FILE_IN_SCOPE["id"])
    group_grants = [g for g in item.snapshot.acl.grants if g.principal_kind == "group"]
    assert len(group_grants) == 1
    assert group_grants[0].principal_id == "eng@example.com"
    assert group_grants[0].mapping_ref is None


def test_permission_page_cap_marks_evidence_partial(server):
    server.routes.clear()
    _install_drive(server, (FILE_IN_SCOPE,))
    pages = [[_user_permission(f"user.{i}@example.com")] for i in range(3)]
    original = server.routes[f"/drive/v3/files/{FILE_IN_SCOPE['id']}/permissions"]
    server.routes[f"/drive/v3/files/{FILE_IN_SCOPE['id']}/permissions"] = lambda q: (
        (200, {"permissions": pages[1], "nextPageToken": "perm-page-2"})
        if parse_qs(q).get("pageToken") == ["perm-page-2"]
        else (200, {"permissions": pages[0], "nextPageToken": "perm-page-2"})
    ) if False else original(q)
    server.routes[f"/drive/v3/files/{FILE_IN_SCOPE['id']}/permissions"] = lambda q: (
        (200, {"permissions": pages[0], "nextPageToken": "perm-page-2"})
        if parse_qs(q).get("pageToken") != ["perm-page-2"]
        else (200, {"permissions": pages[1], "nextPageToken": "perm-page-3"})
    )
    # Third page never arrives within the page cap: evidence stays partial.
    selection = build_selection(max_pages=2)
    with build_discovery(server, selection=selection) as discovery:
        outcome = discovery.discover(context())
    item = item_by_id(outcome, FILE_IN_SCOPE["id"])
    assert item.snapshot.acl.completeness == "partial"


# --- AC 4: shortcuts and binding overrides ---


def test_shortcut_target_is_preserved_but_never_fetched(server):
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    shortcut = item_by_id(outcome, SHORTCUT_OUT_OF_SCOPE["id"])
    assert shortcut.snapshot.handling_refs == ("gdrive-shortcut:1TgtEEEEEEEEEEEEEEEEEEEE",)
    # The out-of-scope target ID never appears as a fetched item.
    assert all(
        o.identity.item_id != "1TgtEEEEEEEEEEEEEEEEEEEE" for o in outcome.items
    )
    assert not any("/drive/v3/files/1TgtE" in path for path in server.requests)


def test_in_scope_shortcut_target_is_observed_by_the_enumeration_itself(server):
    shortcut = item_by_id(_discover(server), SHORTCUT_IN_SCOPE["id"])
    target = item_by_id(_discover(server), FOLDER_IN_SCOPE["id"])
    assert target.snapshot.kind == "folder"
    assert shortcut.snapshot.handling_refs[0].endswith(target.identity.item_id)


def _discover(server, selection=None):
    with build_discovery(server, selection=selection) as discovery:
        return discovery.discover(context())


def test_source_metadata_cannot_override_the_registered_binding(server):
    # Drive pagination carries opaque tokens, never source-built URLs, so the
    # request level has no override vector by construction. The remaining
    # vector is data: foreign drive/parent metadata on items must not change
    # the registered identity, and a URL-shaped item ID is rejected outright.
    foreign = dict(FILE_IN_SCOPE)
    foreign["parentReference"] = {
        "id": "1FgnYYYYYYYYYYYYYYYYYYYY",
        "driveId": "1FgnDriveXXXXXXXXXXXXXX",
    }
    server.routes.clear()
    _install_drive(server, (foreign,))
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    item = item_by_id(outcome, FILE_IN_SCOPE["id"])
    assert item.identity.container_id == DRIVE
    assert item.identity.account_id == ACCOUNT


def test_url_shaped_item_identifier_is_rejected(server):
    hostile = dict(FILE_IN_SCOPE)
    hostile["id"] = "../../other/drive/files"
    server.routes.clear()
    _install_drive(server, (hostile,))
    with build_discovery(server) as discovery, pytest.raises(ConnectorError) as error:
        discovery.discover(context())
    assert error.value.code == ErrorCode.RESOURCE_MISMATCH


def test_selection_cannot_use_the_root_alias(server):
    with pytest.raises(ValidationError):
        build_selection(root_item_id="root")
    assert server.requests == []


# --- AC 5: distinct safe setup states; no escalation ---


def test_insufficient_consent_on_enumeration_is_a_distinct_state(server):
    server.routes.clear()
    _install_drive(server, (FILE_IN_SCOPE,))
    server.routes["/drive/v3/files"] = lambda q: (
        403,
        {
            "error": {
                "code": 403,
                "message": "internal detail",
                "errors": [{"reason": "consentRequired"}],
            }
        },
    )
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    assert outcome.setup_state == GDriveSetupState.INSUFFICIENT_CONSENT
    assert outcome.items == ()
    assert "internal detail" not in json.dumps(outcome.evidence())


def test_missing_grant_is_distinct_from_consent(server):
    server.routes.clear()
    _install_drive(server, (FILE_IN_SCOPE,))
    server.routes["/drive/v3/files"] = lambda q: (
        403,
        {
            "error": {
                "code": 403,
                "message": "internal detail",
                "errors": [{"reason": "insufficientPermissions"}],
            }
        },
    )
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    assert outcome.setup_state == GDriveSetupState.MISSING_SELECTED_RESOURCE_GRANT

    with build_discovery(
        server,
        selection=build_selection(credential_mode="application_consent"),
        authority=build_authority(server, credential_mode="application_consent"),
    ) as discovery:
        application_outcome = discovery.discover(context())
    assert application_outcome.setup_state == GDriveSetupState.INSUFFICIENT_CONSENT


def test_token_rejected_and_not_found_are_distinct_states(server):
    server.routes.clear()
    _install_drive(server, (FILE_IN_SCOPE,))
    server.routes["/drive/v3/files"] = lambda q: (
        401,
        {
            "error": {
                "code": 401,
                "message": "internal",
                "errors": [{"reason": "authError"}],
            }
        },
    )
    with build_discovery(server) as discovery:
        assert discovery.discover(context()).setup_state == GDriveSetupState.TOKEN_REJECTED

    server.routes["/drive/v3/files"] = lambda q: (
        404,
        {
            "error": {
                "code": 404,
                "message": "internal",
                "errors": [{"reason": "notFound"}],
            }
        },
    )
    with build_discovery(server) as discovery:
        assert (
            discovery.discover(context()).setup_state
            == GDriveSetupState.SELECTED_RESOURCE_NOT_FOUND
        )


def test_unsupported_permission_surface_is_a_distinct_state(server):
    server.routes.clear()
    _install_drive(server, (FILE_IN_SCOPE,))
    server.routes[f"/drive/v3/files/{FILE_IN_SCOPE['id']}/permissions"] = lambda q: (
        400,
        {
            "error": {
                "code": 400,
                "message": "internal",
                "errors": [{"reason": "invalid"}],
            }
        },
    )
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    assert outcome.setup_state == GDriveSetupState.UNSUPPORTED_PERMISSION_MODE
    assert outcome.items == ()


def test_permission_surface_blocked_leaves_unavailable_evidence(server):
    server.routes.clear()
    _install_drive(server, (FILE_IN_SCOPE,))
    server.routes[f"/drive/v3/files/{FILE_IN_SCOPE['id']}/permissions"] = lambda q: (
        403,
        {
            "error": {
                "code": 403,
                "message": "internal",
                "errors": [{"reason": "insufficientFilePermissions"}],
            }
        },
    )
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    assert outcome.setup_state == GDriveSetupState.READY
    item = item_by_id(outcome, FILE_IN_SCOPE["id"])
    assert item.snapshot.acl.completeness == "unavailable"
    assert item.snapshot.acl.grants == ()
    assert outcome.permission_surface_available is False
    assert outcome.evidence()["acl_unavailable_count"] == 1


def test_item_deleted_mid_enumeration_leaves_unavailable_evidence(server):
    server.routes.clear()
    _install_drive(server, (FILE_IN_SCOPE, FOLDER_IN_SCOPE))
    server.routes[f"/drive/v3/files/{FILE_IN_SCOPE['id']}/permissions"] = lambda q: (
        404,
        {
            "error": {
                "code": 404,
                "message": "internal",
                "errors": [{"reason": "notFound"}],
            }
        },
    )
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    assert outcome.setup_state == GDriveSetupState.READY
    assert item_by_id(outcome, FILE_IN_SCOPE["id"]).snapshot.acl.completeness == "unavailable"


def test_unreachable_drive_is_a_safe_state(server):
    server.routes.clear()
    _install_drive(server, (FILE_IN_SCOPE,))
    server.routes["/drive/v3/files"] = lambda q: (
        503,
        {
            "error": {
                "code": 503,
                "message": "internal",
                "errors": [{"reason": "backendError"}],
            }
        },
    )
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    assert outcome.setup_state == GDriveSetupState.SOURCE_UNREACHABLE
    assert outcome.items == ()


def test_unsupported_credential_mode_fails_construction(server):
    with pytest.raises(ValidationError):
        build_selection(credential_mode="user_delegated_selected_files")
    assert server.requests == []


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
        {"credential_mode": "user_delegated_selected_files"},
        {"pinned_origin": ("https", "www.googleapis.com", 443)},
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
            selection=build_selection(credential_mode=CREDENTIAL_MODE),
            authority=build_authority(server, credential_mode="application_consent"),
        )
    assert error.value.code == ErrorCode.RESOURCE_MISMATCH
    assert server.requests == []


def test_wrong_tenant_context_is_rejected_without_io(server):
    request = OperationContext(
        tenant_id="tenant-b",
        connector_id="gdrive-docs",
        actor_id="operator",
        operation_id="run-1",
    )
    with build_discovery(server) as discovery, pytest.raises(ConnectorError) as error:
        discovery.discover(request)
    assert error.value.code == ErrorCode.CONTEXT_MISMATCH
    assert server.requests == []


def test_non_json_body_is_a_fixed_error(server):
    server.raw_route(
        "/drive/v3/files",
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
        "/drive/v3/files",
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
    server.routes.clear()
    _install_drive(server, (FILE_IN_SCOPE,))
    server.routes["/drive/v3/files"] = lambda q: (
        403,
        {
            "error": {
                "code": 403,
                "message": "tenant secret detail",
                "errors": [{"reason": "insufficientPermissions"}],
            }
        },
    )
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    serialized = json.dumps(outcome.evidence())
    assert "tenant secret detail" not in serialized
    assert BEARER not in serialized
    assert "insufficientPermissions" not in serialized
    assert BEARER not in repr(discovery)


def test_item_names_never_reach_evidence(server):
    with build_discovery(server) as discovery:
        outcome = discovery.discover(context())
    serialized = json.dumps(outcome.evidence())
    assert "quarterly-report-sentinel" not in serialized
    assert "pointer-elsewhere" not in serialized
    assert outcome.evidence()["item_count"] == 4
    assert outcome.evidence()["shortcut_count"] == 2
