"""Bounded Microsoft 365 library discovery over Graph v1.0; no content reads.

This adapter implements the Microsoft slice of
[#864](https://github.com/Limes-Labs/limes-axis/issues/864) on top of the #863
document observation contract. Trust, identity and durability stay with
existing owners:

* The host constructs the adapter from an explicitly configured
  organizational tenant/site/drive selection (:class:`M365LibrarySelection`)
  and a fail-closed lease/policy evidence pair (:class:`M365SourceAuthority`)
  plus already-resolved lease-scoped bearer material. This module performs no
  lease, secret-resolution or policy lookups, registers no source and grants
  no access.
* Only the declared library is enumerated: no site search, no directory
  crawl, no drive selection from source data. Every request is pinned to the
  egress-approved origin and every continuation must stay inside the selected
  drive scope; a scope-escaping link is a hard error, never a fetch.
* Graph responses are streamed under wire/decoded-byte caps with a shared
  deadline. Permission evidence is normalized into #863
  ``DocumentACLObservation`` objects: application-principal grants and
  unrecognized shapes leave the observation partial, permission surfaces that
  cannot be observed leave it unavailable, and no grant ever receives a
  trust-layer mapping the host did not create. A Graph application's access
  is never recorded as an end-user entitlement.
* Setup outcomes are fixed states (:class:`M365SetupState`) resolved from the
  HTTP status, Graph machine-readable error code and failing surface; the
  mapping table lives in :func:`_setup_state_for`. Consent gaps, missing
  selected-resource grants, unsupported permission surfaces and absent
  resources are distinct and none of them escalates anything. Graph error
  messages, tokens, item names and principal IDs never appear in evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import zlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Self
from urllib.parse import urlsplit

import urllib3
from axis_sdk.connector_authoring.contracts import (
    CURRENT_PROTOCOL,
    ConnectorError,
    ErrorCode,
    OperationContext,
    SecretStr,
)
from pydantic import BaseModel, ConfigDict, Field, model_validator

from axis_api.document_source_contracts import (
    DocumentACLObservation,
    DocumentGrant,
    DocumentIdentity,
    DocumentSnapshot,
)

M365_ADAPTER_NAME = "axis-m365-library-discovery"
M365_DISCOVERY_CONNECTOR_ID = "m365_document_library"

_CONNECT_TIMEOUT_SECONDS = 3.0
_READ_TIMEOUT_SECONDS = 15.0
_STREAM_CHUNK_BYTES = 65_536
_GZIP_WINDOW_BITS = 16 + zlib.MAX_WBITS
_DISCOVERY_TIME_BUDGET_SECONDS = 30
_MAX_WIRE_BYTES = 4_194_304
_MAX_DECODED_BYTES = 4_194_304
_MAX_API_PAGE = 200
_MAX_GRANTS_PER_ITEM = 1_024
_TRANSPORT_ERRORS = (urllib3.exceptions.HTTPError, OSError)
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_GRAPH_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._,:-]{0,239}$")
_GRAPH_TENANT_ID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$"
)
_ITEM_SELECT = "id,name,folder,file,parentReference,eTag,cTag"
_PERMISSION_SELECT = "grantedToV2,grantedToIdentitiesV2,link,roles,inheritedFrom,shareId"


class M365SetupState(StrEnum):
    """Fixed, safe discovery outcomes; never raw Graph errors."""

    READY = "setup_ready"
    TOKEN_REJECTED = "setup_token_rejected"
    MISSING_SELECTED_RESOURCE_GRANT = "setup_missing_selected_resource_grant"
    INSUFFICIENT_CONSENT = "setup_insufficient_consent"
    SELECTED_RESOURCE_NOT_FOUND = "setup_selected_resource_not_found"
    UNSUPPORTED_PERMISSION_MODE = "setup_unsupported_permission_mode"
    SOURCE_UNREACHABLE = "setup_source_unreachable"


SUPPORTED_PERMISSION_MODES = frozenset({"selected_resource_grant", "application_consent"})

# Endpoint-by-permission-mode support: both supported modes may enumerate
# metadata and the item permission surface of the selected library. Narrower
# modes (for example user-delegated per-site scopes) are deliberately not
# claimed; see docs/m365-discovery-permissions.md.
_MODE_ENDPOINT_SUPPORT = {
    "selected_resource_grant": {
        "drive_children": True,
        "item_permissions": True,
    },
    "application_consent": {
        "drive_children": True,
        "item_permissions": True,
    },
}


class M365LibrarySelection(BaseModel):
    """One explicitly configured organizational tenant/site/drive scope."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    tenant_id: str = Field(min_length=1, max_length=80)
    connector_id: str = Field(min_length=1, max_length=180)
    org_tenant_id: str = Field(min_length=36, max_length=36)
    site_id: str = Field(min_length=1, max_length=240)
    drive_id: str = Field(min_length=1, max_length=240)
    folder_item_id: str | None = Field(default=None, min_length=1, max_length=240)
    permission_mode: str = Field(min_length=1, max_length=40)
    max_items: int = Field(default=500, ge=1, le=5_000, strict=True)
    max_pages: int = Field(default=20, ge=1, le=1_000, strict=True)
    acl_validity_minutes: int = Field(default=60, ge=1, le=1_440, strict=True)

    @model_validator(mode="after")
    def bounded_selection(self) -> Self:
        if not _GRAPH_TENANT_ID_PATTERN.fullmatch(self.org_tenant_id):
            raise ValueError("Organization tenant must be a Microsoft Entra tenant ID")
        selected = [self.site_id, self.drive_id]
        if self.folder_item_id is not None:
            selected.append(self.folder_item_id)
        if any(not _GRAPH_ID_PATTERN.fullmatch(value) for value in selected):
            raise ValueError("Selected Graph identities must be bounded opaque IDs")
        if self.permission_mode not in SUPPORTED_PERMISSION_MODES:
            raise ValueError("Permission mode is not supported")
        return self

    @property
    def revision(self) -> str:
        encoded = json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


