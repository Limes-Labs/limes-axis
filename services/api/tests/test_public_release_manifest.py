"""Contract tests for the #838 public dataset release manifest."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from axis_api.public_release_manifest import (
    InternalSourceLedger,
    InternalSourceRef,
    LicenseRecord,
    ManifestVersion,
    PopulationRecord,
    PublicDatasetIdentity,
    PublicReleaseError,
    PublicReleaseManifest,
    PublicSchemaField,
    ReleaseNotes,
    ReviewEvidence,
    SourceBinding,
    SupersedesRecord,
    WithdrawalRecord,
    bind_internal_ledger,
    canonical_release_digest,
    diff_releases,
    parse_public_release_manifest,
    public_release_uri_path,
    release_readiness,
)

_INTERNAL_SOURCE_REF = "dp-8841-alpha-internal"
_SOURCE_DIGEST_V1 = "a" * 64
_SOURCE_DIGEST_V2 = "b" * 64
_POPULATION_DIGEST = "c" * 64


def _identity() -> PublicDatasetIdentity:
    return PublicDatasetIdentity(
        public_id="ds-airquality0001",
        api_name="air-quality-daily",
        title="Daily air quality observations",
        description="Station-level daily observations published by the city.",
        publisher="City Open Data Office",
    )


def _reviews(decided_at: str = "2026-09-02T10:00:00Z") -> tuple[ReviewEvidence, ...]:
    """Approval evidence; must postdate whatever source freeze the manifest pins."""

    return (
        ReviewEvidence(
            kind="disclosure",
            status="approved",
            authority_ref="board/disclosure/2026-087",
            decided_at=decided_at,
        ),
        ReviewEvidence(
            kind="license",
            status="approved",
            authority_ref="legal/license/2026-041",
            decided_at=decided_at,
        ),
    )


def _source(digest: str, captured_at: str) -> SourceBinding:
    return SourceBinding(mode="governed_snapshot", source_digest=digest, captured_at=captured_at)


def _manifest(**overrides: object) -> PublicReleaseManifest:
    values: dict[str, object] = {
        "schema_version": ManifestVersion(major=1, minor=0),
        "identity": _identity(),
        "release_version": "1.0",
        "state": "issued",
        "source": _source(_SOURCE_DIGEST_V1, "2026-09-01T09:00:00Z"),
        "fields": (
            PublicSchemaField(
                name="station_id", dtype="string", nullable=False, description="Station code"
            ),
            PublicSchemaField(
                name="observed_at", dtype="datetime", nullable=False, description="Day of reading"
            ),
            PublicSchemaField(
                name="pm25", dtype="decimal", nullable=True, description="PM2.5 concentration"
            ),
        ),
        "population": PopulationRecord(
            mode="snapshot_rows", row_count=1_200, content_digest=_POPULATION_DIGEST
        ),
        "license": LicenseRecord(license_id="cc-by-4.0", access_rights="Open use with attribution"),
        "reviews": _reviews(),
        "coverage_start": "2024-01-01",
        "coverage_end": "2024-12-31",
        "release_notes": ReleaseNotes(summary="Initial publication", changes=()),
        "issued_at": "2026-09-05T08:00:00Z",
    }
    values.update(overrides)
    return PublicReleaseManifest.model_validate(values)


def _ledger(manifest: PublicReleaseManifest) -> InternalSourceLedger:
    return InternalSourceLedger(
        identity_public_id=manifest.identity.public_id,
        manifest_digest=manifest.digest(),
        internal_catalog_ref="catalog/product-42-alpha",
        sources=(
            InternalSourceRef(
                ref=_INTERNAL_SOURCE_REF, kind="data_product", digest="d" * 64
            ),
        ),
        captured_at="2026-09-01T09:00:00Z",
    )


# --- schema definition and sealed issuance ---------------------------------


def test_sealed_issued_manifest_carries_complete_publication_evidence() -> None:
    manifest = _manifest()
    evidence = manifest.public_evidence()
    assert evidence["state"] == "issued"
    assert evidence["content_digest"] == _POPULATION_DIGEST
    assert evidence["field_count"] == 3
    assert evidence["license_id"] == "cc-by-4.0"


def test_issued_release_without_content_digest_is_fabricated_success() -> None:
    with pytest.raises(ValidationError, match="fabricated success"):
        _manifest(
            population=PopulationRecord(mode="snapshot_rows", row_count=1_200, content_digest=None)
        )


def test_non_sealed_state_cannot_claim_issuance() -> None:
    with pytest.raises(ValidationError, match="issuance timestamp"):
        _manifest(state="draft")


def test_public_manifest_never_contains_internal_lineage() -> None:
    manifest = _manifest()
    payload = json.dumps(manifest.model_dump(mode="json"))
    assert _INTERNAL_SOURCE_REF not in payload
    assert _ledger(manifest).sources[0].ref == _INTERNAL_SOURCE_REF


# --- immutability across internal source changes ----------------------------


def test_internal_source_change_leaves_issued_release_immutable() -> None:
    v1 = _manifest()
    digest_v1 = v1.digest()
    v2 = _manifest(
        release_version="2.0",
        source=_source(_SOURCE_DIGEST_V2, "2026-09-15T09:00:00Z"),
        reviews=_reviews(decided_at="2026-09-16T10:00:00Z"),
        supersedes=SupersedesRecord(
            release_public_id=v1.identity.public_id,
            release_version=v1.release_version,
            manifest_digest=v1.digest(),
        ),
        release_notes=ReleaseNotes(summary="Refreshed source snapshot", changes=()),
        issued_at="2026-09-16T08:00:00Z",
    )
    assert v1.digest() == digest_v1
    assert v2.digest() != digest_v1
    assert v2.supersedes is not None and v2.supersedes.manifest_digest == digest_v1


def test_candidate_v2_diff_reports_public_changes_only() -> None:
    v1 = _manifest()
    candidate = _manifest(
        release_version="2.0",
        fields=v1.fields
        + (PublicSchemaField(name="no2", dtype="decimal", nullable=True, description="NO2 level"),),
        source=_source(_SOURCE_DIGEST_V2, "2026-09-15T09:00:00Z"),
        reviews=_reviews(decided_at="2026-09-16T10:00:00Z"),
        release_notes=ReleaseNotes(summary="placeholder", changes=()),
        issued_at="2026-09-16T08:00:00Z",
    )
    notes = diff_releases(v1, candidate)
    final = candidate.model_copy(update={"release_notes": notes})
    assert diff_releases(v1, final) == notes
    kinds = {change.kind for change in notes.changes}
    assert kinds == {"field_added", "source_refresh"}
    details = json.dumps([change.model_dump(mode="json") for change in notes.changes])
    assert _INTERNAL_SOURCE_REF not in details


def test_diff_rejects_cross_dataset_and_non_monotonic_versions() -> None:
    v1 = _manifest()
    other = _manifest(identity=PublicDatasetIdentity(
        public_id="ds-otherdataset1",
        api_name="other-dataset",
        title="Other",
        description="Other dataset",
        publisher="Other office",
    ))
    with pytest.raises(PublicReleaseError) as cross:
        diff_releases(v1, other)
    assert cross.value.code == PublicReleaseError.CROSS_DATASET_DIFF
    with pytest.raises(PublicReleaseError) as nonmono:
        diff_releases(v1, _manifest(release_version="1.0"))
    assert nonmono.value.code == PublicReleaseError.NON_MONOTONIC_VERSION


# --- opaque public identity -------------------------------------------------


@pytest.mark.parametrize(
    "bad_id",
    ["3f9d2c8a-1234-5678-9abc-def012345678", "1234567890123", "DS-AIR1", "ds-short"],
)
def test_public_ids_are_disjoint_from_internal_id_shapes(bad_id: str) -> None:
    with pytest.raises(ValidationError):
        PublicDatasetIdentity(
            public_id=bad_id,
            api_name="air-quality-daily",
            title="t",
            description="d",
            publisher="p",
        )
    with pytest.raises(ValidationError):
        public_release_uri_path(bad_id, "1.0")


def test_public_uri_path_is_stable_and_versioned() -> None:
    assert (
        public_release_uri_path("ds-airquality0001", "1.0")
        == "/public/datasets/ds-airquality0001/releases/1.0"
    )


@pytest.mark.parametrize("bad_version", ["../..", "1.0/drop", "", "v1"])
def test_public_uri_path_rejects_traversal_payloads(bad_version: str) -> None:
    with pytest.raises(PublicReleaseError) as rejected:
        public_release_uri_path("ds-airquality0001", bad_version)
    assert rejected.value.code == PublicReleaseError.INVALID_MANIFEST


# --- deterministic digest and tamper evidence --------------------------------


def test_digest_is_deterministic_regardless_of_input_key_order() -> None:
    left = json.loads(_manifest().model_dump_json())
    right = dict(reversed(list(left.items())))
    assert canonical_release_digest(left) == canonical_release_digest(right)
    assert canonical_release_digest(left) == _manifest().digest()


def test_tampered_manifest_changes_digest() -> None:
    manifest = _manifest()
    tampered = _manifest(
        license=LicenseRecord(license_id="cc0-1.0", access_rights="No rights reserved")
    )
    assert manifest.digest() != tampered.digest()


def test_parse_rejects_unknown_fields_and_future_majors() -> None:
    payload = _manifest().model_dump(mode="json")
    with pytest.raises(PublicReleaseError) as unknown:
        parse_public_release_manifest({**payload, "internal_sources": [_INTERNAL_SOURCE_REF]})
    assert unknown.value.code == PublicReleaseError.INVALID_MANIFEST
    with pytest.raises(PublicReleaseError) as future:
        parse_public_release_manifest({**payload, "schema_version": {"major": 2, "minor": 0}})
    assert future.value.code == PublicReleaseError.INCOMPATIBLE_VERSION
    with pytest.raises(PublicReleaseError) as malformed:
        parse_public_release_manifest("not-a-manifest")
    assert malformed.value.code == PublicReleaseError.INVALID_MANIFEST


def test_major_version_bump_is_rejected_at_model_level() -> None:
    with pytest.raises(ValidationError, match="current contract version"):
        ManifestVersion(major=2, minor=0)


# --- live-query-as-release and stale authorization rejections ----------------


def test_live_query_source_mode_is_unrepresentable() -> None:
    with pytest.raises(ValidationError):
        SourceBinding(  # type: ignore[arg-type]
            mode="live_query", source_digest=_SOURCE_DIGEST_V1, captured_at="2026-09-01T09:00:00Z"
        )


def test_population_mode_must_follow_from_source_mode() -> None:
    with pytest.raises(ValidationError, match="does not follow from"):
        _manifest(
            population=PopulationRecord(
                mode="external_artifact", row_count=1_200, content_digest=_POPULATION_DIGEST
            )
        )


def test_review_older_than_frozen_source_is_stale_authorization() -> None:
    stale = list(_reviews())
    stale[0] = ReviewEvidence(
        kind="disclosure",
        status="approved",
        authority_ref="board/disclosure/2026-001",
        decided_at="2026-08-15T10:00:00Z",
    )
    with pytest.raises(ValidationError, match="predates the frozen source"):
        _manifest(reviews=tuple(stale))


def test_review_evidence_coherence() -> None:
    with pytest.raises(ValidationError, match="Pending"):
        ReviewEvidence(kind="disclosure", status="pending", decided_at="2026-09-02T10:00:00Z")
    with pytest.raises(ValidationError, match="authority"):
        ReviewEvidence(kind="license", status="approved", decided_at="2026-09-03T10:00:00Z")


# --- withdrawal and supersession evidence ------------------------------------


def test_withdrawal_preserves_issued_evidence_and_honest_scope() -> None:
    issued = _manifest()
    payload = issued.model_dump(mode="json")
    payload["state"] = "withdrawn"
    payload["withdrawal"] = WithdrawalRecord(
        issued_manifest_digest=issued.digest(),
        reason="coverage error discovered in one station",
        withdrawn_at="2026-09-10T08:00:00Z",
    ).model_dump(mode="json")
    withdrawn = PublicReleaseManifest.model_validate(payload)
    assert withdrawn.withdrawal is not None
    assert withdrawn.withdrawal.external_copies_note == "external_copies_not_retracted"
    assert withdrawn.digest() != issued.digest()
    revalidated = PublicReleaseManifest.model_validate(withdrawn.model_dump(mode="json"))
    assert revalidated.withdrawal is not None
    assert revalidated.withdrawal.issued_manifest_digest == issued.digest()


def test_tampered_withdrawal_digest_is_rejected() -> None:
    issued = _manifest()
    payload = issued.model_dump(mode="json")
    payload["state"] = "withdrawn"
    payload["withdrawal"] = WithdrawalRecord(
        issued_manifest_digest="e" * 64,
        reason="anything",
        withdrawn_at="2026-09-10T08:00:00Z",
    ).model_dump(mode="json")
    with pytest.raises(ValidationError, match="exactly as issued"):
        PublicReleaseManifest.model_validate(payload)


def test_withdrawal_record_is_bound_to_the_withdrawn_state() -> None:
    issued = _manifest()
    payload = issued.model_dump(mode="json")
    payload["withdrawal"] = WithdrawalRecord(
        issued_manifest_digest=issued.digest(),
        reason="not withdrawn yet",
        withdrawn_at="2026-09-10T08:00:00Z",
    ).model_dump(mode="json")
    with pytest.raises(ValidationError, match="withdrawal evidence"):
        PublicReleaseManifest.model_validate(payload)


def test_supersedes_must_reference_same_public_dataset() -> None:
    with pytest.raises(ValidationError, match="same public dataset"):
        _manifest(
            release_version="2.0",
            supersedes=SupersedesRecord(
                release_public_id="ds-otherdataset1",
                release_version="1.0",
                manifest_digest="a" * 64,
            ),
            issued_at="2026-09-16T08:00:00Z",
        )


# --- readiness classification -------------------------------------------------


def test_ready_manifest_blocks_on_nothing() -> None:
    verdict = release_readiness(_manifest())
    assert verdict.ready
    assert verdict.blocking == ()
    assert verdict.manifest_digest == _manifest().digest()


@pytest.mark.parametrize(
    ("overrides", "expected_block"),
    [
        pytest.param(
            {"reviews": (_reviews()[1],)},
            "disclosure_review_missing",
            id="no-disclosure",
        ),
        pytest.param({"reviews": (_reviews()[0],)}, "license_review_missing", id="no-license"),
        pytest.param(
            {
                "reviews": (
                    ReviewEvidence(kind="disclosure", status="pending"),
                    _reviews()[1],
                )
            },
            "disclosure_review_not_approved",
            id="disclosure-pending",
        ),  # noqa: E501
        pytest.param(
            {
                "state": "draft",
                "issued_at": None,
                "population": PopulationRecord(mode="snapshot_rows", row_count=1_200),
            },
            "population_digest_missing",
            id="no-population-digest",
        ),
    ],
)
def test_unauthorized_manifests_report_deterministic_blocks(
    overrides: dict[str, object], expected_block: str
) -> None:
    verdict = release_readiness(_manifest(**overrides))
    assert not verdict.ready
    assert expected_block in verdict.blocking


# --- private ledger binding ---------------------------------------------------


def test_internal_ledger_binds_to_exact_manifest_digest() -> None:
    manifest = _manifest()
    assert bind_internal_ledger(_ledger(manifest), manifest).manifest_digest == manifest.digest()
    tampered_ledger = _ledger(manifest).model_copy(update={"manifest_digest": "0" * 64})
    with pytest.raises(PublicReleaseError) as mismatch:
        bind_internal_ledger(tampered_ledger, manifest)
    assert mismatch.value.code == PublicReleaseError.LEDGER_MISMATCH


def test_internal_ledger_repr_hides_lineage() -> None:
    ledger = _ledger(_manifest())
    assert _INTERNAL_SOURCE_REF not in repr(ledger)


# --- coverage sanity ----------------------------------------------------------


def test_coverage_window_must_be_ordered() -> None:
    with pytest.raises(ValidationError, match="Coverage end"):
        _manifest(coverage_start="2024-12-31", coverage_end="2024-01-01")


def test_field_names_must_be_unique() -> None:
    base = _manifest()
    with pytest.raises(ValidationError, match="unique"):
        PublicReleaseManifest.model_validate(
            {
                **base.model_dump(mode="json"),
                "fields": [
                    base.fields[0].model_dump(mode="json"),
                    base.fields[0].model_dump(mode="json"),
                ],
            }
        )
