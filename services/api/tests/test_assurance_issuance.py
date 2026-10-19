"""Contract tests for the #885 issuance and offline verification layer."""

from __future__ import annotations

import hashlib
import io
import json
import socket
import zipfile

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)
from pydantic import ValidationError

from axis_api.assurance_issuance import (
    ALGORITHM_ED25519,
    SIGNATURE_SEMANTICS_NOTE,
    SIGNING_MODE_SELF_HOSTED_ED25519,
    AssuranceIssuanceError,
    Ed25519PackSigner,
    IssuanceApproval,
    IssuedAssurancePack,
    SignatureProof,
    TrustedVerificationMaterial,
    VerificationClock,
    issuance_digest,
    issue_assurance_pack,
    unsigned_issuance_payload,
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
_ISSUER_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
_ATTACKER_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))
_SIGNER = Ed25519PackSigner("issuance-key-2026h2", _ISSUER_KEY)
_TRUST = _SIGNER.verification_material()

_CURRENT_CLOCK = VerificationClock(
    verification_time="2026-09-18",
    revocation_observed_at="2026-09-15",
    revocation_state="not_revoked",
)


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
        issued_on="2026-09-15",
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


class _RsaSigner:
    """A signer with a custody mode this issuance layer does not approve."""

    key_id = "kms-rsa-1"
    algorithm = "rsa-sha256"
    signing_mode = "kms_rsa"

    def sign_payload(self, payload: dict) -> SignatureProof:  # pragma: no cover
        raise AssertionError("unsupported signer must never be invoked")


def _assemble(manifest: PackManifest, attachment: bytes):
    return build_assurance_pack(manifest, _Artifacts(attachment), _Scanner())


def _approval(manifest: PackManifest, pack) -> IssuanceApproval:  # noqa: ANN001
    return IssuanceApproval(
        approver_ref="approver.dana",
        manifest_sha256=manifest.digest(),
        package_sha256=pack.package_sha256,
        audience=manifest.context.audience,
        released_release=manifest.release_snapshot.release,
        released_profile=manifest.release_snapshot.profile,
        recheck={"soc2": "current", "pentest": "current"},
    )


def _issue(manifest: PackManifest, attachment: bytes = ATTACHMENT, **kwargs):
    pack = _assemble(manifest, attachment)
    record = issue_assurance_pack(
        assembled=pack,
        approval=kwargs.pop("approval", _approval(manifest, pack)),
        signer=kwargs.pop("signer", _SIGNER),
        capture_time="2026-09-18T10:00:00+00:00",
        **kwargs,
    )
    return pack, record


def _verify(pack, record, *, trust=_TRUST, clock=_CURRENT_CLOCK,  # noqa: ANN001
            package_bytes=None, issuance_json=None):
    return verify_assurance_pack_offline(
        issuance_json=issuance_json or record.model_dump_json().encode("utf-8"),
        package_bytes=package_bytes or pack.package_bytes,
        trust_material=trust,
        clock=clock,
    )


def _rewrite(package_bytes: bytes, replace: dict[str, bytes | None]) -> bytes:
    buffer = io.BytesIO()
    with (
        zipfile.ZipFile(buffer, "w") as target,
        zipfile.ZipFile(io.BytesIO(package_bytes)) as source,
    ):
        for info in source.infolist():
            content = replace.get(info.filename, source.read(info))
            if content is not None:
                target.writestr(info, content)
    return buffer.getvalue()


def _resign(record: IssuedAssurancePack, key: Ed25519PrivateKey, **updates) -> bytes:
    """Recompute a record with updates and sign it with ``key``."""

    data = record.model_dump(mode="json")
    data.update(updates)
    statement = IssuedAssurancePack.model_validate(data)
    signer = Ed25519PackSigner(statement.signing_profile.key_id, key)
    proof = signer.sign_payload(unsigned_issuance_payload(statement))
    data["signature"] = proof.model_dump(mode="json")
    return json.dumps(data).encode("utf-8")


