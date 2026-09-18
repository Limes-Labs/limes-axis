"""#885 Assurance packs 3/3: immutable signed issuance + offline verification.

Delivers the issuance/lifecycle layer of the assurance-pack family on top of
the two merged siblings:

- **#883 contract** (`assurance_pack_contracts.py`): the audience-bound
  ``PackManifest``, its digest and the support re-check rule. This module
  never rebuilds them.
- **#884 packaging** (`assurance_packaging.py`): the deterministic package
  assembly. Issuance binds an approval to an already *assembled* package.
- **#477 key custody** (`audit_signing.py`): the approved signer pattern —
  a protocol signer, a self-hosted implementation, proofs that never carry
  secret material, and HMAC-SHA256 over canonical JSON. No new PKI here.
- **#729 evidence lifecycle**: capture time, ``valid_through`` constraints
  and supersession references as separate, explicit lifecycle facts.
- **#329 audit integrity**: issued records are immutable facts; verification
  never rewrites history.

Boundaries this module enforces:

- **Authorization is the caller's job.** ``issue_assurance_pack`` never
  consults roles or tenants; it records who was already approved. The gate
  it *does* own: the approval must cover the exact manifest/package digests
  being issued, and the sign-time support re-check must still be current.
- **Trust is always a parameter.** ``verify_assurance_pack_offline`` has no
  network, no database and no global key material. An untrusted package's
  embedded trust anchor cannot authenticate itself: the verifier demands
  separately trusted verification material for the signer identity the
  record claims. Missing or mismatching material yields qualified results,
  never an unqualified "current and trusted".
- **Signature semantics are bounded**: a valid signature proves integrity
  and provenance of the bytes — not certification, not the truth of
  self-attested claims. The wording constant is exported for UI/CLI/report
  surfaces so the caveat cannot be dropped.
- **Historical results never change**: expiration, revocation-for-future-use
  and supersession change *current reuse* state; re-verifying an issued
  package with the same inputs always yields the same integrity verdict.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from axis_api.assurance_pack_contracts import (
    PackManifest,
    check_support_freshness,
)
from axis_api.assurance_packaging import _attachment_name

ISSUANCE_FORMAT = "axis.assurance-pack.issuance"
ISSUANCE_FORMAT_MAJOR = 1
ISSUANCE_FORMAT_MINOR = 0

ALGORITHM_HMAC_SHA256 = "hmac-sha256"
SUPPORTED_ALGORITHMS = (ALGORITHM_HMAC_SHA256,)
SIGNING_MODE_SELF_HOSTED_HMAC = "self_hosted_hmac"

_SIGNATURE_SEMANTICS_NOTE = (
    "Signature verification proves integrity and provenance of the issued "
    "package bytes. It is not regulatory certification, not a statement "
    "about evidence freshness beyond the recorded lifecycle facts, and not "
    "a verification of self-attested claims inside the pack."
)

_MAX_REVOKE_AGE_DAYS = 7

_UNSAFE = re.compile(r"(?i)(<\s*script|javascript:|\{\{|\}\}|\$\{|__proto__)")


class AssuranceIssuanceError(ValueError):
    """Fixed issuance codes; raw validation details are never rendered."""

    NOT_ASSEMBLED = "issuance_requires_assembled_package"
    APPROVAL_MISMATCH = "approval_does_not_match_package"
    STALE_SUPPORT = "stale_pack_support"
    UNSUPPORTED_SIGNER = "unsupported_signing_provider"
    INVALID_INPUT = "invalid_issuance_input"

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


class SignatureProof(BaseModel):
    """Signature over the issuance payload; never carries secret material."""

    algorithm: str = Field(min_length=1)
    key_id: str = Field(min_length=1)
    signing_mode: str = Field(min_length=1)
    signed_payload_sha256: str = Field(min_length=64, max_length=64)
    signature: str = Field(min_length=16)


class PackageSigner(Protocol):
    """#477-style custody: sign one canonical payload, return one proof."""

    key_id: str
    algorithm: str

    def sign_payload(self, payload: dict) -> SignatureProof: ...


class SelfHostedHmacPackSigner:
    """Self-hosted HMAC custody reusing the #477 canonical-JSON scheme."""

    algorithm = ALGORITHM_HMAC_SHA256

    def __init__(self, key_id: str, secret_key: str) -> None:
        if not key_id or not secret_key:
            raise AssuranceIssuanceError(AssuranceIssuanceError.INVALID_INPUT)
        self.key_id = key_id
        self._secret_key = secret_key.encode("utf-8")

    def sign_payload(self, payload: dict) -> SignatureProof:
        encoded = _canonical_json(payload).encode("utf-8")
        return SignatureProof(
            algorithm=self.algorithm,
            key_id=self.key_id,
            signing_mode=SIGNING_MODE_SELF_HOSTED_HMAC,
            signed_payload_sha256=hashlib.sha256(encoded).hexdigest(),
            signature=hmac.new(self._secret_key, encoded, hashlib.sha256).hexdigest(),
        )


