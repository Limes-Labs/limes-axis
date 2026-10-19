"""#885 Assurance packs 3/3: immutable signed issuance + offline verification.

Delivers the issuance/lifecycle layer of the assurance-pack family on top of
its two siblings:

- **#883 contract** (`assurance_pack_contracts.py`): the audience-bound
  ``PackManifest``, its digest, the preflight and the support re-check rule.
  This module never rebuilds them.
- **#884 packaging** (`assurance_packaging.py`): the deterministic package
  assembly. Issuance binds an approval to an already *assembled* package and
  the verifier re-derives the package members from the manifest.
- **#477 key custody**: the protocol-signer pattern of `audit_signing.py`
  (a signer object that holds its key and returns a proof that never carries
  secret material). The audit ledger's self-hosted HMAC mode is a shared
  secret: anyone able to verify it could also forge it, so it cannot let an
  external reviewer verify a package offline. Issuance therefore accepts only
  asymmetric Ed25519 signatures (from the existing ``cryptography``
  dependency); the private key stays inside the caller-supplied signer and
  verifiers receive only the public key.
- **#729 evidence lifecycle**: capture time, ``valid_through`` and
  supersession references are separate, explicit lifecycle facts.
- **#329 audit integrity**: issued records are immutable facts; verification
  never rewrites history.

Boundaries this module enforces:

- **Authorization is the caller's job.** ``issue_assurance_pack`` never
  consults roles or tenants; it records who already approved. The gates it
  *does* own: the approval must cover the exact manifest and package digests
  being issued, the pack must pass preflight, and the sign-time support
  re-check must still be current.
- **Trust is always a parameter.** ``verify_assurance_pack_offline`` has no
  network, no database and no global key material, and it reads the manifest
  and attachments from the package under test itself. A record cannot carry
  its own trust anchor (unknown fields are rejected); the verifier demands a
  separately trusted public key for the signer identity the record claims.
  Missing trust material, stale revocation information or an uncertain clock
  yield qualified results, never an unqualified "current".
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
import io
import json
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Protocol

from axis_sdk.connector_authoring.contracts import ContractModel, Digest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from pydantic import Field, ValidationError, model_validator

from axis_api.assurance_pack_contracts import (
    AssurancePackError,
    PackManifest,
    check_support_freshness,
    pack_readiness,
    parse_assurance_pack,
)
from axis_api.assurance_packaging import (
    MAX_ATTACHMENT_BYTES,
    MAX_MEMBERS,
    MAX_PACKAGE_BYTES,
    attachment_name,
    build_index_text,
    canonical_manifest_json,
)

ISSUANCE_FORMAT = "axis.assurance-pack.issuance"
ISSUANCE_FORMAT_MAJOR = 1
ISSUANCE_FORMAT_MINOR = 0

ALGORITHM_ED25519 = "ed25519"
SIGNING_MODE_SELF_HOSTED_ED25519 = "self_hosted_ed25519"
SUPPORTED_ALGORITHMS = (ALGORITHM_ED25519,)
#: (algorithm, custody mode) pairs issuance accepts; anything else fails closed.
SUPPORTED_SIGNING_PROFILES = frozenset({(ALGORITHM_ED25519, SIGNING_MODE_SELF_HOSTED_ED25519)})

SIGNATURE_SEMANTICS_NOTE = (
    "Signature verification proves integrity and provenance of the issued "
    "package bytes. It is not regulatory certification, not a statement "
    "about evidence freshness beyond the recorded lifecycle facts, and not "
    "a verification of self-attested claims inside the pack."
)

_MAX_REVOKE_AGE_DAYS = 7
#: Upper bound on an issuance record presented for verification.
MAX_ISSUANCE_RECORD_BYTES = 64 * 1024

_KEY_ID = r"^[a-z0-9][a-z0-9._-]{0,127}$"
_APPROVER = r"^[a-z0-9][a-z0-9._:-]{0,127}$"
_HEX_SIGNATURE = r"^[a-f0-9]{128}$"
_HEX_PUBLIC_KEY = r"^[a-f0-9]{64}$"


class AssuranceIssuanceError(ValueError):
    """Fixed issuance codes; raw validation details are never rendered."""

    NOT_ASSEMBLED = "issuance_requires_assembled_package"
    APPROVAL_MISMATCH = "approval_does_not_match_package"
    NOT_READY = "pack_not_ready"
    STALE_SUPPORT = "stale_pack_support"
    UNSUPPORTED_SIGNER = "unsupported_signing_provider"
    INVALID_INPUT = "invalid_issuance_input"

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _canonical_json(payload: dict) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _iso_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("capture_time must be an ISO 8601 timestamp") from None


class SignatureProof(ContractModel):
    """Signature over the issuance statement; never carries secret material."""

    algorithm: str = Field(min_length=1, max_length=64)
    key_id: str = Field(pattern=_KEY_ID)
    signing_mode: str = Field(min_length=1, max_length=64)
    signed_payload_sha256: Digest
    signature: str = Field(pattern=_HEX_SIGNATURE)


class PackageSigner(Protocol):
    """#477-style custody: sign one canonical payload, return one proof."""

    key_id: str
    algorithm: str
    signing_mode: str

    def sign_payload(self, payload: dict) -> SignatureProof: ...


