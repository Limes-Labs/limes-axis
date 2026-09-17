"""Bounded Google Drive discovery over Drive API v3; no content reads.

This adapter implements the Google slice of
[#866](https://github.com/Limes-Labs/limes-axis/issues/866) on top of the #863
document observation contract. Trust, identity and durability stay with
existing owners:

* The host constructs the adapter from an explicitly configured credential
  mode, provider account, drive kind and root selection
  (:class:`GDriveSelection`) and a fail-closed lease/policy evidence pair
  (:class:`GDriveSourceAuthority`) plus already-resolved lease-scoped bearer
  material. This module performs no lease, secret-resolution or policy
  lookups, registers no source and grants no access.
* Only the declared drive and root are enumerated: no drive listing, no
  ``sharedWithMe`` corpus, no directory crawl, no selection from source data.
  Every request is pinned to the egress-approved origin and built by the
  adapter itself; Drive pagination carries opaque page tokens, so the source
  can never point this adapter at another origin, drive or API surface.
* Drive responses are streamed under wire/decoded-byte caps with a shared
  deadline. Permission evidence is normalized into #863
  ``DocumentACLObservation`` objects: unrecognized permission shapes leave
  the observation partial, unreadable permission surfaces leave it
  unavailable, and no grant ever receives a trust-layer mapping the host did
  not create. ``anyone``/``anyoneWithLink`` and ``domain`` grants are kept as
  link/domain evidence, which the #863 contract holds ineligible for baseline
  read authorization.
* Shortcuts are metadata only: a shortcut is observed with its target
  identifier preserved in ``handling_refs``, but no shortcut target is ever
  fetched. In-scope targets are observed by the enumeration itself; an
  out-of-scope target stays exactly what Drive reported — an unobserved ID.
  Source metadata cannot override the registered endpoint or account binding.
* Setup outcomes are fixed states (:class:`GDriveSetupState`) resolved from
  the HTTP status, Drive machine-readable reason and failing surface.
  Revoked consent, missing grants, unsupported credential modes and absent
  resources are distinct and none of them escalates anything. Drive error
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
from typing import Literal, Self
from urllib.parse import quote, urlsplit

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

GDRIVE_ADAPTER_NAME = "axis-gdrive-corpus-discovery"
GDRIVE_DISCOVERY_CONNECTOR_ID = "gdrive_document_corpus"

_CONNECT_TIMEOUT_SECONDS = 3.0
_READ_TIMEOUT_SECONDS = 15.0
_STREAM_CHUNK_BYTES = 65_536
_GZIP_WINDOW_BITS = 16 + zlib.MAX_WBITS
_DISCOVERY_TIME_BUDGET_SECONDS = 30
_MAX_WIRE_BYTES = 4_194_304
_MAX_DECODED_BYTES = 4_194_304
_MAX_FILES_PAGE = 200
# permissions.list caps pageSize at 100, unlike files.list.
_MAX_PERMISSIONS_PAGE = 100
_MAX_GRANTS_PER_ITEM = 1_024
_TRANSPORT_ERRORS = (urllib3.exceptions.HTTPError, OSError)
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_DRIVE_ITEM_PATTERN = re.compile(r"^[A-Za-z0-9_-]{10,64}$")
_ACCOUNT_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{3,189}$")
_PAGE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_.~-]{1,512}$")
_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
_SHORTCUT_MIME_TYPE = "application/vnd.google-apps.shortcut"
_FILES_FIELDS = "id,name,mimeType,parentReference,version,shortcutDetails"
_PERMISSION_FIELDS = "id,type,emailAddress,domain"
_MAX_DISPLAY_NAME = 512
_MAX_MEDIA_TYPE = 128

DriveKind = Literal["my_drive", "shared_drive"]


class GDriveSetupState(StrEnum):
    """Fixed, safe discovery outcomes; never raw Drive errors."""

    READY = "setup_ready"
    TOKEN_REJECTED = "setup_token_rejected"
    MISSING_SELECTED_RESOURCE_GRANT = "setup_missing_selected_resource_grant"
    INSUFFICIENT_CONSENT = "setup_insufficient_consent"
    SELECTED_RESOURCE_NOT_FOUND = "setup_selected_resource_not_found"
    UNSUPPORTED_PERMISSION_MODE = "setup_unsupported_permission_mode"
    SOURCE_UNREACHABLE = "setup_source_unreachable"


SUPPORTED_CREDENTIAL_MODES = frozenset({"selected_resource_grant", "application_consent"})


# Endpoint-by-credential-mode support: both supported modes may enumerate the
# selected root and the item permission surface. Narrower modes (for example
# Files.Read.Selected user-delegated scopes against arbitrary folders) are
# deliberately not claimed; see docs/gdrive-discovery-permissions.md.
_MODE_ENDPOINT_SUPPORT = {
    "selected_resource_grant": {
        "root_listing": True,
        "item_permissions": True,
    },
    "application_consent": {
        "root_listing": True,
        "item_permissions": True,
    },
}


class GDriveSelection(BaseModel):
    """One explicitly configured provider account, drive and root selection.

    ``root_item_id`` is always a concrete Drive item ID — never the ``root``
    alias, which only resolves against the credentialed user's My Drive and
    would silently enumerate the wrong corpus if copied into another drive.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    tenant_id: str = Field(min_length=1, max_length=80)
    connector_id: str = Field(min_length=1, max_length=180)
    provider_account_id: str = Field(min_length=6, max_length=254)
    credential_mode: str = Field(min_length=1, max_length=40)
    drive_kind: DriveKind
    drive_id: str = Field(min_length=10, max_length=64)
    root_item_id: str = Field(min_length=10, max_length=64)
    max_items: int = Field(default=500, ge=1, le=5_000, strict=True)
    max_pages: int = Field(default=20, ge=1, le=1_000, strict=True)
    acl_validity_minutes: int = Field(default=60, ge=1, le=1_440, strict=True)

    @model_validator(mode="after")
    def bounded_selection(self) -> Self:
        if not _ACCOUNT_PATTERN.fullmatch(self.provider_account_id):
            raise ValueError("Provider account must be a bounded account identity")
        for value in (self.drive_id, self.root_item_id):
            if not _DRIVE_ITEM_PATTERN.fullmatch(value):
                raise ValueError("Drive identities must be bounded opaque Drive identifiers")
        if self.root_item_id == "root":
            raise ValueError("The root alias is not an explicit selection")
        if self.credential_mode not in SUPPORTED_CREDENTIAL_MODES:
            raise ValueError("Credential mode is not supported")
        return self

    @property
    def revision(self) -> str:
        encoded = json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


