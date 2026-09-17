"""Contract tests for the #883 assurance pack manifest contracts."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from axis_api.assurance_pack_contracts import (
    AnswerSelection,
    AssurancePackError,
    ManifestVersion,
    PackContext,
    PackManifest,
    ReleaseSnapshot,
    canonical_pack_digest,
    check_support_freshness,
    pack_readiness,
    parse_assurance_pack,
    reference_scope_note,
)

_SNAPSHOT_DIGEST = "a" * 64
_ANSWER_DIGEST = "b" * 64
_ARTIFACT_DIGEST = "c" * 64


def _context(**overrides: object) -> PackContext:
    values: dict[str, object] = {
        "engagement_ref": "engagements.acme-2026",
        "audience": "acme-enterprise",
        "purpose": "Enterprise review evidence for the Acme engagement.",
        "disclosure_class": "under_nda",
    }
    values.update(overrides)
    return PackContext.model_validate(values)


def _snapshot() -> ReleaseSnapshot:
    return ReleaseSnapshot(
        release="1.14.0",
        profile="gov-hardened",
        posture_observation_ref="observations.deployment-posture",
        posture_revision="7",
        posture_digest=_SNAPSHOT_DIGEST,
    )


def _entries() -> tuple[AnswerSelection, ...]:
    return (
        # One current included artifact.
        AnswerSelection(
            entry_id="ent-soc2",
            question_ref="questions.soc2-summary",
            answer_revision="3",
            answer_digest=_ANSWER_DIGEST,
            support="current",
            mode="included_artifact",
            artifact_digest=_ARTIFACT_DIGEST,
            evidence_refs=("evidence.audit-report-2026",),
            as_of="2026-09-01",
        ),
        # One NDA/reference-only item.
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
        # One customer-responsibility answer.
        AnswerSelection(
            entry_id="ent-tenant-dns",
            question_ref="questions.dns-hardening",
            answer_revision="1",
            answer_digest="e" * 64,
            support="current",
            responsibility="customer",
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


def _manifest(**overrides: object) -> PackManifest:
    values: dict[str, object] = {
        "schema_version": ManifestVersion(major=1, minor=0),
        "pack_id": "pack-acme-2026",
        "title": "Acme assurance pack",
        "context": _context(),
        "release_snapshot": _snapshot(),
        "entries": _entries(),
        "valid_through": "2026-12-31",
    }
    values.update(overrides)
    return PackManifest.model_validate(values)


# --- AC: the synthetic four-entry pack ----------------------------------------


def test_synthetic_pack_covers_all_four_entry_shapes() -> None:
    manifest = _manifest()
    shapes = {
        (entry.entry_id, entry.mode, entry.support, entry.responsibility)
        for entry in manifest.entries
    }
    assert ("ent-soc2", "included_artifact", "current", "axis") in shapes
    assert ("ent-pen-test", "reference_only", "current", "axis") in shapes
    assert ("ent-tenant-dns", "reference_only", "current", "customer") in shapes
    assert ("ent-fedramp", "reference_only", "not_evidenced", "axis") in shapes


def test_pack_digest_is_deterministic_and_tamper_evident() -> None:
    manifest = _manifest()
    raw = json.loads(manifest.model_dump_json())
    reordered = dict(reversed(list(raw.items())))
    assert canonical_pack_digest(raw) == canonical_pack_digest(reordered)
    assert canonical_pack_digest(raw) == manifest.digest()
    tampered = dict(raw)
    tampered["valid_through"] = "2027-12-31"
    assert canonical_pack_digest(tampered) != manifest.digest()


# --- AC: expired, wrong snapshot, superseded answers fail freshness -----------


def test_stale_support_states_are_surfaced_not_hidden() -> None:
    manifest = _manifest()
    digest, stale = check_support_freshness(
        manifest,
        observed={
            "ent-soc2": "expired_certificate",
            "ent-pen-test": "wrong_release_profile",
            "ent-tenant-dns": "superseded_answer",
            "ent-fedramp": "current",
        },
    )
    assert digest == manifest.digest()
    assert stale == (
        "ent-soc2:expired_certificate",
        "ent-pen-test:wrong_release_profile",
        "ent-tenant-dns:superseded_answer",
    )


def test_fresh_pack_observation_is_clean() -> None:
    manifest = _manifest()
    digest, stale = check_support_freshness(
        manifest, observed={entry.entry_id: "current" for entry in manifest.entries}
    )
    assert stale == () and digest == manifest.digest()


def test_missing_observation_is_itself_stale() -> None:
    _, stale = check_support_freshness(_manifest(), observed={})
    assert len(stale) == 4 and all(state.endswith(":missing_observation") for state in stale)


# --- construction-time structural rules ---------------------------------------


def test_partial_and_planned_entries_must_state_limitations() -> None:
    with pytest.raises(ValidationError, match="must state their exact limitation"):
        AnswerSelection(
            entry_id="ent-partial",
            question_ref="questions.dr-recovery",
            answer_revision="1",
            answer_digest="9" * 64,
            support="partial",
            as_of="2026-09-01",
        )


def test_included_artifact_requires_digest_and_bars_internal_disclosure() -> None:
    with pytest.raises(ValidationError, match="carry their content digest"):
        AnswerSelection(
            entry_id="ent-artifact",
            question_ref="questions.soc2-summary",
            answer_revision="3",
            answer_digest=_ANSWER_DIGEST,
            support="current",
            mode="included_artifact",
            as_of="2026-09-01",
        )
    with pytest.raises(ValidationError, match="Internal-only"):
        AnswerSelection(
            entry_id="ent-artifact",
            question_ref="questions.soc2-summary",
            answer_revision="3",
            answer_digest=_ANSWER_DIGEST,
            support="current",
            mode="included_artifact",
            artifact_digest=_ARTIFACT_DIGEST,
            disclosure="internal_only",
            as_of="2026-09-01",
        )


def test_reference_only_entries_carry_no_artifact() -> None:
    with pytest.raises(ValidationError, match="no artifact bytes"):
        AnswerSelection(
            entry_id="ent-ref",
            question_ref="questions.pentest-coverage",
            answer_revision="2",
            answer_digest="d" * 64,
            support="current",
            mode="reference_only",
            artifact_digest=_ARTIFACT_DIGEST,
            as_of="2026-09-01",
        )


def test_customer_responsibility_cannot_claim_axis_ownership() -> None:
    with pytest.raises(ValidationError, match="cannot claim Axis ownership"):
        AnswerSelection(
            entry_id="ent-dns",
            question_ref="questions.dns-hardening",
            answer_revision="1",
            answer_digest="e" * 64,
            support="customer_responsibility",
            responsibility="axis",
            as_of="2026-09-01",
        )


def test_duplicate_entries_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate_pack_entry"):
        _manifest(entries=_entries()[:1] + _entries()[:1])


def test_unsafe_text_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unsafe_pack_text"):
        _manifest(context=_context(purpose="Trusted <script>alert(1)</script> review"))
    with pytest.raises(ValidationError, match="unsafe_pack_text"):
        _manifest(title="Pack {{renderer}}")


# --- preflight gating ----------------------------------------------------------


def test_preflight_blocks_pack_without_any_current_support() -> None:
    manifest = _manifest(
        entries=(
            AnswerSelection(
                entry_id="ent-only",
                question_ref="questions.fedramp-status",
                answer_revision="1",
                answer_digest="f" * 64,
                support="not_evidenced",
                limitation="Not performed.",
                as_of="2026-09-01",
            ),
        )
    )
    _, ready, blocking = pack_readiness(manifest)
    assert not ready
    assert "no_current_support_in_pack" in blocking


def test_preflight_passes_the_synthetic_pack() -> None:
    _, ready, blocking = pack_readiness(_manifest())
    assert ready and blocking == ()


def test_changing_anything_after_approval_invalidates_the_digest() -> None:
    approved = _manifest()
    changed = PackManifest.model_validate(
        {
            **approved.model_dump(mode="json"),
            "context": _context(audience="acme-enterprise-plus"),
        }
    )
    assert changed.digest() != approved.digest()
    # Freshness observations keyed to the approved digest no longer apply;
    # preflight must run again against the new candidate.
    _, stale = check_support_freshness(changed, observed={})
    assert len(stale) == len(changed.entries)


# --- scope note and untrusted parsing ------------------------------------------


def test_reference_scope_note_binds_871_and_879_citations() -> None:
    note = reference_scope_note()
    assert "#871" in note and "#879" in note
    assert "not evidence" in note


def test_round_trip_is_byte_stable() -> None:
    manifest = _manifest()
    parsed = parse_assurance_pack(json.loads(manifest.model_dump_json()))
    assert parsed == manifest
    assert parsed.digest() == manifest.digest()


def test_parse_rejects_future_major_with_dedicated_code() -> None:
    raw = json.loads(_manifest().model_dump_json())
    raw["schema_version"] = {"major": 2, "minor": 0}
    with pytest.raises(AssurancePackError) as blocked:
        parse_assurance_pack(raw)
    assert blocked.value.code == AssurancePackError.INCOMPATIBLE_VERSION


def test_parse_reports_malformed_payload_with_safe_code() -> None:
    with pytest.raises(AssurancePackError) as blocked:
        parse_assurance_pack("not-a-pack")
    assert blocked.value.code == AssurancePackError.INVALID_MANIFEST