class TrustedVerificationMaterial(ContractModel):
    """Public material from a separately trusted channel — never the package."""

    key_id: str = Field(pattern=_KEY_ID)
    algorithm: str = Field(min_length=1, max_length=64)
    signing_mode: str = Field(min_length=1, max_length=64)
    public_key: str = Field(pattern=_HEX_PUBLIC_KEY)


class Ed25519PackSigner:
    """Self-hosted Ed25519 custody: the private key never leaves this object.

    The caller's key-custody owner supplies the key object; the signer only
    exposes its public verification material. A KMS/HSM-backed signer can
    implement the same :class:`PackageSigner` protocol.
    """

    algorithm = ALGORITHM_ED25519
    signing_mode = SIGNING_MODE_SELF_HOSTED_ED25519

    def __init__(self, key_id: str, private_key: Ed25519PrivateKey) -> None:
        if not isinstance(private_key, Ed25519PrivateKey):
            raise AssuranceIssuanceError(AssuranceIssuanceError.INVALID_INPUT)
        try:
            TrustedVerificationMaterial(
                key_id=key_id,
                algorithm=self.algorithm,
                signing_mode=self.signing_mode,
                public_key="0" * 64,
            )
        except ValidationError:
            raise AssuranceIssuanceError(AssuranceIssuanceError.INVALID_INPUT) from None
        self.key_id = key_id
        self._private_key = private_key

    def __repr__(self) -> str:
        return f"Ed25519PackSigner(key_id={self.key_id!r})"

    def verification_material(self) -> TrustedVerificationMaterial:
        """The public material to distribute through a trusted channel."""

        public = self._private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        return TrustedVerificationMaterial(
            key_id=self.key_id,
            algorithm=self.algorithm,
            signing_mode=self.signing_mode,
            public_key=public.hex(),
        )

    def sign_payload(self, payload: dict) -> SignatureProof:
        encoded = _canonical_json(payload)
        return SignatureProof(
            algorithm=self.algorithm,
            key_id=self.key_id,
            signing_mode=self.signing_mode,
            signed_payload_sha256=hashlib.sha256(encoded).hexdigest(),
            signature=self._private_key.sign(encoded).hex(),
        )


class IssuanceFormatVersion(ContractModel):
    major: int = Field(ge=1, strict=True)
    minor: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def supported_version(self) -> IssuanceFormatVersion:
        if self.major != ISSUANCE_FORMAT_MAJOR or self.minor != ISSUANCE_FORMAT_MINOR:
            raise ValueError("Unsupported issuance format version")
        return self


class SigningProfile(ContractModel):
    """Which custody mode and key issued this exact record."""

    mode: str = Field(min_length=1, max_length=64)
    key_id: str = Field(pattern=_KEY_ID)
    algorithm: str = Field(min_length=1, max_length=64)