class M365SourceAuthority(BaseModel):
    """Fail-closed lease/policy evidence; mirrors the governed REST reader."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    tenant_id: str = Field(min_length=1, max_length=80)
    connector_id: str = Field(min_length=1, max_length=180)
    credential_lease_id: str = Field(min_length=1, max_length=180)
    egress_policy_id: str = Field(min_length=1, max_length=180)
    lease_status: str = Field(min_length=1, max_length=40)
    lease_ref: str = Field(min_length=1, max_length=500)
    # Fail closed: absent evidence is treated as if material had been returned.
    lease_secret_material_returned: str = "true"
    lease_expires_at: datetime
    egress_mode: str = Field(min_length=1, max_length=120)
    egress_endpoint_target_sha256: str = Field(min_length=64, max_length=64)
    pinned_origin: tuple[str, str, int]
    # Mirrors the S3 profile convention: TLS is mandatory except for explicit
    # loopback fixtures.
    allow_insecure_local: bool = False
    permission_mode: str = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def fail_closed_posture(self) -> Self:
        if self.lease_status not in {"lease_executed", "lease_renewed"}:
            raise ValueError("M365 discovery requires an executed or renewed credential lease")
        if not self.lease_ref:
            raise ValueError("M365 discovery requires provider lease reference evidence")
        if str(self.lease_secret_material_returned).strip().lower() != "false":
            raise ValueError("Lease evidence reports secret material was returned")
        if self.lease_expires_at.tzinfo is None:
            raise ValueError("Lease expiry must be timezone-aware")
        if self.egress_mode != "approved_private_endpoint":
            raise ValueError("M365 discovery requires an approved private endpoint egress mode")
        if not _SHA256_PATTERN.fullmatch(self.egress_endpoint_target_sha256):
            raise ValueError("Egress endpoint binding must be a SHA-256 hex digest")
        scheme, hostname, port = self.pinned_origin
        if (scheme, port) != ("https", 443) and not (
            self.allow_insecure_local
            and scheme == "http"
            and hostname.lower() in _LOOPBACK_HOSTS
        ):
            raise ValueError("Microsoft Graph discovery requires an HTTPS pinned origin")
        if (
            self.egress_endpoint_target_sha256
            != hashlib.sha256(f"{hostname.lower()}:{port}".encode()).hexdigest()
        ):
            raise ValueError("Egress endpoint binding does not match the pinned origin")
        if self.permission_mode not in SUPPORTED_PERMISSION_MODES:
            raise ValueError("Permission mode is not supported")
        return self


class _GraphFailure(Exception):
    """Bounded Graph failure; status, machine code and surface only."""

    def __init__(self, status: int, error_code: str | None, surface: str):
        self.status = status
        self.error_code = error_code
        self.surface = surface
        super().__init__(f"graph_status_{status}")


def _setup_state_for(failure: _GraphFailure, permission_mode: str) -> M365SetupState:
    """Fixed mapping; Graph codes are identifiers, never rendered messages.

    Enumeration surface: 401 means the token itself was rejected; 403 means
    the selected scope was not authorized for this connection, which the
    selected-resource mode reports as a missing grant and the application
    mode as insufficient consent; 404 means the configured selection no
    longer exists. Permission surface: a request-shaped rejection (400/405/501)
    means this permission mode cannot observe ACLs at all. Anything else is
    reported as an unreachable source without further interpretation.
    """

    if failure.surface == "permissions" and failure.status in {400, 405, 501}:
        return M365SetupState.UNSUPPORTED_PERMISSION_MODE
    if failure.status == 401:
        return M365SetupState.TOKEN_REJECTED
    if failure.status == 403:
        if failure.error_code == "consentRequired":
            return M365SetupState.INSUFFICIENT_CONSENT
        if permission_mode == "selected_resource_grant":
            return M365SetupState.MISSING_SELECTED_RESOURCE_GRANT
        return M365SetupState.INSUFFICIENT_CONSENT
    if failure.status == 404:
        return M365SetupState.SELECTED_RESOURCE_NOT_FOUND
    return M365SetupState.SOURCE_UNREACHABLE


def _setup_outcome(state: M365SetupState, authority: M365SourceAuthority) -> M365DiscoveryOutcome:
    return M365DiscoveryOutcome(
        setup_state=state,
        credential_lease_id=authority.credential_lease_id,
        egress_policy_id=authority.egress_policy_id,
    )


class _PinnedGraphTransport:
    """Graph transport pinned to the approved origin; redirects never followed."""

    def __init__(self, origin: tuple[str, str, int]):
        self._origin = origin
        self._pool = urllib3.PoolManager(
            timeout=urllib3.Timeout(connect=_CONNECT_TIMEOUT_SECONDS, read=_READ_TIMEOUT_SECONDS),
            retries=False,
            maxsize=1,
        )

    def close(self) -> None:
        self._pool.clear()

    def get_json(self, url: str, *, bearer: SecretStr, deadline: float) -> object:
        if _target(url) != self._origin:
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ConnectorError(ErrorCode.TIME_BUDGET_EXCEEDED)
        response = self._pool.urlopen(
            "GET",
            url,
            headers={
                "Authorization": f"Bearer {bearer.get_secret_value()}",
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
            },
            preload_content=False,
            decode_content=False,
            redirect=False,
            retries=False,
            timeout=urllib3.Timeout(
                total=remaining,
                connect=min(_CONNECT_TIMEOUT_SECONDS, remaining),
                read=min(_READ_TIMEOUT_SECONDS, remaining),
            ),
        )
        try:
            if response.status != 200:
                # The machine-readable Graph code is safe evidence; the human
                # message and any payload are consumed and discarded here.
                raise _GraphFailure(response.status, _graph_error_code(response), "enumerate")
            return _bounded_json(response)
        finally:
            response.close()
            response.release_conn()


def _target(url: str) -> tuple[str, str, int]:
    parsed = urlsplit(url)
    return (
        parsed.scheme,
        parsed.hostname or "",
        parsed.port or (443 if parsed.scheme == "https" else 80),
    )


def _graph_error_code(response) -> str | None:
    try:
        payload = _bounded_json(response)
    except (ConnectorError, zlib.error):
        return None
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        code = payload["error"].get("code")
        if isinstance(code, str) and len(code) <= 100:
            return code
    return None


def _bounded_json(response) -> object:
    content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    if not (content_type == "application/json" or content_type.endswith("+json")):
        raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
    encoding = (response.headers.get("Content-Encoding") or "").strip().lower()
    if encoding not in {"", "identity", "gzip"}:
        raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
    decoder = zlib.decompressobj(_GZIP_WINDOW_BITS) if encoding == "gzip" else None
    wire = 0
    decoded = bytearray()
    while True:
        remaining_wire = _MAX_WIRE_BYTES - wire
        if remaining_wire <= 0:
            raise ConnectorError(ErrorCode.LIMIT_EXCEEDED)
        chunk = response.read(min(_STREAM_CHUNK_BYTES, remaining_wire), decode_content=False)
        if not chunk:
            break
        wire += len(chunk)
        if decoder is None:
            if len(decoded) + len(chunk) > _MAX_DECODED_BYTES:
                raise ConnectorError(ErrorCode.LIMIT_EXCEEDED)
            decoded.extend(chunk)
            continue
        decoded.extend(_bounded_gzip(decoder, chunk, _MAX_DECODED_BYTES - len(decoded)))
    if decoder is not None and not decoder.eof:
        raise ConnectorError(ErrorCode.SOURCE_UNAVAILABLE)
    try:
        return json.loads(bytes(decoded), parse_constant=_reject_constant)
    except (ValueError, UnicodeDecodeError):
        raise ConnectorError(ErrorCode.RESOURCE_MISMATCH) from None


def _bounded_gzip(decoder: zlib.decompressobj, chunk: bytes, budget: int) -> bytes:
    if budget <= 0:
        raise ConnectorError(ErrorCode.LIMIT_EXCEEDED)
    try:
        output = decoder.decompress(chunk, budget)
    except zlib.error:
        raise ConnectorError(ErrorCode.SOURCE_UNAVAILABLE) from None
    if decoder.unconsumed_tail:
        raise ConnectorError(ErrorCode.LIMIT_EXCEEDED)
    if decoder.unused_data:
        raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
    return output


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-JSON constant {value} is not accepted")


@dataclass(frozen=True)
class M365ItemObservation:
    identity: DocumentIdentity
    snapshot: DocumentSnapshot


@dataclass
class M365DiscoveryOutcome:
    """Setup state plus bounded metadata inventory; names stay in snapshots only."""

    setup_state: M365SetupState
    truncated: bool = False
    items: tuple[M365ItemObservation, ...] = field(default_factory=tuple)
    permission_surface_available: bool = False
    credential_lease_id: str = ""
    egress_policy_id: str = ""

    def evidence(self) -> dict[str, str | int | bool]:
        """Public-safe projection for operator setup inspection and audit."""

        completions = [item.snapshot.acl.completeness for item in self.items]
        return {
            "adapter": M365_ADAPTER_NAME,
            "setup_state": self.setup_state.value,
            "truncated": self.truncated,
            "item_count": len(self.items),
            "file_count": sum(1 for item in self.items if item.snapshot.kind == "file"),
            "folder_count": sum(1 for item in self.items if item.snapshot.kind == "folder"),
            "acl_complete_count": completions.count("complete"),
            "acl_partial_count": completions.count("partial"),
            "acl_unavailable_count": completions.count("unavailable"),
            "permission_surface_available": self.permission_surface_available,
            "credential_lease_id": self.credential_lease_id,
            "egress_policy_id": self.egress_policy_id,
        }


class M365LibraryDiscovery:
    """Enumerates one approved library; the host owns leases, grants and persistence."""

    def __init__(
        self,
        *,
        selection: M365LibrarySelection,
        authority: M365SourceAuthority,
        credential_bearer: SecretStr,
        clock=time.monotonic,
        transport_factory=None,
    ):
        if (
            selection.tenant_id != authority.tenant_id
            or selection.connector_id != authority.connector_id
        ):
            raise ConnectorError(ErrorCode.CONTEXT_MISMATCH)
        if selection.permission_mode != authority.permission_mode:
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        if not _MODE_ENDPOINT_SUPPORT[selection.permission_mode]["drive_children"]:
            raise ConnectorError(ErrorCode.UNSUPPORTED_CAPABILITY)
        self.selection = selection
        self.authority = authority
        self.credential_bearer = credential_bearer
        self.clock = clock
        self.transport_factory = transport_factory or _PinnedGraphTransport
        self.transport = self.transport_factory(authority.pinned_origin)

    def close(self) -> None:
        self.transport.close()

    def __enter__(self) -> M365LibraryDiscovery:
        return self

    def __exit__(self, *exception: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"M365LibraryDiscovery(tenant_id={self.authority.tenant_id!r}, "
            f"connector_id={self.authority.connector_id!r})"
        )

    def discover(self, context: OperationContext) -> M365DiscoveryOutcome:
        self._context(context)
        deadline = self.clock() + _DISCOVERY_TIME_BUDGET_SECONDS
        try:
            return self._enumerate(context, deadline)
        except _GraphFailure as failure:
            state = _setup_state_for(failure, self.selection.permission_mode)
            return _setup_outcome(state, self.authority)
        except _TRANSPORT_ERRORS:
            return _setup_outcome(M365SetupState.SOURCE_UNREACHABLE, self.authority)

    def _context(self, context: OperationContext) -> None:
        if (
            context.protocol != CURRENT_PROTOCOL
            or context.tenant_id != self.authority.tenant_id
            or context.connector_id != self.authority.connector_id
        ):
            raise ConnectorError(ErrorCode.CONTEXT_MISMATCH)
        if datetime.now(UTC) >= self.authority.lease_expires_at:
            raise ConnectorError(ErrorCode.CONTEXT_MISMATCH)

    def _children_url(self) -> str:
        scope = (
            f"drives/{self.selection.drive_id}/root/children"
            if self.selection.folder_item_id is None
            else f"drives/{self.selection.drive_id}/items/{self.selection.folder_item_id}/children"
        )
        return (
            f"{self._graph_url(scope)}?$top={min(_MAX_API_PAGE, self.selection.max_items)}"
            f"&$select={_ITEM_SELECT}"
        )

    def _graph_url(self, path_and_query: str) -> str:
        scheme, hostname, port = self.authority.pinned_origin
        # IPv6 literals require brackets in rendered URLs; the target check
        # in _validate_scope_url compares the parsed origin back.
        host = f"[{hostname}]" if ":" in hostname else hostname
        if (scheme, port) == ("https", 443):
            return f"{scheme}://{host}/v1.0/{path_and_query}"
        return f"{scheme}://{host}:{port}/v1.0/{path_and_query}"

    def _validate_scope_url(self, url: str, surface: str) -> None:
        # Continuation links come from source data: the destination must be
        # the pinned Graph origin *and* stay inside the selected drive before
        # any request, so other tenants/sites/drives are never dialed.
        if _target(url) != self.authority.pinned_origin:
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        path = urlsplit(url).path
        if not path.startswith(f"/v1.0/drives/{self.selection.drive_id}/"):
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        if surface == "permissions" and "/permissions" not in urlsplit(url).path:
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)

    def _enumerate(self, context: OperationContext, deadline: float) -> M365DiscoveryOutcome:
        items: list[M365ItemObservation] = []
        truncated = False
        permission_surface_available = True
        url: str | None = self._children_url()
        pages = 0
        while url is not None:
            if pages >= self.selection.max_pages or len(items) >= self.selection.max_items:
                truncated = True
                break
            pages += 1
            page = self._fetch(url, "children", deadline)
            next_link = _next_link(page)
            for raw in _page_items(page):
                if len(items) >= self.selection.max_items:
                    truncated = True
                    break
                observation = self._observe(context, raw, deadline)
                items.append(observation)
                if observation.snapshot.acl.completeness == "unavailable":
                    permission_surface_available = False
            url = next_link
            cap_reached = (
                len(items) >= self.selection.max_items or pages >= self.selection.max_pages
            )
            if url is not None and cap_reached:
                # A next link exists but the operator cap is exhausted: the
                # enumeration is honestly truncated, never silently complete.
                truncated = True
                url = None
        return M365DiscoveryOutcome(
            setup_state=M365SetupState.READY,
            truncated=truncated,
            items=tuple(items),
            permission_surface_available=permission_surface_available,
            credential_lease_id=self.authority.credential_lease_id,
            egress_policy_id=self.authority.egress_policy_id,
        )

    def _fetch(self, url: str, surface: str, deadline: float) -> object:
        self._validate_scope_url(url, surface)
        try:
            return self.transport.get_json(url, bearer=self.credential_bearer, deadline=deadline)
        except _GraphFailure as failure:
            # The transport does not know which surface it served; failures are
            # re-tagged here so the state mapping can be surface-aware.
            if surface == "permissions":
                raise _GraphFailure(failure.status, failure.error_code, "permissions") from None
            raise

    def _observe(
        self, context: OperationContext, raw: object, deadline: float
    ) -> M365ItemObservation:
        if not isinstance(raw, dict):
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        item_id = raw.get("id")
        name = raw.get("name")
        etag = raw.get("eTag")
        if (
            not isinstance(item_id, str)
            or not _GRAPH_ID_PATTERN.fullmatch(item_id)
            or not isinstance(name, str)
            or not name
            or not isinstance(etag, str)
            or not etag
        ):
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        parent = raw.get("parentReference")
        parent_id = parent.get("id") if isinstance(parent, dict) else None
        identity = DocumentIdentity(
            tenant_id=context.tenant_id,
            connector_id=context.connector_id,
            provider="microsoft_graph",
            account_id=self.selection.org_tenant_id,
            container_id=self.selection.drive_id,
            item_id=item_id,
        )
        acl = self._acl(item_id, deadline)
        snapshot = _snapshot(raw, name, etag, parent_id, acl)
        return M365ItemObservation(identity=identity, snapshot=snapshot)

    def _acl(self, item_id: str, deadline: float) -> DocumentACLObservation:
        url = (
            f"{self._graph_url(f'drives/{self.selection.drive_id}/items/{item_id}/permissions')}"
            f"?$select={_PERMISSION_SELECT}&$top={_MAX_API_PAGE}"
        )
        now = datetime.now(UTC)
        validity = timedelta(minutes=self.selection.acl_validity_minutes)
        try:
            page = self._fetch(url, "permissions", deadline)
        except _GraphFailure as failure:
            if failure.status in {403, 404}:
                # The permission surface is blocked for this grant mode or the
                # item vanished mid-enumeration; the item stays observable but
                # its evidence is unreadable. Only an enumeration-surface 404
                # means the selected library itself is gone.
                return DocumentACLObservation(
                    revision=f"unavailable:{hashlib.sha256(item_id.encode()).hexdigest()[:32]}",
                    observed_at=now,
                    valid_until=now + validity,
                    completeness="unavailable",
                )
            raise
        grants: list[DocumentGrant] = []
        complete = True
        pages = 1
        while True:
            if not isinstance(page, dict) or not isinstance(page.get("value"), list):
                raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
            for permission in page["value"]:
                if not isinstance(permission, dict):
                    raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
                normalized = _normalize_grants(permission, self.selection.org_tenant_id)
                if normalized is None:
                    complete = False
                    continue
                grants.extend(normalized)
            next_link = _next_link(page)
            if next_link is None:
                break
            if len(grants) > _MAX_GRANTS_PER_ITEM or pages >= self.selection.max_pages:
                complete = False
                break
            pages += 1
            page = self._fetch(next_link, "permissions", deadline)
        if len(grants) > _MAX_GRANTS_PER_ITEM:
            grants = grants[:_MAX_GRANTS_PER_ITEM]
            complete = False
        grant_dump = [grant.model_dump(mode="json") for grant in grants]
        return DocumentACLObservation(
            revision=hashlib.sha256(
                json.dumps(
                    {"item": item_id, "grants": grant_dump},
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest(),
            observed_at=now,
            valid_until=now + validity,
            # An empty but fully enumerated grant list is honest complete
            # evidence; baseline readability still requires grants elsewhere.
            completeness="complete" if complete else "partial",
            grants=tuple(grants),
        )


def _next_link(page: object) -> str | None:
    if not isinstance(page, dict):
        raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
    next_link = page.get("@odata.nextLink")
    if next_link is None:
        return None
    if not isinstance(next_link, str):
        raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
    return next_link


def _page_items(page: object) -> list[object]:
    if not isinstance(page, dict) or not isinstance(page.get("value"), list):
        raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
    return page["value"]


def _snapshot(raw: dict, name: str, etag: str, parent_id: object, acl) -> DocumentSnapshot:
    parent = parent_id if isinstance(parent_id, str) else None
    if isinstance(raw.get("folder"), dict):
        return DocumentSnapshot(
            kind="folder",
            display_name=name[:512],
            parent_item_id=parent,
            source_revision=etag,
            acl=acl,
        )
    file_facet = raw.get("file")
    if not isinstance(file_facet, dict):
        raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
    media_type = file_facet.get("mimeType")
    content_tag = raw.get("cTag") or etag
    if not isinstance(media_type, str) or not media_type or not isinstance(content_tag, str):
        raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
    return DocumentSnapshot(
        kind="file",
        display_name=name[:512],
        parent_item_id=parent,
        source_revision=etag,
        content_revision=content_tag,
        media_type=media_type[:128],
        acl=acl,
    )


def _normalize_grants(permission: dict, account_id: str) -> list[DocumentGrant] | None:
    """Map one Graph permission into #863 grants, or None when unnormalizable.

    Application principals are the connection service identity's own access,
    never an end-user entitlement, so they leave the observation partial.
    Organizational and anonymous links are preserved as domain/link evidence,
    which the #863 contract keeps ineligible for baseline read authorization.
    """

    grants: list[DocumentGrant] = []
    inherited = permission.get("inheritedFrom")
    inherited_id = inherited.get("id") if isinstance(inherited, dict) else None
    inherited_from = inherited_id if isinstance(inherited_id, str) and inherited_id else None
    direct = permission.get("grantedToV2")
    if direct is not None and not _append_principal(grants, direct, account_id, inherited_from):
        return None
    identities = permission.get("grantedToIdentitiesV2")
    if identities is not None:
        if not isinstance(identities, list):
            return None
        for principal in identities:
            if not _append_principal(grants, principal, account_id, inherited_from):
                return None
    link = permission.get("link")
    if link is not None and direct is None and not identities:
        if not isinstance(link, dict):
            return None
        scope = link.get("scope")
        kind = "domain" if scope == "organization" else "link"
        grants.append(
            DocumentGrant(
                source_account_id=account_id,
                principal_kind=kind,
                principal_id=_link_id(permission, scope),
                inherited_from_item_id=inherited_from,
            )
        )
    return grants or None


def _append_principal(
    grants: list[DocumentGrant], principal: object, account_id: str, inherited_from: str | None
) -> bool:
    if not isinstance(principal, dict) or "application" in principal:
        return False
    for kind in ("user", "group"):
        facet = principal.get(kind)
        if isinstance(facet, dict) and isinstance(facet.get("id"), str):
            if not _GRAPH_ID_PATTERN.fullmatch(facet["id"]):
                return False
            grants.append(
                DocumentGrant(
                    source_account_id=account_id,
                    principal_kind=kind,
                    principal_id=facet["id"],
                    inherited_from_item_id=inherited_from,
                )
            )
            return True
    return False


def _link_id(permission: dict, scope: object) -> str:
    share_id = permission.get("shareId")
    base = share_id if isinstance(share_id, str) and share_id else "link"
    suffix = scope if isinstance(scope, str) and scope else "anonymous"
    return f"{base}:{suffix}"[:200]