# AC1: a synthetic issued package verifies in an isolated environment with
# trusted public material and no network access.
def test_issued_package_verifies_offline_with_trusted_material(monkeypatch):
    manifest = _manifest()
    pack, record = _issue(manifest)

    def _no_network(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("offline verification must not open sockets")

    monkeypatch.setattr(socket, "socket", _no_network)
    monkeypatch.setattr(socket, "create_connection", _no_network)
    result = _verify(pack, record)
    assert result.qualified_result == "verified_current"
    assert result.signature_integrity == "verified"
    assert result.package_integrity == "verified"
    assert result.evidence_freshness == "current"
    assert result.clock_status == "certain"
    assert result.revocation_status == "observed_at:2026-09-15"


def test_issuance_is_deterministic_and_binds_the_approval():
    manifest = _manifest()
    pack, first = _issue(manifest)
    _, second = _issue(manifest)
    assert first == second
    assert first.approver_ref == "approver.dana"
    assert first.pack_id == manifest.pack_id
    assert first.package_sha256 == pack.package_sha256
    assert first.manifest_sha256 == manifest.digest()
    with pytest.raises(ValidationError):
        first.pack_id = "other"  # frozen record


# AC2: a modified attachment fails verification, even when the record's
# package digest is recomputed for the tampered archive.
def test_modified_attachment_fails_verification():
    pack, record = _issue(_manifest())
    tampered = _rewrite(pack.package_bytes, {"attachments/pentest.bin": b"tampered-report\n"})
    assert _verify(pack, record, package_bytes=tampered).package_integrity == "failed"

    rebound = record.model_copy(update={"package_sha256": _digest(tampered)})
    result = _verify(pack, rebound, package_bytes=tampered)
    assert result.qualified_result == "failed"
    assert result.package_integrity == "failed"
    assert "attachment digest mismatch" in result.notes[-1]


# AC2: a modified manifest cannot pass the digest binding.
def test_modified_manifest_fails_verification():
    manifest = _manifest()
    pack, record = _issue(manifest)
    forged = manifest.model_copy(update={"title": "Rewritten title"})
    tampered = _rewrite(
        pack.package_bytes,
        {"manifest.json": json.dumps(forged.model_dump(mode="json"), sort_keys=True,
                                     separators=(",", ":")).encode()},
    )
    rebound = record.model_copy(update={"package_sha256": _digest(tampered)})
    result = _verify(pack, rebound, package_bytes=tampered)
    assert result.qualified_result == "failed"
    assert result.package_integrity == "failed"


def test_modified_index_and_extra_member_fail_verification():
    pack, record = _issue(_manifest())
    for replace in ({"index.md": b"# Fully certified pack\n"},):
        tampered = _rewrite(pack.package_bytes, replace)
        rebound = record.model_copy(update={"package_sha256": _digest(tampered)})
        assert _verify(pack, rebound, package_bytes=tampered).qualified_result == "failed"
    buffer = io.BytesIO(pack.package_bytes)
    with zipfile.ZipFile(buffer, "a") as archive:
        archive.writestr("attachments/extra.bin", b"smuggled")
    extra = buffer.getvalue()
    rebound = record.model_copy(update={"package_sha256": _digest(extra)})
    result = _verify(pack, rebound, package_bytes=extra)
    assert result.qualified_result == "failed"
    assert "members differ" in result.notes[-1]


# AC2: trust material for a different signer identity or key fails.
def test_wrong_signer_fails_verification():
    pack, record = _issue(_manifest())
    other_id = _TRUST.model_copy(update={"key_id": "other-key"})
    result = _verify(pack, record, trust=other_id)
    assert result.qualified_result == "failed"
    assert result.package_integrity == "verified"

    other_key = Ed25519PackSigner("issuance-key-2026h2", _ATTACKER_KEY).verification_material()
    result = _verify(pack, record, trust=other_key)
    assert result.qualified_result == "failed"
    assert result.signature_integrity == "failed"


# AC2: an unsupported algorithm fails closed before any signature math.
def test_unsupported_algorithm_fails_verification():
    pack, record = _issue(_manifest())
    payload = json.loads(record.model_dump_json())
    payload["signing_profile"]["algorithm"] = "hmac-sha256"
    payload["signature"]["algorithm"] = "hmac-sha256"
    result = _verify(pack, record, issuance_json=json.dumps(payload).encode())
    assert result.qualified_result == "failed"
    assert "unsupported signature algorithm" in result.notes[-1]


# AC2: a required attachment member missing from the package fails.
def test_missing_required_attachment_member_fails():
    pack, record = _issue(_manifest())
    stripped = _rewrite(pack.package_bytes, {"attachments/pentest.bin": None})
    rebound = record.model_copy(update={"package_sha256": _digest(stripped)})
    result = _verify(pack, rebound, package_bytes=stripped)
    assert result.qualified_result == "failed"
    assert result.package_integrity == "failed"
    assert "required package member missing" in result.notes[-1]


# AC2: a tampered issuance record fails.
def test_tampered_issuance_record_fails():
    pack, record = _issue(_manifest())
    payload = json.loads(record.model_dump_json())
    payload["approver_ref"] = "approver.mallory"
    result = _verify(pack, record, issuance_json=json.dumps(payload).encode("utf-8"))
    assert result.qualified_result == "failed"
    assert result.signature_integrity == "failed"


def test_malformed_and_oversized_inputs_fail_closed():
    pack, record = _issue(_manifest())
    assert _verify(pack, record, issuance_json=b"{").qualified_result == "failed"
    not_zip = b"not a zip archive"
    rebound = record.model_copy(update={"package_sha256": _digest(not_zip)})
    result = _verify(pack, rebound, package_bytes=not_zip)
    assert result.qualified_result == "failed"
    assert "not a readable archive" in result.notes[-1]
    huge = b"\0" * (16 * 1024 * 1024 + 1)
    assert _verify(pack, record, package_bytes=huge).qualified_result == "failed"


# AC5: a forged embedded trust anchor cannot authenticate its own package.
def test_forged_embedded_anchor_cannot_authenticate():
    pack, record = _issue(_manifest())
    # A record cannot carry a trust anchor at all ...
    payload = json.loads(record.model_dump_json())
    payload["trust_anchor"] = _ATTACKER_KEY.public_key().public_bytes_raw().hex()
    assert _verify(
        pack, record, issuance_json=json.dumps(payload).encode()
    ).qualified_result == "failed"
    # ... and a record re-signed by an attacker under the issuer's key id
    # fails against the separately trusted public key.
    forged = _resign(record, _ATTACKER_KEY, approver_ref="approver.mallory")
    result = _verify(pack, record, issuance_json=forged)
    assert result.qualified_result == "failed"
    assert result.signature_integrity == "failed"


# AC5: without separately trusted material the result is never verified.
def test_missing_trust_material_is_untrusted_not_verified():
    pack, record = _issue(_manifest())
    result = _verify(pack, record, trust=None)
    assert result.qualified_result == "untrusted_input"
    assert result.signature_integrity == "unverifiable"
    assert result.package_integrity == "consistent_unauthenticated"
    assert "embedded key cannot authenticate" in result.notes[-1]


# AC5: stale revocation information cannot yield an unqualified result.
def test_stale_revocation_information_qualifies_not_current():
    pack, record = _issue(_manifest())
    stale_clock = _CURRENT_CLOCK.model_copy(update={"revocation_observed_at": "2026-06-01"})
    result = _verify(pack, record, clock=stale_clock)
    assert result.qualified_result == "verified_but_qualified"
    assert result.revocation_status == "stale_revocation_information"


def test_observed_revocation_blocks_current_reuse():
    pack, record = _issue(_manifest())
    revoked = _CURRENT_CLOCK.model_copy(update={"revocation_state": "revoked_for_future_use"})
    result = _verify(pack, record, clock=revoked)
    assert result.qualified_result == "verified_but_qualified"
    assert result.revocation_status == "revoked_for_future_use"
    assert result.signature_integrity == "verified"


# AC5: no revocation information or an uncertain clock stays qualified.
def test_uncertain_clock_and_missing_revocation_stay_qualified():
    pack, record = _issue(_manifest())
    no_clock = _verify(pack, record, clock=None)
    assert no_clock.qualified_result == "verified_but_qualified"
    assert no_clock.clock_status == "uncertain"
    assert no_clock.revocation_status == "no_current_revocation_information"
    time_only = _verify(pack, record, clock=VerificationClock(verification_time="2026-09-18"))
    assert time_only.qualified_result == "verified_but_qualified"
    no_state = _verify(
        pack, record,
        clock=_CURRENT_CLOCK.model_copy(update={"revocation_state": None}),
    )
    assert no_state.revocation_status == "no_current_revocation_information"
    future = _verify(
        pack, record,
        clock=_CURRENT_CLOCK.model_copy(update={"revocation_observed_at": "2026-10-01"}),
    )
    assert future.qualified_result == "verified_but_qualified"
    garbled = _verify(
        pack, record,
        clock=_CURRENT_CLOCK.model_copy(update={"verification_time": "soon"}),
    )
    assert garbled.clock_status == "uncertain"
    assert garbled.qualified_result == "verified_but_qualified"


# AC3: evidence expiring after issuance blocks current reuse while the exact
# historical package keeps its valid historical signature result.
def test_expiry_blocks_current_reuse_but_preserves_history():
    pack, record = _issue(_manifest())
    issuance_bytes = record.model_dump_json().encode("utf-8")

    def at(day: str) -> VerificationClock:
        return VerificationClock(
            verification_time=day,
            revocation_observed_at="2027-08-28",
            revocation_state="not_revoked",
        )

    before = _verify(pack, record, clock=at("2027-08-31"))
    after = _verify(pack, record, clock=at("2027-09-02"))
    again = _verify(pack, record, clock=at("2027-08-31"))
    assert before.qualified_result == "verified_current"
    assert after.qualified_result == "verified_but_qualified"
    assert after.evidence_freshness == "expired"
    assert after.signature_integrity == "verified"
    assert record.model_dump_json().encode("utf-8") == issuance_bytes
    assert again.qualified_result == "verified_current"


# AC4: a corrected answer creates an explicitly superseding issue while the
# previous issue stays independently verifiable.
def test_superseding_issue_keeps_previous_verifiable():
    original_pack, original_record = _issue(_manifest())
    corrected_pack, corrected_record = _issue(
        _manifest(CORRECTED_ATTACHMENT),
        CORRECTED_ATTACHMENT,
        supersedes=(issuance_digest(original_record),),
    )

    assert corrected_record.manifest_sha256 != original_record.manifest_sha256
    assert corrected_record.package_sha256 != original_record.package_sha256
    assert corrected_record.lifecycle.supersedes == (issuance_digest(original_record),)
    assert original_record.lifecycle.supersedes == ()

    assert _verify(original_pack, original_record).qualified_result == "verified_current"
    assert _verify(corrected_pack, corrected_record).qualified_result == "verified_current"


# AC3/AC4: lifecycle facts are recorded as separate explicit fields.
def test_lifecycle_fields_are_separate_and_explicit():
    _, record = _issue(_manifest())
    assert record.lifecycle.capture_time == "2026-09-18T10:00:00+00:00"
    assert record.lifecycle.valid_through == "2027-09-01"
    assert record.lifecycle.revocation_status == "not_revoked"
    assert record.lifecycle.supersedes == ()


def test_issuance_rejects_invalid_capture_time():
    manifest = _manifest()
    pack = _assemble(manifest, ATTACHMENT)
    with pytest.raises(AssuranceIssuanceError) as excinfo:
        issue_assurance_pack(
            assembled=pack,
            approval=_approval(manifest, pack),
            signer=_SIGNER,
            capture_time="yesterday-ish",
        )
    assert excinfo.value.code == AssuranceIssuanceError.INVALID_INPUT


# Issuance gate: an approval not covering this exact package is refused.
@pytest.mark.parametrize("field", ["manifest_sha256", "package_sha256", "audience"])
def test_issuance_rejects_approval_not_covering_package(field):
    manifest = _manifest()
    pack = _assemble(manifest, ATTACHMENT)
    value = "other-audience" if field == "audience" else _digest(b"other")
    approval = _approval(manifest, pack).model_copy(update={field: value})
    with pytest.raises(AssuranceIssuanceError) as excinfo:
        issue_assurance_pack(
            assembled=pack,
            approval=approval,
            signer=_SIGNER,
            capture_time="2026-09-18T10:00:00+00:00",
        )
    assert excinfo.value.code == AssuranceIssuanceError.APPROVAL_MISMATCH


def test_issuance_rejects_inconsistent_assembled_package():
    manifest = _manifest()
    pack = _assemble(manifest, ATTACHMENT)

    class _Forged:
        manifest = pack.manifest
        package_sha256 = pack.package_sha256
        package_bytes = pack.package_bytes + b"x"

    with pytest.raises(AssuranceIssuanceError) as excinfo:
        issue_assurance_pack(
            assembled=_Forged(),
            approval=_approval(manifest, pack),
            signer=_SIGNER,
            capture_time="2026-09-18T10:00:00+00:00",
        )
    assert excinfo.value.code == AssuranceIssuanceError.NOT_ASSEMBLED


# Issuance gate: support drift between approval and signing time is refused.
def test_issuance_rejects_stale_support_at_sign_time():
    manifest = _manifest()
    pack = _assemble(manifest, ATTACHMENT)
    approval = _approval(manifest, pack).model_copy(
        update={"recheck": {"soc2": "superseded_answer", "pentest": "current"}}
    )
    with pytest.raises(AssuranceIssuanceError) as excinfo:
        issue_assurance_pack(
            assembled=pack,
            approval=approval,
            signer=_SIGNER,
            capture_time="2026-09-18T10:00:00+00:00",
        )
    assert excinfo.value.code == AssuranceIssuanceError.STALE_SUPPORT


# Issuance gate: an unapproved custody mode fails closed.
def test_issuance_rejects_unsupported_signer():
    manifest = _manifest()
    pack = _assemble(manifest, ATTACHMENT)
    with pytest.raises(AssuranceIssuanceError) as excinfo:
        issue_assurance_pack(
            assembled=pack,
            approval=_approval(manifest, pack),
            signer=_RsaSigner(),
            capture_time="2026-09-18T10:00:00+00:00",
        )
    assert excinfo.value.code == AssuranceIssuanceError.UNSUPPORTED_SIGNER


# Security: no private key material in the record, the package or the
# distributed verification material.
def test_issuance_never_carries_secret_material():
    pack, record = _issue(_manifest())
    private = _ISSUER_KEY.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    record_json = record.model_dump_json()
    for blob in (record_json.encode(), pack.package_bytes, _TRUST.model_dump_json().encode()):
        assert private not in blob
        assert private.hex().encode() not in blob
    assert "private" not in repr(_SIGNER).lower()
    assert record.signature.algorithm == ALGORITHM_ED25519
    assert record.signing_profile.mode == SIGNING_MODE_SELF_HOSTED_ED25519
    assert set(TrustedVerificationMaterial.model_fields) == {
        "key_id", "algorithm", "signing_mode", "public_key",
    }


# AC6: the wording bounds what a signature proves, everywhere it is shown.
def test_signature_wording_is_bounded():
    pack, record = _issue(_manifest())
    result = _verify(pack, record)
    note = result.signature_semantics_note()
    assert note == SIGNATURE_SEMANTICS_NOTE
    assert SIGNATURE_SEMANTICS_NOTE in result.notes
    assert "integrity" in note
    assert "provenance" in note
    assert "not regulatory certification" in note
    assert "self-attested claims" in note


# Issuance gate: a self-consistent archive that does not hold exactly this
# manifest's package (here: another manifest's package) is never signed.
def test_issuance_rejects_package_of_another_manifest():
    manifest = _manifest()
    pack = _assemble(manifest, ATTACHMENT)
    other = _assemble(_manifest(CORRECTED_ATTACHMENT), CORRECTED_ATTACHMENT)

    class _Swapped:
        manifest = pack.manifest
        package_sha256 = other.package_sha256
        package_bytes = other.package_bytes

    approval = _approval(manifest, pack).model_copy(
        update={"package_sha256": other.package_sha256}
    )
    with pytest.raises(AssuranceIssuanceError) as excinfo:
        issue_assurance_pack(
            assembled=_Swapped(),
            approval=approval,
            signer=_SIGNER,
            capture_time="2026-09-18T10:00:00+00:00",
        )
    assert excinfo.value.code == AssuranceIssuanceError.NOT_ASSEMBLED


def test_issuance_refuses_pack_already_expired_at_capture():
    manifest = _manifest()
    pack = _assemble(manifest, ATTACHMENT)
    with pytest.raises(AssuranceIssuanceError) as excinfo:
        issue_assurance_pack(
            assembled=pack,
            approval=_approval(manifest, pack),
            signer=_SIGNER,
            capture_time="2027-09-02T00:00:00+00:00",
        )
    assert excinfo.value.code == AssuranceIssuanceError.EXPIRED


def test_issuance_requires_offset_aware_capture_time():
    manifest = _manifest()
    pack = _assemble(manifest, ATTACHMENT)
    with pytest.raises(AssuranceIssuanceError) as excinfo:
        issue_assurance_pack(
            assembled=pack,
            approval=_approval(manifest, pack),
            signer=_SIGNER,
            capture_time="2026-09-18T10:00:00",
        )
    assert excinfo.value.code == AssuranceIssuanceError.INVALID_INPUT


# Audience binding: a reviewer can refuse a package issued for someone else.
def test_verification_binds_expected_audience():
    pack, record = _issue(_manifest())
    common = {
        "issuance_json": record.model_dump_json().encode("utf-8"),
        "package_bytes": pack.package_bytes,
        "trust_material": _TRUST,
        "clock": _CURRENT_CLOCK,
    }
    matching = verify_assurance_pack_offline(**common, expected_audience="enterprise")
    assert matching.qualified_result == "verified_current"
    other = verify_assurance_pack_offline(**common, expected_audience="public-buyer")
    assert other.qualified_result == "failed"
    assert other.notes == ("Verification failed: package was issued for a different audience.",)


# Clock facts parse strictly; trailing garbage never yields a certain clock.
def test_malformed_verification_time_leaves_clock_uncertain():
    pack, record = _issue(_manifest())
    clock = _CURRENT_CLOCK.model_copy(update={"verification_time": "2026-09-18garbage"})
    result = _verify(pack, record, clock=clock)
    assert result.clock_status == "uncertain"
    assert result.qualified_result == "verified_but_qualified"
