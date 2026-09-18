"""Offline (zero-egress) readiness: configured posture versus observed evidence.

[#871](https://github.com/Limes-Labs/limes-axis/issues/871) (parent #473, builds
on #869 and #870). Deployment readiness in
[`deployment_readiness.py`](deployment_readiness.py) reports whether configuration
and runbooks *exist*. This module keeps three distinct concepts apart and never
conflates them:

- **configured**: the operator declared an offline profile and its approved local
  bindings, and configuration validation accepted them.
- **observed in a rehearsal**: a bounded local rehearsal-artifact reference
  matches the live profile digest, release identity and capture window.
- **externally accredited**: not established here, ever.

Nothing in this module probes the network, mutates firewall state or trusts a
caller-supplied ``verified`` flag. It reads declared configuration, computes a
profile digest over public-safe material facts and validates a declared
rehearsal-artifact reference. Missing, malformed, tampered, stale or mismatched
evidence is reported as unverified, never as observed. The report never contains
endpoint values, secret material or file contents: endpoint locality is resolved
through operator-approved local bindings, not through address text.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from axis_api import __version__
from axis_api.config import Settings

OFFLINE_EGRESS_MODES = frozenset({"offline", "local_only"})

# Requirement classes are the #869 dependency ids. Required dependencies must be
# locally bound for an offline profile to validate; optional ones may be disabled
# and are then reported with the configuration that disables them.
REQUIRED_OFFLINE_DEPENDENCIES: tuple[str, ...] = (
    "artifact-object-store",
    "identity-validation",
    "operational-database",
    "workflow-engine",
)
OPTIONAL_OFFLINE_DEPENDENCIES: tuple[str, ...] = (
    "distributed-rate-limit",
    "external-database-source",
    "model-inference",
    "ontology-store",
    "s3-input",
    "telemetry-export",
)

OFFLINE_PROFILE_SCHEMA = "axis.offline-profile.v1"
OFFLINE_REHEARSAL_MAX_AGE_SECONDS = 90 * 24 * 60 * 60
OFFLINE_REHEARSAL_FUTURE_SKEW_SECONDS = 300
SHA256_HEX_LENGTH = 64
MANIFEST_REVISION_LENGTH = 40

REHEARSAL_EVIDENCE_FIELDS: tuple[str, ...] = (
    "ref",
    "release",
    "profile_digest",
    "captured_at",
    "scope",
    "result_digest",
)

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
_MANIFEST_REVISION = re.compile(r"^[0-9a-f]{40}$")
_DEPENDENCY_ID = re.compile(r"^[a-z][a-z0-9-]{0,79}$")
# Approved local bindings are opaque references, not endpoints: the existing
# external-database live-query binding uses the same private-endpoint convention.
_BINDING_REFERENCE = re.compile(r"^[a-z][a-z0-9+.-]*://[^@?#\s]{1,200}$")
_FORBIDDEN_BINDING_SCHEMES = ("http://", "https://", "file://", "ftp://")


class OfflineOmittedCapability(BaseModel):
    dependency_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class OfflineDependencyBinding(BaseModel):
    dependency_id: str = Field(min_length=1)
    requirement: Literal["required", "optional"]
    state: Literal["local", "external", "disabled"]
    detail: str = Field(min_length=1)


class OfflineConfigurationValidation(BaseModel):
    state: Literal["not_evaluated", "valid", "invalid"]
    local_bindings: list[str]
    blockers: list[str]
    omitted_capabilities: list[OfflineOmittedCapability]
    dependencies: list[OfflineDependencyBinding]


class OfflineObservedEvidence(BaseModel):
    state: Literal[
        "not_run",
        "incomplete",
        "malformed",
        "tampered",
        "mismatched",
        "stale",
        "matched",
    ]
    detail: str = Field(min_length=1)
    reference: str | None = None
    tested_release_identity: str | None = None
    tested_profile_digest: str | None = None
    captured_at: str | None = None
    environment_scope: str | None = None
    age_seconds: int | None = None

    @property
    def matched(self) -> bool:
        return self.state == "matched"


class OfflineReadinessSection(BaseModel):
    """Additive offline-readiness section of the deployment readiness report."""

    state: Literal[
        "not_declared",
        "action_required",
        "configured_unverified",
        "verified_in_rehearsal",
    ]
    declared: bool
    egress_mode: str = Field(min_length=1)
    release_identity: str = Field(min_length=1)
    profile_digest: str = Field(min_length=1)
    dependency_manifest_revision: str | None = None
    configuration: OfflineConfigurationValidation
    observed_evidence: OfflineObservedEvidence
    notes: list[str]


def resolve_release_identity(settings: Settings) -> str:
    """Declared release identity, falling back to the application build."""
    return settings.deployment_release_identity.strip() or __version__


def _canonical_json(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256_hex(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def parse_local_bindings(entries: list[str]) -> tuple[dict[str, str], list[str]]:
    """Parse ``dependency=reference`` bindings. Returns (bindings, blocker_codes).

    Blocker codes never echo a reference, so a malformed value cannot leak
    endpoint text into the readiness response.
    """
    bindings: dict[str, str] = {}
    blockers: list[str] = []
    for index, raw in enumerate(entries):
        entry = raw.strip()
        dependency_id, separator, reference = entry.partition("=")
        dependency_id = dependency_id.strip()
        reference = reference.strip()
        if not separator or not _DEPENDENCY_ID.match(dependency_id):
            blockers.append(f"malformed_local_binding:{index}")
            continue
        if dependency_id not in REQUIRED_OFFLINE_DEPENDENCIES + OPTIONAL_OFFLINE_DEPENDENCIES:
            blockers.append(f"unknown_binding_dependency:{dependency_id}")
            continue
        if dependency_id in bindings:
            blockers.append(f"duplicate_binding_dependency:{dependency_id}")
            continue
        forbidden = reference.casefold().startswith(_FORBIDDEN_BINDING_SCHEMES)
        if forbidden or not _BINDING_REFERENCE.match(reference):
            blockers.append(f"invalid_binding_reference:{dependency_id}")
            continue
        bindings[dependency_id] = reference
    return bindings, blockers


def offline_profile_facts(
    *,
    egress_mode: str,
    release_identity: str,
    dependency_manifest_revision: str,
    bindings: dict[str, str],
) -> dict[str, object]:
    """Public-safe material facts bound into the profile digest.

    Only dependency ids and opaque binding references are included: no resolved
    endpoint, DSN, issuer or credential value enters the digest, so the exposed
    digest cannot be used to recover configuration values. Changing an approved
    binding reference changes the digest, which invalidates prior evidence.
    """
    return {
        "schema": OFFLINE_PROFILE_SCHEMA,
        "egress_mode": egress_mode,
        "release_identity": release_identity,
        "dependency_manifest_revision": dependency_manifest_revision,
        "local_bindings": {key: bindings[key] for key in sorted(bindings)},
        "required_dependencies": list(REQUIRED_OFFLINE_DEPENDENCIES),
        "optional_dependencies": list(OPTIONAL_OFFLINE_DEPENDENCIES),
    }


def offline_profile_digest(
    *,
    egress_mode: str,
    release_identity: str,
    dependency_manifest_revision: str,
    bindings: dict[str, str],
) -> str:
    return _sha256_hex(
        offline_profile_facts(
            egress_mode=egress_mode,
            release_identity=release_identity,
            dependency_manifest_revision=dependency_manifest_revision,
            bindings=bindings,
        )
    )


def rehearsal_result_digest(declared: Mapping[str, str]) -> str:
    """Consistency binding over the declared evidence header.

    Detects an edited or partially copied reference; it is not a signature and
    establishes no provenance or accreditation.
    """
    payload = {
        field: declared[field]
        for field in REHEARSAL_EVIDENCE_FIELDS
        if field != "result_digest"
    }
    return _sha256_hex(payload)


def _dependency_state(settings: Settings, dependency_id: str) -> tuple[bool, str]:
    """Return ``(active, disabled_reason)`` for one inventory dependency."""
    match dependency_id:
        case "operational-database":
            return True, ""
        case "workflow-engine":
            if settings.temporal_address.strip():
                return True, ""
            return False, "AXIS_TEMPORAL_ADDRESS is not configured."
        case "identity-validation":
            if settings.oidc_auth_required or settings.oidc_issuer.strip():
                return True, ""
            return (
                False,
                "OIDC authentication is disabled "
                "(AXIS_OIDC_AUTH_REQUIRED=false and AXIS_OIDC_ISSUER is not configured).",
            )
        case "artifact-object-store":
            if settings.connector_export_object_store_adapter == "local_filesystem":
                return (
                    False,
                    "AXIS_CONNECTOR_EXPORT_OBJECT_STORE_ADAPTER=local_filesystem uses a "
                    "local replacement instead of an object-storage service.",
                )
            return True, ""
        case "distributed-rate-limit":
            if settings.api_rate_limit_enabled and settings.api_rate_limit_backend == "redis":
                return True, ""
            return (
                False,
                "AXIS_API_RATE_LIMIT_ENABLED is false or "
                "AXIS_API_RATE_LIMIT_BACKEND is memory.",
            )
        case "model-inference":
            if settings.external_model_egress_enabled or settings.model_routing_execution_enabled:
                return True, ""
            return (
                False,
                "External model egress and model routing execution are disabled by "
                "configuration.",
            )
        case "ontology-store":
            if settings.ontology_queries_enabled or settings.ontology_mutations_enabled:
                return True, ""
            return (
                False,
                "Ontology queries and mutations are disabled by configuration.",
            )
        case "telemetry-export":
            if settings.otel_enabled:
                return True, ""
            return False, "OpenTelemetry export is disabled (AXIS_OTEL_ENABLED=false)."
        case "s3-input":
            if settings.s3_source_ingestion_enabled:
                return True, ""
            return (
                False,
                "S3 source ingestion is disabled (AXIS_S3_SOURCE_INGESTION_ENABLED=false).",
            )
        case "external-database-source":
            if (
                settings.external_db_discovery_enabled
                or settings.external_db_sync_execution_enabled
                or settings.external_db_live_query_execution_enabled
            ):
                return True, ""
            return (
                False,
                "External database discovery, sync and live query execution are "
                "disabled by configuration.",
            )
    return False, "The dependency is not part of the offline readiness catalogue."


def _evaluate_configuration(
    settings: Settings,
    *,
    bindings: dict[str, str],
    binding_blockers: list[str],
    manifest_revision: str,
) -> OfflineConfigurationValidation:
    blockers = list(binding_blockers)
    if not manifest_revision:
        blockers.append("dependency_manifest_revision_not_declared")
    elif not _MANIFEST_REVISION.match(manifest_revision):
        blockers.append("dependency_manifest_revision_not_a_git_revision")

    dependencies: list[OfflineDependencyBinding] = []
    omitted: list[OfflineOmittedCapability] = []
    for dependency_id in REQUIRED_OFFLINE_DEPENDENCIES + OPTIONAL_OFFLINE_DEPENDENCIES:
        requirement: Literal["required", "optional"] = (
            "required" if dependency_id in REQUIRED_OFFLINE_DEPENDENCIES else "optional"
        )
        if dependency_id in bindings:
            dependencies.append(
                OfflineDependencyBinding(
                    dependency_id=dependency_id,
                    requirement=requirement,
                    state="local",
                    detail=(
                        "The dependency is bound to an operator-approved local binding for "
                        "this offline profile."
                    ),
                )
            )
            continue
        active, disabled_reason = _dependency_state(settings, dependency_id)
        if not active:
            dependencies.append(
                OfflineDependencyBinding(
                    dependency_id=dependency_id,
                    requirement=requirement,
                    state="disabled",
                    detail=disabled_reason,
                )
            )
            omitted.append(
                OfflineOmittedCapability(dependency_id=dependency_id, reason=disabled_reason)
            )
            continue
        dependencies.append(
            OfflineDependencyBinding(
                dependency_id=dependency_id,
                requirement=requirement,
                state="external",
                detail=(
                    "The dependency is active but is not declared as an approved local "
                    "binding, so the offline profile cannot validate it."
                ),
            )
        )
        blockers.append(f"{requirement}_dependency_not_locally_bound:{dependency_id}")

    return OfflineConfigurationValidation(
        state="invalid" if blockers else "valid",
        local_bindings=sorted(bindings),
        blockers=sorted(blockers),
        omitted_capabilities=omitted,
        dependencies=dependencies,
    )


def _evaluate_evidence(
    settings: Settings,
    *,
    now: datetime,
    release_identity: str,
    profile_digest: str,
) -> OfflineObservedEvidence:
    raw = settings.offline_rehearsal_evidence.strip()
    if not raw:
        return OfflineObservedEvidence(
            state="not_run",
            detail=(
                "No local rehearsal artifact reference is configured, so isolation is "
                "configured but unverified."
            ),
        )
    try:
        declared = json.loads(raw)
    except json.JSONDecodeError:
        return OfflineObservedEvidence(
            state="malformed",
            detail="The rehearsal artifact reference is not valid JSON.",
        )
    if not isinstance(declared, dict):
        return OfflineObservedEvidence(
            state="malformed",
            detail="The rehearsal artifact reference must be a JSON object.",
        )
    missing = [
        field
        for field in REHEARSAL_EVIDENCE_FIELDS
        if not isinstance(declared.get(field), str) or not str(declared.get(field)).strip()
    ]
    if missing:
        return OfflineObservedEvidence(
            state="incomplete",
            detail=(
                "The rehearsal artifact reference is missing declared fields: "
                f"{', '.join(sorted(missing))}."
            ),
        )

    evidence = {field: str(declared[field]).strip() for field in REHEARSAL_EVIDENCE_FIELDS}
    reference = evidence["ref"]
    scope = evidence["scope"]

    captured_at = _parse_timestamp(evidence["captured_at"])
    if captured_at is None:
        return OfflineObservedEvidence(
            state="malformed",
            detail="The rehearsal capture time is not a timezone-aware ISO-8601 timestamp.",
            reference=reference,
            environment_scope=scope,
        )
    if not _SHA256_HEX.match(evidence["profile_digest"]) or not _SHA256_HEX.match(
        evidence["result_digest"]
    ):
        return OfflineObservedEvidence(
            state="malformed",
            detail="The rehearsal profile and result digests must be lowercase SHA-256 hex.",
            reference=reference,
            tested_release_identity=evidence["release"],
            environment_scope=scope,
        )

    age_seconds = int((now - captured_at).total_seconds())
    observed = {
        "reference": reference,
        "tested_release_identity": evidence["release"],
        "tested_profile_digest": evidence["profile_digest"],
        "captured_at": captured_at.isoformat(),
        "environment_scope": scope,
        "age_seconds": age_seconds,
    }

    if age_seconds < -OFFLINE_REHEARSAL_FUTURE_SKEW_SECONDS:
        return OfflineObservedEvidence(
            state="malformed",
            detail="The rehearsal capture time is in the future.",
            **observed,
        )
    if rehearsal_result_digest(evidence) != evidence["result_digest"]:
        return OfflineObservedEvidence(
            state="tampered",
            detail=(
                "The declared result digest does not match the declared rehearsal header, so "
                "the reference cannot be trusted."
            ),
            **observed,
        )
    if evidence["release"] != release_identity:
        return OfflineObservedEvidence(
            state="mismatched",
            detail="The rehearsal was captured for a different release identity.",
            **observed,
        )
    if evidence["profile_digest"] != profile_digest:
        return OfflineObservedEvidence(
            state="mismatched",
            detail=(
                "The rehearsal was captured for a different offline profile, so a material "
                "endpoint, profile or release change invalidated it."
            ),
            **observed,
        )
    if age_seconds > OFFLINE_REHEARSAL_MAX_AGE_SECONDS:
        return OfflineObservedEvidence(
            state="stale",
            detail=(
                "The rehearsal reference is older than the "
                f"{OFFLINE_REHEARSAL_MAX_AGE_SECONDS // 86400}-day freshness window."
            ),
            **observed,
        )
    return OfflineObservedEvidence(
        state="matched",
        detail=(
            "A local rehearsal artifact matches the live profile digest, release identity and "
            "freshness window. This is observed in a rehearsal, not an external accreditation."
        ),
        **observed,
    )


def _parse_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def evaluate_offline_readiness(
    settings: Settings,
    *,
    egress_mode: str,
    now: datetime,
) -> OfflineReadinessSection:
    """Build the additive offline-readiness section for the readiness report."""
    release_identity = resolve_release_identity(settings)
    manifest_revision = settings.deployment_dependency_manifest_revision.strip().casefold()
    bindings, binding_blockers = parse_local_bindings(settings.deployment_offline_local_bindings)
    profile_digest = offline_profile_digest(
        egress_mode=egress_mode,
        release_identity=release_identity,
        dependency_manifest_revision=manifest_revision,
        bindings=bindings,
    )
    notes = [
        "The offline profile digest is computed over public-safe material facts: it contains "
        "dependency ids and opaque binding references, never resolved endpoints or secrets.",
        "Configured posture, observed rehearsal evidence and external accreditation are "
        "distinct: this section establishes no accreditation and runs no network probe.",
    ]

    if egress_mode not in OFFLINE_EGRESS_MODES:
        return OfflineReadinessSection(
            state="not_declared",
            declared=False,
            egress_mode=egress_mode,
            release_identity=release_identity,
            profile_digest=profile_digest,
            dependency_manifest_revision=manifest_revision or None,
            configuration=OfflineConfigurationValidation(
                state="not_evaluated",
                local_bindings=[],
                blockers=[],
                omitted_capabilities=[],
                dependencies=[],
            ),
            observed_evidence=OfflineObservedEvidence(
                state="not_run",
                detail=(
                    "The deployment does not declare an offline egress profile, so offline "
                    "readiness is not evaluated."
                ),
            ),
            notes=notes,
        )

    configuration = _evaluate_configuration(
        settings,
        bindings=bindings,
        binding_blockers=binding_blockers,
        manifest_revision=manifest_revision,
    )
    evidence = _evaluate_evidence(
        settings,
        now=now,
        release_identity=release_identity,
        profile_digest=profile_digest,
    )
    if configuration.state == "invalid":
        state = "action_required"
    elif evidence.matched:
        state = "verified_in_rehearsal"
    else:
        state = "configured_unverified"
    return OfflineReadinessSection(
        state=state,
        declared=True,
        egress_mode=egress_mode,
        release_identity=release_identity,
        profile_digest=profile_digest,
        dependency_manifest_revision=manifest_revision or None,
        configuration=configuration,
        observed_evidence=evidence,
        notes=notes,
    )
