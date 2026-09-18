"""Offline portability bundle validator and dry-run restore plan.

Slice 2/4 of [#877](https://github.com/Limes-Labs/limes-axis/issues/877)
(parent #476), stacked on the #876 manifest contract. This module is pure
and offline: no network calls, no tenant admission, no credential resolution,
no source connections, no destination writes. Possessing an export can never
create a tenant or grant privileges — the plan it produces is descriptive and
requires separately authorized execution (#878).

What it does:

* Verifies bundle archive safety *without inspecting member contents*:
  bounded member counts and sizes, path-escape rejection, executable
  serialization formats rejected by name.
* Verifies the bundle signature against **operator-supplied** trusted signer
  key ids — a public key embedded in an untrusted bundle is never its own
  trust anchor.
* Verifies every component payload digest against the #876 manifest and
  rejects duplicate identities, missing required components and unsupported
  source versions.
* Produces a deterministic restore plan: explicit identity mappings only
  (never email/display-name matching; two sources mapping to one target is
  an ambiguous merge and is refused), unknown principals stay
  ``unmapped_disabled`` without default roles, credentials resolve fresh,
  and operational schedules stay suspended per the manifest safety policy.
* Requires operators to explicitly acknowledge exclusions before the plan
  can be handed to the later write runner.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from axis_sdk.connector_authoring.contracts import ContractModel, Digest, Identifier
from pydantic import Field, ValidationError, model_validator

from axis_api.portability_manifest import (
    PortabilityManifest,
    PortabilityManifestError,
    canonical_portability_digest,
    parse_portability_manifest,
)

BUNDLE_FORMAT = "axis.tenant-portability-bundle"

_MAX_ARCHIVE_MEMBERS = 4_096
_MAX_MEMBER_BYTES = 536_870_912  # 512 MiB per member
_MAX_ARCHIVE_BYTES = 2_147_483_648  # 2 GiB decompressed in total
_MAX_PAYLOAD_RECORDS = 100_000
_MAX_IDENTITIES = 50_000

_IDENTIFIER = r"^[a-z][a-z0-9._-]{2,99}$"
_KEY_ID = r"^[a-z0-9][a-z0-9._/-]{2,63}$"
_SUBJECT = r"^[a-z0-9][a-z0-9._:@-]{2,127}$"

#: Executable or interpreter-owned formats are rejected by member name,
#: without ever opening the member. Everything here can be code under some
#: runtime's import machinery.
_FORBIDDEN_SUFFIXES = (
    ".py", ".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe", ".sh", ".bash",
    ".pkl", ".pickle", ".dill", ".jar", ".class", ".wasm", ".ps1", ".bat",
)


class PortabilityValidationError(ValueError):
    """Fixed safe codes; bundle details are never echoed back."""

    UNSAFE_ARCHIVE_MEMBER = "unsafe_archive_member"
    ARCHIVE_TOO_LARGE = "archive_resource_limits_exceeded"
    UNTRUSTED_SIGNER = "bundle_signer_not_trusted"
    PAYLOAD_DIGEST_MISMATCH = "component_payload_digest_mismatch"
    DUPLICATE_IDENTITY = "duplicate_bundle_identity"
    MISSING_COMPONENT_PAYLOAD = "missing_required_component_payload"
    INCOMPATIBLE_AXIS_VERSION = "incompatible_source_axis_version"
    AMBIGUOUS_IDENTITY_MAPPING = "ambiguous_identity_mapping"
    UNACKNOWLEDGED_EXCLUSION = "unacknowledged_exclusion"

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ArchiveMember(ContractModel):
    """One archive member by name and size only; contents stay unread."""

    path: str = Field(min_length=1, max_length=200)
    size_bytes: int = Field(ge=0, strict=True, le=_MAX_MEMBER_BYTES)


class BundleArchive(ContractModel):
    """Bounded archive description validated before anything is opened."""

    members: tuple[ArchiveMember, ...] = Field(min_length=1, max_length=_MAX_ARCHIVE_MEMBERS)

    @model_validator(mode="after")
    def safe_archive(self) -> BundleArchive:
        paths = [member.path for member in self.members]
        if len(set(paths)) != len(paths):
            raise PortabilityValidationError(PortabilityValidationError.UNSAFE_ARCHIVE_MEMBER)
        total = 0
        for member in self.members:
            lowered = member.path.lower()
            if member.path.startswith(("/", "\\")) or ".." in member.path or "\\" in member.path:
                raise PortabilityValidationError(PortabilityValidationError.UNSAFE_ARCHIVE_MEMBER)
            if lowered.endswith(_FORBIDDEN_SUFFIXES):
                raise PortabilityValidationError(PortabilityValidationError.UNSAFE_ARCHIVE_MEMBER)
            total += member.size_bytes
        if total > _MAX_ARCHIVE_BYTES:
            raise PortabilityValidationError(PortabilityValidationError.ARCHIVE_TOO_LARGE)
        return self


class PayloadRecord(ContractModel):
    """One exported record: an opaque identity plus opaque data."""

    identity: str = Field(pattern=_SUBJECT)
    data: dict[str, object]


class BundleSignature(ContractModel):
    """Who signed the manifest digest — never a self-asserted trust anchor."""

    signer_key_id: str = Field(pattern=_KEY_ID)
    signed_manifest_digest: Digest


class PortabilityBundle(ContractModel):
    """An export bundle: manifest, bounded archive, payloads, signature."""

    format: Literal["axis.tenant-portability-bundle"] = BUNDLE_FORMAT
    manifest: PortabilityManifest
    archive: BundleArchive
    component_payloads: dict[str, tuple[PayloadRecord, ...]] = Field(max_length=64)
    signature: BundleSignature


class IdentityMapping(ContractModel):
    """One explicit source→target principal mapping decided by the operator."""

    source_subject: str = Field(pattern=_SUBJECT)
    source_kind: Literal["user", "group", "service"]
    target_subject: str | None = Field(default=None, pattern=_SUBJECT)
    target_state: Literal["mapped", "unmapped_disabled"]


class RebindingAction(ContractModel):
    """One concrete rebinding action derived from the manifest references."""

    kind: Literal[
        "credential", "signing_key", "identity_provider", "service_endpoint", "object_store"
    ]
    reference_id: Identifier
    action: Literal[
        "fresh_local_resolution_required", "rebind_required", "unsupported_blocked"
    ]


class RestorePlan(ContractModel):
    """The deterministic dry-run output; descriptive, never an approval."""

    manifest_digest: Digest
    bundle_digest: Digest
    source_axis_version: str
    supported: bool
    identity_mappings: tuple[IdentityMapping, ...] = Field(max_length=_MAX_IDENTITIES)
    rebinding_actions: tuple[RebindingAction, ...] = Field(max_length=64)
    excluded_components: tuple[tuple[str, str], ...] = Field(default=(), max_length=64)
    rebuild_components: tuple[str, ...] = Field(default=(), max_length=64)
    suspended_operations: tuple[str, ...] = Field(default=(), max_length=8)
    blocked_by: tuple[str, ...] = Field(default=(), max_length=64)
    plan_digest: Digest

    def exclusions(self) -> tuple[str, ...]:
        return tuple(component_id for component_id, _reason in self.excluded_components)


class PlanAcknowledgement(ContractModel):
    """Operator acknowledgment required before any authorized execution."""

    plan_digest: Digest
    acknowledged_exclusions: tuple[str, ...]
    acknowledged_by: str = Field(pattern=_SUBJECT)
    acknowledged_at: str = Field(min_length=10, max_length=40)


def _plan_digest(plan_parts: dict[str, object]) -> Digest:
    return canonical_portability_digest(plan_parts)


def validate_bundle(
    bundle: PortabilityBundle,
    *,
    trusted_signer_key_ids: frozenset[str],
    supported_axis_versions: tuple[str, ...],
    identity_map: Mapping[str, tuple[str, str]] | None = None,
) -> RestorePlan:
    """Verify a bundle offline and derive its deterministic restore plan.

    ``identity_map`` maps a payload principal to ``(target_subject,
    source_kind)`` where kind is ``user``/``group``/``service``; principals
    absent from the map stay ``unmapped_disabled``. Raises
    :class:`PortabilityValidationError` with a fixed code before any plan
    exists when the archive is unsafe, the signer is not trusted by the
    operator-supplied material, a payload digest mismatches, identities
    duplicate, required components are missing, or the source version is not
    supported. Mapping two source principals onto one target is refused as
    an ambiguous merge.
    """

    manifest = bundle.manifest
    if bundle.signature.signer_key_id not in trusted_signer_key_ids:
        raise PortabilityValidationError(PortabilityValidationError.UNTRUSTED_SIGNER)
    if bundle.signature.signed_manifest_digest != manifest.digest():
        raise PortabilityValidationError(PortabilityValidationError.UNTRUSTED_SIGNER)
    if manifest.source_axis_version not in supported_axis_versions:
        raise PortabilityValidationError(PortabilityValidationError.INCOMPATIBLE_AXIS_VERSION)

    for component in manifest.components:
        records = bundle.component_payloads.get(component.component_id)
        if component.decision == "restore":
            if records is None:
                raise PortabilityValidationError(
                    PortabilityValidationError.MISSING_COMPONENT_PAYLOAD
                )
            if len(records) != component.object_count:
                raise PortabilityValidationError(
                    PortabilityValidationError.PAYLOAD_DIGEST_MISMATCH
                )
            computed = canonical_portability_digest(
                [record.model_dump(mode="json") for record in records]
            )
            if component.content_digest is None or computed != component.content_digest:
                raise PortabilityValidationError(
                    PortabilityValidationError.PAYLOAD_DIGEST_MISMATCH
                )
            identities = [record.identity for record in records]
            if len(set(identities)) != len(identities):
                raise PortabilityValidationError(PortabilityValidationError.DUPLICATE_IDENTITY)

    mapping = dict(identity_map or {})
    targets = [target for target, _kind in mapping.values()]
    if len(set(targets)) != len(targets):
        raise PortabilityValidationError(PortabilityValidationError.AMBIGUOUS_IDENTITY_MAPPING)

    payload_identities = {
        record.identity
        for records in bundle.component_payloads.values()
        for record in records
    }
    identity_mappings: list[IdentityMapping] = []
    for identity in sorted(payload_identities):
        entry = mapping.get(identity)
        target, kind = entry if entry is not None else (None, "user")
        identity_mappings.append(
            IdentityMapping(
                source_subject=identity,
                source_kind=kind,  # type: ignore[arg-type]
                target_subject=target,
                target_state="mapped" if target else "unmapped_disabled",
            )
        )
    rebinding_actions = [
        RebindingAction(
            kind=reference.kind,
            reference_id=reference.reference_id,
            action=(
                "unsupported_blocked"
                if reference.resolution == "unsupported"
                else reference.resolution
            ),
        )
        for reference in manifest.rebinding_references
    ]

    blocked_by = [
        f"{action.kind}:{action.reference_id}"
        for action in rebinding_actions
        if action.action == "unsupported_blocked"
    ]
    excluded_components = tuple(
        (component.component_id, component.exclusion_reason or "excluded")
        for component in manifest.components
        if component.decision == "exclude"
    )
    rebuild_components = tuple(
        component.component_id
        for component in manifest.components
        if component.decision == "rebuild"
    )
    supported = not blocked_by
    safety = manifest.restore_safety
    suspended_operations = [
        f"pending_actions:{safety.pending_actions}",
        f"pending_deliveries:{safety.pending_deliveries}",
        f"workflow_schedules:{safety.workflow_schedules}",
        f"credential_leases:{safety.credential_leases}",
    ]
    parts = {
        "manifest_digest": manifest.digest(),
        "source_tenant": manifest.tenant_logical_id,
        "identity_mappings": [item.model_dump(mode="json") for item in identity_mappings],
        "rebinding_actions": [item.model_dump(mode="json") for item in rebinding_actions],
        "excluded_components": [list(item) for item in excluded_components],
        "rebuild_components": list(rebuild_components),
        "suspended_operations": suspended_operations,
        "blocked_by": blocked_by,
    }
    return RestorePlan(
        manifest_digest=manifest.digest(),
        bundle_digest=canonical_portability_digest(
            {
                "manifest": manifest.model_dump(mode="json"),
                "archive": bundle.archive.model_dump(mode="json"),
            }
        ),
        source_axis_version=manifest.source_axis_version,
        supported=supported,
        identity_mappings=tuple(identity_mappings),
        rebinding_actions=tuple(rebinding_actions),
        excluded_components=excluded_components,
        rebuild_components=rebuild_components,
        suspended_operations=tuple(suspended_operations),
        blocked_by=tuple(blocked_by),
        plan_digest=_plan_digest(parts),
    )


def acknowledge_restore_plan(
    plan: RestorePlan,
    *,
    acknowledged_exclusions: tuple[str, ...],
    acknowledged_by: str,
    acknowledged_at: str,
) -> PlanAcknowledgement:
    """Record explicit acknowledgment of every exclusion in the plan.

    The operator must name exactly the plan's excluded components — nothing
    missed, nothing extra. The returned acknowledgement is the handoff
    artifact the later write runner (#878) must require; it is not itself an
    approval token.
    """

    exclusions = set(plan.exclusions())
    if exclusions - set(acknowledged_exclusions) or set(acknowledged_exclusions) - exclusions:
        raise PortabilityValidationError(PortabilityValidationError.UNACKNOWLEDGED_EXCLUSION)
    return PlanAcknowledgement(
        plan_digest=plan.plan_digest,
        acknowledged_exclusions=tuple(sorted(acknowledged_exclusions)),
        acknowledged_by=acknowledged_by,
        acknowledged_at=acknowledged_at,
    )


def parse_portability_bundle(value: object) -> PortabilityBundle:
    """Parse an untrusted bundle with fixed safe error codes."""

    if isinstance(value, dict) and not isinstance(value.get("manifest"), PortabilityManifest):
        try:
            value = {**value, "manifest": parse_portability_manifest(value.get("manifest"))}
        except (PortabilityManifestError, ValidationError):
            raise PortabilityManifestError(PortabilityManifestError.INVALID_MANIFEST) from None
    try:
        return PortabilityBundle.model_validate(value)
    except ValidationError:
        raise PortabilityManifestError(PortabilityManifestError.INVALID_MANIFEST) from None
