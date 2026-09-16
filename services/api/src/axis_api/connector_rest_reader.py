"""Host-owned bounded REST page reads implementing connector authoring protocol 1.0.

This adapter turns one approved REST source profile
(:mod:`axis_api.connector_rest_profiles`) into single governed HTTP page reads
for [#860](https://github.com/Limes-Labs/limes-axis/issues/860). Trust and
durability stay with existing owners:

* The host constructs the source with an active credential-lease and
  egress-policy evidence pair (:class:`RestSourceAuthority`) plus an already
  resolved lease-scoped bearer material. This module performs no lease,
  secret-resolution or policy lookups and adds no secret store.
* The egress policy is enforced on the actual connection: the transport is
  pinned to the approved origin, redirects are never followed and pagination
  continuations must resolve to the same origin before any request. A 3xx is
  a fixed safe failure.
* GET-only transport with explicit connect/read timeouts and hard
  wire/decoded-byte caps; responses stream under a shared deadline so a slow
  or endless source cannot exceed the configured bounds.
* Provider payloads appear only as raw records inside the returned SDK
  ``ReadBatch``. Every derived surface (progress evidence, error codes) is
  fixed metadata: no authorization headers, tokens, cursors, provider
  messages or row values.
* Failure codes stay on the protocol 1.0 SDK surface. A 401 therefore maps
  to ``SOURCE_UNAVAILABLE`` like the SDK credential fixture, with
  ``auth_failure`` evidence marking it terminal for this lease; the host's
  recovery is reauthorization. 429 and eligible 5xx report a bounded
  ``Retry-After`` hint without ever sleeping or retrying inside the adapter.
* The host owns retries, page-count admission across a traversal and durable
  checkpoint commits; this source only proposes candidate checkpoints. A page
  that exceeds its declared record/byte bounds is an honest ``truncated``
  result without a checkpoint, never a silently skipping ``more``.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self
from urllib.parse import urlencode, urlsplit

import urllib3
from axis_sdk.connector_authoring.contracts import (
    CURRENT_PROTOCOL,
    ConnectorError,
    ErrorCode,
    OperationContext,
    ReadBatch,
    ReadRequest,
    batch_byte_size,
)
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from axis_api.connector_rest_profiles import (
    NextLinkPagination,
    OpaqueCursorPagination,
    RestSourceProfile,
)

REST_ADAPTER_NAME = "axis-rest-page-source"

_ACTIVE_LEASE_STATUSES = frozenset({"lease_executed", "lease_renewed"})
_APPROVED_EGRESS_MODE = "approved_private_endpoint"
_AUTHORIZATION_HEADER = "Authorization"
_BEARER_SCHEME = "Bearer"
_CONNECT_TIMEOUT_SECONDS = 3.0
_READ_TIMEOUT_SECONDS = 15.0
_STREAM_CHUNK_BYTES = 65_536
_GZIP_WINDOW_BITS = 16 + zlib.MAX_WBITS
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_SUCCESS_STATUS = 200
_UNAUTHORIZED_STATUS = 401
_RATE_LIMITED_STATUS = 429
_RETRY_AFTER_MAX_SECONDS = 3_600
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_JSON_MEDIA_TYPES = frozenset({"application/json"})
_JSON_STRUCTURED_SUFFIX = "+json"
_PATH_PARAMETER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]{0,63})\}")
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_TRANSPORT_ERRORS = (urllib3.exceptions.HTTPError, OSError)


def _endpoint_target_sha256(origin: tuple[str, str, int]) -> str:
    scheme, hostname, port = origin
    return hashlib.sha256(f"{hostname.lower()}:{port}".encode()).hexdigest()


class RestSourceAuthority(BaseModel):
    """Fail-closed lease/policy evidence for one REST page read.

    Constructed by the host from its tenant-scoped lease and egress-policy
    records (same posture gate as the S3/live-query boundaries). Carrying
    evidence, never material, and never a repository handle.
    """

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
    allow_insecure_local: bool = False
    registered_endpoint_profile_revision: str = Field(min_length=64, max_length=64)

    @model_validator(mode="after")
    def fail_closed_posture(self) -> Self:
        if self.lease_status not in _ACTIVE_LEASE_STATUSES:
            raise ValueError("REST source requires an executed or renewed credential lease")
        if not self.lease_ref:
            raise ValueError("REST source requires provider lease reference evidence")
        if str(self.lease_secret_material_returned).strip().lower() != "false":
            raise ValueError("Lease evidence reports secret material was returned")
        if self.lease_expires_at.tzinfo is None:
            raise ValueError("Lease expiry must be timezone-aware")
        if self.egress_mode != _APPROVED_EGRESS_MODE:
            raise ValueError("REST source requires an approved private endpoint egress mode")
        if not _SHA256_PATTERN.fullmatch(self.egress_endpoint_target_sha256):
            raise ValueError("Egress endpoint binding must be a SHA-256 hex digest")
        if self.egress_endpoint_target_sha256 != _endpoint_target_sha256(self.pinned_origin):
            raise ValueError("Egress endpoint binding does not match the pinned origin")
        if not _SHA256_PATTERN.fullmatch(self.registered_endpoint_profile_revision):
            raise ValueError("Endpoint profile revision must be a SHA-256 hex digest")
        scheme, hostname, _ = self.pinned_origin
        if scheme not in {"https", "http"}:
            raise ValueError("Pinned origin must be an HTTP(S) origin")
        if scheme != "https" and not (
            self.allow_insecure_local and hostname.lower() in _LOOPBACK_HOSTS
        ):
            raise ValueError("REST source requires TLS except for explicit loopback fixtures")
        return self


@dataclass
class RestReadProgress:
    """Attempt facts shared with the host, including reads that later fail."""

    credential_lease_id: str = ""
    egress_policy_id: str = ""
    egress_target_validated: bool = False
    records_read: int = 0
    wire_bytes: int = 0
    decoded_bytes: int = 0
    completion: str = ""
    checkpoint_present: bool = False
    auth_failure: bool = False
    retry_after_seconds: int | None = None

    def evidence(self) -> dict[str, str | int | bool | None]:
        """Public-safe projection for result summaries and audit metadata."""

        return {
            "adapter": REST_ADAPTER_NAME,
            "credential_lease_id": self.credential_lease_id,
            "egress_policy_id": self.egress_policy_id,
            "egress_target_validated": self.egress_target_validated,
            "records_read": self.records_read,
            "wire_bytes": self.wire_bytes,
            "decoded_bytes": self.decoded_bytes,
            "completion": self.completion,
            "checkpoint_present": self.checkpoint_present,
            "auth_failure": self.auth_failure,
            "retry_after_seconds": self.retry_after_seconds,
        }


class _PinnedOriginTransport:
    """GET transport pinned to the approved origin; redirects are never followed."""

    def __init__(self, origin: tuple[str, str, int]):
        self._origin = origin
        self._pool = urllib3.PoolManager(
            timeout=urllib3.Timeout(connect=_CONNECT_TIMEOUT_SECONDS, read=_READ_TIMEOUT_SECONDS),
            retries=False,
            maxsize=1,
        )

    def close(self) -> None:
        self._pool.clear()

    def get(self, url: str, *, headers: dict[str, str], timeout: urllib3.Timeout):
        if _target(url) != self._origin:
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        return self._pool.urlopen(
            "GET",
            url,
            headers=headers,
            preload_content=False,
            decode_content=False,
            redirect=False,
            retries=False,
            timeout=timeout,
        )


def _target(url: str) -> tuple[str, str, int]:
    parsed = urlsplit(url)
    return (
        parsed.scheme,
        parsed.hostname or "",
        parsed.port or (443 if parsed.scheme == "https" else 80),
    )


def _render_path(template: str, path_values: dict[str, str]) -> str:
    return _PATH_PARAMETER.sub(lambda match: path_values[match.group(1)], template)


def _member(payload: object, path: tuple[str, ...]) -> object:
    current = payload
    for name in path:
        if not isinstance(current, dict) or name not in current:
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        current = current[name]
    return current


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-JSON constant {value} is not accepted")


def _query_value(value: str | int | bool) -> str:
    if type(value) is bool:
        return "true" if value else "false"
    return str(value)


def _json_content_type(content_type: str | None) -> bool:
    if not content_type:
        return False
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type in _JSON_MEDIA_TYPES or (
        media_type.startswith("application/") and media_type.endswith(_JSON_STRUCTURED_SUFFIX)
    )


def _bounded_retry_after(value: str | None) -> int | None:
    if not value or not value.strip().isdigit():
        return None
    seconds = int(value.strip())
    if not 1 <= seconds <= _RETRY_AFTER_MAX_SECONDS:
        return None
    return seconds


def _canonical_record_bytes(record: dict) -> int:
    return batch_byte_size((record,)) - 2


class RestPageSource:
    """Reads one governed page per ``read()`` call; the host commits progress."""

    def __init__(
        self,
        *,
        profile: RestSourceProfile,
        authority: RestSourceAuthority,
        credential_bearer: SecretStr,
        path_values: dict[str, str],
        query_values: dict[str, str | int | bool],
        clock=time.monotonic,
        transport_factory=None,
    ):
        if authority.registered_endpoint_profile_revision != profile.endpoint_profile_revision:
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        self.profile = profile
        self.authority = authority
        self.credential_bearer = credential_bearer
        self.path_values = dict(path_values)
        self.query_values = dict(query_values)
        self.clock = clock
        self.transport_factory = transport_factory or _PinnedOriginTransport
        self.transport = self.transport_factory(authority.pinned_origin)
        self.progress = RestReadProgress(
            credential_lease_id=authority.credential_lease_id,
            egress_policy_id=authority.egress_policy_id,
        )
        self._deadline: float | None = None

    def __repr__(self) -> str:
        return (
            f"RestPageSource(collection_id={self.profile.collection_id!r}, "
            f"tenant_id={self.authority.tenant_id!r}, "
            f"connector_id={self.authority.connector_id!r})"
        )

    def close(self) -> None:
        self.transport.close()

    def __enter__(self) -> RestPageSource:
        return self

    def __exit__(self, *exception: object) -> None:
        self.close()

    def read(self, request: ReadRequest) -> ReadBatch:
        self.progress = RestReadProgress(
            credential_lease_id=self.authority.credential_lease_id,
            egress_policy_id=self.authority.egress_policy_id,
        )
        self._context(request.context)
        # Also binds path/query values: resume_cursor validates the selection
        # digest even when no checkpoint is present.
        token = self.profile.resume_cursor(
            request, path_values=self.path_values, query_values=self.query_values
        )
        deadline = self.clock() + min(
            request.limits.time_budget_seconds,
            self.profile.limits.page.time_budget_seconds,
        )
        self._check_deadline(deadline)
        try:
            return self._page(request, token, deadline)
        except _TRANSPORT_ERRORS:
            # Neither source messages nor chained exceptions are evidence.
            raise ConnectorError(ErrorCode.SOURCE_UNAVAILABLE) from None

    def _context(self, context: OperationContext) -> None:
        if (
            context.protocol != CURRENT_PROTOCOL
            or context.tenant_id != self.authority.tenant_id
            or context.connector_id != self.authority.connector_id
        ):
            raise ConnectorError(ErrorCode.CONTEXT_MISMATCH)
        if datetime.now(UTC) >= self.authority.lease_expires_at:
            raise ConnectorError(ErrorCode.CONTEXT_MISMATCH)
        self.progress.egress_target_validated = True

    def _check_deadline(self, deadline: float) -> None:
        if self.clock() >= deadline:
            raise ConnectorError(ErrorCode.TIME_BUDGET_EXCEEDED)

    def _timeout(self, deadline: float) -> urllib3.Timeout:
        remaining = deadline - self.clock()
        if remaining <= 0:
            raise ConnectorError(ErrorCode.TIME_BUDGET_EXCEEDED)
        return urllib3.Timeout(
            total=remaining,
            connect=min(_CONNECT_TIMEOUT_SECONDS, remaining),
            read=min(_READ_TIMEOUT_SECONDS, remaining),
        )

    def _headers(self) -> dict[str, str]:
        return {
            _AUTHORIZATION_HEADER: f"{_BEARER_SCHEME} {self.credential_bearer.get_secret_value()}",
            "Accept": "application/json",
            "Accept-Encoding": "identity",
        }

    def _page_url(self, token: SecretStr | None) -> str:
        scheme, hostname, port = self.authority.pinned_origin
        default_port = 443 if scheme == "https" else 80
        # IPv6 literals need brackets in URL authority positions.
        host = f"[{hostname}]" if ":" in hostname else hostname
        base = f"{scheme}://{host}"
        if port != default_port:
            base = f"{base}:{port}"
        if token is None:
            parameters = {name: _query_value(value) for name, value in self.query_values.items()}
        elif isinstance(self.profile.pagination, OpaqueCursorPagination):
            parameters = {
                **{name: _query_value(value) for name, value in self.query_values.items()},
                self.profile.pagination.parameter: token.get_secret_value(),
            }
        else:
            return self._same_origin_link(token)
        path = _render_path(self.profile.path_template, self.path_values)
        return f"{base}{path}?{urlencode(parameters)}"

    def _same_origin_link(self, token: SecretStr) -> str:
        link = token.get_secret_value()
        self._validate_same_origin(link)
        return link

    def _validate_same_origin(self, link: str) -> None:
        # Continuations are validated before any request, so a disallowed
        # pagination origin is never dialed and never receives credentials.
        if _target(link) != self.authority.pinned_origin:
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)

    def _page(self, request: ReadRequest, token: SecretStr | None, deadline: float) -> ReadBatch:
        limits = self.profile.limits
        max_records = min(request.limits.max_records, limits.page.max_records)
        max_bytes = min(request.limits.max_bytes, limits.page.max_bytes)
        self._deadline = deadline
        response = self.transport.get(
            self._page_url(token), headers=self._headers(), timeout=self._timeout(deadline)
        )
        try:
            if response.status in _REDIRECT_STATUSES:
                # A redirect target was never dialed and never received credentials.
                raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
            if response.status != _SUCCESS_STATUS:
                self._failure_status(response.status, response.headers.get("Retry-After"))
            payload = self._bounded_payload(
                response, limits.max_wire_bytes, limits.max_decoded_bytes
            )
        finally:
            response.close()
            response.release_conn()
        records, continuation = self._records(payload, max_records, max_bytes)
        batch = self._batch(request, records, continuation)
        batch.validate_for(request)
        self.progress.records_read = len(batch.records)
        self.progress.completion = batch.completion
        self.progress.checkpoint_present = batch.checkpoint is not None
        return batch

    def _batch(
        self, request: ReadRequest, records: list[dict] | None, continuation: str | None
    ) -> ReadBatch:
        if records is None:
            # A capped page drops unread source records; it is unresumable and
            # must never advertise progress that would skip them.
            return ReadBatch(records=(), completion="truncated")
        checkpoint = None
        completion = "complete"
        if continuation is not None:
            completion = "more"
            checkpoint = self.profile.checkpoint(
                request.context,
                request.resource,
                SecretStr(continuation),
                path_values=self.path_values,
                query_values=self.query_values,
            )
        return ReadBatch(records=tuple(records), completion=completion, checkpoint=checkpoint)

    def _failure_status(self, status: int, retry_after: str | None) -> None:
        if status == _UNAUTHORIZED_STATUS:
            # Protocol 1.0 reports source unavailability; the auth_failure
            # evidence flag marks this lease terminal so the host can
            # reauthorize instead of retrying.
            self.progress.auth_failure = True
            raise ConnectorError(ErrorCode.SOURCE_UNAVAILABLE)
        if status == _RATE_LIMITED_STATUS:
            self.progress.retry_after_seconds = _bounded_retry_after(retry_after)
            raise ConnectorError(ErrorCode.RATE_LIMITED)
        if status >= 500:
            self.progress.retry_after_seconds = _bounded_retry_after(retry_after)
            raise ConnectorError(ErrorCode.SOURCE_UNAVAILABLE)
        raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)

    def _bounded_payload(self, response, max_wire_bytes: int, max_decoded_bytes: int) -> bytes:
        if not _json_content_type(response.headers.get("Content-Type")):
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        encoding = (response.headers.get("Content-Encoding") or "").strip().lower()
        if encoding not in {"", "identity", "gzip"}:
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        declared_length = response.headers.get("Content-Length", "")
        if declared_length.isdigit() and int(declared_length) > max_wire_bytes:
            raise ConnectorError(ErrorCode.LIMIT_EXCEEDED)
        decoder = zlib.decompressobj(_GZIP_WINDOW_BITS) if encoding == "gzip" else None
        decoded = bytearray()
        wire = 0
        while True:
            self._check_deadline(self._deadline)
            remaining_wire = max_wire_bytes - wire
            if remaining_wire <= 0:
                raise ConnectorError(ErrorCode.LIMIT_EXCEEDED)
            chunk = response.read(min(_STREAM_CHUNK_BYTES, remaining_wire), decode_content=False)
            if not chunk:
                break
            wire += len(chunk)
            self.progress.wire_bytes = wire
            if decoder is None:
                if len(decoded) + len(chunk) > max_decoded_bytes:
                    raise ConnectorError(ErrorCode.LIMIT_EXCEEDED)
                decoded += chunk
                continue
            decoded += self._bounded_gzip(decoder, chunk, max_decoded_bytes - len(decoded))
        if decoder is not None and not decoder.eof:
            raise ConnectorError(ErrorCode.SOURCE_UNAVAILABLE)
        self.progress.decoded_bytes = len(decoded)
        return bytes(decoded)

    @staticmethod
    def _bounded_gzip(decoder: zlib.decompressobj, chunk: bytes, budget: int) -> bytes:
        if budget <= 0:
            raise ConnectorError(ErrorCode.LIMIT_EXCEEDED)
        try:
            output = decoder.decompress(chunk, budget)
        except zlib.error:
            raise ConnectorError(ErrorCode.SOURCE_UNAVAILABLE) from None
        # A non-empty tail means the stream exceeded the decoded budget; the
        # honest response is a hard stop, not a silently capped document.
        if decoder.unconsumed_tail:
            raise ConnectorError(ErrorCode.LIMIT_EXCEEDED)
        if decoder.unused_data:
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        return output

    def _records(
        self, payload: bytes, max_records: int, max_bytes: int
    ) -> tuple[list[dict] | None, str | None]:
        try:
            document = json.loads(payload, parse_constant=_reject_constant)
        except (ValueError, UnicodeDecodeError):
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH) from None
        if not isinstance(document, dict):
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        items = _member(document, self.profile.records_path)
        if not isinstance(items, list):
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        continuation = self._continuation(document)
        records: list[dict] = []
        used_bytes = 2  # Canonical JSON array brackets; append costs include commas.
        for item in items:
            if not isinstance(item, dict):
                raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
            record_bytes = _canonical_record_bytes(item)
            if record_bytes + 2 > max_bytes:
                raise ConnectorError(ErrorCode.RECORD_TOO_LARGE)
            if len(records) >= max_records or (
                used_bytes + (1 if records else 0) + record_bytes > max_bytes
            ):
                return None, None
            records.append(item)
            used_bytes += (1 if len(records) > 1 else 0) + record_bytes
        return records, continuation

    def _continuation(self, document: dict) -> str | None:
        current: object = document
        path = self.profile.pagination.next_path
        for name in path[:-1]:
            if not isinstance(current, dict) or name not in current:
                return None
            current = current[name]
        if not isinstance(current, dict) or path[-1] not in current:
            # A page without a continuation member ends the traversal.
            return None
        value = current[path[-1]]
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ConnectorError(ErrorCode.RESOURCE_MISMATCH)
        if isinstance(self.profile.pagination, NextLinkPagination):
            self._validate_same_origin(value)
        return value