def unsigned_issuance_payload(record: IssuedAssurancePack) -> dict:
    """The exact canonical payload the signature covers — one owner.

    Both the issuer (before signing) and the verifier (re-deriving the
    expected signature) call this; they cannot drift apart.
    """

    data = record.model_dump(mode="json")
    data.pop("signature", None)
    return {"issuance": data}


class IssuanceFormatVersion(BaseModel):
    major: int = Field(ge=1, strict=True)
    minor: int = Field(ge=0, strict=True)


class SigningProfile(BaseModel):
    """Which approved custody mode and key issued this exact record."""

    mode: str = Field(min_length=1, max_length=64)
    key_id: str = Field(min_length=1, max_length=128)
    algorithm: str = Field(min_length=1, max_length=64)


class IssuanceLifecycle(BaseModel):
    """#729 lifecycle facts as separate fields, never folded into one flag."""

    capture_time: str = Field(min_length=1, max_length=64)
    valid_through: str = Field(min_length=10, max_length=10)
    revocation_status: str = Field(min_length=1, max_length=64)
    supersession: tuple[str, ...] = Field(default=(), max_length=16)


class IssuedAssurancePack(BaseModel):
    """Immutable issuance record: one issued version, one signer, one digest.

    Binds the #883 manifest digest and the #884 package digest to the exact
    audience and signing profile. Records are not mutated after issuance;
    any change is a new package with a new record and, when it corrects a
    prior one, an explicit supersession reference.
    """

    format: Literal["axis.assurance-pack.issuance"] = ISSUANCE_FORMAT
    format_version: IssuanceFormatVersion
    pack_id: str = Field(min_length=1, max_length=128)
    audience: str = Field(min_length=1, max_length=128)
    purpose: str = Field(min_length=1, max_length=500)
    manifest_sha256: str = Field(min_length=64, max_length=64, repr=False)
    package_sha256: str = Field(min_length=64, max_length=64, repr=False)
    released_release: str = Field(min_length=1, max_length=64)
    released_profile: str = Field(min_length=1, max_length=64)
    signing_profile: SigningProfile
    lifecycle: IssuanceLifecycle
    signature: SignatureProof


class IssuanceApproval(BaseModel):
    """The caller's authorization fact for one exact issuance.

    The issuer records it verbatim; it never re-derives who may approve.
    ``recheck`` maps entry ids to observed support states (`current` while
    unexpired and on the frozen release/profile) for the sign-time gate.
    """

    approver_ref: str = Field(min_length=1, max_length=128)
    manifest_sha256: str = Field(min_length=64, max_length=64)
    audience: str = Field(min_length=1, max_length=128)
    released_release: str = Field(min_length=1, max_length=64)
    released_profile: str = Field(min_length=1, max_length=64)
    recheck: dict[str, str] = Field(default_factory=dict)


class AssembledPackView(Protocol):
    """Minimal #884 shape the issuer binds to (avoids a hard import cycle)."""

    manifest: PackManifest
    package_sha256: str


