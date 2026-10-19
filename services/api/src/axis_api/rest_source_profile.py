"""Deployment-owned REST collection bindings; construction neither authorizes nor dials.

This is the host side of the #859 REST profile contract: it binds an opaque
declared collection to one approved HTTP(S) origin, lease-scoped credential
reference, typed selection values and the SDK protocol range the deployment
implements. It contains no credentials, no headers and no executable selector;
resolving material, checking lease/policy evidence and committing checkpoints
stay with the existing host owners.
"""

from __future__ import annotations

import hashlib
import json
from typing import Annotated
from urllib.parse import urlsplit

from axis_sdk.connector_authoring.contracts import (
    Capability,
    ProtocolRange,
)
from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from axis_api.connector_rest_profiles import RestSourceProfile

REST_SOURCE_CONNECTOR_ID = "rest_collection_source"

# Deliberate observation provenance: a REST binding is activated against the
# profile's DECLARED schema, not against provider discovery execution.
REST_DECLARED_OBSERVATION_KIND = "rest_declared_schema"

_PATH_VALUE = r"^[A-Za-z0-9._~-]+$"
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

ParameterValue = str | int | bool
QueryValues = Annotated[dict[str, ParameterValue], Field(max_length=32)]


class RestHostProfile(BaseModel):
    """One declared collection plus the host authority it must be bound to."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    tenant_id: str = Field(min_length=1, max_length=80)
    profile_id: str = Field(min_length=1, max_length=180)
    display_name: str = Field(default="REST collection", min_length=1, max_length=180)
    endpoint: str = Field(min_length=1, max_length=300)
    source: RestSourceProfile
    path_values: dict[str, str] = Field(default_factory=dict)
    query_values: QueryValues = Field(default_factory=dict)
    credential_secret_ref: str = Field(pattern=r"^env://[A-Z][A-Z0-9_]*$")
    private_endpoint_ref: str = Field(min_length=1, max_length=200)
    allow_insecure_local: bool = False
    protocol: ProtocolRange = Field(default_factory=ProtocolRange)
    capabilities: frozenset[Capability] = Field(default_factory=lambda: frozenset({"read"}))

    @model_validator(mode="after")
    def bounded_binding(self):
        target = urlsplit(self.endpoint)
        if (
            target.scheme not in {"https", "http"}
            or not target.hostname
            or target.username is not None
            or target.password is not None
            or target.path not in {"", "/"}
            or target.query
            or target.fragment
        ):
            raise ValueError("REST endpoint must be an HTTP(S) origin without credentials")
        _ = target.port  # Reject invalid ports before any client can be constructed.
        if target.scheme != "https" and not (
            self.allow_insecure_local and target.hostname.lower() in _LOOPBACK_HOSTS
        ):
            raise ValueError("REST source requires TLS except for explicit loopback fixtures")
        if "read" not in self.capabilities:
            raise ValueError("REST source must declare the read capability")
        # Bind selection values through the same rules the reader enforces so a
        # misconfigured profile fails at startup, not mid-page.
        self.source.selection_digest(
            path_values=self.path_values, query_values=self.query_values
        )
        return self

    @field_serializer("source")
    def _dump_source(self, value: RestSourceProfile) -> dict:
        """Emit JSON-shaped member paths so the flat env contract round-trips."""
        return value.model_dump(mode="json")

    @field_serializer("capabilities")
    def _dump_capabilities(self, value: frozenset) -> list[str]:
        return sorted(value)

    @property
    def revision(self) -> str:
        encoded = json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    @property
    def resource_name(self) -> str:
        # A scope change requires a new declared observation and explicit activation.
        return f"rest.collection_{self.revision}"

    @property
    def endpoint_target_sha256(self) -> str:
        target = urlsplit(self.endpoint)
        port = target.port or (443 if target.scheme == "https" else 80)
        return hashlib.sha256(f"{target.hostname.lower()}:{port}".encode()).hexdigest()

    @property
    def pinned_origin(self) -> tuple[str, str, int]:
        target = urlsplit(self.endpoint)
        port = target.port or (443 if target.scheme == "https" else 80)
        return (target.scheme, target.hostname or "", port)


def parse_rest_host_profile(value: object) -> RestHostProfile:
    """Map untrusted configuration errors to a fixed shape, never raw errors."""

    from axis_sdk.connector_authoring.contracts import ConnectorError, ErrorCode

    try:
        return RestHostProfile.model_validate(value)
    except Exception:
        raise ConnectorError(ErrorCode.RESOURCE_MISMATCH) from None
