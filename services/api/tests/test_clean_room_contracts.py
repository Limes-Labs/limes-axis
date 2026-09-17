"""Contract tests for the #855 clean-room agreement contracts."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from axis_api.clean_room_contracts import (
    AgreementRevision,
    CleanRoomError,
    InputClass,
    IsolationProfile,
    ManifestVersion,
    OutputClass,
    Party,
    PartyApproval,
    PurposeScope,
    activate_agreement,
    agreement_readiness,
    amend_agreement,
    authorizes_execution,
    canonical_clean_room_digest,
    input_classes_after_removal,
    parse_clean_room_agreement,
    remove_party,
    suspend_agreement,
    terminate_agreement,
)

_HOST = "acme"


def _parties() -> tuple[Party, ...]:
    return (
        Party(
            party_id="party-acme",
            organization="acme",
            domain="acme.example.com",
            roles=("administrator", "result_reviewer"),
            owner_contact="ops@acme.example.com",
        ),
        Party(
            party_id="party-globex",
            organization="globex",
            domain="globex.example.com",
            roles=("data_contributor", "analyst"),
            owner_contact="data@globex.example.com",
            contributes_inputs=True,
        ),
        Party(
            party_id="party-initech",
            organization="initech",
            domain="initech.example.com",
            roles=("data_contributor",),
            owner_contact="data@initech.example.com",
            contributes_inputs=True,
        ),
    )


def _approval(party_id: str, organization: str, at: str = "2026-09-01T10:00:00Z") -> PartyApproval:
    return PartyApproval(
        party_id=party_id,
        decided_by_organization=organization,
        decided_at=at,
        authority_ref=f"{organization}/board/2026-clean-room",
    )


def _isolation() -> IsolationProfile:
    return IsolationProfile(
        compute="confidential_compute",
        egress="aggregated_only",
        tenant_boundary_refs=("tenants/acme", "tenants/globex"),
        retention_days=90,
        requires_confidential_compute=True,
    )


def _agreement(**overrides: object) -> AgreementRevision:
    values: dict[str, object] = {
        "schema_version": ManifestVersion(major=1, minor=0),
        "agreement_id": "cr-quality-bench",
        "revision": "1",
        "title": "Cross-org quality benchmarking",
        "host_organization": _HOST,
        "parties": _parties(),
        "purpose": PurposeScope(
            intents=("benchmark OEE across member plants",),
            prohibited_uses=("individual performance evaluation",),
            statement="Aggregate quality benchmarking between the member organizations.",
        ),
        "input_classes": (
            InputClass(
                class_id="ic-oee",
                data_class="classes.oee-timeseries",
                handling_ref="policy/purpose/perf-benchmark",
                contributing_parties=("party-globex", "party-initech"),
            ),
        ),
        "output_classes": (
            OutputClass(class_id="oc-bench", shape="aggregate", reviewer_role="result_reviewer"),
        ),
        "isolation": _isolation(),
        "valid_from": "2026-09-01",
        "valid_until": "2027-08-31",
        "governance_refs": ("legal/dpa-2026-11",),
        "state": "under_review",
    }
    values.update(overrides)
    return AgreementRevision.model_validate(values)


def _fully_approved() -> AgreementRevision:
    """Each organization signs for its own party (independent owner approval)."""

    return _agreement(
        approvals=(
            _approval("party-acme", "acme"),
            _approval("party-globex", "globex"),
            _approval("party-initech", "initech"),
        )
    )


# --- AC: schema definition and two-party independent approval -----------------


def test_agreement_requires_two_independent_approvals_before_activation() -> None:
    _, ready, blocking = agreement_readiness(_agreement())
    assert not ready
    assert any(code.startswith("approvals_missing:") for code in blocking)
    activated = activate_agreement(_fully_approved(), now="2026-09-02T08:00:00Z")
    assert activated.state == "approved_current" and activated.activated_at is not None


def test_activation_without_all_approvals_refuses() -> None:
    with pytest.raises(CleanRoomError) as blocked:
        activate_agreement(_agreement(approvals=(_approval("party-acme", "acme"),)), now="x")
    assert blocked.value.code == CleanRoomError.NOT_EXECUTABLE


def test_readiness_surfaces_exact_gaps() -> None:
    bare = _agreement(input_classes=(), governance_refs=(), approvals=())
    digest, ready, blocking = agreement_readiness(bare)
    assert digest == bare.digest()
    assert not ready
    assert "input_classes_undeclared" in blocking
    assert "governance_references_recorded" in blocking
    assert "confidential_compute_attestation_required" in blocking


# --- approval independence: self-approval and forging unrepresentable ---------


def test_authority_ref_must_match_the_signing_organization() -> None:
    with pytest.raises(ValidationError, match="approval_not_by_party_owner"):
        PartyApproval(
            party_id="party-globex",
            decided_by_organization="initech",
            decided_at="2026-09-01T10:00:00Z",
            authority_ref="globex/board/2026",
        )


def test_forged_other_party_approval_is_rejected() -> None:
    with pytest.raises(ValidationError, match="approval_not_by_party_owner"):
        _agreement(
            approvals=(
                _approval("party-globex", "initech"),
            )
        )


def test_duplicate_party_approvals_are_rejected() -> None:
    with pytest.raises(ValidationError, match="at most once"):
        _agreement(
            approvals=(
                _approval("party-acme", "acme"),
                _approval("party-acme", "acme"),
            )
        )


def test_unknown_party_approval_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown_clean_room_party"):
        _agreement(approvals=(_approval("party-ghost", "acme"),))


# --- AC: purpose/input/output classes plus isolation profile ------------------


def test_purpose_and_classes_are_typed_enforcement_inputs() -> None:
    agreement = _agreement()
    assert agreement.purpose.intents[0].startswith("benchmark")
    assert agreement.input_classes[0].handling_ref == "policy/purpose/perf-benchmark"
    assert agreement.output_classes[0].shape == "aggregate"
    assert agreement.isolation.compute == "confidential_compute"


def test_administrator_cannot_contribute_inputs() -> None:
    with pytest.raises(ValidationError, match="do not automatically"):
        Party(
            party_id="party-acme",
            organization="acme",
            domain="acme.example.com",
            roles=("administrator",),
            owner_contact="ops@acme.example.com",
            contributes_inputs=True,
        )


def test_input_class_must_name_existing_contributors() -> None:
    with pytest.raises(ValidationError, match="unknown_clean_room_party"):
        _agreement(
            input_classes=(
                InputClass(
                    class_id="ic-ghost",
                    data_class="classes.secret",
                    handling_ref="policy/purpose/x",
                    contributing_parties=("party-ghost",),
                ),
            )
        )


# --- AC: material amendment invalidates prior approvals -----------------------


def test_amendment_creates_new_revision_with_empty_approvals() -> None:
    approved = _fully_approved()
    amended = amend_agreement(
        approved,
        {
            "purpose": PurposeScope(
                intents=("benchmark OEE and energy use",),
                prohibited_uses=(),
                statement="Widened benchmarking purpose.",
            )
        },
        kind="purpose",
    )
    assert amended.revision == "2"
    assert amended.state == "draft"
    assert amended.approvals == ()
    assert amended.activated_at is None
    # The old revision is untouched: prior approvals bind to revision 1 only.
    assert approved.revision == "1" and approved.approvals != ()


def test_non_material_change_is_refused_as_amendment() -> None:
    with pytest.raises(ValueError, match="material term"):
        amend_agreement(_fully_approved(), {"title": "Renamed"}, kind="purpose")


def test_isolation_amendment_kind_is_distinct() -> None:
    amended = amend_agreement(
        _fully_approved(),
        {"isolation": _isolation().model_copy(update={"retention_days": 30})},
        kind="retention",
    )
    assert amended.isolation.retention_days == 30
    assert amended.approvals == ()


# --- AC: suspension/expiry block execution authoritatively ---------------------


def test_suspension_blocks_execution_regardless_of_sessions() -> None:
    activated = activate_agreement(_fully_approved(), now="2026-09-02T08:00:00Z")
    assert authorizes_execution(activated, on_date="2026-09-10")
    suspended = suspend_agreement(activated, now="2026-09-11T08:00:00Z")
    assert suspended.state == "suspended" and suspended.suspended_at is not None
    assert not authorizes_execution(suspended, on_date="2026-09-12")


def test_expiry_blocks_execution_even_when_state_is_current() -> None:
    activated = activate_agreement(_fully_approved(), now="2026-09-02T08:00:00Z")
    assert not authorizes_execution(activated, on_date="2027-09-01")


def test_termination_keeps_suspension_timestamp_or_stamps_it() -> None:
    activated = activate_agreement(_fully_approved(), now="2026-09-02T08:00:00Z")
    terminated = terminate_agreement(activated, now="2026-09-20T08:00:00Z")
    assert terminated.state == "terminated"
    assert terminated.terminated_at == "2026-09-20T08:00:00Z"
    assert terminated.suspended_at == "2026-09-20T08:00:00Z"


# --- AC: party removal preserves history, blocks future inputs -----------------


def test_party_removal_amends_and_cites_historical_digest() -> None:
    activated = activate_agreement(_fully_approved(), now="2026-09-02T08:00:00Z")
    historical_digest = activated.digest()
    amended, cited = remove_party(activated, "party-initech")
    assert cited == historical_digest
    assert {party.party_id for party in amended.parties} == {"party-acme", "party-globex"}
    assert amended.approvals == () and amended.revision == "2"


def test_removed_party_inputs_become_unusable() -> None:
    activated = activate_agreement(_fully_approved(), now="2026-09-02T08:00:00Z")
    amended, _ = remove_party(activated, "party-globex")
    # The amended revision names no input contributed by the removed party;
    # the shared class survives with the remaining contributor only.
    assert all(
        "party-globex" not in input_class.contributing_parties
        for input_class in amended.input_classes
    )
    assert amended.input_classes[0].contributing_parties == ("party-initech",)
    # Removing the other contributor makes the class unusable too.
    assert input_classes_after_removal(amended, "party-initech") == ()


def test_removal_never_drops_below_two_parties() -> None:
    two_party = _agreement(
        parties=_parties()[:2],
        input_classes=(
            InputClass(
                class_id="ic-oee",
                data_class="classes.oee-timeseries",
                handling_ref="policy/purpose/perf-benchmark",
                contributing_parties=("party-globex",),
            ),
        ),
    )
    with pytest.raises(ValueError, match="at least two parties"):
        remove_party(two_party, "party-globex")


# --- attack matrix -------------------------------------------------------------


def test_guest_membership_does_not_substitute_domain_approval() -> None:
    # A guest vendor organization is not a party of the agreement, so its
    # signature cannot stand for any party's approval.
    with pytest.raises(ValidationError, match="approval_not_by_party_owner"):
        _agreement(
            approvals=(
                PartyApproval(
                    party_id="party-globex",
                    decided_by_organization="guest-vendor",
                    decided_at="2026-09-01T10:00:00Z",
                    authority_ref="guest-vendor/board/2026",
                ),
            )
        )


def test_host_must_be_a_party() -> None:
    outsiders = (
        Party(
            party_id="party-globex",
            organization="globex",
            domain="globex.example.com",
            roles=("data_contributor",),
            owner_contact="data@globex.example.com",
            contributes_inputs=True,
        ),
        _parties()[2],
    )
    with pytest.raises(ValidationError, match="host must itself be a party"):
        _agreement(host_organization="acme", parties=outsiders)


def test_validity_window_must_be_ordered() -> None:
    with pytest.raises(ValidationError):
        _agreement(valid_from="2027-08-31", valid_until="2026-09-01")


def test_confidential_requirement_must_match_compute_mode() -> None:
    with pytest.raises(ValidationError):
        IsolationProfile(
            compute="isolated_job",
            egress="review_gate",
            tenant_boundary_refs=("tenants/acme",),
            retention_days=30,
            requires_confidential_compute=True,
        )


def test_duplicate_parties_are_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicate_clean_room_party"):
        _agreement(parties=_parties()[:2] + _parties()[:1])


def test_federated_query_with_no_egress_is_contradictory() -> None:
    with pytest.raises(ValidationError, match="at least aggregated egress"):
        IsolationProfile(
            compute="federated_query",
            egress="none",
            tenant_boundary_refs=("tenants/acme",),
            retention_days=30,
        )


# --- round-trip, digests and untrusted parsing ---------------------------------


def test_round_trip_is_byte_stable_and_deterministic() -> None:
    agreement = _fully_approved()
    parsed = parse_clean_room_agreement(json.loads(agreement.model_dump_json()))
    assert parsed == agreement
    assert parsed.digest() == agreement.digest()


def test_digest_is_order_insensitive_and_tamper_evident() -> None:
    agreement = _agreement()
    raw = json.loads(agreement.model_dump_json())
    reordered = dict(reversed(list(raw.items())))
    assert canonical_clean_room_digest(raw) == canonical_clean_room_digest(reordered)
    tampered = dict(raw)
    tampered["valid_until"] = "2099-12-31"
    assert canonical_clean_room_digest(tampered) != agreement.digest()


def test_parse_rejects_future_major_with_dedicated_code() -> None:
    raw = json.loads(_agreement().model_dump_json())
    raw["schema_version"] = {"major": 2, "minor": 0}
    with pytest.raises(CleanRoomError) as blocked:
        parse_clean_room_agreement(raw)
    assert blocked.value.code == CleanRoomError.INCOMPATIBLE_VERSION


def test_parse_reports_malformed_payload_with_safe_code() -> None:
    with pytest.raises(CleanRoomError) as blocked:
        parse_clean_room_agreement("not-an-agreement")
    assert blocked.value.code == CleanRoomError.INVALID_AGREEMENT
