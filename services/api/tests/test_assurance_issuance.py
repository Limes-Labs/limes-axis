"""Contract tests for the #885 issuance and offline verification layer."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile

import pytest

from axis_api.assurance_issuance import (
    ALGORITHM_HMAC_SHA256,
    AssuranceIssuanceError,
    IssuanceApproval,
    SelfHostedHmacPackSigner,
    SigningProfile,
    TrustedVerificationMaterial,
    VerificationClock,
    issue_assurance_pack,
    verify_assurance_pack_offline,
)
from axis_api.assurance_pack_contracts import (
    AnswerSelection,
    ManifestVersion,
    PackContext,
    PackManifest,
    ReleaseSnapshot,
)
from axis_api.assurance_packaging import build_assurance_pack

ATTACHMENT = b"pentest-report-2026q3\n"
CORRECTED_ATTACHMENT = b"pentest-report-2026q3-corrected\n"
CUSTODY_SECRET = "custody-secret-2026h2"


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _manifest(attachment: bytes = ATTACHMENT) -> PackManifest:
    return PackManifest(
        schema_version=ManifestVersion(major=1, minor=0),
        pack_id="pack-enterprise-q3",
        title="Enterprise Q3 pack",
        context=PackContext(
            engagement_ref="eng.acme.2026",
            audience="enterprise",
            purpose="Evidence pack for enterprise review",
        ),
        release_snapshot=ReleaseSnapshot(
            release="1.4.0",
            profile="standard",
            posture_observation_ref="obs.posture.2026q3",
            posture_revision="7",
            posture_digest=_digest(b"posture"),
        ),
        entries=(
            AnswerSelection(
                entry_id="soc2",
                question_ref="q.soc2.status",
                answer_revision="12",
                answer_digest=_digest(b"answer-12"),
                support="current",
                mode="reference_only",
                as_of="2026-09-01",
            ),
            AnswerSelection(
                entry_id="pentest",
                question_ref="q.pentest.report",
                answer_revision="3",
                answer_digest=_digest(b"answer-3"),
                support="current",
                mode="included_artifact",
                artifact_digest=_digest(attachment),
                as_of="2026-09-01",
            ),
        ),
        valid_through="2027-09-01",
    )


class _Artifacts:
    def __init__(self, content: bytes) -> None:
        self._content = content

    def resolve(self, entry, manifest) -> bytes:  # noqa: ANN001
        return self._content


class _Scanner:
    def scan(self, content: bytes, fmt: str) -> bool:
        return b"sk-live-" not in content


class _MemberArtifacts:
    """Serves attachment bytes extracted from the package under test."""

    def __init__(self, archive: zipfile.ZipFile) -> None:
        self._names = {name: archive.read(name) for name in archive.namelist()}

    def resolve(self, entry_id: str) -> bytes:
        return self._names[f"attachments/{entry_id}.bin"]


class _RsaSigner:
    """A signer with a custody mode this issuance layer does not approve."""

    key_id = "kms-rsa-1"
    algorithm = "rsa-sha256"

    def sign_payload(self, payload: dict) -> dict:  # pragma: no cover
        raise AssertionError("unsupported signer must never be invoked")


def _assemble(manifest: PackManifest, attachment: bytes):
    return build_assurance_pack(manifest, _Artifacts(attachment), _Scanner())


def _approval(manifest: PackManifest) -> IssuanceApproval:
    return IssuanceApproval(
        approver_ref="approver.dana",
        manifest_sha256=manifest.digest(),
        audience=manifest.context.audience,
        released_release=manifest.release_snapshot.release,
        released_profile=manifest.release_snapshot.profile,
        recheck={"soc2": "current", "pentest": "current"},
    )


def _issue(manifest: PackManifest, attachment: bytes = ATTACHMENT, **kwargs):
    pack = _assemble(manifest, attachment)
    signer = SelfHostedHmacPackSigner(
        key_id="issuance-key-2026h2", secret_key=CUSTODY_SECRET
    )
    record = issue_assurance_pack(
        pack_id=manifest.pack_id,
        purpose="Q3 enterprise evidence",
        assembled=pack,
        approval=kwargs.pop("approval", _approval(manifest)),
        signer=kwargs.pop("signer", signer),
        capture_time="2026-09-18T10:00:00Z",
        **kwargs,
    )
    return pack, record


def _extracted(pack) -> tuple[PackManifest, _MemberArtifacts]:
    archive = zipfile.ZipFile(io.BytesIO(pack.package_bytes))
    manifest = PackManifest.model_validate_json(archive.read("manifest.json"))
    return manifest, _MemberArtifacts(archive)


_TRUST = TrustedVerificationMaterial(
    key_id="issuance-key-2026h2",
    algorithm=ALGORITHM_HMAC_SHA256,
    signing_mode="self_hosted_hmac",
    secret_key=CUSTODY_SECRET,
)

_CURRENT_CLOCK = VerificationClock(
    verification_time="2026-09-18", revocation_observed_at="2026-09-15"
)


def _verify(pack, record, manifest, members, *, trust=_TRUST, clock=_CURRENT_CLOCK,
            package_bytes=None, issuance_json=None):
    return verify_assurance_pack_offline(
        issuance_json=issuance_json or record.model_dump_json().encode("utf-8"),
        package_bytes=package_bytes or pack.package_bytes,
        manifest=manifest,
        artifacts=members,
        trust_material=trust,
        clock=clock,
    )


# AC1: a synthetic issued package verifies in an isolated environment with
# trusted material and no network access — every input is a local argument.
def test_issued_package_verifies_offline_with_trusted_material():
    manifest = _manifest()
    pack, record = _issue(manifest)
    extracted, members = _extracted(pack)
    result = _verify(pack, record, extracted, members)
    assert result.qualified_result == "verified_current"
    assert result.signature_integrity == "verified"
    assert result.package_integrity == "verified"
    assert result.evidence_freshness == "current"
    assert result.clock_status == "certain"
    assert result.revocation_status == "observed_at:2026-09-15"


# AC2: a modified attachment fails verification (rebuild the ZIP with a
# genuinely different attachment member; DEFLATE hides plaintext edits).
def test_modified_attachment_fails_verification():
    manifest = _manifest()
    pack, record = _issue(manifest)
    extracted, members = _extracted(pack)
    buffer = io.BytesIO()
    with (
        zipfile.ZipFile(buffer, "w") as target,
        zipfile.ZipFile(io.BytesIO(pack.package_bytes)) as source,
    ):
        for name in source.namelist():
            content = source.read(name)
            if name == "attachments/pentest.bin":
                content = b"tampered-report-body\n"
            target.writestr(name, content)
    tampered = buffer.getvalue()
    result = _verify(pack, record, extracted, members, package_bytes=tampered)
    assert result.qualified_result == "failed"
    assert result.package_integrity == "failed"


# AC2: a modified manifest (or issuance) cannot pass the digest binding.
def test_modified_manifest_fails_verification():
    manifest = _manifest()
    pack, record = _issue(manifest)
    extracted, members = _extracted(pack)
    forged = extracted.model_copy(update={"title": "Rewritten title"})
    result = _verify(pack, record, forged, members)
    assert result.qualified_result == "failed"


# AC2: trust material for a different signer identity fails verification.
def test_wrong_signer_fails_verification():
    manifest = _manifest()
    pack, record = _issue(manifest)
    extracted, members = _extracted(pack)
    result = _verify(
        pack,
        record,
        extracted,
        members,
        trust=TrustedVerificationMaterial(
            key_id="other-key",
            algorithm=ALGORITHM_HMAC_SHA256,
            signing_mode="self_hosted_hmac",
            secret_key=CUSTODY_SECRET,
        ),
    )
    assert result.qualified_result == "failed"
    assert result.package_integrity == "verified"


# AC2: an unsupported algorithm fails closed before any signature math.
def test_unsupported_algorithm_fails_verification():
    manifest = _manifest()
    pack, record = _issue(manifest)
    extracted, members = _extracted(pack)
    rewritten = record.model_copy(
        update={
            "signing_profile": SigningProfile(
                mode="kms_rsa", key_id="kms-rsa-1", algorithm="rsa-sha256"
            )
        }
    )
    result = _verify(pack, rewritten, extracted, members)
    assert result.qualified_result == "failed"


# AC2: a required attachment member missing from the package fails. The
# record's package digest is re-bound to the stripped archive so the check
# reaches the membership gate instead of failing earlier on the digest.
def test_missing_required_attachment_member_fails():
    manifest = _manifest()
    pack, record = _issue(manifest)
    extracted, members = _extracted(pack)
    buffer = io.BytesIO()
    with (
        zipfile.ZipFile(buffer, "w") as archive,
        zipfile.ZipFile(io.BytesIO(pack.package_bytes)) as source,
    ):
        for name in ("manifest.json", "index.md"):
            archive.writestr(name, source.read(name))
    stripped = buffer.getvalue()
    rebound = record.model_copy(
        update={"package_sha256": hashlib.sha256(stripped).hexdigest()}
    )
    result = _verify(pack, rebound, extracted, members, package_bytes=stripped)
    assert result.qualified_result == "failed"
    assert result.package_integrity == "failed"
    assert "required package member missing" in result.notes[-1]


# AC2: a tampered issuance record fails.
def test_tampered_issuance_record_fails():
    manifest = _manifest()
    pack, record = _issue(manifest)
    extracted, members = _extracted(pack)
    payload = json.loads(record.model_dump_json())
    payload["pack_id"] = "pack-enterprise-q4"
    result = _verify(
        pack, record, extracted, members,
        issuance_json=json.dumps(payload).encode("utf-8"),
    )
    assert result.qualified_result == "failed"


# AC5: a forged embedded trust anchor cannot authenticate its own package.
def test_forged_embedded_anchor_cannot_authenticate():
    manifest = _manifest()
    pack, record = _issue(manifest)
    extracted, members = _extracted(pack)
    attacker_trust = TrustedVerificationMaterial(
        key_id="issuance-key-2026h2",
        algorithm=ALGORITHM_HMAC_SHA256,
        signing_mode="self_hosted_hmac",
        secret_key="attacker-secret",
    )
    result = _verify(pack, record, extracted, members, trust=attacker_trust)
    assert result.qualified_result == "failed"
    assert result.signature_integrity == "failed"


# AC5: without separately trusted material the result is never verified.
def test_missing_trust_material_is_untrusted_not_verified():
    manifest = _manifest()
    pack, record = _issue(manifest)
    extracted, members = _extracted(pack)
    result = _verify(pack, record, extracted, members, trust=None)
    assert result.qualified_result == "untrusted_input"
    assert result.signature_integrity == "unverifiable"
    assert result.package_integrity == "verified"
    assert "embedded key cannot authenticate" in result.notes[-1]


# AC5: stale revocation information cannot yield an unqualified result.
def test_stale_revocation_information_quals_not_current():
    manifest = _manifest()
    pack, record = _issue(manifest)
    extracted, members = _extracted(pack)
    stale_clock = VerificationClock(
        verification_time="2026-09-18",
        revocation_observed_at="2026-06-01",
    )
    result = _verify(pack, record, extracted, members, clock=stale_clock)
    assert result.qualified_result == "verified_but_qualified"
    assert result.revocation_status == "stale_revocation_information"


# AC5: no revocation information or an uncertain clock stays qualified.
def test_uncertain_clock_and_missing_revocation_stay_qualified():
    manifest = _manifest()
    pack, record = _issue(manifest)
    extracted, members = _extracted(pack)
    no_clock = _verify(pack, record, extracted, members, clock=None)
    assert no_clock.qualified_result == "verified_but_qualified"
    assert no_clock.clock_status == "uncertain"
    assert no_clock.revocation_status == "no_current_revocation_information"
    time_only = _verify(
        pack, record, extracted, members,
        clock=VerificationClock(verification_time="2026-09-18"),
    )
    assert time_only.qualified_result == "verified_but_qualified"


# AC3: evidence expiring after issuance blocks current reuse while the exact
# historical package keeps its valid historical signature result.
def test_expiry_blocks_current_reuse_but_preserves_history():
    manifest = _manifest()
    pack, record = _issue(manifest)
    extracted, members = _extracted(pack)
    issuance_bytes = record.model_dump_json().encode("utf-8")

    before = _verify(pack, record, extracted, members,
                     clock=VerificationClock(
                         verification_time="2027-08-31",
                         revocation_observed_at="2027-08-28",
                     ))
    after = _verify(pack, record, extracted, members,
                    clock=VerificationClock(
                        verification_time="2027-09-02",
                        revocation_observed_at="2027-08-28",
                    ))
    again = _verify(pack, record, extracted, members,
                    clock=VerificationClock(
                        verification_time="2027-08-31",
                        revocation_observed_at="2027-08-28",
                    ))
    assert before.qualified_result == "verified_current"
    assert after.qualified_result == "verified_but_qualified"
    assert after.evidence_freshness == "expired"
    assert after.signature_integrity == "verified"
    assert record.model_dump_json().encode("utf-8") == issuance_bytes
    assert again.qualified_result == "verified_current"


# AC4: a corrected answer creates an explicitly superseding issue while the
# previous issue stays independently verifiable.
def test_superseding_issue_keeps_previous_verifiable():
    original_manifest = _manifest()
    original_pack, original_record = _issue(original_manifest)
    original_extracted, original_members = _extracted(original_pack)

    corrected_manifest = _manifest(CORRECTED_ATTACHMENT)
    corrected_pack, corrected_record = _issue(
        corrected_manifest,
        CORRECTED_ATTACHMENT,
        supersedes=(original_record.pack_id,),
    )
    corrected_extracted, corrected_members = _extracted(corrected_pack)

    assert corrected_record.manifest_sha256 != original_record.manifest_sha256
    assert corrected_record.package_sha256 != original_record.package_sha256
    assert corrected_record.lifecycle.supersession == (original_record.pack_id,)
    assert original_record.lifecycle.supersession == ()

    original_result = _verify(
        original_pack, original_record, original_extracted, original_members
    )
    corrected_result = _verify(
        corrected_pack, corrected_record, corrected_extracted, corrected_members
    )
    assert original_result.qualified_result == "verified_current"
    assert corrected_result.qualified_result == "verified_current"


# AC3/AC4: lifecycle facts are recorded as separate explicit fields.
def test_lifecycle_fields_are_separate_and_explicit():
    _, record = _issue(_manifest())
    assert record.lifecycle.capture_time == "2026-09-18T10:00:00Z"
    assert record.lifecycle.valid_through == "2027-09-01"
    assert record.lifecycle.revocation_status == "not_revoked"
    assert record.lifecycle.supersession == ()


# Issuance gate: an approval not covering this exact package is refused.
def test_issuance_rejects_approval_not_covering_package():
    manifest = _manifest()
    pack = _assemble(manifest, ATTACHMENT)
    signer = SelfHostedHmacPackSigner(
        key_id="issuance-key-2026h2", secret_key=CUSTODY_SECRET
    )
    with pytest.raises(AssuranceIssuanceError) as excinfo:
        issue_assurance_pack(
            pack_id=manifest.pack_id,
            purpose="Q3 enterprise evidence",
            assembled=pack,
            approval=IssuanceApproval(
                approver_ref="approver.dana",
                manifest_sha256=_digest(b"other-manifest"),
                audience=manifest.context.audience,
                released_release=manifest.release_snapshot.release,
                released_profile=manifest.release_snapshot.profile,
                recheck={"soc2": "current", "pentest": "current"},
            ),
            signer=signer,
            capture_time="2026-09-18T10:00:00Z",
        )
    assert excinfo.value.code == AssuranceIssuanceError.APPROVAL_MISMATCH


# Issuance gate: support drift between approval and signing time is refused.
def test_issuance_rejects_stale_support_at_sign_time():
    manifest = _manifest()
    pack = _assemble(manifest, ATTACHMENT)
    signer = SelfHostedHmacPackSigner(
        key_id="issuance-key-2026h2", secret_key=CUSTODY_SECRET
    )
    approval = _approval(manifest).model_copy(
        update={"recheck": {"soc2": "superseded_answer", "pentest": "current"}}
    )
    with pytest.raises(AssuranceIssuanceError) as excinfo:
        issue_assurance_pack(
            pack_id=manifest.pack_id,
            purpose="Q3 enterprise evidence",
            assembled=pack,
            approval=approval,
            signer=signer,
            capture_time="2026-09-18T10:00:00Z",
        )
    assert excinfo.value.code == AssuranceIssuanceError.STALE_SUPPORT


# Issuance gate: an unapproved custody mode fails closed.
def test_issuance_rejects_unsupported_signer():
    manifest = _manifest()
    pack = _assemble(manifest, ATTACHMENT)
    with pytest.raises(AssuranceIssuanceError) as excinfo:
        issue_assurance_pack(
            pack_id=manifest.pack_id,
            purpose="Q3 enterprise evidence",
            assembled=pack,
            approval=_approval(manifest),
            signer=_RsaSigner(),
            capture_time="2026-09-18T10:00:00Z",
        )
    assert excinfo.value.code == AssuranceIssuanceError.UNSUPPORTED_SIGNER


# Security: no custody secret in the record, the package or the signature.
def test_issuance_never_carries_secret_material():
    manifest = _manifest()
    pack, record = _issue(manifest)
    record_json = record.model_dump_json()
    assert CUSTODY_SECRET not in record_json
    assert CUSTODY_SECRET.encode("utf-8") not in pack.package_bytes
    assert record.signature.algorithm == ALGORITHM_HMAC_SHA256
    assert record.signing_profile.mode == "self_hosted_hmac"


# AC6: the wording bounds what a signature proves, everywhere it is shown.
def test_signature_wording_is_bounded():
    manifest = _manifest()
    pack, record = _issue(manifest)
    extracted, members = _extracted(pack)
    note = _verify(pack, record, extracted, members).signature_semantics_note()
    assert "integrity" in note
    assert "provenance" in note
    assert "not regulatory certification" in note
    assert "self-attested claims" in note
