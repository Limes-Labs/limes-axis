"""Contract tests for the #876 restore-capable portability manifest profile."""

import json

import pytest
from pydantic import ValidationError

from axis_api.portability_manifest import (
    ComponentInventory,
    ConsistencyPoint,
    PortabilityManifest,
    PortabilityManifestError,
    PortabilityReview,
    RebindingReference,
    RestoreSafetyPolicy,
    StoreWatermark,
    canonical_portability_digest,
    parse_portability_manifest,
    review_portability_manifest,
)

DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def component(component_id, **overrides):
    defaults = {
        "component_id": component_id,
        "owner_layer": "data",
        "store": "postgres",
        "consistency": "quiesced_export",
        "decision": "restore",
        "schema_version": {"major": 1, "minor": 0},
        "object_count": 12,
        "content_digest": DIGEST_A,
        "depends_on": (),
        "handler_registered": True,
    }
    return ComponentInventory.model_validate(defaults | overrides)


def consistency_point(**overrides):
    defaults = {
        "mode": "quiesced",
        "captured_at": "2026-09-16T10:00:00+00:00",
        "disclosures": "Export captured during a declared quiesced window.",
        "per_store": [StoreWatermark.model_validate({"store": "postgres", "watermark": "pg/42"})],
    }
    return ConsistencyPoint.model_validate(defaults | overrides)


def rebinding(**overrides):
    defaults = {
        "kind": "credential",
        "reference_id": "lease-credential-1",
        "resolution": "fresh_local_resolution_required",
    }
    return RebindingReference.model_validate(defaults | overrides)


def manifest(**overrides):
    defaults = {
        "schema_version": {"major": 1, "minor": 0},
        "tenant_logical_id": "tenant-demo-manufacturing",
        "source_axis_version": "1.42.0",
        "consistency_point": consistency_point(),
        "components": (component("relational-core"),),
        "rebinding_references": (rebinding(),),
    }
    return PortabilityManifest.model_validate(defaults | overrides)


def to_dict(value) -> dict:
    return json.loads(value.model_dump_json())


# --- Strict round-trips and deterministic digests ---


def test_manifest_round_trips_through_json_with_stable_digest():
    original = manifest()
    parsed = parse_portability_manifest(to_dict(original))
    assert parsed == original
    assert parsed.digest() == original.digest()
    assert canonical_portability_digest(to_dict(parsed)) == original.digest()


def test_digest_is_order_and_whitespace_independent():
    payload = {"b": 1, "a": {"z": 1, "y": 2}}
    reordered = {"a": {"y": 2, "z": 1}, "b": 1}
    assert canonical_portability_digest(payload) == canonical_portability_digest(reordered)


def test_field_order_does_not_change_the_manifest_digest():
    first = manifest()
    reshuffled = PortabilityManifest.model_validate(dict(reversed(list(to_dict(first).items()))))
    assert first.digest() == reshuffled.digest()


# --- Version handling: majors are hard boundaries ---


@pytest.mark.parametrize(
    "version", [{"major": 2, "minor": 0}, {"major": 3, "minor": 1}, {"major": 0, "minor": 9}]
)
def test_incompatible_major_versions_are_rejected_with_a_fixed_code(version):
    payload = to_dict(manifest()) | {"schema_version": version}
    with pytest.raises(PortabilityManifestError) as error:
        parse_portability_manifest(payload)
    assert error.value.code == PortabilityManifestError.INCOMPATIBLE_VERSION


def test_unknown_major_version_is_not_silently_normalized():
    payload = to_dict(manifest()) | {"schema_version": {"major": 2, "minor": 0}}
    with pytest.raises(PortabilityManifestError):
        parse_portability_manifest(payload)
    assert "schema_version" in payload


def test_unknown_fields_are_rejected_at_the_untrusted_boundary():
    payload = to_dict(manifest()) | {"producer_extension": {"anything": True}}
    with pytest.raises(PortabilityManifestError) as error:
        parse_portability_manifest(payload)
    assert error.value.code == PortabilityManifestError.INVALID_MANIFEST


def test_malformed_manifest_yields_only_the_safe_code():
    with pytest.raises(PortabilityManifestError) as error:
        parse_portability_manifest({"format": "axis.tenant-portability-manifest"})
    assert error.value.code == PortabilityManifestError.INVALID_MANIFEST