def issue_assurance_pack(
    *,
    pack_id: str,
    purpose: str,
    assembled: AssembledPackView,
    approval: IssuanceApproval,
    signer: PackageSigner,
    capture_time: str,
    supersedes: tuple[str, ...] = (),
) -> IssuedAssurancePack:
    """Bind final issue approval to the exact assembled package digest.

    Raises fixed-code :class:`AssuranceIssuanceError` — the caller is left
    with no issuance record — when the approval does not cover this exact
    manifest digest/audience/release/profile, when the sign-time support
    re-check has drifted, or when the signer is not an approved mode. The
    manifest's ``valid_through`` is copied verbatim into the lifecycle:
    expiration is an evidence fact, not an issuance decision.
    """

    if not isinstance(assembled.manifest, PackManifest):
        raise AssuranceIssuanceError(AssuranceIssuanceError.NOT_ASSEMBLED)
    manifest = assembled.manifest

    if (
        approval.manifest_sha256 != manifest.digest()
        or approval.audience != manifest.context.audience
        or approval.released_release != manifest.release_snapshot.release
        or approval.released_profile != manifest.release_snapshot.profile
    ):
        raise AssuranceIssuanceError(AssuranceIssuanceError.APPROVAL_MISMATCH)

    _, stale = check_support_freshness(manifest, observed=approval.recheck)
    if stale:
        raise AssuranceIssuanceError(AssuranceIssuanceError.STALE_SUPPORT)

    if signer.algorithm not in SUPPORTED_ALGORITHMS:
        raise AssuranceIssuanceError(AssuranceIssuanceError.UNSUPPORTED_SIGNER)
    for text in (pack_id, purpose):
        if _UNSAFE.search(text):
            raise AssuranceIssuanceError(AssuranceIssuanceError.INVALID_INPUT)

    unsigned = IssuedAssurancePack(
        format=ISSUANCE_FORMAT,
        format_version=IssuanceFormatVersion(
            major=ISSUANCE_FORMAT_MAJOR,
            minor=ISSUANCE_FORMAT_MINOR,
        ),
        pack_id=pack_id,
        audience=manifest.context.audience,
        purpose=purpose,
        manifest_sha256=manifest.digest(),
        package_sha256=assembled.package_sha256,
        released_release=manifest.release_snapshot.release,
        released_profile=manifest.release_snapshot.profile,
        signing_profile=SigningProfile(
            mode=SIGNING_MODE_SELF_HOSTED_HMAC,
            key_id=signer.key_id,
            algorithm=signer.algorithm,
        ),
        lifecycle=IssuanceLifecycle(
            capture_time=capture_time,
            valid_through=manifest.valid_through,
            revocation_status="not_revoked",
            supersession=supersedes,
        ),
        signature=SignatureProof(
            algorithm="unsigned",
            key_id="unsigned",
            signing_mode="pending",
            signed_payload_sha256="0" * 64,
            signature="pending-signature-payload",
        ),
    )
    proof = signer.sign_payload(unsigned_issuance_payload(unsigned))
    return unsigned.model_copy(update={"signature": proof})


# --------------------------------------------------------------------------
# Offline verification
# --------------------------------------------------------------------------


class TrustedVerificationMaterial(BaseModel):
    """Material from a separately trusted channel — never from the package.

    A package that embeds its own "trust anchor" authenticates nothing but
    itself; the verifier demands an independently obtained identity and key
    for the signer the record claims to be.
    """

    key_id: str = Field(min_length=1)
    algorithm: str = Field(min_length=1)
    signing_mode: str = Field(min_length=1)
    secret_key: str = Field(min_length=1, repr=False)


class VerificationClock(BaseModel):
    """Explicit verification-time facts; absence must stay visible."""

    verification_time: str | None = None
    revocation_observed_at: str | None = None
    max_revocation_age_days: int = Field(default=_MAX_REVOKE_AGE_DAYS, ge=1)


@dataclass(frozen=True)
class OfflineVerificationResult:
    """Qualified result with separate integrity, freshness, revocation fields.

    ``qualified_result`` is the strongest claim the inputs support:
    ``verified_current`` only when the signature verified under separately
    trusted material, every digest matched, the evidence is within its
    ``valid_through`` on a certain clock, and revocation information is
    current. Anything less is explicitly qualified or failed.
    """

    qualified_result: str
    signature_integrity: str
    package_integrity: str
    evidence_freshness: str
    revocation_status: str
    clock_status: str
    notes: tuple[str, ...]

    def signature_semantics_note(self) -> str:
        """The bounded wording every UI/CLI/report surface must keep."""

        return _SIGNATURE_SEMANTICS_NOTE


class ArtifactByteSource(Protocol):
    """Provides attachment bytes extracted from the package under test."""

    def resolve(self, entry_id: str) -> bytes: ...


