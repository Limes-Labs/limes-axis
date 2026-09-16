"""Restore-capable portability profile for the canonical tenant export manifest.

Contract slice of [#876](https://github.com/Limes-Labs/limes-axis/issues/876)
(parent #476), extending the #324 canonical export manifest rather than defining
a second archive format. This module is pure: no I/O, no producer, no restore
writes, no credential resolution. It defines the vocabulary a producer must
emit and a validator must check:

* A versioned manifest envelope (``schema_version``) with strict round-trips.
  Unknown fields and incompatible versions are rejected; there is no implicit
  major fallback and no all-version compatibility promise.
* One bounded entry per authoritative component: owner layer, consistency rule,
  object counts and digests, dependency order, and an explicit restore decision
  (``restore``, ``rebuild``, ``exclude``). Future or unknown components are
  ``unsupported``, never silent empty successes.
* Secret/session/private-key material is structurally excluded: it can appear
  only as a typed :class:`RebindingReference` pointing at deployment-local
  resolution, never as portable data.
* A consistency declaration distinguishes a quiesced export from a captured
  watermark; independent per-store timestamps are never treated as one
  transactionally consistent snapshot.
* A restore safety policy that defaults every pending external effect to
  suspended/review-required; incomplete exports cannot claim portable success.

The digest helper is shared with the manifest itself so producers cannot sign
non-canonical bytes.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from axis_sdk.connector_authoring.contracts import ContractModel, Digest, Identifier
from pydantic import Field, ValidationError, model_validator

MANIFEST_FORMAT = "axis.tenant-portability-manifest"
MANIFEST_VERSION_MAJOR = 1
MANIFEST_VERSION_MINOR = 0

#: Supported schema versions for reading. Major bumps change semantics; there
#: is no implicit fallback, so readers reject anything outside this tuple.
SUPPORTED_MAJOR_VERSIONS = (MANIFEST_VERSION_MAJOR,)
SUPPORTED_MINOR_VERSIONS = (MANIFEST_VERSION_MINOR,)

_MAX_COMPONENTS = 64
_MAX_ENTRIES_PER_COMPONENT = 100_000

OwnerLayer = Literal[
    "trust", "data", "operational-model", "workflow", "intelligence", "deployment", "experience"
]
RestoreDecision = Literal["restore", "rebuild", "exclude"]
ConsistencyRule = Literal["quiesced_export", "captured_watermark", "rebuildable_projection"]
StoreKind = Literal["postgres", "object_storage", "ontology", "audit_ledger"]


class PortabilityManifestError(ValueError):
    """Fixed public-safe codes; raw validation details are never rendered."""

    INCOMPATIBLE_VERSION = "incompatible_manifest_version"
    INVALID_MANIFEST = "invalid_portability_manifest"

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_portability_digest(value: object) -> Digest:
    """Deterministic digest over canonical JSON; producers must reuse this."""

    data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _parse_version(value: object) -> tuple[int, int]:
    if not isinstance(value, dict):
        raise PortabilityManifestError(PortabilityManifestError.INVALID_MANIFEST)
    major = value.get("major")
    minor = value.get("minor")
    if (
        not isinstance(major, int)
        or isinstance(major, bool)
        or not isinstance(minor, int)
        or isinstance(minor, bool)
    ):
        raise PortabilityManifestError(PortabilityManifestError.INVALID_MANIFEST)
    return major, minor


class ManifestVersion(ContractModel):
    major: int = Field(ge=1, strict=True)
    minor: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def bounded_version(self) -> ManifestVersion:
        if self.major != MANIFEST_VERSION_MAJOR or self.minor != MANIFEST_VERSION_MINOR:
            raise ValueError("Manifest version is not the current contract version")
        return self


class RebindingReference(ContractModel):
    """A typed pointer to deployment-local material that is never portable data.

    ``kind`` is closed: credentials, signing keys and sessions resolve fresh at
    the destination or block restore; they are never embedded or exported. Only
    credentials and signing keys may be declared ``unsupported``; endpoints and
    stores always have a concrete rebinding action.
    """

    kind: Literal[
        "credential", "signing_key", "identity_provider", "service_endpoint", "object_store"
    ]
    reference_id: Identifier
    resolution: Literal["fresh_local_resolution_required", "rebind_required", "unsupported"]
    notes: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def bounded_unsupported(self) -> RebindingReference:
        if self.resolution == "unsupported" and self.kind not in {"credential", "signing_key"}:
            raise ValueError("Only credentials and signing keys may be declared unsupported")
        return self


class ComponentInventory(ContractModel):
    """One authoritative component's export profile and restore decision.

    A component without a registered restore handler must be declared with the
    ``exclude`` decision and its reason; a ``restore`` decision without a
    handler would be a fabricated success and is refused at construction.
    """

    component_id: Identifier
    owner_layer: OwnerLayer
    store: StoreKind
    consistency: ConsistencyRule
    decision: RestoreDecision
    schema_version: ManifestVersion
    object_count: int = Field(ge=0, strict=True, le=_MAX_ENTRIES_PER_COMPONENT)
    content_digest: Digest | None = None
    depends_on: tuple[Identifier, ...] = Field(default=(), max_length=_MAX_COMPONENTS)
    exclusion_reason: str | None = Field(default=None, min_length=1, max_length=500)
    handler_registered: bool

    @model_validator(mode="after")
    def coherent_inventory(self) -> ComponentInventory:
        if self.decision == "exclude" and self.exclusion_reason is None:
            raise ValueError("Excluded components require an explicit exclusion reason")
        if self.decision == "restore" and not self.handler_registered:
            raise ValueError(
                "Restoring a component without a registered handler is a fabricated success"
            )
        if self.decision == "restore" and self.content_digest is None:
            raise ValueError("Restored components must bind exported content to a digest")
        if self.decision == "rebuild" and self.consistency != "rebuildable_projection":
            raise ValueError("Only rebuildable projections can carry the rebuild decision")
        if self.decision == "exclude" and self.object_count != 0:
            raise ValueError("Excluded components cannot claim exported objects")
        return self


class ConsistencyPoint(ContractModel):
    """Cross-store consistency disclosure; per-store watermarks stay explicit."""

    mode: Literal["quiesced", "captured_watermark"]
    captured_at: str = Field(min_length=10, max_length=40)
    per_store: tuple[StoreWatermark, ...] = Field(min_length=1, max_length=8)
    disclosures: str = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def honest_mode(self) -> ConsistencyPoint:
        kinds = {watermark.store for watermark in self.per_store}
        if len(kinds) != len(self.per_store):
            raise ValueError("Each store contributes at most one watermark")
        return self


class StoreWatermark(ContractModel):
    store: StoreKind
    watermark: str = Field(min_length=1, max_length=200)


ConsistencyPoint.model_rebuild()


class RestoreSafetyPolicy(ContractModel):
    """Default-suspend posture for operational state carried across tenants.

    Pending external effects never auto-replay after restore; every class here
    starts suspended and requires fresh explicit activation at the destination.
    """

    pending_actions: Literal["suspended", "review_required"] = "suspended"
    pending_deliveries: Literal["suspended", "review_required"] = "suspended"
    workflow_schedules: Literal["suspended", "review_required"] = "suspended"
    credential_leases: Literal["suspended", "review_required"] = "suspended"
    auto_replay_external_effects: Literal[False] = False


class PortabilityManifest(ContractModel):
    """The restore-capable profile of one tenant export bundle."""

    format: Literal["axis.tenant-portability-manifest"] = MANIFEST_FORMAT
    schema_version: ManifestVersion
    tenant_logical_id: Identifier
    source_axis_version: str = Field(min_length=1, max_length=40)
    consistency_point: ConsistencyPoint
    components: tuple[ComponentInventory, ...] = Field(min_length=1, max_length=_MAX_COMPONENTS)
    rebinding_references: tuple[RebindingReference, ...] = Field(
        default=(), max_length=_MAX_COMPONENTS
    )
    restore_safety: RestoreSafetyPolicy = Field(default_factory=RestoreSafetyPolicy)

    @model_validator(mode="after")
    def coherent_manifest(self) -> PortabilityManifest:
        component_ids = [component.component_id for component in self.components]
        if len(set(component_ids)) != len(component_ids):
            raise ValueError("Component inventories must be unique per component")
        stores = [component.store for component in self.components]
        if len(set(stores)) != len(stores):
            raise ValueError("Each store kind is inventoried by exactly one component")
        covered = {watermark.store for watermark in self.consistency_point.per_store}
        missing = set(stores) - covered
        if missing:
            raise ValueError(
                "Every inventoried store needs a declared watermark for the consistency point"
            )
        if self.consistency_point.mode == "quiesced" and any(
            component.consistency == "captured_watermark" for component in self.components
        ):
            raise ValueError(
                "A quiesced export cannot contain captured-watermark components"
            )
        return self

    def digest(self) -> Digest:
        return canonical_portability_digest(self.model_dump(mode="json"))

    def evidence(self) -> dict[str, object]:
        """Metadata-only projection; no component content, digests only."""

        return {
            "format": self.format,
            "schema_version": self.schema_version.model_dump(mode="json"),
            "tenant_logical_id_present": bool(self.tenant_logical_id),
            "component_count": len(self.components),
            "restore_decisions": {
                component.component_id: component.decision for component in self.components
            },
            "rebinding_reference_count": len(self.rebinding_references),
            "restore_safety": self.restore_safety.model_dump(mode="json"),
        }


class PortabilityReview(ContractModel):
    """Deterministic verdict over one manifest; no restore authority."""

    manifest_digest: Digest
    portable: bool
    blocked_by: tuple[str, ...] = Field(default=(), max_length=_MAX_COMPONENTS)
    suspended_by_policy: tuple[str, ...] = Field(
        default=(
            "pending_actions",
            "pending_deliveries",
            "workflow_schedules",
            "credential_leases",
        ),
    )
    acknowledgements_required: tuple[str, ...] = Field(default=(), max_length=_MAX_COMPONENTS)


def review_portability_manifest(manifest: PortabilityManifest) -> PortabilityReview:
    """Classify a manifest's portability without executing anything.

    A manifest is portable only when nothing is blocked; unsupported rebinding
    references block outright, while exclusions, required rebinding and
    watermark-based consistency surface as acknowledgements operators must
    accept before any later execution. Inconsistent manifests never pass
    silently: the contract refuses to construct them at all.
    """

    blocked: list[str] = []
    acknowledgements: list[str] = []
    for component in manifest.components:
        if component.decision == "exclude":
            acknowledgements.append(f"excluded:{component.component_id}")
    for reference in manifest.rebinding_references:
        if reference.resolution == "unsupported":
            # The manifest tolerates this state only so the reviewer can block
            # it explicitly; it can never pass as portable success.
            blocked.append(f"rebinding_unsupported:{reference.reference_id}")
        elif reference.resolution == "rebind_required":
            acknowledgements.append(f"rebind_required:{reference.reference_id}")
    if manifest.consistency_point.mode == "captured_watermark":
        acknowledgements.append("captured_watermark:not_transactionally_consistent")
    return PortabilityReview(
        manifest_digest=manifest.digest(),
        portable=not blocked,
        blocked_by=tuple(blocked),
        acknowledgements_required=tuple(acknowledgements),
    )


def parse_portability_manifest(value: object) -> PortabilityManifest:
    """Parse at an untrusted boundary with fixed safe error codes.

    The version pre-check exists to report an incompatible *version* (a future
    producer) distinctly from a malformed manifest; everything else falls to
    strict validation and its single safe code.
    """

    if isinstance(value, dict):
        version = value.get("schema_version")
        if version is not None:
            try:
                major, _minor = _parse_version(version)
            except PortabilityManifestError:
                raise
            if major not in SUPPORTED_MAJOR_VERSIONS:
                raise PortabilityManifestError(
                    PortabilityManifestError.INCOMPATIBLE_VERSION
                ) from None
    try:
        return PortabilityManifest.model_validate(value)
    except ValidationError:
        raise PortabilityManifestError(PortabilityManifestError.INVALID_MANIFEST) from None
