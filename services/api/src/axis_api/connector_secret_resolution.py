"""Lease-scoped secret resolution for connector live queries.

This module is the fail-closed boundary between lease *evidence* (checked and
persisted everywhere else) and lease-scoped secret *material* (resolved here,
held in memory only, and handed straight to the database driver).

Invariants:

* Secret material is resolved only for an ACTIVE lease (``lease_executed`` /
  ``lease_renewed``) whose credential access mode is
  ``lease_scoped_secret_ref`` and whose lease evidence reports
  ``secret_material_returned=false``.
* Resolved material lives in a :class:`ResolvedSecret` that is never a
  pydantic model, never serialized, never logged (``repr`` is redacted) and
  never copied into any persisted or audited payload. Only
  :meth:`ResolvedSecret.public_evidence` — decision and boundary metadata —
  may be persisted.
* The only public-safe live resolver is the ``env://`` provider profile
  (:class:`EnvLeaseScopedSecretResolver`). Vault/AWS/GCP/Azure provider
  profiles are explicit fail-closed not-implemented branches with typed
  reasons, so a misconfigured deployment can never silently fall back to an
  unreviewed secret path.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

SECRET_RESOLUTION_RUNTIME_BOUNDARY = "axis-lease-scoped-secret-resolver"
RESOLVED_LEASE_SCOPED_SECRET_DECISION = "resolved_lease_scoped_secret"
LEASE_SCOPED_CREDENTIAL_ACCESS_MODE = "lease_scoped_secret_ref"
ACTIVE_LEASE_RESULT_STATUSES = frozenset({"lease_executed", "lease_renewed"})
ENV_SECRET_REF_SCHEME = "env://"
ENV_PROVIDER_PROFILE = "env"
ENV_PROVIDER_ALIASES = frozenset({"env", "env_dev", "local_env"})
ENV_VAR_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
NOT_IMPLEMENTED_PROVIDER_PROFILES: dict[str, frozenset[str]] = {
    "hashicorp_vault": frozenset({"external_vault", "hashicorp_vault", "vault", "vault_dev"}),
    "aws_secrets_manager": frozenset({"aws_secrets_manager"}),
    "gcp_secret_manager": frozenset({"gcp_secret_manager"}),
    "azure_key_vault": frozenset({"azure_key_vault"}),
}

SECRET_RESOLUTION_RESOLVER_NOT_CONFIGURED = "secret_resolution_resolver_not_configured"
SECRET_RESOLUTION_UNSUPPORTED_ACCESS_MODE = "secret_resolution_unsupported_access_mode"
SECRET_RESOLUTION_LEASE_NOT_ACTIVE = "secret_resolution_lease_not_active"
SECRET_RESOLUTION_LEASE_REF_MISSING = "secret_resolution_lease_ref_missing"
SECRET_RESOLUTION_SECRET_MATERIAL_RETURNED = "secret_resolution_secret_material_returned"
SECRET_RESOLUTION_PROVIDER_NOT_IMPLEMENTED = "secret_resolution_provider_not_implemented"
SECRET_RESOLUTION_UNKNOWN_PROVIDER = "secret_resolution_unknown_provider"
SECRET_RESOLUTION_MALFORMED_SECRET_REF = "secret_resolution_malformed_secret_ref"
SECRET_RESOLUTION_ENV_SECRET_NOT_CONFIGURED = "secret_resolution_env_secret_not_configured"


class SecretResolutionError(Exception):
    """Fail-closed lease-scoped secret resolution failure with a typed reason."""

    def __init__(self, reason: str, message: str, *, provider_profile: str = "") -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.provider_profile = provider_profile


class SecretResolutionRequest(BaseModel):
    """Lease evidence handed to a resolver. Contains references only, never material."""

    model_config = ConfigDict(extra="forbid")

    connector_id: str = Field(min_length=1)
    connection_profile_id: str = ""
    credential_access_mode: str = ""
    secret_provider: str = ""
    secret_ref: str = ""
    lease_status: str = ""
    lease_ref: str = ""
    # Fail closed: absent evidence is treated as if material had been returned.
    secret_material_returned: str = "true"


class ResolvedSecret:
    """In-memory-only resolved secret material.

    Deliberately not a pydantic model: it cannot be ``model_dump``-ed into an
    audit payload or result summary by accident. ``repr`` never includes the
    material. Only :meth:`public_evidence` may be persisted.
    """

    __slots__ = ("_dsn", "provider_profile")

    def __init__(self, *, dsn: str, provider_profile: str) -> None:
        self._dsn = dsn
        self.provider_profile = provider_profile

    @property
    def dsn(self) -> str:
        return self._dsn

    def __repr__(self) -> str:
        return f"ResolvedSecret(provider_profile={self.provider_profile!r}, dsn='[redacted]')"

    def public_evidence(self) -> dict[str, str]:
        """Public-safe resolution evidence for result summaries and stage audits."""
        return {
            "secret_retrieval_decision": RESOLVED_LEASE_SCOPED_SECRET_DECISION,
            "secret_resolution_provider_profile": self.provider_profile,
            "secret_resolution_runtime_boundary": SECRET_RESOLUTION_RUNTIME_BOUNDARY,
        }


class LeaseScopedSecretResolver(Protocol):
    """Resolves a DSN from (secret reference, lease evidence), fail closed."""

    provider_profile: str

    def resolve(self, request: SecretResolutionRequest) -> ResolvedSecret:
        ...


class EnvLeaseScopedSecretResolver:
    """Resolves ``env://VAR_NAME`` secret references from process environment.

    This is the only public-safe live resolver profile: the deployment operator
    injects the DSN into the runtime environment (typically from a Kubernetes
    secret), and the resolver returns it in memory only after the full
    lease-evidence gate passes.
    """

    provider_profile = ENV_PROVIDER_PROFILE

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ: Mapping[str, str] = os.environ if environ is None else environ

    def resolve(self, request: SecretResolutionRequest) -> ResolvedSecret:
        _validate_lease_scoped_evidence(request)
        _validate_env_provider_profile(request.secret_provider)
        variable_name = _env_variable_name(request.secret_ref)
        value = self._environ.get(variable_name, "")
        if not value:
            raise SecretResolutionError(
                SECRET_RESOLUTION_ENV_SECRET_NOT_CONFIGURED,
                (
                    f"Environment secret reference {ENV_SECRET_REF_SCHEME}{variable_name} "
                    "is not configured in the runtime environment; failing closed."
                ),
                provider_profile=ENV_PROVIDER_PROFILE,
            )
        return ResolvedSecret(dsn=value, provider_profile=ENV_PROVIDER_PROFILE)


def _validate_lease_scoped_evidence(request: SecretResolutionRequest) -> None:
    if request.credential_access_mode != LEASE_SCOPED_CREDENTIAL_ACCESS_MODE:
        raise SecretResolutionError(
            SECRET_RESOLUTION_UNSUPPORTED_ACCESS_MODE,
            "Lease-scoped secret resolution requires the "
            "lease_scoped_secret_ref credential access mode.",
        )
    if request.lease_status not in ACTIVE_LEASE_RESULT_STATUSES:
        raise SecretResolutionError(
            SECRET_RESOLUTION_LEASE_NOT_ACTIVE,
            "Lease-scoped secret resolution requires an executed or renewed "
            "credential lease.",
        )
    if not request.lease_ref:
        raise SecretResolutionError(
            SECRET_RESOLUTION_LEASE_REF_MISSING,
            "Lease-scoped secret resolution requires provider lease reference evidence.",
        )
    if str(request.secret_material_returned).lower() != "false":
        raise SecretResolutionError(
            SECRET_RESOLUTION_SECRET_MATERIAL_RETURNED,
            "Lease evidence reports secret material was returned; failing closed.",
        )


def _validate_env_provider_profile(secret_provider: str) -> None:
    normalized = secret_provider.strip().lower().replace("-", "_")
    if normalized in ENV_PROVIDER_ALIASES:
        return
    for canonical_profile, aliases in NOT_IMPLEMENTED_PROVIDER_PROFILES.items():
        if normalized in aliases:
            raise SecretResolutionError(
                SECRET_RESOLUTION_PROVIDER_NOT_IMPLEMENTED,
                (
                    f"Lease-scoped secret resolution for the {canonical_profile} "
                    "provider profile is not implemented; failing closed."
                ),
                provider_profile=canonical_profile,
            )
    raise SecretResolutionError(
        SECRET_RESOLUTION_UNKNOWN_PROVIDER,
        "Lease-scoped secret resolution does not recognize the credential "
        "secret provider profile; failing closed.",
    )


def _env_variable_name(secret_ref: str) -> str:
    reference = secret_ref.strip()
    if not reference.startswith(ENV_SECRET_REF_SCHEME):
        raise SecretResolutionError(
            SECRET_RESOLUTION_MALFORMED_SECRET_REF,
            "Environment secret references must use the env:// scheme.",
            provider_profile=ENV_PROVIDER_PROFILE,
        )
    variable_name = reference[len(ENV_SECRET_REF_SCHEME) :]
    if not ENV_VAR_NAME_PATTERN.fullmatch(variable_name):
        raise SecretResolutionError(
            SECRET_RESOLUTION_MALFORMED_SECRET_REF,
            "Environment secret references must name an uppercase environment variable.",
            provider_profile=ENV_PROVIDER_PROFILE,
        )
    return variable_name