def verify_assurance_pack_offline(
    *,
    issuance_json: bytes,
    package_bytes: bytes,
    manifest: PackManifest,
    artifacts: ArtifactByteSource,
    trust_material: TrustedVerificationMaterial | None,
    clock: VerificationClock | None,
) -> OfflineVerificationResult:
    """Bounded offline verification of one issued package.

    No network, no database, no process-global trust: every input arrives
    as an argument. ``manifest`` and per-attachment bytes are extracted
    from the package under test by the caller; trust material must come
    through a separately trusted channel. Stale revocation data or an
    uncertain clock can only qualify the result, never upgrade it.
    """

    try:
        record = IssuedAssurancePack.model_validate_json(issuance_json)
    except Exception:
        return _failed("issuance record is not a valid #885 payload")

    notes = [_SIGNATURE_SEMANTICS_NOTE]

    # Structural integrity first: issued digests over the presented bytes.
    package_integrity = "verified"
    if record.manifest_sha256 != manifest.digest():
        return _failed("manifest digest does not match the issued record")
    if record.package_sha256 != hashlib.sha256(package_bytes).hexdigest():
        return _failed(
            "package digest does not match the issued record",
            package_integrity="failed",
        )
    for entry in manifest.entries:
        if entry.mode != "included_artifact":
            continue
        name = _attachment_name(entry.entry_id)
        # Membership before resolution: a missing member must produce a
        # fixed verification failure, never a resolver crash.
        if name not in _member_names(package_bytes):
            return _failed(
                f"required package member missing: {name}",
                package_integrity="failed",
            )
        content = artifacts.resolve(entry.entry_id)
        if hashlib.sha256(content).hexdigest() != entry.artifact_digest:
            return _failed(
                f"attachment digest mismatch for {entry.entry_id}",
                package_integrity="failed",
            )

    if trust_material is None:
        return OfflineVerificationResult(
            qualified_result="untrusted_input",
            signature_integrity="unverifiable",
            package_integrity=package_integrity,
            evidence_freshness=_freshness(record, clock),
            revocation_status=_revocation(record, clock),
            clock_status=_clock_status(clock),
            notes=(
                *notes,
                "No separately trusted verification material was supplied; "
                "an embedded key cannot authenticate its own package.",
            ),
        )

    if record.signing_profile.algorithm not in SUPPORTED_ALGORITHMS:
        return _failed(
            f"unsupported signature algorithm: {record.signing_profile.algorithm}",
            package_integrity=package_integrity,
        )
    if (
        trust_material.key_id != record.signing_profile.key_id
        or trust_material.algorithm != record.signing_profile.algorithm
        or trust_material.signing_mode != record.signing_profile.mode
    ):
        return _failed(
            "trusted material does not match the issued signer identity",
            package_integrity=package_integrity,
        )

    payload = unsigned_issuance_payload(record)
    encoded = _canonical_json(payload).encode("utf-8")
    expected = hmac.new(
        trust_material.secret_key.encode("utf-8"),
        encoded,
        hashlib.sha256,
    ).hexdigest()
    signature_ok = hmac.compare_digest(
        record.signature.signature, expected
    ) and hmac.compare_digest(
        record.signature.signed_payload_sha256,
        hashlib.sha256(encoded).hexdigest(),
    )
    if not signature_ok:
        return _failed(
            "signature does not verify over the issuance payload",
            package_integrity=package_integrity,
        )

    notes.append(
        "Signature verified with separately trusted verification material."
    )

    freshness = _freshness(record, clock)
    revocation = _revocation(record, clock)
    clock_status = _clock_status(clock)
    return OfflineVerificationResult(
        qualified_result=_qualified(freshness, revocation, clock_status),
        signature_integrity="verified",
        package_integrity="verified",
        evidence_freshness=freshness,
        revocation_status=revocation,
        clock_status=clock_status,
        notes=tuple(notes),
    )


def _member_names(package_bytes: bytes) -> set[str]:
    with zipfile.ZipFile(io.BytesIO(package_bytes)) as archive:
        return set(archive.namelist())


def _failed(
    reason: str,
    *,
    package_integrity: str = "not_checked",
) -> OfflineVerificationResult:
    return OfflineVerificationResult(
        qualified_result="failed",
        signature_integrity="failed",
        package_integrity=package_integrity,
        evidence_freshness="not_checked",
        revocation_status="not_checked",
        clock_status="not_checked",
        notes=(f"Verification failed: {reason}.",),
    )


def _freshness(record: IssuedAssurancePack, clock: VerificationClock | None) -> str:
    if clock is None or clock.verification_time is None:
        return f"valid_through:{record.lifecycle.valid_through}"
    now = _date_of(clock.verification_time)
    valid_through = _date_of(record.lifecycle.valid_through)
    if now is None or valid_through is None:
        return "undetermined"
    return "current" if now <= valid_through else "expired"


def _revocation(record: IssuedAssurancePack, clock: VerificationClock | None) -> str:
    if record.lifecycle.revocation_status == "revoked_for_future_use":
        return "revoked_for_future_use"
    if clock is None or clock.revocation_observed_at is None:
        return "no_current_revocation_information"
    observed = _date_of(clock.revocation_observed_at)
    now = _date_of(clock.verification_time or "")
    if observed is None:
        return "unparseable_revocation_observation"
    if now is not None and (now - observed).days > clock.max_revocation_age_days:
        return "stale_revocation_information"
    return f"observed_at:{clock.revocation_observed_at}"


def _clock_status(clock: VerificationClock | None) -> str:
    if clock is None or clock.verification_time is None:
        return "uncertain"
    return "certain"


def _qualified(freshness: str, revocation: str, clock_status: str) -> str:
    if freshness != "current":
        return "verified_but_qualified"
    if revocation in {
        "no_current_revocation_information",
        "stale_revocation_information",
        "revoked_for_future_use",
        "unparseable_revocation_observation",
    }:
        return "verified_but_qualified"
    if clock_status == "uncertain":
        return "verified_but_qualified"
    return "verified_current"


def _date_of(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