def test_wrong_format_string_is_rejected():
    payload = to_dict(manifest()) | {"format": "some-other-archive"}
    with pytest.raises(PortabilityManifestError):
        parse_portability_manifest(payload)


# --- Component inventory honesty ---


def test_restore_decision_requires_a_registered_handler_and_digest():
    with pytest.raises(ValidationError):
        component("core", handler_registered=False)
    with pytest.raises(ValidationError):
        component("core", content_digest=None)


def test_excluded_components_carry_no_objects():
    excluded = component(
        "legacy-vertical",
        decision="exclude",
        object_count=0,
        exclusion_reason="No restore handler exists for this component",
        content_digest=None,
    )
    assert excluded.object_count == 0
    assert excluded.exclusion_reason


def test_exclusion_without_reason_is_rejected():
    with pytest.raises(ValidationError):
        component("legacy", decision="exclude", exclusion_reason=None, content_digest=DIGEST_A)


def test_excluded_component_with_exported_objects_is_rejected():
    with pytest.raises(ValidationError):
        component("legacy", decision="exclude", exclusion_reason="no restore handler")


def test_rebuild_decision_only_applies_to_rebuildable_projections():
    with pytest.raises(ValidationError):
        component("search-index", decision="rebuild", consistency="quiesced_export")
    rebuildable = component(
        "search-index", decision="rebuild", consistency="rebuildable_projection"
    )
    assert rebuildable.decision == "rebuild"


def test_duplicate_components_and_duplicate_stores_are_rejected():
    with pytest.raises(ValidationError):
        manifest(components=(component("core"), component("core")))
    with pytest.raises(ValidationError):
        manifest(
            components=(
                component("core", store="postgres"),
                component("objects", store="postgres", content_digest=DIGEST_B),
            )
        )


def test_every_inventoried_store_needs_a_consistency_watermark():
    with pytest.raises(ValidationError):
        manifest(
            components=(
                component("core", store="postgres"),
                component("objects", store="object_storage", content_digest=DIGEST_B),
            )
        )
    covered = manifest(
        components=(
            component("core", store="postgres"),
            component("objects", store="object_storage", content_digest=DIGEST_B),
        ),
        consistency_point=consistency_point(
            per_store=(
                StoreWatermark.model_validate({"store": "postgres", "watermark": "pg/42"}),
                StoreWatermark.model_validate({"store": "object_storage", "watermark": "obj/1"}),
            )
        ),
    )
    assert len(covered.consistency_point.per_store) == 2


def test_duplicate_store_watermarks_are_rejected():
    with pytest.raises(ValidationError):
        consistency_point(
            per_store=(
                StoreWatermark.model_validate({"store": "postgres", "watermark": "pg/42"}),
                StoreWatermark.model_validate({"store": "postgres", "watermark": "pg/43"}),
            )
        )


def test_quiesced_export_cannot_contain_captured_watermark_components():
    with pytest.raises(ValidationError):
        manifest(
            components=(
                component("core", consistency="captured_watermark", store="postgres"),
                component("objects", store="object_storage", content_digest=DIGEST_B),
            ),
            consistency_point=consistency_point(
                per_store=(
                    StoreWatermark.model_validate({"store": "postgres", "watermark": "pg/42"}),
                    StoreWatermark.model_validate(
                        {"store": "object_storage", "watermark": "obj/1"}
                    ),
                )
            ),
        )


# --- Secrets are never portable data ---


def test_secret_material_has_no_field_and_cannot_be_attached():
    payload = to_dict(manifest())
    assert "secrets" not in payload
    payload["secrets"] = {"api_key": "super-secret"}
    with pytest.raises(PortabilityManifestError):
        parse_portability_manifest(payload)


def test_rebinding_references_are_typed_and_never_carry_values():
    reference = rebinding()
    assert reference.model_dump(mode="json") == {
        "kind": "credential",
        "reference_id": "lease-credential-1",
        "resolution": "fresh_local_resolution_required",
        "notes": None,
    }


def test_credential_resolution_defaults_to_fresh_local_required():
    reference = rebinding(resolution="fresh_local_resolution_required")
    assert reference.resolution == "fresh_local_resolution_required"


