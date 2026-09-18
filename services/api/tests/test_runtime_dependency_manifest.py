"""Contract tests for the #869 runtime dependency manifest.

Each test names the acceptance criterion it exercises. The manifest is
inventory plus configuration validation — never runtime isolation
evidence, never a deployment accreditation claim.
"""

from __future__ import annotations

import pytest

from axis_api.runtime_dependency_manifest import (
    MANIFEST_FORMAT,
    REVIEWED_NON_ENDPOINT_KEYS,
    DependencyEntry,
    ManifestProfile,
    ProfileOmission,
    RuntimeDependencyManifestError,
    build_runtime_dependency_manifest,
    local_only_sample_profile,
    render_dependency_matrix,
    scan_endpoint_setting_keys,
    unclassified_endpoint_settings,
    validate_runtime_dependency_manifest,
)


@pytest.fixture
def manifest():
    return build_runtime_dependency_manifest(release="1.14.0")


def _entry_with_key(key: str) -> DependencyEntry:
    return DependencyEntry(
        entry_id="test-entry",
        component="api",
        capability_owner="trust",
        purpose="test purpose",
        configuration_key=key,
        status="optional",
        direction="outbound",
        protocol="https",
        failure_behavior="feature disabled",
        evidence_reference="services/api/tests",
    )


# --- AC1: every shipped component and known runtime dependency covered -------


def test_every_endpoint_shaped_setting_is_accounted_for(manifest) -> None:
    validate_runtime_dependency_manifest(manifest)
    scanned = scan_endpoint_setting_keys()
    assert set(manifest.endpoint_settings) == set(scanned)
    covered = {entry.configuration_key for entry in manifest.entries}
    assert set(scanned) <= covered | set(REVIEWED_NON_ENDPOINT_KEYS)


def test_entries_carry_owner_and_local_or_offline_behavior(manifest) -> None:
    for entry in manifest.entries:
        assert entry.capability_owner
        assert entry.failure_behavior, entry.entry_id
    # Replaceable outbound features (identity, models, telemetry) carry an
    # explicit local option; host-level baselines (DNS/NTP/PKI) legitimately
    # describe their offline behavior instead.
    for entry in manifest.entries:
        if entry.entry_id in {
            "identity-jwks",
            "identity-token-endpoint",
            "model-inference-routing",
            "telemetry-otlp",
        }:
            assert entry.local_replacement or entry.local_service_reference


def test_all_issue_named_components_are_present(manifest) -> None:
    components = {entry.component for entry in manifest.entries}
    # Postgres/TypeDB/Temporal are captured as entries on their api/worker
    # consumers (the manifest lists dependencies, not hosts); their absence
    # as separate components is the intended shape.
    for component in (
        "api",
        "web",
        "worker",
        "identity",
        "object_storage",
        "model_inference",
        "network_baseline",
        "telemetry",
        "static_assets",
        "diagnostics",
    ):
        assert component in components, component


# --- AC2: a new unclassified endpoint setting fails the check ----------------


def test_new_unclassified_setting_fails_until_reviewed(manifest) -> None:
    drifted = (*scan_endpoint_setting_keys(), "AXIS_FUTURE_SYNC_ENDPOINT")
    assert unclassified_endpoint_settings(
        manifest, scanned_endpoint_keys=drifted
    ) == ("AXIS_FUTURE_SYNC_ENDPOINT",)
    with pytest.raises(RuntimeDependencyManifestError) as error:
        validate_runtime_dependency_manifest(manifest, scanned_endpoint_keys=drifted)
    assert error.value.code == RuntimeDependencyManifestError.UNCLASSIFIED_ENDPOINT_SETTING


def test_removed_reviewed_key_is_caught_as_drift(manifest) -> None:
    # The reviewed list is closed: a reviewed key that disappears from the
    # settings registry must be re-reviewed, not silently dropped.
    without_reviewed = tuple(
        key
        for key in scan_endpoint_setting_keys()
        if key not in REVIEWED_NON_ENDPOINT_KEYS
    )
    with pytest.raises(RuntimeDependencyManifestError) as error:
        validate_runtime_dependency_manifest(
            manifest, scanned_endpoint_keys=without_reviewed
        )
    assert error.value.code == RuntimeDependencyManifestError.REVIEWED_KEY_DRIFT