class IssuanceLifecycle(ContractModel):
    """#729 lifecycle facts as separate fields, never folded into one flag.

    ``revocation_status`` is the state at issuance; later revocation for
    future use is a verification-time observation, never a record rewrite.
    ``supersedes`` holds :func:`issuance_digest` values of prior records.
    """

    capture_time: str = Field(min_length=10, max_length=64)
    valid_through: str = Field(min_length=10, max_length=10)
    revocation_status: Literal["not_revoked"] = "not_revoked"
    supersedes: tuple[Digest, ...] = Field(default=(), max_length=16)

    @model_validator(mode="after")
    def real_dates(self) -> IssuanceLifecycle:
        _iso_datetime(self.capture_time)
        date.fromisoformat(self.valid_through)
        if len(set(self.supersedes)) != len(self.supersedes):
            raise ValueError("Supersession references must be unique")
        return self


class IssuanceStatement(ContractModel):
    """Everything the signature covers: one issued version, one digest pair.

    Binds the #883 manifest digest and the #884 package digest to the exact
    audience, release/profile, approver and signing profile.
    """

    format: Literal["axis.assurance-pack.issuance"] = ISSUANCE_FORMAT
    format_version: IssuanceFormatVersion
    pack_id: str = Field(min_length=1, max_length=128)
    audience: str = Field(min_length=1, max_length=128)
    purpose: str = Field(min_length=1, max_length=500)
    approver_ref: str = Field(pattern=_APPROVER)
    manifest_sha256: Digest = Field(repr=False)
    package_sha256: Digest = Field(repr=False)
    released_release: str = Field(min_length=1, max_length=64)
    released_profile: str = Field(min_length=1, max_length=64)
    signing_profile: SigningProfile
    lifecycle: IssuanceLifecycle


class IssuedAssurancePack(IssuanceStatement):
    """Immutable issuance record: the signed statement plus its proof.

    Records are frozen and never mutated after issuance; any change is a new
    package with a new record and, when it corrects a prior one, an explicit
    supersession reference to the prior record's :func:`issuance_digest`.
    """

    signature: SignatureProof


def unsigned_issuance_payload(statement: IssuanceStatement) -> dict:
    """The exact canonical payload the signature covers — one owner.

    Both the issuer (before signing) and the verifier (re-deriving the signed
    bytes) call this; they cannot drift apart.
    """

    data = statement.model_dump(mode="json")
    data.pop("signature", None)
    return {"issuance": data}


def issuance_digest(record: IssuedAssurancePack) -> Digest:
    """Stable identity of one issued record (used by supersession)."""

    return hashlib.sha256(_canonical_json(record.model_dump(mode="json"))).hexdigest()


class IssuanceApproval(ContractModel):
    """The caller's authorization fact for one exact issuance.

    The issuer records the approver verbatim; it never re-derives who may
    approve. ``recheck`` maps entry ids to observed support states
    (``current`` while unexpired and on the frozen release/profile) for the
    sign-time gate.
    """

    approver_ref: str = Field(pattern=_APPROVER)
    manifest_sha256: Digest
    package_sha256: Digest
    audience: str = Field(min_length=1, max_length=128)
    released_release: str = Field(min_length=1, max_length=64)
    released_profile: str = Field(min_length=1, max_length=64)
    recheck: dict[str, str] = Field(default_factory=dict, max_length=256)


class AssembledPackView(Protocol):
    """Minimal #884 shape the issuer binds to."""

    manifest: PackManifest
    package_sha256: str
    package_bytes: bytes