def test_unsupported_resolution_is_reserved_for_credentials_and_signing_keys():
    with pytest.raises(ValidationError):
        rebinding(
            kind="service_endpoint",
            reference_id="endpoint-1",
            resolution="unsupported",
        )
    with pytest.raises(ValidationError):
        rebinding(
            kind="object_store",
            reference_id="store-1",
            resolution="unsupported",
        )
    blocked_key = rebinding(
        kind="signing_key", reference_id="audit-signing-key", resolution="unsupported"
    )
    assert blocked_key.resolution == "unsupported"


# --- Restore safety: suspension is the default and cannot be flipped ---


def test_restore_safety_defaults_every_operational_class_to_suspended():
    policy = RestoreSafetyPolicy()
    assert policy.pending_actions == "suspended"
    assert policy.pending_deliveries == "suspended"
    assert policy.workflow_schedules == "suspended"
    assert policy.credential_leases == "suspended"


def test_external_effect_auto_replay_is_structurally_impossible():
    with pytest.raises(ValidationError):
        RestoreSafetyPolicy.model_validate({"auto_replay_external_effects": True})


def test_manifest_review_reports_suspended_classes():
    review = review_portability_manifest(manifest())
    assert review.suspended_by_policy == (
        "pending_actions",
        "pending_deliveries",
        "workflow_schedules",
        "credential_leases",
    )


# --- Review classification: incomplete exports cannot claim success ---


def test_fully_supported_manifest_is_portable_with_acknowledgements():
    review = review_portability_manifest(manifest())
    assert review.portable is True
    assert review.blocked_by == ()
    assert review.acknowledgements_required == ()


def test_restore_without_handler_is_a_fabricated_success_and_never_constructs():
    # The contract refuses the inventory outright: a producer cannot emit a
    # "restore" decision for a component with no registered handler, and the
    # reviewer therefore never sees this state as a soft "blocked" case.
    with pytest.raises(ValidationError):
        component("ontology-store", handler_registered=False)


def test_unsupported_rebinding_blocks_portability():
    blocked = manifest(
        rebinding_references=(
            rebinding(),
            rebinding(kind="signing_key", reference_id="audit-key", resolution="unsupported"),
        )
    )
    review = review_portability_manifest(blocked)
    assert review.portable is False
    assert "rebinding_unsupported:audit-key" in review.blocked_by


def test_exclusions_and_rebinds_require_explicit_acknowledgement():
    reviewed = manifest(
        components=(
            component("relational-core", store="postgres"),
            component(
                "legacy-vertical",
                store="object_storage",
                decision="exclude",
                exclusion_reason="Reference vertical pack has no restore handler",
                owner_layer="experience",
                content_digest=None,
                object_count=0,
                handler_registered=False,
            ),
        ),
        consistency_point=consistency_point(
            per_store=(
                StoreWatermark.model_validate({"store": "postgres", "watermark": "pg/42"}),
                StoreWatermark.model_validate({"store": "object_storage", "watermark": "obj/1"}),
            )
        ),
        rebinding_references=(rebinding(resolution="rebind_required"),),
    )
    review = review_portability_manifest(reviewed)
    assert review.portable is True
    assert "excluded:legacy-vertical" in review.acknowledgements_required
    assert "rebind_required:lease-credential-1" in review.acknowledgements_required


def test_unsupported_rebinding_blocks_portability_with_fixed_code():
    blocked = manifest(
        rebinding_references=(
            rebinding(),
            rebinding(kind="signing_key", reference_id="audit-key", resolution="unsupported"),
        )
    )
    review = review_portability_manifest(blocked)
    assert review.portable is False
    assert "rebinding_unsupported:audit-key" in review.blocked_by


def test_captured_watermark_exports_require_an_explicit_consistency_acknowledgement():
    watermarked = manifest(
        consistency_point=consistency_point(
            mode="captured_watermark",
            disclosures="Independent per-store watermarks; not one transactional snapshot.",
        )
    )
    review = review_portability_manifest(watermarked)
    assert "captured_watermark:not_transactionally_consistent" in review.acknowledgements_required


def test_review_is_deterministic():
    first = review_portability_manifest(manifest())
    second = review_portability_manifest(manifest())
    assert first == second
    assert PortabilityReview.model_validate(to_dict(first)) == first