class GDriveSourceAuthority(BaseModel):
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
    credential_mode: str = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def fail_closed_posture(self) -> Self:
        if self.lease_status not in {"lease_executed", "lease_renewed"}:
            raise ValueError("Google Drive discovery requires an executed or renewed lease")
        if not self.lease_ref:
            raise ValueError("Google Drive discovery requires provider lease reference evidence")
        if str(self.lease_secret_material_returned).strip().lower() != "false":
            raise ValueError("Lease evidence reports secret material was returned")
        if self.lease_expires_at.tzinfo is None:
            raise ValueError("Lease expiry must be timezone-aware")
        if self.egress_mode != "approved_private_endpoint":
            raise ValueError("Google Drive discovery requires an approved private endpoint")
        if not _SHA256_PATTERN.fullmatch(self.egress_endpoint_target_sha256):
            raise ValueError("Egress endpoint binding must be a SHA-256 hex digest")
        scheme, hostname, port = self.pinned_origin
        if (scheme, port) != ("https", 443) and not (
            self.allow_insecure_local
            and scheme == "http"
            and hostname.lower() in _LOOPBACK_HOSTS
        ):
            raise ValueError("Google Drive discovery requires an HTTPS pinned origin")
        if (
            self.egress_endpoint_target_sha256
            != hashlib.sha256(f"{hostname.lower()}:{port}".encode()).hexdigest()
        ):
            raise ValueError("Egress endpoint binding does not match the pinned origin")
        if self.credential_mode not in SUPPORTED_CREDENTIAL_MODES:
            raise ValueError("Credential mode is not supported")
        return self


