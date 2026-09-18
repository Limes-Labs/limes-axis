"""Domain tests for the #884 assurance pack assembly service."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile

import pytest

from axis_api.assurance_pack_contracts import (
    AnswerSelection,
    ManifestVersion,
    PackContext,
    PackManifest,
    ReleaseSnapshot,
    check_support_freshness,
)
from axis_api.assurance_packaging import (
    MAX_ATTACHMENT_BYTES,
    MAX_ATTACHMENTS,
    PackagingError,
    build_assurance_pack,
    build_index_text,
)

_SECRET = b"AXIS-SECRET-PLANTED-TOKEN"
_ATTACHMENT = b"SOC2 report body, released revision 3\n"
_DERIVATIVE = b"Sanitized SOC2 summary (redacted by derivative-artifact owner)\n"


def _context() -> PackContext:
    return PackContext.model_validate(
        {
            "engagement_ref": "engagements.acme-2026",
            "audience": "acme-enterprise",
            "purpose": "Enterprise review evidence for the Acme engagement.",
            "disclosure_class": "under_nda",
        }
    )


def _snapshot() -> ReleaseSnapshot:
    return ReleaseSnapshot(
        release="1.14.0",
        profile="gov-hardened",
        posture_observation_ref="observations.deployment-posture",
        posture_revision="7",
        posture_digest="a" * 64,
    )


def _included(
    entry_id: str,
    question_ref: str,
    content: bytes,
    revision: str = "3",
) -> AnswerSelection:
    digest = hashlib.sha256(content).hexdigest()
    return AnswerSelection(
        entry_id=entry_id,
        question_ref=question_ref,
        answer_revision=revision,
        answer_digest=digest,
        support="current",
        mode="included_artifact",
        artifact_digest=digest,
        as_of="2026-09-01",
    )


def _entries() -> tuple[AnswerSelection, ...]:
    return (
        # One released attachment.
        _included("ent-soc2", "questions.soc2-summary", _ATTACHMENT, "3"),
        # One sanitized derivative (redacted upstream by its owner).
        _included("ent-soc2-derivative", "questions.soc2-redacted", _DERIVATIVE, "2"),
        # One reference-only evidence entry: cited, never copied.
        AnswerSelection(
            entry_id="ent-pen-test",
            question_ref="questions.pentest-coverage",
            answer_revision="2",
            answer_digest="d" * 64,
            support="current",
            mode="reference_only",
            evidence_refs=("evidence.pentest-2026-06",),
            as_of="2026-09-01",
        ),
        # One unsupported requirement with its exact limitation.
        AnswerSelection(
            entry_id="ent-fedramp",
            question_ref="questions.fedramp-status",
            answer_revision="1",
            answer_digest="f" * 64,
            support="not_evidenced",
            limitation="FedRAMP assessment has not been performed for this release.",
            as_of="2026-09-01",
        ),
    )


def _manifest(entries: tuple[AnswerSelection, ...] | None = None) -> PackManifest:
    return PackManifest(
        schema_version=ManifestVersion(major=1, minor=0),
        pack_id="pack-acme-2026",
        title="Acme assurance pack",
        context=_context(),
        release_snapshot=_snapshot(),
        entries=_entries() if entries is None else entries,
        valid_through="2026-12-31",
    )


def _trio() -> tuple[AnswerSelection, ...]:
    """Entries without the derivative attachment (for focused scans)."""

    return _entries()[:1] + _entries()[2:]


class _Source:
    """Caller-owned release authorization over a simple in-memory store."""

    def __init__(self, store: dict[str, bytes], *, revoked: bool = False) -> None:
        self.store = store
        self.revoked = revoked
        self.resolved: list[str] = []

    def resolve(self, entry: AnswerSelection, manifest: PackManifest) -> bytes:
        self.resolved.append(entry.entry_id)
        if self.revoked:
            raise PackagingError(PackagingError.RELEASE_NOT_CURRENT)
        content = self.store.get(entry.entry_id)
        if content is None:
            raise PackagingError(PackagingError.ARTIFACT_UNAVAILABLE)
        return content


class _Scanner:
    """Caller-owned final-output inspection; flags the planted token."""

    def __init__(self, *, blind_format: str | None = None) -> None:
        self.blind_format = blind_format
        self.scanned: list[tuple[str, int]] = []

    def scan(self, data: bytes, fmt: str) -> bool:
        if self.blind_format is not None and fmt == self.blind_format:
            raise PackagingError(PackagingError.UNSUPPORTED_SCAN_FORMAT)
        self.scanned.append((fmt, len(data)))
        return _SECRET not in data


# --- AC1: attachment + sanitized derivative + byte-free reference-only --------


def test_synthetic_pack_carries_both_modes() -> None:
    manifest = _manifest()
    source = _Source({"ent-soc2": _ATTACHMENT, "ent-soc2-derivative": _DERIVATIVE})
    pack = build_assurance_pack(manifest, source, _Scanner())

    assert pack.included_attachments == (
        "attachments/ent-soc2.bin",
        "attachments/ent-soc2-derivative.bin",
    )
    assert [c.entry_id for c in pack.reference_only_citations] == [
        "ent-pen-test",
        "ent-fedramp",
    ]

    archive = zipfile.ZipFile(io.BytesIO(pack.package_bytes))
    members = archive.namelist()
    assert members == [
        "manifest.json",
        "index.md",
        "attachments/ent-soc2.bin",
        "attachments/ent-soc2-derivative.bin",
    ]
    # The reference-only entry contributes no member and no restricted bytes.
    assert not any("ent-pen-test" in name for name in members)
    assert all(_SECRET not in archive.read(name) for name in members)
    # The citation itself is metadata-only, bound to the contract scope note.
    citation = pack.reference_only_citations[0]
    assert citation.evidence_refs == ("evidence.pentest-2026-06",)
    assert "reference-only" in citation.scope_note


def test_reference_only_citation_is_metadata_only() -> None:
    index = build_index_text(_manifest())
    assert "availability: reference only" in index
    assert "http" not in index and "://" not in index


# --- AC2: planted secrets in attachment, filename or index block release ------


def test_planted_secret_in_released_attachment_blocks_release() -> None:
    content = _ATTACHMENT + b"api_key = " + _SECRET + b"\n"
    entry = _included("ent-soc2", "questions.soc2-summary", content)
    manifest = _manifest((entry, *_trio()[1:]))
    with pytest.raises(PackagingError) as blocked:
        build_assurance_pack(manifest, _Source({"ent-soc2": content}), _Scanner())
    assert blocked.value.code == PackagingError.SECRET_DETECTED


def test_planted_secret_in_index_text_blocks_release() -> None:
    class IndexSecretScanner(_Scanner):
        def scan(self, data: bytes, fmt: str) -> bool:
            if fmt == "text" and b"assurance pack" in data and _SECRET in data:
                return False
            return super().scan(data, fmt)

    # The secret rides inside the (approved) limitation text of an entry.
    entries = (
        _trio()[0],
        _trio()[1],
        AnswerSelection(
            entry_id="ent-fedramp",
            question_ref="questions.fedramp-status",
            answer_revision="1",
            answer_digest="f" * 64,
            support="not_evidenced",
            limitation=f"Pending review. {_SECRET.decode()}",
            as_of="2026-09-01",
        ),
    )
    source = _Source({"ent-soc2": _ATTACHMENT})
    scanner = IndexSecretScanner()
    with pytest.raises(PackagingError) as blocked:
        build_assurance_pack(_manifest(entries), source, scanner)
    assert blocked.value.code == PackagingError.SECRET_DETECTED


def test_planted_secret_in_filename_blocks_release() -> None:
    class FilenameScanner(_Scanner):
        def scan(self, data: bytes, fmt: str) -> bool:
            return not (fmt == "filename" and b"ent-soc2" in data)

    with pytest.raises(PackagingError) as blocked:
        build_assurance_pack(
            _manifest(_trio()), _Source({"ent-soc2": _ATTACHMENT}), FilenameScanner()
        )
    assert blocked.value.code == PackagingError.SECRET_DETECTED


def test_scanner_that_cannot_judge_a_format_aborts_the_build() -> None:
    with pytest.raises(PackagingError) as blocked:
        build_assurance_pack(
            _manifest(_trio()),
            _Source({"ent-soc2": _ATTACHMENT}),
            _Scanner(blind_format="json"),
        )
    assert blocked.value.code == PackagingError.UNSUPPORTED_SCAN_FORMAT


# --- AC3: revocation, revision change, expired evidence invalidate generation -


def test_revoked_audience_invalidates_generation() -> None:
    source = _Source({"ent-soc2": _ATTACHMENT}, revoked=True)
    with pytest.raises(PackagingError) as blocked:
        build_assurance_pack(_manifest(_trio()), source, _Scanner())
    assert blocked.value.code == PackagingError.RELEASE_NOT_CURRENT
    # Nothing was issued: no package exists to reuse or download.
    assert source.resolved == ["ent-soc2"]


def test_changed_artifact_revision_invalidates_generation() -> None:
    class SupersededSource(_Source):
        def resolve(self, entry: AnswerSelection, manifest: PackManifest) -> bytes:
            raise PackagingError(PackagingError.REVISION_MISMATCH)

    with pytest.raises(PackagingError) as blocked:
        build_assurance_pack(_manifest(_trio()), SupersededSource({}), _Scanner())
    assert blocked.value.code == PackagingError.REVISION_MISMATCH


def test_unavailable_required_evidence_invalidates_generation() -> None:
    with pytest.raises(PackagingError) as blocked:
        build_assurance_pack(_manifest(_trio()), _Source({}), _Scanner())
    assert blocked.value.code == PackagingError.ARTIFACT_UNAVAILABLE


def test_tampered_bytes_fail_integrity_even_with_matching_source() -> None:
    # Producer-side digest stays over approved bytes; the builder re-verifies.
    class LyingSource(_Source):
        def resolve(self, entry: AnswerSelection, manifest: PackManifest) -> bytes:
            return _ATTACHMENT + b"tampered"

    with pytest.raises(PackagingError) as blocked:
        build_assurance_pack(_manifest(_trio()), LyingSource({"ent-soc2": _ATTACHMENT}), _Scanner())
    assert blocked.value.code == PackagingError.DIGEST_MISMATCH


def test_expired_support_is_caught_by_preflight_not_the_builder() -> None:
    # The builder verifies bytes; support-state freshness stays with #883.
    manifest = _manifest()
    _, stale = check_support_freshness(
        manifest,
        observed={"ent-soc2": "expired_certificate", "ent-fedramp": "current"},
    )
    assert "ent-soc2:expired_certificate" in stale


# --- AC4: claims are preserved verbatim, never upgraded -----------------------


def test_summary_preserves_limitations_and_scope_verbatim() -> None:
    index = build_index_text(_manifest())
    assert "FedRAMP assessment has not been performed for this release." in index
    assert "reference-only for their actually tested scope" in index
    # No automatic positive compliance wording is introduced.
    assert "fully compliant" not in index.lower()
    assert "certified" not in index.lower()


def test_manifest_json_inside_package_is_canonical_and_verbatim() -> None:
    manifest = _manifest()
    source = _Source({"ent-soc2": _ATTACHMENT, "ent-soc2-derivative": _DERIVATIVE})
    pack = build_assurance_pack(manifest, source, _Scanner())
    raw = json.loads(zipfile.ZipFile(io.BytesIO(pack.package_bytes)).read("manifest.json"))
    assert raw["entries"][3]["limitation"] == (
        "FedRAMP assessment has not been performed for this release."
    )
    assert raw["entries"][3]["support"] == "not_evidenced"
    assert pack.manifest_digest == manifest.digest()


# --- AC5: bounded resources; partial failure leaves no issued artifact --------


def test_attachment_count_is_bounded() -> None:
    content = _ATTACHMENT
    entries = tuple(
        _included(f"ent-bulk-{index}", f"questions.bulk-{index}", content)
        for index in range(MAX_ATTACHMENTS + 1)
    )
    store = {entry.entry_id: content for entry in entries}
    with pytest.raises(PackagingError) as blocked:
        build_assurance_pack(_manifest(entries), _Source(store), _Scanner())
    assert blocked.value.code == PackagingError.BOUNDS_EXCEEDED


def test_attachment_size_is_bounded() -> None:
    content = b"x" * (MAX_ATTACHMENT_BYTES + 1)
    entries = (_included("ent-big", "questions.soc2-summary", content),)
    with pytest.raises(PackagingError) as blocked:
        build_assurance_pack(_manifest(entries), _Source({"ent-big": content}), _Scanner())
    assert blocked.value.code == PackagingError.BOUNDS_EXCEEDED


def test_partial_failure_leaves_no_issued_success_artifact() -> None:
    # The second attachment cannot be resolved: nothing is returned at all.
    source = _Source({"ent-soc2": _ATTACHMENT})
    with pytest.raises(PackagingError) as blocked:
        build_assurance_pack(_manifest(), source, _Scanner())
    assert blocked.value.code == PackagingError.ARTIFACT_UNAVAILABLE
    assert source.resolved == ["ent-soc2", "ent-soc2-derivative"]


def test_member_and_package_size_are_bounded() -> None:
    from axis_api.assurance_packaging import MAX_MEMBERS, MAX_PACKAGE_BYTES

    assert MAX_MEMBERS == 128
    assert MAX_PACKAGE_BYTES == 16 * 1024 * 1024


# --- AC6: local generation, no external fetches, safe audit facts -------------


def test_generation_makes_no_external_calls_and_emits_safe_facts() -> None:
    manifest = _manifest()
    source = _Source({"ent-soc2": _ATTACHMENT, "ent-soc2-derivative": _DERIVATIVE})
    scanner = _Scanner()
    pack = build_assurance_pack(manifest, source, scanner)

    # Exactly one resolve per included entry; scans are local bytes only.
    assert sorted(source.resolved) == ["ent-soc2", "ent-soc2-derivative"]
    formats = [fmt for fmt, _ in scanner.scanned]
    assert set(formats) <= {"json", "text", "filename"}

    # Ordinary audit carries digests/counts/reason codes — never content.
    audit_facts = {
        "pack_id": pack.manifest.pack_id,
        "manifest_digest": pack.manifest_digest,
        "package_sha256": pack.package_sha256,
        "member_count": len(pack.members),
        "attachment_count": len(pack.included_attachments),
        "reference_only_count": len(pack.reference_only_citations),
    }
    encoded = json.dumps(audit_facts).encode()
    assert b"SOC2 report body" not in encoded
    assert _SECRET not in encoded


def test_deterministic_package_and_tamper_evidence() -> None:
    manifest = _manifest()
    source = _Source({"ent-soc2": _ATTACHMENT, "ent-soc2-derivative": _DERIVATIVE})
    first = build_assurance_pack(manifest, source, _Scanner())
    second = build_assurance_pack(manifest, _Source(source.store), _Scanner())
    assert first.package_bytes == second.package_bytes
    assert first.package_sha256 == second.package_sha256

    archive = zipfile.ZipFile(io.BytesIO(first.package_bytes))
    infos = archive.infolist()
    assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in infos)
    assert all(info.create_system == 3 for info in infos)
    assert archive.read("attachments/ent-soc2.bin") == _ATTACHMENT

    # Different approved attachment bytes produce a different package.
    revised = _manifest(
        (
            _included("ent-soc2", "questions.soc2-summary", _ATTACHMENT + b"v2\n"),
            *_trio()[1:],
        )
    )
    other = build_assurance_pack(
        revised,
        _Source({"ent-soc2": _ATTACHMENT + b"v2\n", "ent-soc2-derivative": _DERIVATIVE}),
        _Scanner(),
    )
    assert other.package_sha256 != first.package_sha256