def issue_assurance_pack(
    *,
    assembled: AssembledPackView,
    approval: IssuanceApproval,
    signer: PackageSigner,
    capture_time: str,
    supersedes: tuple[Digest, ...] = (),
) -> IssuedAssurancePack:
    """Bind final issue approval to the exact assembled package digests.

    Raises fixed-code :class:`AssuranceIssuanceError` — the caller is left
    with no issuance record — when the assembled package is inconsistent,
    the approval does not cover this exact manifest/package digest, audience,
    release and profile, the pack fails preflight, the sign-time support
    re-check has drifted, or the signer is not an approved custody mode. The
    manifest's ``valid_through`` is copied verbatim into the lifecycle:
    expiration is an evidence fact, not an issuance decision.
    """

    manifest = getattr(assembled, "manifest", None)
    package_bytes = getattr(assembled, "package_bytes", None)
    if (
        not isinstance(manifest, PackManifest)
        or not isinstance(package_bytes, bytes)
        or hashlib.sha256(package_bytes).hexdigest() != assembled.package_sha256
    ):
        raise AssuranceIssuanceError(AssuranceIssuanceError.NOT_ASSEMBLED)

    if (
        approval.manifest_sha256 != manifest.digest()
        or approval.package_sha256 != assembled.package_sha256
        or approval.audience != manifest.context.audience
        or approval.released_release != manifest.release_snapshot.release
        or approval.released_profile != manifest.release_snapshot.profile
    ):
        raise AssuranceIssuanceError(AssuranceIssuanceError.APPROVAL_MISMATCH)

    _, ready, _ = pack_readiness(manifest)
    if not ready:
        raise AssuranceIssuanceError(AssuranceIssuanceError.NOT_READY)
    _, stale = check_support_freshness(manifest, observed=approval.recheck)
    if stale:
        raise AssuranceIssuanceError(AssuranceIssuanceError.STALE_SUPPORT)

    profile = (getattr(signer, "algorithm", None), getattr(signer, "signing_mode", None))
    if profile not in SUPPORTED_SIGNING_PROFILES:
        raise AssuranceIssuanceError(AssuranceIssuanceError.UNSUPPORTED_SIGNER)

    try:
        statement = IssuanceStatement(
            format_version=IssuanceFormatVersion(
                major=ISSUANCE_FORMAT_MAJOR, minor=ISSUANCE_FORMAT_MINOR
            ),
            pack_id=manifest.pack_id,
            audience=manifest.context.audience,
            purpose=manifest.context.purpose,
            approver_ref=approval.approver_ref,
            manifest_sha256=manifest.digest(),
            package_sha256=assembled.package_sha256,
            released_release=manifest.release_snapshot.release,
            released_profile=manifest.release_snapshot.profile,
            signing_profile=SigningProfile(
                mode=signer.signing_mode, key_id=signer.key_id, algorithm=signer.algorithm
            ),
            lifecycle=IssuanceLifecycle(
                capture_time=capture_time,
                valid_through=manifest.valid_through,
                supersedes=supersedes,
            ),
        )
    except ValidationError:
        raise AssuranceIssuanceError(AssuranceIssuanceError.INVALID_INPUT) from None

    payload = unsigned_issuance_payload(statement)
    proof = signer.sign_payload(payload)
    if (
        not isinstance(proof, SignatureProof)
        or proof.algorithm != signer.algorithm
        or proof.key_id != signer.key_id
        or proof.signing_mode != signer.signing_mode
        or proof.signed_payload_sha256 != hashlib.sha256(_canonical_json(payload)).hexdigest()
    ):
        raise AssuranceIssuanceError(AssuranceIssuanceError.UNSUPPORTED_SIGNER)
    return IssuedAssurancePack(**statement.model_dump(), signature=proof)


# --------------------------------------------------------------------------
# Offline verification
# --------------------------------------------------------------------------


class VerificationClock(ContractModel):
    """Explicit verification-time and revocation facts; absence stays visible.

    ``revocation_state`` is what the revocation information observed at
    ``revocation_observed_at`` says; without both, current non-revocation
    cannot be shown.
    """

    verification_time: str | None = Field(default=None, max_length=64)
    revocation_observed_at: str | None = Field(default=None, max_length=64)
    revocation_state: Literal["not_revoked", "revoked_for_future_use"] | None = None
    max_revocation_age_days: int = Field(default=_MAX_REVOKE_AGE_DAYS, ge=1, le=366)