class _DriveFailure(Exception):
    """Bounded Drive failure; status, machine reason and surface only."""

    def __init__(self, status: int, reason: str | None, surface: str):
        self.status = status
        self.reason = reason
        self.surface = surface
        super().__init__(f"drive_status_{status}")


def _setup_state_for(failure: _DriveFailure, credential_mode: str) -> GDriveSetupState:
    """Fixed mapping; Drive reasons are identifiers, never rendered messages.

    Enumeration surface: 401 means the token itself was rejected; 403 means
    the selected scope was not authorized for this connection, which the
    selected-resource mode reports as a missing grant and the application
    mode as insufficient consent; 404 means the configured selection no
    longer exists. Permission surface: a request-shaped rejection (400/405/501)
    means this credential mode cannot observe item permissions at all.
    Anything else is reported as an unreachable source without further
    interpretation.
    """

    if failure.surface == "permissions" and failure.status in {400, 405, 501}:
        return GDriveSetupState.UNSUPPORTED_PERMISSION_MODE
    if failure.status == 401:
        return GDriveSetupState.TOKEN_REJECTED
    if failure.status == 403:
        if failure.reason == "consentRequired":
            return GDriveSetupState.INSUFFICIENT_CONSENT
        if credential_mode == "selected_resource_grant":
            return GDriveSetupState.MISSING_SELECTED_RESOURCE_GRANT
        return GDriveSetupState.INSUFFICIENT_CONSENT
    if failure.status == 404:
        return GDriveSetupState.SELECTED_RESOURCE_NOT_FOUND
    return GDriveSetupState.SOURCE_UNREACHABLE


def _setup_outcome(
    state: GDriveSetupState, authority: GDriveSourceAuthority
) -> GDriveDiscoveryOutcome:
    return GDriveDiscoveryOutcome(
        setup_state=state,
        credential_lease_id=authority.credential_lease_id,
        egress_policy_id=authority.egress_policy_id,
    )


class _PinnedDriveTransport:
    """Drive transport pinned to the approved origin; redirects never followed."""

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
                # The machine-readable Drive reason is safe evidence; the human
                # message and any payload are consumed and discarded here.
                raise _DriveFailure(response.status, _drive_error_reason(response), "list")
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


def _drive_error_reason(response) -> str | None:
    try:
        payload = _bounded_json(response)
    except (ConnectorError, zlib.error):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("error"), dict):
        return None
    error = payload["error"]
    errors = error.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        reason = errors[0].get("reason")
        if isinstance(reason, str) and len(reason) <= 100:
            return reason
    reason = error.get("status")
    if isinstance(reason, str) and len(reason) <= 100:
        return reason
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
class GDriveItemObservation:
    identity: DocumentIdentity
    snapshot: DocumentSnapshot


@dataclass
class GDriveDiscoveryOutcome:
    """Setup state plus bounded metadata inventory; names stay in snapshots only."""

    setup_state: GDriveSetupState
    truncated: bool = False
    items: tuple[GDriveItemObservation, ...] = field(default_factory=tuple)
    permission_surface_available: bool = False
    credential_lease_id: str = ""
    egress_policy_id: str = ""

    def evidence(self) -> dict[str, str | int | bool]:
        """Public-safe projection for operator setup inspection and audit."""

        completions = [item.snapshot.acl.completeness for item in self.items]
        return {
            "adapter": GDRIVE_ADAPTER_NAME,
            "setup_state": self.setup_state.value,
            "truncated": self.truncated,
            "item_count": len(self.items),
            "file_count": sum(1 for item in self.items if item.snapshot.kind == "file"),
            "folder_count": sum(1 for item in self.items if item.snapshot.kind == "folder"),
            "shortcut_count": sum(1 for item in self.items if _is_shortcut(item.snapshot)),
            "acl_complete_count": completions.count("complete"),
            "acl_partial_count": completions.count("partial"),
            "acl_unavailable_count": completions.count("unavailable"),
            "permission_surface_available": self.permission_surface_available,
            "credential_lease_id": self.credential_lease_id,
            "egress_policy_id": self.egress_policy_id,
        }