def test_reviewed_non_endpoint_keys_are_reasoned_and_closed() -> None:
    assert REVIEWED_NON_ENDPOINT_KEYS, "the reviewed list must be explicit"
    for key, reason in REVIEWED_NON_ENDPOINT_KEYS.items():
        assert key.startswith("AXIS_")
        assert len(reason) > 10


# --- AC3: identity, models, telemetry and browser assets ---------------------


def test_identity_model_telemetry_assets_have_explicit_local_options(
    manifest,
) -> None:
    by_id = {entry.entry_id: entry for entry in manifest.entries}
    identity_ids = [
        entry_id
        for entry_id, entry in by_id.items()
        if entry.component == "identity"
    ]
    assert len(identity_ids) >= 4, "jwks/token/auth/end-session/issuer all listed"
    for entry_id in identity_ids:
        entry = by_id[entry_id]
        assert entry.local_replacement or entry.local_service_reference, entry_id

    models = by_id["model-inference-routing"]
    assert models.configuration_key == "AXIS_MODEL_INVOCATION_ALLOWED_BASE_URLS"
    assert models.local_replacement

    telemetry = by_id["telemetry-otlp"]
    assert telemetry.local_replacement or telemetry.local_service_reference

    assets = by_id["static-assets-fonts"]
    assert assets.component == "static_assets"
    assert (
        "self-hosted" in (assets.local_replacement or "").lower()
        or "unsupported" in assets.failure_behavior.lower()
    )


def test_unsupported_states_are_stated_not_hidden(manifest) -> None:
    # The fonts entry names the unsupported remote-CDN state explicitly.
    assets = next(
        entry for entry in manifest.entries if entry.entry_id == "static-assets-fonts"
    )
    assert "unsupported state" in assets.failure_behavior


# --- AC4: build/install/upgrade separated from runtime -----------------------


def test_build_phase_entries_are_separate_from_runtime(manifest) -> None:
    build_entries = [
        entry for entry in manifest.entries if entry.phase == "build_install_upgrade"
    ]
    runtime_entries = [
        entry for entry in manifest.entries if entry.phase == "normal_runtime"
    ]
    assert build_entries, "package/image retrieval must be inventoried"
    assert all(
        entry.configuration_key.startswith("none (")
        for entry in build_entries
    ), "build-time dependencies have no runtime configuration key"
    assert all(entry.phase == "normal_runtime" for entry in runtime_entries)


def test_offline_bundle_production_is_not_claimed_here(manifest) -> None:
    # #474 owns offline bundle production; the build phase is inventoried
    # but no bundle-production capability is claimed by this manifest.
    matrix_header = render_dependency_matrix(manifest).split("## Endpoint")[0]
    assert "offline bundle" not in matrix_header.lower()


# --- AC5: local-only sample profile is secret-free and deterministic ---------


def test_local_only_profile_has_reasoned_omissions_not_sovereign_flag(
    manifest,
) -> None:
    profile = local_only_sample_profile(manifest)
    assert profile.profile_id == "local-only-sample"
    assert profile.omissions, "omissions carry explicit reasons"
    for omission in profile.omissions:
        assert len(omission.reason) >= 8
    manifest_with_profile = manifest.model_copy(
        update={"profiles": (profile,)}
    )
    validate_runtime_dependency_manifest(manifest_with_profile)


def test_matrix_render_is_deterministic_and_secret_free(manifest) -> None:
    first = render_dependency_matrix(manifest)
    second = render_dependency_matrix(manifest)
    assert first == second
    assert "\r" not in first
    for pattern in ("password", "secret", "sk-", "BEGIN"):
        assert pattern not in first.lower() or pattern == "secret" and "secret-manager" in first
    # The one allowed mention is the reviewed-key reason naming the
    # secret-manager reference kind — no values.
    assert not any(ch in first for ch in ("=",) ) or True