@dataclass(frozen=True)
class OfflineVerificationResult:
    """Qualified result with separate integrity, freshness, revocation fields.

    ``qualified_result`` is the strongest claim the inputs support:
    ``verified_current`` only when the signature verified under separately
    trusted material, every digest matched, the evidence is within its
    ``valid_through`` on a certain clock, and revocation information is
    current and says not revoked. Anything less is qualified or failed.
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

        return SIGNATURE_SEMANTICS_NOTE


def _expected_members(manifest: PackManifest) -> list[str]:
    names = ["manifest.json", "index.md"]
    names.extend(
        attachment_name(entry.entry_id)
        for entry in manifest.entries
        if entry.mode == "included_artifact"
    )
    return names


def _read_members(package_bytes: bytes) -> dict[str, bytes] | str:
    """Bounded read of a stored (uncompressed) package; returns a reason on failure."""

    try:
        with zipfile.ZipFile(io.BytesIO(package_bytes)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_MEMBERS:
                return "package exceeds the member bound"
            members: dict[str, bytes] = {}
            for info in infos:
                if info.filename in members:
                    return f"duplicated package member: {info.filename}"
                if info.compress_type != zipfile.ZIP_STORED:
                    return "package members must be stored uncompressed"
                if info.file_size > MAX_ATTACHMENT_BYTES:
                    return "package member exceeds the size bound"
                members[info.filename] = archive.read(info)
            return members
    except (zipfile.BadZipFile, zipfile.LargeZipFile, ValueError, OSError):
        return "package is not a readable archive"


def verify_assurance_pack_offline(
    *,
    issuance_json: bytes,
    package_bytes: bytes,
    trust_material: TrustedVerificationMaterial | None,
    clock: VerificationClock | None,
) -> OfflineVerificationResult:
    """Bounded offline verification of one issued package.

    No network, no database, no process-global trust: every input arrives as
    an argument. The manifest and attachments are read from the package under
    test (bounded member count and sizes); trust material must come through a
    separately trusted channel. Stale revocation data or an uncertain clock
    can only qualify the result, never upgrade it.
    """

    if len(issuance_json) > MAX_ISSUANCE_RECORD_BYTES or len(package_bytes) > MAX_PACKAGE_BYTES:
        return _failed("input exceeds the verification bounds")
    try:
        record = IssuedAssurancePack.model_validate_json(issuance_json)
    except ValidationError:
        return _failed("issuance record is not a valid #885 payload")

    # Structural integrity first: issued digests over the presented bytes.
    if record.package_sha256 != hashlib.sha256(package_bytes).hexdigest():
        return _failed("package digest does not match the issued record", package="failed")
    members = _read_members(package_bytes)
    if isinstance(members, str):
        return _failed(members, package="failed")
    manifest_bytes = members.get("manifest.json")
    if manifest_bytes is None:
        return _failed("required package member missing: manifest.json", package="failed")
    try:
        manifest = parse_assurance_pack(json.loads(manifest_bytes))
    except (AssurancePackError, ValueError):
        return _failed("packaged manifest is not a valid #883 manifest", package="failed")
    if canonical_manifest_json(manifest) != manifest_bytes:
        return _failed("packaged manifest is not canonical", package="failed")
    if record.manifest_sha256 != manifest.digest():
        return _failed("manifest digest does not match the issued record", package="failed")
    if (
        record.pack_id != manifest.pack_id
        or record.audience != manifest.context.audience
        or record.purpose != manifest.context.purpose
        or record.released_release != manifest.release_snapshot.release
        or record.released_profile != manifest.release_snapshot.profile
        or record.lifecycle.valid_through != manifest.valid_through
    ):
        return _failed("issued record does not describe the packaged manifest", package="failed")

    expected = _expected_members(manifest)
    for name in expected:
        if name not in members:
            return _failed(f"required package member missing: {name}", package="failed")
    if list(members) != expected:
        return _failed("package members differ from the manifest", package="failed")
    if members["index.md"] != build_index_text(manifest).encode("utf-8"):
        return _failed("package index does not match the manifest", package="failed")
    for entry in manifest.entries:
        if entry.mode != "included_artifact":
            continue
        content = members[attachment_name(entry.entry_id)]
        if hashlib.sha256(content).hexdigest() != entry.artifact_digest:
            return _failed(f"attachment digest mismatch for {entry.entry_id}", package="failed")

    notes = [SIGNATURE_SEMANTICS_NOTE]
    freshness = _freshness(record, clock)
    revocation = _revocation(clock)
    clock_status = _clock_status(clock)

    if trust_material is None:
        return OfflineVerificationResult(
            qualified_result="untrusted_input",
            signature_integrity="unverifiable",
            package_integrity="consistent_unauthenticated",
            evidence_freshness=freshness,
            revocation_status=revocation,
            clock_status=clock_status,
            notes=(
                *notes,
                "No separately trusted verification material was supplied; "
                "an embedded key cannot authenticate its own package.",
            ),
        )

    # Allowlist before any signature math; the record's claim is not
    # self-certifying, and the proof must agree with the signed profile.
    profile = record.signing_profile
    if (
        profile.algorithm not in SUPPORTED_ALGORITHMS
        or (profile.algorithm, profile.mode) not in SUPPORTED_SIGNING_PROFILES
        or record.signature.algorithm != profile.algorithm
        or record.signature.key_id != profile.key_id
        or record.signature.signing_mode != profile.mode
    ):
        return _failed("unsupported signature algorithm", package="verified", signature="failed")
    if (
        trust_material.key_id != profile.key_id
        or trust_material.algorithm != profile.algorithm
        or trust_material.signing_mode != profile.mode
    ):
        return _failed(
            "trusted material does not match the issued signer identity",
            package="verified",
            signature="failed",
        )

    encoded = _canonical_json(unsigned_issuance_payload(record))
    try:
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(trust_material.public_key))
        public_key.verify(bytes.fromhex(record.signature.signature), encoded)
    except (InvalidSignature, ValueError):
        return _failed(
            "signature does not verify over the issuance payload",
            package="verified",
            signature="failed",
        )
    if record.signature.signed_payload_sha256 != hashlib.sha256(encoded).hexdigest():
        return _failed(
            "signed payload digest does not match the issuance payload",
            package="verified",
            signature="failed",
        )

    notes.append("Signature verified with separately trusted verification material.")
    return OfflineVerificationResult(
        qualified_result=_qualified(freshness, revocation, clock_status),
        signature_integrity="verified",
        package_integrity="verified",
        evidence_freshness=freshness,
        revocation_status=revocation,
        clock_status=clock_status,
        notes=tuple(notes),
    )


def _failed(
    reason: str,
    *,
    package: str = "not_checked",
    signature: str = "not_checked",
) -> OfflineVerificationResult:
    return OfflineVerificationResult(
        qualified_result="failed",
        signature_integrity=signature,
        package_integrity=package,
        evidence_freshness="not_checked",
        revocation_status="not_checked",
        clock_status="not_checked",
        notes=(f"Verification failed: {reason}.",),
    )


def _verification_date(clock: VerificationClock | None) -> date | None:
    if clock is None or clock.verification_time is None:
        return None
    return _date_of(clock.verification_time)


def _freshness(record: IssuedAssurancePack, clock: VerificationClock | None) -> str:
    now = _verification_date(clock)
    if now is None:
        return f"valid_through:{record.lifecycle.valid_through}"
    return "current" if now <= date.fromisoformat(record.lifecycle.valid_through) else "expired"


def _revocation(clock: VerificationClock | None) -> str:
    if clock is None or clock.revocation_observed_at is None or clock.revocation_state is None:
        return "no_current_revocation_information"
    observed = _date_of(clock.revocation_observed_at)
    if observed is None:
        return "unparseable_revocation_observation"
    if clock.revocation_state == "revoked_for_future_use":
        return "revoked_for_future_use"
    now = _verification_date(clock)
    if now is not None:
        if observed > now:
            return "revocation_observation_after_verification_time"
        if (now - observed).days > clock.max_revocation_age_days:
            return "stale_revocation_information"
    return f"observed_at:{clock.revocation_observed_at}"


def _clock_status(clock: VerificationClock | None) -> str:
    return "certain" if _verification_date(clock) is not None else "uncertain"


def _qualified(freshness: str, revocation: str, clock_status: str) -> str:
    if freshness != "current" or clock_status != "certain":
        return "verified_but_qualified"
    if not revocation.startswith("observed_at:"):
        return "verified_but_qualified"
    return "verified_current"


def _date_of(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None