def _is_shortcut(snapshot: DocumentSnapshot) -> bool:
    return snapshot.media_type == _SHORTCUT_MIME_TYPE


class GDriveCorpusDiscovery:
    """Enumerates one approved drive/root; the host owns leases, grants and persistence."""

    def __init__(
        self,
        *,
        selection: GDriveSelection,
        authority: GDriveSourceAuthority,
        credential_bearer: SecretStr,
        clock=time.monotonic,
        transport_factory=None,
    ):
        if (
            selection.tenant_id != authority.tenant_id
            or selection.connector_id != authority.connector_id
        ):
            raise ConnectorError(ErrorCode.CONTEXT_MISMATCH)
        if selection.credential_mode != authority.credential_mode:
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        if not _MODE_ENDPOINT_SUPPORT[selection.credential_mode]["root_listing"]:
            raise ConnectorError(ErrorCode.UNSUPPORTED_CAPABILITY)
        self.selection = selection
        self.authority = authority
        self.credential_bearer = credential_bearer
        self.clock = clock
        self.transport_factory = transport_factory or _PinnedDriveTransport
        self.transport = self.transport_factory(authority.pinned_origin)

    def close(self) -> None:
        self.transport.close()

    def __enter__(self) -> GDriveCorpusDiscovery:
        return self

    def __exit__(self, *exception: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"GDriveCorpusDiscovery(tenant_id={self.authority.tenant_id!r}, "
            f"connector_id={self.authority.connector_id!r})"
        )

    def discover(self, context: OperationContext) -> GDriveDiscoveryOutcome:
        self._context(context)
        deadline = self.clock() + _DISCOVERY_TIME_BUDGET_SECONDS
        try:
            return self._enumerate(context, deadline)
        except _DriveFailure as failure:
            state = _setup_state_for(failure, self.selection.credential_mode)
            return _setup_outcome(state, self.authority)
        except _TRANSPORT_ERRORS:
            return _setup_outcome(GDriveSetupState.SOURCE_UNREACHABLE, self.authority)

    def _context(self, context: OperationContext) -> None:
        if (
            context.protocol != CURRENT_PROTOCOL
            or context.tenant_id != self.authority.tenant_id
            or context.connector_id != self.authority.connector_id
        ):
            raise ConnectorError(ErrorCode.CONTEXT_MISMATCH)
        if datetime.now(UTC) >= self.authority.lease_expires_at:
            raise ConnectorError(ErrorCode.CONTEXT_MISMATCH)

    def _list_url(self, page_token: str | None = None) -> str:
        # Only the adapter builds URLs: Drive pagination carries opaque page
        # tokens, never request URLs, so source data cannot point this adapter
        # at another origin, drive or API surface.
        query = self._list_query()
        if page_token is not None:
            query = f"{query}&pageToken={quote(page_token, safe='')}"
        return f"{self._drive_url('files')}?{query}"

    def _list_query(self) -> str:
        scope = quote(f"'{self.selection.root_item_id}' in parents and trashed = false", safe="")
        base = (
            f"pageSize={min(_MAX_FILES_PAGE, self.selection.max_items)}"
            f"&fields=nextPageToken,files({_FILES_FIELDS})"
            f"&q={scope}&supportsAllDrives=true"
        )
        if self.selection.drive_kind == "shared_drive":
            # A shared drive is a drive-scoped corpus, not an ordinary user
            # folder: the driveId parameter keeps the walk pinned to the
            # registered drive identity.
            return (
                f"{base}&includeItemsFromAllDrives=true"
                f"&corpora=drive&driveId={self.selection.drive_id}"
            )
        return base

    def _permissions_url(self, item_id: str, page_token: str | None = None) -> str:
        query = (
            f"pageSize={_MAX_PERMISSIONS_PAGE}&fields={_PERMISSION_FIELDS}"
            f"&supportsAllDrives=true"
        )
        if page_token is not None:
            query = f"{query}&pageToken={quote(page_token, safe='')}"
        return f"{self._drive_url(f'files/{item_id}/permissions')}?{query}"

    def _drive_url(self, path_and_query: str) -> str:
        scheme, hostname, port = self.authority.pinned_origin
        # IPv6 literals require brackets in rendered URLs; the target check
        # in _PinnedDriveTransport.get_json compares the parsed origin back.
        host = f"[{hostname}]" if ":" in hostname else hostname
        if (scheme, port) == ("https", 443):
            return f"{scheme}://{host}/drive/v3/{path_and_query}"
        return f"{scheme}://{host}:{port}/drive/v3/{path_and_query}"

    def _enumerate(self, context: OperationContext, deadline: float) -> GDriveDiscoveryOutcome:
        items: list[GDriveItemObservation] = []
        truncated = False
        permission_surface_available = True
        page_token: str | None = None
        pages = 0
        while True:
            if pages >= self.selection.max_pages or len(items) >= self.selection.max_items:
                truncated = True
                break
            page = self._fetch(self._list_url(page_token), deadline, "list")
            if not isinstance(page, dict) or not isinstance(page.get("files"), list):
                raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
            for raw in page["files"]:
                if len(items) >= self.selection.max_items:
                    truncated = True
                    break
                observation = self._observe(context, raw, deadline)
                items.append(observation)
                if observation.snapshot.acl.completeness == "unavailable":
                    permission_surface_available = False
            if truncated:
                break
            next_token = page.get("nextPageToken")
            if next_token is None:
                break
            if not isinstance(next_token, str) or not _PAGE_TOKEN_PATTERN.fullmatch(next_token):
                raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
            page_token = next_token
            pages += 1
        return GDriveDiscoveryOutcome(
            setup_state=GDriveSetupState.READY,
            truncated=truncated,
            items=tuple(items),
            permission_surface_available=permission_surface_available,
            credential_lease_id=self.authority.credential_lease_id,
            egress_policy_id=self.authority.egress_policy_id,
        )

    def _fetch(self, url: str, deadline: float, surface: str) -> object:
        try:
            return self.transport.get_json(url, bearer=self.credential_bearer, deadline=deadline)
        except _DriveFailure as failure:
            # The transport does not know which surface it served; failures are
            # re-tagged here so the state mapping can be surface-aware.
            raise _DriveFailure(failure.status, failure.reason, surface) from None

    def _observe(
        self, context: OperationContext, raw: object, deadline: float
    ) -> GDriveItemObservation:
        if not isinstance(raw, dict):
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        item_id = raw.get("id")
        name = raw.get("name")
        revision = raw.get("version")
        if (
            not isinstance(item_id, str)
            or not _DRIVE_ITEM_PATTERN.fullmatch(item_id)
            or not isinstance(name, str)
            or not name
            or not isinstance(revision, str)
            or not revision
        ):
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        parent = raw.get("parentReference")
        parent_id = parent.get("id") if isinstance(parent, dict) else None
        identity = DocumentIdentity(
            tenant_id=context.tenant_id,
            connector_id=context.connector_id,
            provider="google_drive",
            account_id=self.selection.provider_account_id,
            container_id=self.selection.drive_id,
            item_id=item_id,
        )
        acl = self._acl(item_id, deadline)
        snapshot = _snapshot(raw, name, revision, parent_id, acl)
        return GDriveItemObservation(identity=identity, snapshot=snapshot)

    def _acl(self, item_id: str, deadline: float) -> DocumentACLObservation:
        now = datetime.now(UTC)
        validity = timedelta(minutes=self.selection.acl_validity_minutes)
        grants: list[DocumentGrant] = []
        complete = True
        pages = 1
        page_token: str | None = None
        while True:
            try:
                page = self._fetch(
                    self._permissions_url(item_id, page_token), deadline, "permissions"
                )
            except _DriveFailure as failure:
                if failure.status in {403, 404}:
                    # The permission surface is blocked for this credential mode
                    # or the item vanished mid-enumeration; the item stays
                    # observable but its evidence is unreadable. Only an
                    # enumeration-surface 404 means the selected root itself is
                    # gone.
                    return DocumentACLObservation(
                        revision=f"unavailable:{hashlib.sha256(item_id.encode()).hexdigest()[:32]}",
                        observed_at=now,
                        valid_until=now + validity,
                        completeness="unavailable",
                    )
                raise
            if not isinstance(page, dict) or not isinstance(page.get("permissions"), list):
                raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
            for permission in page["permissions"]:
                if not isinstance(permission, dict):
                    raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
                normalized = _normalize_grant(permission, self.selection.provider_account_id)
                if normalized is None:
                    complete = False
                    continue
                grants.append(normalized)
            next_token = page.get("nextPageToken")
            if next_token is None:
                break
            if len(grants) > _MAX_GRANTS_PER_ITEM or pages >= self.selection.max_pages:
                complete = False
                break
            if not isinstance(next_token, str) or not _PAGE_TOKEN_PATTERN.fullmatch(next_token):
                raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
            page_token = next_token
            pages += 1
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