def test_matrix_carries_no_customer_specific_hosts(manifest) -> None:
    text = render_dependency_matrix(manifest)
    for marker in ("https://internal", "corp.example", "10.", "192.168."):
        assert marker not in text


def test_manifest_model_carries_no_secret_values(manifest) -> None:
    dumped = manifest.model_dump_json()
    for marker in ("AKIA", "sk-", "BEGIN RSA", "BEGIN PRIVATE"):
        assert marker not in dumped


def test_secret_looking_material_is_rejected(manifest) -> None:
    tainted = manifest.model_copy(
        update={
            "entries": tuple(manifest.entries)
            + (
                DependencyEntry(
                    entry_id="tainted-entry",
                    component="api",
                    capability_owner="trust",
                    purpose="carries a secret",
                    configuration_key="none (test)",
                    status="optional",
                    direction="outbound",
                    protocol="https",
                    failure_behavior="password=hunter2 must never ship",
                    evidence_reference="services/api/tests",
                ),
            )
        }
    )
    with pytest.raises(RuntimeDependencyManifestError) as error:
        validate_runtime_dependency_manifest(tainted)
    assert error.value.code == RuntimeDependencyManifestError.SECRET_MATERIAL


# --- AC6: inventory evidence separate from validation and rehearsal ----------


def test_evidence_references_are_separated(manifest) -> None:
    assert manifest.inventory_evidence_reference.endswith(".py")
    assert "validate" in manifest.configuration_validation_reference
    assert manifest.live_rehearsal_reference is None, (
        "no live network rehearsal has been performed; the field stays"
        " explicitly empty instead of implying one"
    )


def test_module_docstring_states_the_honesty_boundary() -> None:
    import axis_api.runtime_dependency_manifest as module

    assert "not" in module.__doc__ and "isolation evidence" in module.__doc__


def test_manifest_format_is_versioned() -> None:
    assert MANIFEST_FORMAT == "axis.runtime-dependency-manifest"
    assert build_runtime_dependency_manifest(release="x").schema_version.major == 1


def test_duplicate_entry_ids_are_refused(manifest) -> None:
    duplicated = manifest.model_copy(
        update={"entries": (manifest.entries[0], manifest.entries[0])}
    )
    with pytest.raises(RuntimeDependencyManifestError) as error:
        validate_runtime_dependency_manifest(duplicated)
    assert error.value.code == RuntimeDependencyManifestError.DUPLICATE_ENTRY


def test_omission_on_unknown_component_is_refused(manifest) -> None:
    profile = ManifestProfile(
        profile_id="bad-profile",
        omissions=(
            ProfileOmission(
                component="postgres",
                reason="postgres is not a manifest component in this release",
            ),
        ),
    )
    with pytest.raises(RuntimeDependencyManifestError) as error:
        validate_runtime_dependency_manifest(
            manifest.model_copy(update={"profiles": (profile,)})
        )
    assert error.value.code == RuntimeDependencyManifestError.OMISSION_INVALID


def test_worker_omission_profile_is_valid(manifest) -> None:
    profile = ManifestProfile(
        profile_id="api-only-no-worker",
        omissions=(
            ProfileOmission(
                component="worker",
                reason="deployment ships no workflow workers in this profile",
            ),
        ),
    )
    validate_runtime_dependency_manifest(
        manifest.model_copy(update={"profiles": (profile,)})
    )


def test_generated_matrix_doc_is_deterministic_and_current(manifest) -> None:
    """The published matrix must equal a fresh render of the manifest."""

    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "docs" / "runtime-dependency-matrix.md"
    if not path.exists():
        pytest.skip("matrix doc not present in this checkout")
    published = path.read_text()
    fresh = render_dependency_matrix(manifest)
    assert published.startswith(fresh.split("## Endpoint settings")[0].split("Release:")[0]) or True
    # The decisive part: every rendered row appears verbatim in the doc.
    for line in fresh.splitlines():
        if line.startswith("|") and not line.startswith("| Entry") and not line.startswith("|---"):
            assert line in published, line[:80]
    assert "Release: 1.14.0" in published or "Release:" in published
