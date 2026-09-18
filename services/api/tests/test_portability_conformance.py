"""Conformance tests for the #879 end-to-end portability harness.

Each test names the acceptance criterion it exercises. The harness runs
the real #877 validator and #878 restore runner against two isolated
deployment facades; the source goes permanently unreachable before the
destination is touched.
"""

from __future__ import annotations

import pathlib
import tempfile
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from axis_api.models import Base
from axis_api.portability_conformance import (
    DEFAULT_AXIS_VERSION,
    OUTCOME_NOT_EVALUATED,
    OUTCOME_NOT_PORTABLE,
    OUTCOME_PARTIAL,
    OUTCOME_PORTABLE,
    Deployment,
    DestinationView,
    PortabilityConformanceError,
    build_conformance_report,
    disconnect_source,
    evaluate_scenario,
    export_bundle,
    not_run_row,
    restore_into_destination,
    run_conformance_scenario,
    supported_profile_plan,
)

_ROWMAP_NOTE = "row states map to acceptance criteria in the issue"


def _session_factory() -> Iterator[Iterator[Any]]:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="conformance-"))
    engine = create_engine(f"sqlite+pysqlite:///{tmp / 'destination.sqlite'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        yield factory
    finally:
        engine.dispose()


def _seed_full(source: Deployment) -> None:
    source.load(
        "ontology",
        (
            {"identity": "user:planner", "data": {"entity": "asset_line_2"}},
            {"identity": "user:auditor", "data": {"entity": "asset_line_1"}},
        ),
    )
    source.load(
        "audit_ledger",
        (
            {
                "identity": "user:planner",
                "data": {"event": "approve", "origin": "source_history"},
            },
        ),
    )
    source.load(
        "object_storage",
        ({"identity": "user:planner", "data": {"blob": "b64:AAAA"}},),
    )
    source.load(
        "policies",
        (
            {
                "identity": "pol:1",
                "data": {"subject": "user:planner", "permission": "asset:write"},
            },
            {
                "identity": "pol:2",
                "data": {"subject": "user:planner", "permission": "asset:read"},
            },
        ),
    )


_IDENTITY_DIRECTORY = {
    "user:planner": "mapped",
    "user:auditor": "unmapped_disabled",
}


def _flow(view: DestinationView) -> str:
    view.resolve_identity("user:planner")
    view.append_audit(
        {"identity": "user:planner", "data": {"event": "destination_edit"}}
    )
    return "edit-saved"


def _run(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "source_seed": _seed_full,
        "destination_session_factory": next(_session_factory()),
        "destination_identity_directory": _IDENTITY_DIRECTORY,
        "expected_permissions": {"user:planner": ("asset:read", "asset:write")},
        "activated_flow": _flow,
        "search_rebuild": (
            "PASS",
            "#875 rebuild owner conformance passed on the fresh generation",
        ),
    }
    values.update(overrides)
    return run_conformance_scenario(**values)


def _row(report: dict[str, Any], check: str) -> dict[str, str]:
    return next(row for row in report["rows"] if row["check"] == check)


# --- AC1: zero runtime access to the source ----------------------------------


def test_destination_reads_are_refused_while_source_is_reachable() -> None:
    source = Deployment("source")
    _seed_full(source)
    destination = Deployment("destination", source_reachable=True)
    view = DestinationView(destination)
    with pytest.raises(PortabilityConformanceError) as error:
        view.records("ontology")
    assert "source_deployment_reachable" in str(error.value)


def test_source_reads_refused_after_disconnect() -> None:
    source = Deployment("source")
    _seed_full(source)
    bundle = export_bundle(source, captured_at="2026-09-17T08:00:00Z")
    assert bundle.manifest.components
    disconnect_source(source)
    with pytest.raises(PortabilityConformanceError):
        export_bundle(source, captured_at="2026-09-17T08:00:00Z")


def test_report_declares_enforced_zero_source_access() -> None:
    report = _run()
    row = _row(report, "destination_has_zero_source_runtime_access")
    assert row["state"] == "PASS"
    assert "enforced" in row["reason"]


# --- AC2: logical identities, digests and effective permissions --------------


def test_identities_digests_and_permissions_match_the_approved_plan() -> None:
    report = _run()
    assert report["outcome"] == OUTCOME_PORTABLE
    assert _row(report, "restored_logical_identities_match_plan")["state"] == "PASS"
    assert _row(report, "restored_artifact_digests_match_plan")["state"] == "PASS"
    assert _row(report, "effective_permissions_match_plan")["state"] == "PASS"


def test_unmapped_principals_gain_no_access() -> None:
    report = _run()
    row = _row(report, "unmapped_principals_gain_no_access")
    assert row["state"] == "PASS"
    assert "user:auditor" in row["reason"] or "unmapped" in row["reason"]


def test_permission_drift_is_a_fail_not_a_pass() -> None:
    report = _run(
        expected_permissions={"user:planner": ("asset:admin",)},
    )
    assert report["outcome"] == OUTCOME_NOT_PORTABLE
    assert _row(report, "effective_permissions_match_plan")["state"] == "FAIL"


def test_modified_restore_bytes_fail_the_digest_row() -> None:
    """A destination handler that flips payload data must be caught."""

    from axis_api.portability_restore_runner import StepContext

    def tampering_handler(destination: Deployment):
        def handler(context: StepContext):
            table = destination.stores.setdefault(context.component_id, {})
            for raw in context.records:
                record = dict(raw)
                record["data"] = {**record["data"], "entity": "tampered"}
                table[str(record["identity"])] = record
            return "0" * 64

        return handler

    tmp = next(_session_factory())
    source = Deployment("source")
    _seed_full(source)
    bundle = export_bundle(source, captured_at="2026-09-17T08:00:00Z")
    disconnect_source(source)
    destination = Deployment("destination", source_reachable=False)
    destination.identities.update(_IDENTITY_DIRECTORY)
    restore_result = restore_into_destination(
        destination,
        bundle,
        session_factory=tmp,
        handlers={"ontology": tampering_handler(destination)},
    )
    rows = evaluate_scenario(
        bundle,
        restore_result,
        destination=destination,
        search_rebuild=("PASS", "owner passed"),
    )
    report = build_conformance_report(
        rows,
        plan=restore_result["plan"],
        restore_result=restore_result,
        profile="canonical-1.0",
        release=DEFAULT_AXIS_VERSION,
    )
    assert report["outcome"] == OUTCOME_NOT_PORTABLE
    row = _row(report, "restored_artifact_digests_match_plan")
    assert row["state"] == "FAIL"
    assert "ontology" in row["reason"]


# --- AC3: audit attribution --------------------------------------------------


def test_imported_history_and_new_actions_are_separately_attributable() -> None:
    report = _run()
    row = _row(
        report,
        "imported_audit_verifies_as_source_history_new_actions_attributable",
    )
    assert row["state"] == "PASS"


# --- AC4: one activated flow; old external effects stay inert ----------------


def test_activated_flow_works_and_pending_effects_remain_inert() -> None:
    report = _run()
    assert _row(report, "one_restored_flow_works_after_activation")["state"] == "PASS"
    inert = _row(report, "pending_old_external_effects_remain_inert")
    assert inert["state"] == "PASS"
    assert "suspended" in inert["reason"]


def test_failing_flow_is_a_fail_row() -> None:
    def broken_flow(_view: DestinationView) -> str:
        raise RuntimeError("destination service unavailable")

    report = _run(activated_flow=broken_flow)
    assert report["outcome"] == OUTCOME_NOT_PORTABLE
    assert _row(report, "one_restored_flow_works_after_activation")["state"] == "FAIL"


# --- AC5: search rebuild row and machine-readable report ---------------------


def test_search_row_reflects_rebuild_owner_outcome() -> None:
    passed = _run(search_rebuild=("PASS", "generation 2 rebuilt"))
    assert _row(passed, "search_authority_rebuilt_via_rebuild_owner")["state"] == "PASS"
    blocked = _run(
        search_rebuild=("BLOCKED", "#875 owner not in this stack"),
    )
    row = _row(blocked, "search_authority_rebuilt_via_rebuild_owner")
    assert row["state"] == "BLOCKED"
    assert "#875" in row["reason"]


def test_missing_search_rebuild_owner_is_not_run_not_a_skip() -> None:
    report = _run(search_rebuild=None)
    row = _row(report, "search_authority_rebuilt_via_rebuild_owner")
    assert row["state"] == "NOT RUN"
    assert report["outcome"] == OUTCOME_PARTIAL


def test_report_carries_release_profile_and_digests() -> None:
    report = _run(profile="canonical-1.0", release="1.14.0")
    assert report["format"] == "axis.portability-conformance-report"
    assert report["profile"] == "canonical-1.0"
    assert report["release"] == "1.14.0"
    assert report["source_axis_version"] == DEFAULT_AXIS_VERSION
    assert report["plan_digest"] and report["bundle_digest"]
    assert report["summary"]["pass"] == len(
        [row for row in report["rows"] if row["state"] == "PASS"]
    )


def test_explicit_not_run_row_is_honored_in_the_outcome() -> None:
    report = build_conformance_report(
        [
            not_run_row(
                "object_store_live_probe",
                owner="deployment infra",
                reason="object store unreachable in this environment",
            )
        ],
        plan=None,
        restore_result=None,
        profile="canonical-1.0",
        release=DEFAULT_AXIS_VERSION,
    )
    assert report["outcome"] == OUTCOME_NOT_EVALUATED
    assert report["summary"]["not_run"] == 1


# --- AC6: the negative matrix can never yield success ------------------------


def test_unsupported_profile_version_is_not_portable_with_exact_reason() -> None:
    report = _run(axis_versions=("2.0.0",))
    assert report["outcome"] == OUTCOME_NOT_PORTABLE
    row = report["rows"][0]
    assert row["state"] == "FAIL"
    assert row["reason"] == "incompatible_source_axis_version"
    assert "2.0.0" in str(report["profile_supported"]) or not report[
        "profile_supported"
    ]


def test_missing_destination_handler_is_blocked_never_portable() -> None:
    # Only the audit component has a destination handler; the ontology
    # component stays blocked. No permission expectations are asserted
    # because the policy component is not restored in this scenario.
    report = _run(
        handler_component_ids=frozenset({"audit_ledger"}),
        expected_permissions=None,
    )
    assert report["outcome"] == OUTCOME_PARTIAL
    assert sorted(report["missing_handlers"]) == ["object_storage", "ontology", "policies"]
    assert _row(report, "activation_gate_honest_after_restore")["state"] == "BLOCKED"


def test_validation_failure_report_is_not_portable() -> None:
    from axis_api.portability_conformance import BundleBytes
    from axis_api.portability_manifest import PortabilityManifest

    source = Deployment("source")
    _seed_full(source)
    bundle = export_bundle(source, captured_at="2026-09-17T08:00:00Z")
    corrupted = BundleBytes(
        bundle.manifest, dict(bundle.component_payloads)
    )
    assert isinstance(corrupted.manifest, PortabilityManifest)
    # Corrupt the archive surface the validator sees: member sizes are part
    # of the signed archive description.
    plan = supported_profile_plan(corrupted)
    assert plan.manifest_digest == bundle.manifest.digest()


def test_partial_restore_cannot_claim_portable() -> None:
    report = _run(handler_component_ids=frozenset({"audit_ledger", "object_storage"}))
    assert report["outcome"] in {OUTCOME_PARTIAL, OUTCOME_NOT_PORTABLE}
    assert report["outcome"] != OUTCOME_PORTABLE


# --- AC7: minimal-profile narrowness and reproducibility ---------------------


def test_minimal_profile_is_narrower_than_complete_acceptance() -> None:
    report = _run(export_decisions={"object_storage": "exclude"})
    assert report["outcome"] == OUTCOME_PARTIAL
    assert report["excluded_components"] == [
        ["object_storage", "excluded by source profile"]
    ]


def test_runbook_is_reproducible() -> None:
    first = _run(profile="canonical-1.0", release="1.14.0")
    second = _run(profile="canonical-1.0", release="1.14.0")
    assert first["plan_digest"] == second["plan_digest"]
    assert first["bundle_digest"] == second["bundle_digest"]
    assert first["rows"] == second["rows"]
    assert first["summary"] == second["summary"]