def _snapshot(raw: dict, name: str, revision: str, parent_id: object, acl) -> DocumentSnapshot:
    parent = parent_id if isinstance(parent_id, str) else None
    media_type = raw.get("mimeType")
    if not isinstance(media_type, str) or not media_type:
        raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
    if media_type == _SHORTCUT_MIME_TYPE:
        # A shortcut is observed as a pointer: its target ID is preserved but
        # never fetched. Whether the target is inside the approved scope is
        # decided by later slices that observe it through the same enumeration;
        # here it stays exactly what Drive reported — an unobserved identifier.
        shortcut = raw.get("shortcutDetails")
        target_id = shortcut.get("targetId") if isinstance(shortcut, dict) else None
        if not isinstance(target_id, str) or not _DRIVE_ITEM_PATTERN.fullmatch(target_id):
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        return DocumentSnapshot(
            kind="file",
            display_name=name[:_MAX_DISPLAY_NAME],
            parent_item_id=parent,
            source_revision=revision,
            content_revision=revision,
            media_type=media_type[:_MAX_MEDIA_TYPE],
            acl=acl,
            handling_refs=(f"gdrive-shortcut:{target_id}",),
        )
    if media_type == _FOLDER_MIME_TYPE:
        return DocumentSnapshot(
            kind="folder",
            display_name=name[:_MAX_DISPLAY_NAME],
            parent_item_id=parent,
            source_revision=revision,
            acl=acl,
        )
    return DocumentSnapshot(
        kind="file",
        display_name=name[:_MAX_DISPLAY_NAME],
        parent_item_id=parent,
        source_revision=revision,
        content_revision=revision,
        media_type=media_type[:_MAX_MEDIA_TYPE],
        acl=acl,
    )


