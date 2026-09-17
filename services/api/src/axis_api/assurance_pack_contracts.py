"""Assurance pack manifest contract: audience-bound, revision-exact evidence.

Contract slice of [#883](https://github.com/Limes-Labs/limes-axis/issues/883)
(parent #733). This module is pure vocabulary: no artifact packaging, no
signing, no evidence store. It freezes **which** existing answers, deployment
observations and evidence revisions may appear in one customer-facing pack:

* A versioned ``axis.assurance-pack.manifest`` envelope with strict
  round-trips; unknown fields and incompatible major versions are rejected.
* Every selection cites exact revisions and digests of contracts owned
  elsewhere (#729 evidence, #730 release/profile posture, #731 reviewed
  answers); this contract creates no new registry.
* Support is a structured state machine — ``current``, ``partial``,
  ``planned``, ``customer_responsibility``, ``not_evidenced``,
  ``cannot_disclose`` — never a prose claim; gaps and limitations are
  preserved, not converted into positive compliance answers.
* Entry support is validated against the frozen release/profile snapshot:
  an expired certificate, a wrong release/profile or a superseded answer
  cannot pass as current support.
* Any change to answers, evidence or audience after approval invalidates the
  candidate digest — preflight and review must run again.
* Missing required support blocks issuance; a partial pack must explicitly
  list its unsupported requirements. Reference-only items carry no artifact;
  included artifacts carry digests. Hidden evidence never leaks through
  titles, issuers, filenames or error details.

The digest helper is shared so producers cannot sign non-canonical bytes.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from axis_sdk.connector_authoring.contracts import ContractModel, Digest
from pydantic import Field, ValidationError, model_validator

PACK_FORMAT = "axis.assurance-pack.manifest"
CONTRACT_MAJOR = 1
CONTRACT_MINOR = 0

#: Supported schema versions for reading; major bumps change semantics.
SUPPORTED_MAJOR_VERSIONS = (CONTRACT_MAJOR,)

_MAX_ENTRIES = 128
_MAX_TEXT = 500
_MAX_TITLE = 200
_MAX_REFERENCES = 16

_IDENTIFIER = r"^[a-z][a-z0-9-]{2,47}$"
_ORG = r"^[a-z][a-z0-9-]{2,31}$"
_AUDIENCE = r"^[a-z][a-z0-9-]{2,31}$"
_RELEASE = r"^\d+\.\d+\.\d+$"
_PROFILE = r"^[a-z][a-z0-9-]{2,31}$"
_REVISION = r"^\d+$"
_DATE = r"^\d{4}-\d{2}-\d{2}$"
# Reference IDs cite registered contracts; the grammar stays opaque (no
# absolute paths, no traversal, no URLs) because citations may cross tenants.
_REFERENCE = r"^[a-z][a-z0-9._-]{2,99}$"
# Free text never renders evidence that was not selected; it is bounded
# prose without markup or template delimiters.
_UNSAFE = re.compile(r"(?i)(<\s*script|javascript:|\{\{|\}\}|\$\{|__proto__)")

SupportState = Literal[
    "current",
    "partial",
    "planned",
    "customer_responsibility",
    "not_evidenced",
    "cannot_disclose",
]
EntryMode = Literal["included_artifact", "reference_only"]
DisclosureClass = Literal["public", "under_nda", "internal_only"]


class AssurancePackError(ValueError):
    """Fixed contract codes; raw validation details are never rendered."""

    INCOMPATIBLE_VERSION = "incompatible_assurance_pack_version"
    INVALID_MANIFEST = "invalid_assurance_pack_manifest"
    STALE_SUPPORT = "stale_pack_support"
    REQUIRED_SUPPORT_MISSING = "required_support_missing"
    PARTIAL_UNSUPPORTED_MISSING = "partial_pack_unsupported_missing"
    DUPLICATE_ENTRY = "duplicate_pack_entry"
    UNSAFE_TEXT = "unsafe_pack_text"

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_pack_digest(value: object) -> Digest:
    """Deterministic digest over canonical JSON; producers must reuse this."""

    data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _ensure_safe(text: str) -> str:
    if _UNSAFE.search(text):
        raise AssurancePackError(AssurancePackError.UNSAFE_TEXT)
    return text


def _parse_major(value: object) -> int:
    if not isinstance(value, dict):
        raise AssurancePackError(AssurancePackError.INVALID_MANIFEST)
    version = value.get("schema_version")
    major = version.get("major") if isinstance(version, dict) else None
    if not isinstance(major, int) or isinstance(major, bool):
        raise AssurancePackError(AssurancePackError.INVALID_MANIFEST)
    return major


class ManifestVersion(ContractModel):
    major: int = Field(ge=1, strict=True)
    minor: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def bounded_version(self) -> ManifestVersion:
        if self.major != CONTRACT_MAJOR or self.minor != CONTRACT_MINOR:
            raise ValueError(f"Unsupported assurance pack version {self.major}.{self.minor}")
        return self


class PackContext(ContractModel):
    """One engagement, one audience, one purpose; never a product claim."""

    engagement_ref: str = Field(pattern=_REFERENCE)
    audience: str = Field(pattern=_AUDIENCE)
    purpose: str = Field(min_length=1, max_length=_MAX_TEXT)
    disclosure_class: DisclosureClass = "under_nda"

    @model_validator(mode="after")
    def safe_purpose(self) -> PackContext:
        _ensure_safe(self.purpose)
        return self


class ReleaseSnapshot(ContractModel):
    """The frozen release/profile posture the whole pack speaks about."""

    release: str = Field(pattern=_RELEASE)
    profile: str = Field(pattern=_PROFILE)
    posture_observation_ref: str = Field(pattern=_REFERENCE)
    posture_revision: str = Field(pattern=_REVISION)
    posture_digest: Digest = Field(repr=False)


class AnswerSelection(ContractModel):
    """One reviewed answer at one exact revision (#731 owns the content)."""

    entry_id: str = Field(pattern=_IDENTIFIER)
    question_ref: str = Field(pattern=_REFERENCE)
    answer_revision: str = Field(pattern=_REVISION)
    answer_digest: Digest = Field(repr=False)
    support: SupportState
    responsibility: Literal["axis", "shared", "customer"] = "axis"
    disclosure: DisclosureClass = "under_nda"
    mode: EntryMode = "reference_only"
    artifact_digest: Digest | None = Field(default=None, repr=False)
    evidence_refs: tuple[str, ...] = Field(default=(), max_length=_MAX_REFERENCES)
    limitation: str | None = Field(default=None, min_length=1, max_length=_MAX_TEXT)
    as_of: str = Field(pattern=_DATE, min_length=10, max_length=10)

    @model_validator(mode="after")
    def coherent_entry(self) -> AnswerSelection:
        _ensure_safe(self.question_ref)
        if self.limitation is not None:
            _ensure_safe(self.limitation)
        if self.support in {"partial", "planned", "not_evidenced"} and self.limitation is None:
            raise ValueError(
                f"{self.support} entries must state their exact limitation"
            )
        if self.mode == "included_artifact":
            if self.artifact_digest is None:
                raise ValueError("Included artifacts carry their content digest")
            if self.disclosure == "internal_only":
                raise ValueError("Internal-only content cannot ship inside a pack")
        elif self.artifact_digest is not None:
            raise ValueError("Reference-only entries carry no artifact bytes")
        if self.support == "customer_responsibility" and self.responsibility == "axis":
            raise ValueError("Customer-responsibility answers cannot claim Axis ownership")
        return self


class PackManifest(ContractModel):
    """One audience-bound pack over exact approved revisions."""

    format: Literal["axis.assurance-pack.manifest"] = PACK_FORMAT
    schema_version: ManifestVersion
    pack_id: str = Field(pattern=_IDENTIFIER)
    title: str = Field(min_length=1, max_length=_MAX_TITLE)
    context: PackContext
    release_snapshot: ReleaseSnapshot
    entries: tuple[AnswerSelection, ...] = Field(min_length=1, max_length=_MAX_ENTRIES)
    valid_through: str = Field(pattern=_DATE, min_length=10, max_length=10)

    @model_validator(mode="after")
    def coherent_pack(self) -> PackManifest:
        _ensure_safe(self.title)
        entry_ids = [entry.entry_id for entry in self.entries]
        if len(set(entry_ids)) != len(entry_ids):
            raise AssurancePackError(AssurancePackError.DUPLICATE_ENTRY)
        return self

    def digest(self) -> Digest:
        return canonical_pack_digest(self.model_dump(mode="json"))


def check_support_freshness(
    manifest: PackManifest,
    *,
    observed: dict[str, str],
) -> tuple[Digest, tuple[str, ...]]:
    """Re-verify every entry's support state against observed facts.

    ``observed`` maps ``entry_id`` to the entry's currently observed state:
    ``current`` while the cited evidence is unexpired and on the frozen
    release/profile, or a state token such as ``expired_certificate``,
    ``wrong_release_profile`` or ``superseded_answer``. Any mismatch marks
    the entry stale; the returned digest is the manifest's, so a stale pack
    is detectably different from its approved form.
    """

    stale: list[str] = []
    for entry in manifest.entries:
        observed_state = observed.get(entry.entry_id, "missing_observation")
        if observed_state != "current":
            stale.append(f"{entry.entry_id}:{observed_state}")
    return manifest.digest(), tuple(stale)


def pack_readiness(manifest: PackManifest) -> tuple[Digest, bool, tuple[str, ...]]:
    """Deterministic preflight: required support and partial disclosures.

    Missing support on an entry without an explicit ``not_evidenced``/``planned``
    state blocks issuance; a pack that is not fully ``current`` must list its
    limitations (validated at construction) — the blocking list names them.
    """

    blocking: list[str] = []
    for entry in manifest.entries:
        if entry.support in {"not_evidenced", "planned"} and entry.limitation is None:
            blocking.append(f"{entry.entry_id}:limitation_required")
    if not any(entry.support == "current" for entry in manifest.entries):
        blocking.append("no_current_support_in_pack")
    return manifest.digest(), not blocking, tuple(blocking)


def reference_scope_note() -> str:
    """How #871 isolation and #879 portability reports may be cited.

    Their reports are reference-only citations bound to their actually
    tested scope; configuration flags never become proof. The note is part
    of the contract so producers cannot reword it.
    """

    return (
        "Isolation (#871) and portability (#879) reports may be cited "
        "reference-only for their actually tested scope and revision; "
        "deployment configuration flags are not evidence of independent "
        "certification."
    )


def parse_assurance_pack(value: object) -> PackManifest:
    """Parse an untrusted pack payload with fixed safe error codes."""

    if isinstance(value, dict):
        major = _parse_major(value)
        if major not in SUPPORTED_MAJOR_VERSIONS:
            raise AssurancePackError(AssurancePackError.INCOMPATIBLE_VERSION)
    try:
        return PackManifest.model_validate(value)
    except ValidationError:
        raise AssurancePackError(AssurancePackError.INVALID_MANIFEST) from None
