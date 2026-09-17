"""Immutable public dataset release contract for Open Data Publishing.

Contract slice of [#838](https://github.com/Limes-Labs/limes-axis/issues/838)
(parent #837). This module is pure: no storage, no distribution packaging, no
anonymous API, no rendering. It defines the vocabulary a publication pipeline
must emit and a consumer must verify:

* A versioned manifest envelope (``schema_version``) with strict round-trips.
  Unknown fields and incompatible versions are rejected; there is no implicit
  major fallback and no all-version compatibility promise.
* One manifest freezes exactly one release revision. A released manifest is
  immutable: source corrections create a new release version, they never
  rewrite bytes behind an existing public version.
* Public identity is opaque by construction: the ``ds-`` grammar is disjoint
  from internal UUID identifiers, so public IDs cannot be transformed or
  guessed into private tenant resource endpoints.
* Exact internal lineage lives in a separate :class:`InternalSourceLedger`
  bound to the public manifest by digest; the public manifest structurally
  cannot carry internal-only references (``extra="forbid"``, no such field).
* A release can only be issued over approved disclosure and license review
  evidence captured no earlier than the frozen source; missing or stale
  authorization is a construction/readiness failure, never a silent success.
* Withdrawal and supersession preserve the historical issued evidence by
  digest and never claim that external copies were deleted.

The digest helper is shared with the manifest itself so producers cannot sign
non-canonical bytes.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from axis_sdk.connector_authoring.contracts import ContractModel, Digest, Identifier
from pydantic import Field, ValidationError, model_validator

RELEASE_MANIFEST_FORMAT = "axis.public-dataset-release"
RELEASE_VERSION_MAJOR = 1
RELEASE_VERSION_MINOR = 0

#: Supported schema versions for reading. Major bumps change semantics; there
#: is no implicit fallback, so readers reject anything outside this tuple.
SUPPORTED_MAJOR_VERSIONS = (RELEASE_VERSION_MAJOR,)

_MAX_FIELDS = 256
_MAX_CHANGES = 256
_MAX_REVIEWS = 8
_MAX_LIMITATIONS = 64
_MAX_ROW_COUNT = 5_000_000_000

# RFC3339 UTC timestamps at whole-second precision. Comparisons in this
# module are lexicographic, which is order-correct only for this fixed
# normalized form (no fractional seconds, always Z).
_TIMESTAMP = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
_DATE = r"^\d{4}-\d{2}-\d{2}$"
_PUBLIC_ID = r"^ds-[a-z0-9]{12,32}$"
_RELEASE_VERSION = re.compile(r"^\d+\.\d+$")

SourceMode = Literal[
    "governed_snapshot", "materialized_view", "frozen_publication", "external_artifact"
]
LifecycleState = Literal[
    "draft",
    "disclosure_review",
    "approved",
    "issued",
    "superseded",
    "deprecated",
    "withdrawn",
    "archived",
]
ReviewKind = Literal["disclosure", "license", "sensitivity"]
ReviewStatus = Literal["approved", "rejected", "pending"]
ChangeKind = Literal[
    "field_added", "field_removed", "field_retyped", "coverage_extended",
    "correction", "license_change", "source_refresh", "deprecation",
]

#: Post-issue states: a release in one of these was sealed, so it must carry
#: the content digest of what was actually published.
_SEALED_STATES = frozenset({"issued", "superseded", "deprecated", "withdrawn", "archived"})


class PublicReleaseError(ValueError):
    """Fixed public-safe codes; raw validation details are never rendered."""

    INCOMPATIBLE_VERSION = "incompatible_release_manifest_version"
    INVALID_MANIFEST = "invalid_public_release_manifest"
    LEDGER_MISMATCH = "internal_ledger_manifest_mismatch"
    CROSS_DATASET_DIFF = "cross_dataset_diff"
    NON_MONOTONIC_VERSION = "non_monotonic_release_version"

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_release_digest(value: object) -> Digest:
    """Deterministic digest over canonical JSON; producers must reuse this."""

    data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _parse_version(value: object) -> int:
    if not isinstance(value, dict):
        raise PublicReleaseError(PublicReleaseError.INVALID_MANIFEST)
    major = value.get("major")
    if not isinstance(major, int) or isinstance(major, bool):
        raise PublicReleaseError(PublicReleaseError.INVALID_MANIFEST)
    return major


class ManifestVersion(ContractModel):
    major: int = Field(ge=1, strict=True)
    minor: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def bounded_version(self) -> ManifestVersion:
        if self.major != RELEASE_VERSION_MAJOR or self.minor != RELEASE_VERSION_MINOR:
            raise ValueError("Release manifest version is not the current contract version")
        return self


class PublicDatasetIdentity(ContractModel):
    """Opaque public identity, structurally disjoint from internal IDs.

    ``public_id`` is ``ds-`` plus a lowercase base36 body: internal UUIDs and
    numeric tenant IDs can never satisfy the pattern, so a public identifier
    cannot be transformed into a private resource endpoint by construction.
    """

    public_id: str = Field(pattern=_PUBLIC_ID)
    api_name: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2_000)
    publisher: str = Field(min_length=1, max_length=200)


class PublicSchemaField(ContractModel):
    name: str = Field(pattern=r"^[a-z_][a-z0-9_]{0,63}$")
    dtype: Literal["string", "integer", "decimal", "boolean", "date", "datetime", "json"]
    nullable: bool
    description: str = Field(min_length=1, max_length=500)


class SourceBinding(ContractModel):
    """The exact frozen source the release was created from.

    ``mode`` is closed: a live tenant query is not a release identity and no
    live mode exists in the vocabulary, so live-query-as-release cannot be
    expressed, only rejected. Only non-resolving evidence stays here (a
    digest, a capture time); the exact internal source references belong to
    the private :class:`InternalSourceLedger`, never the public manifest.
    """

    mode: SourceMode
    source_digest: Digest
    captured_at: str = Field(pattern=_TIMESTAMP, min_length=20, max_length=40)


class PopulationRecord(ContractModel):
    """Population claim for the release; mode must match the source mode."""

    mode: Literal["snapshot_rows", "materialization_rows", "external_artifact"]
    row_count: int = Field(ge=0, strict=True, le=_MAX_ROW_COUNT)
    content_digest: Digest | None = None


class LicenseRecord(ContractModel):
    license_id: Identifier
    access_rights: str = Field(min_length=1, max_length=1_000)


class ReviewEvidence(ContractModel):
    """Reviewed authorization evidence; approval is never inferred."""

    kind: ReviewKind
    status: ReviewStatus
    authority_ref: Identifier | None = None
    decided_at: str | None = Field(default=None, pattern=_TIMESTAMP, min_length=20, max_length=40)

    @model_validator(mode="after")
    def decided_evidence(self) -> ReviewEvidence:
        if self.status == "pending" and self.decided_at is not None:
            raise ValueError("Pending reviews cannot carry a decision timestamp")
        if self.status != "pending" and (self.decided_at is None or self.authority_ref is None):
            raise ValueError("Decided reviews require an authority and a decision timestamp")
        return self


class KnownLimitation(ContractModel):
    kind: Literal["coverage", "quality", "freshness", "partial_population"]
    description: str = Field(min_length=1, max_length=500)


class SupersedesRecord(ContractModel):
    """Binding to the exact prior release manifest this version replaces."""

    release_public_id: str = Field(pattern=_PUBLIC_ID)
    release_version: str = Field(pattern=r"^\d+\.\d+$")
    manifest_digest: Digest


class WithdrawalRecord(ContractModel):
    """Withdrawal evidence that cannot overstate its effect.

    ``issued_manifest_digest`` pins the digest of the manifest exactly as it
    was issued (same content, ``state="issued"``, no withdrawal record); the
    manifest validator reconstructs and re-digests that issuance to reject
    tampered withdrawal evidence. ``external_copies_note`` is a fixed literal:
    withdrawal stops future delivery, it does not and cannot retract copies
    already downloaded.
    """

    issued_manifest_digest: Digest
    reason: str = Field(min_length=1, max_length=1_000)
    withdrawn_at: str = Field(pattern=_TIMESTAMP, min_length=20, max_length=40)
    external_copies_note: Literal["external_copies_not_retracted"] = "external_copies_not_retracted"


class ReleaseChange(ContractModel):
    kind: ChangeKind
    detail: str = Field(min_length=1, max_length=300)


class ReleaseNotes(ContractModel):
    summary: str = Field(min_length=1, max_length=2_000)
    changes: tuple[ReleaseChange, ...] = Field(default=(), max_length=_MAX_CHANGES)


class PublicReleaseManifest(ContractModel):
    """One immutable public dataset release revision."""

    format: Literal["axis.public-dataset-release"] = RELEASE_MANIFEST_FORMAT
    schema_version: ManifestVersion
    identity: PublicDatasetIdentity
    release_version: str = Field(pattern=r"^\d+\.\d+$")
    state: LifecycleState
    source: SourceBinding
    fields: tuple[PublicSchemaField, ...] = Field(min_length=1, max_length=_MAX_FIELDS)
    population: PopulationRecord
    license: LicenseRecord
    reviews: tuple[ReviewEvidence, ...] = Field(min_length=1, max_length=_MAX_REVIEWS)
    coverage_start: str = Field(pattern=_DATE, min_length=10, max_length=10)
    coverage_end: str | None = Field(default=None, pattern=_DATE, min_length=10, max_length=10)
    release_notes: ReleaseNotes
    supersedes: SupersedesRecord | None = None
    withdrawal: WithdrawalRecord | None = None
    limitations: tuple[KnownLimitation, ...] = Field(default=(), max_length=_MAX_LIMITATIONS)
    issued_at: str | None = Field(default=None, pattern=_TIMESTAMP, min_length=20, max_length=40)

    @model_validator(mode="after")
    def coherent_release(self) -> PublicReleaseManifest:
        names = [field.name for field in self.fields]
        if len(set(names)) != len(names):
            raise ValueError("Public schema field names must be unique")
        kinds = [review.kind for review in self.reviews]
        if len(set(kinds)) != len(kinds):
            raise ValueError("Each review kind contributes at most one evidence record")
        stale = [
            review.kind
            for review in self.reviews
            if review.decided_at is not None and review.decided_at < self.source.captured_at
        ]
        if stale:
            raise ValueError("Source authorization predates the frozen source capture")
        if self.state in _SEALED_STATES:
            if self.issued_at is None:
                raise ValueError("A sealed release must carry its issuance timestamp")
            if self.population.content_digest is None:
                raise ValueError(
                    "Issuing without the published content digest is a fabricated success"
                )
        else:
            if self.issued_at is not None:
                raise ValueError("Only sealed states carry an issuance timestamp")
        if (self.state == "withdrawn") != (self.withdrawal is not None):
            raise ValueError(
                "Withdrawn releases require withdrawal evidence; no other state may carry it"
            )
        if self.withdrawal is not None:
            issued_as_before = self.model_copy(update={"state": "issued", "withdrawal": None})
            if self.withdrawal.issued_manifest_digest != issued_as_before.digest():
                raise ValueError(
                    "Withdrawal evidence must reference the digest of the manifest "
                    "exactly as issued"
                )
        if (
            self.supersedes is not None
            and self.supersedes.release_public_id != self.identity.public_id
        ):
            raise ValueError("Supersession records must reference the same public dataset")
        if self.coverage_end is not None and self.coverage_end < self.coverage_start:
            raise ValueError("Coverage end cannot precede coverage start")
        _EXPECTED_POPULATION = {
            "governed_snapshot": "snapshot_rows",
            "materialized_view": "materialization_rows",
            "frozen_publication": "materialization_rows",
            "external_artifact": "external_artifact",
        }
        expected_population = _EXPECTED_POPULATION[self.source.mode]
        if self.population.mode != expected_population:
            raise ValueError(
                f"Population mode {self.population.mode!r} does not follow from "
                f"source mode {self.source.mode!r}"
            )
        return self

    def digest(self) -> Digest:
        return canonical_release_digest(self.model_dump(mode="json"))

    def public_evidence(self) -> dict[str, object]:
        """Metadata-only projection for logs; every field is public by construction."""

        return {
            "format": self.format,
            "schema_version": self.schema_version.model_dump(mode="json"),
            "public_id": self.identity.public_id,
            "release_version": self.release_version,
            "state": self.state,
            "row_count": self.population.row_count,
            "field_count": len(self.fields),
            "license_id": self.license.license_id,
            "content_digest": self.population.content_digest,
            "supersedes_present": self.supersedes is not None,
            "withdrawal_present": self.withdrawal is not None,
            "limitation_count": len(self.limitations),
        }


class InternalSourceRef(ContractModel):
    """One internal lineage item; never serialized into the public manifest."""

    ref: Identifier = Field(repr=False)
    kind: Literal["data_product", "snapshot", "materialization", "query_revision"]
    digest: Digest = Field(repr=False)


class InternalSourceLedger(ContractModel):
    """The private companion of one public release manifest.

    Exact internal source references and digests live here, bound to the
    public manifest by digest and public id. Nothing in this document is
    published; it exists so internal lineage remains referenced securely
    while the public provenance stays curated and minimized.
    """

    identity_public_id: str = Field(pattern=_PUBLIC_ID, repr=False)
    manifest_digest: Digest = Field(repr=False)
    internal_catalog_ref: Identifier = Field(repr=False)
    sources: tuple[InternalSourceRef, ...] = Field(min_length=1, max_length=16, repr=False)
    captured_at: str = Field(pattern=_TIMESTAMP, min_length=20, max_length=40, repr=False)


class ReleaseReadiness(ContractModel):
    """Deterministic verdict over one manifest; no publication authority."""

    manifest_digest: Digest
    ready: bool
    blocking: tuple[str, ...] = Field(default=(), max_length=_MAX_REVIEWS + 2)  # noqa: E501


def release_readiness(manifest: PublicReleaseManifest) -> ReleaseReadiness:
    """Classify whether a manifest may be issued without executing anything."""

    blocking: list[str] = []
    by_kind = {review.kind: review for review in manifest.reviews}
    for kind, missing_code, unapproved_code in (
        ("disclosure", "disclosure_review_missing", "disclosure_review_not_approved"),
        ("license", "license_review_missing", "license_review_not_approved"),
    ):
        review = by_kind.get(kind)
        if review is None:
            blocking.append(missing_code)
        elif review.status != "approved":
            blocking.append(unapproved_code)
    if manifest.population.content_digest is None:
        blocking.append("population_digest_missing")
    return ReleaseReadiness(
        manifest_digest=manifest.digest(),
        ready=not blocking,
        blocking=tuple(blocking),
    )


def bind_internal_ledger(
    ledger: InternalSourceLedger, manifest: PublicReleaseManifest
) -> InternalSourceLedger:
    """Bind an internal lineage ledger to the exact manifest it documents."""

    if (
        ledger.manifest_digest != manifest.digest()
        or ledger.identity_public_id != manifest.identity.public_id
    ):
        raise PublicReleaseError(PublicReleaseError.LEDGER_MISMATCH)
    return ledger


def _version_key(version: str) -> tuple[int, int]:
    major, minor = version.split(".", 1)
    return int(major), int(minor)


def diff_releases(
    previous: PublicReleaseManifest, candidate: PublicReleaseManifest
) -> ReleaseNotes:
    """Deterministic vN→vN+1 release notes; never exposes internal lineage."""

    if previous.identity.public_id != candidate.identity.public_id:
        raise PublicReleaseError(PublicReleaseError.CROSS_DATASET_DIFF)
    if _version_key(candidate.release_version) <= _version_key(previous.release_version):
        raise PublicReleaseError(PublicReleaseError.NON_MONOTONIC_VERSION)
    changes: list[ReleaseChange] = []
    previous_fields = {field.name: field for field in previous.fields}
    candidate_fields = {field.name: field for field in candidate.fields}
    for name in sorted(set(candidate_fields) - set(previous_fields)):
        changes.append(ReleaseChange(kind="field_added", detail=name))
    for name in sorted(set(previous_fields) - set(candidate_fields)):
        changes.append(ReleaseChange(kind="field_removed", detail=name))
    for name in sorted(set(previous_fields) & set(candidate_fields)):
        before, after = previous_fields[name], candidate_fields[name]
        if before.dtype != after.dtype or before.nullable != after.nullable:
            changes.append(ReleaseChange(kind="field_retyped", detail=name))
    if candidate.source.source_digest != previous.source.source_digest:
        changes.append(ReleaseChange(kind="source_refresh", detail=previous.release_version))
    if (
        candidate.coverage_start < previous.coverage_start
        or (candidate.coverage_end or "") > (previous.coverage_end or "")
    ):
        changes.append(ReleaseChange(kind="coverage_extended", detail=previous.release_version))
    if candidate.license.license_id != previous.license.license_id:
        changes.append(
            ReleaseChange(kind="license_change", detail=candidate.license.license_id)
        )
    if candidate.state == "deprecated" and previous.state != "deprecated":
        changes.append(ReleaseChange(kind="deprecation", detail=candidate.release_version))
    return ReleaseNotes(
        summary=f"Changes from {previous.release_version} to {candidate.release_version}",
        changes=tuple(sorted(changes, key=lambda change: (change.kind, change.detail))),
    )


class _PublicIdCheck(ContractModel):
    """Minimal pattern guard so URI helpers validate IDs without a manifest."""

    public_id: str = Field(pattern=_PUBLIC_ID)


def public_release_uri_path(public_id: str, release_version: str) -> str:
    """Stable public URI path; rejects internal-ID shapes and traversal payloads."""

    checked = _PublicIdCheck(public_id=public_id).public_id
    if not _RELEASE_VERSION.match(release_version):
        raise PublicReleaseError(PublicReleaseError.INVALID_MANIFEST)
    return f"/public/datasets/{checked}/releases/{release_version}"


def parse_public_release_manifest(value: object) -> PublicReleaseManifest:
    """Parse at an untrusted boundary with fixed safe error codes.

    The version pre-check exists to report an incompatible *version* (a future
    producer) distinctly from a malformed manifest; everything else falls to
    strict validation and its single safe code.
    """

    if isinstance(value, dict):
        version = value.get("schema_version")
        if version is not None:
            major = _parse_version(version)
            if major not in SUPPORTED_MAJOR_VERSIONS:
                raise PublicReleaseError(PublicReleaseError.INCOMPATIBLE_VERSION) from None
    try:
        return PublicReleaseManifest.model_validate(value)
    except ValidationError:
        raise PublicReleaseError(PublicReleaseError.INVALID_MANIFEST) from None