def _normalize_grant(permission: dict, account_id: str) -> DocumentGrant | None:
    """Map one Drive permission into a #863 grant, or None when unnormalizable.

    ``anyone`` and ``anyoneWithLink`` become link evidence and ``domain``
    becomes domain evidence, which the #863 contract keeps ineligible for
    baseline read authorization. Group principals are recorded as group
    evidence with their address; group membership is unknown to this adapter
    and is never resolved here. Drive returns effective (including inherited)
    permissions, and its permissionDetails carry permission IDs, not item IDs,
    so the #863 inherited-item provenance stays unset rather than misnamed.
    """

    kind = permission.get("type")
    principal_id = permission.get("id")
    if not _bounded_principal(principal_id):
        return None
    if kind in {"user", "group"}:
        email = permission.get("emailAddress")
        if not isinstance(email, str) or not _ACCOUNT_PATTERN.fullmatch(email):
            return None
        return DocumentGrant(
            source_account_id=account_id,
            principal_kind=kind,
            principal_id=email,
        )
    if kind == "domain":
        domain = permission.get("domain")
        if not _bounded_principal(domain):
            return None
        return DocumentGrant(
            source_account_id=account_id,
            principal_kind="domain",
            principal_id=domain,
        )
    if kind in {"anyone", "anyoneWithLink"}:
        return DocumentGrant(
            source_account_id=account_id,
            principal_kind="link",
            principal_id=principal_id,
        )
    return None


def _bounded_principal(value: object) -> bool:
    """#863 principal identifiers are bounded; oversized source values are
    unrecognized shapes, not validation failures."""

    return isinstance(value, str) and 0 < len(value) <= 200
