"""Contract tests for the #877 offline portability validator."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from axis_api.portability_manifest import (
    ComponentInventory,
    ConsistencyPoint,
    ManifestVersion,
    PortabilityManifest,
    RebindingReference,
    StoreWatermark,
)
from axis_api.portability_validator import (
    ArchiveMember,
    BundleArchive,
    BundleSignature,
    PayloadRecord,
    PortabilityBundle,
    PortabilityValidationError,
    acknowledge_restore_plan,
    canonical_portability_digest,
    validate_bundle,
)

_SOURCE_TENANT = "tenant-source-alpha"
_TRUSTED_KEY = "signing/2026/portability"
_AXIS_VERSION = "1.14.0"

_COMPONENTS = (
    ("ontology", "data", "ontology", "rebuildable_projection"),
    ("audit-ledger", "trust", "audit_ledger", "quiesced_export"),
    ("object-store", "data", "object_storage", "captured_watermark"),
)


def _payloads(
    decisions: dict[str, str] | None = None,
) -> dict[str, tuple[PayloadRecord, ...]]:
    records = {
        "ontology": (
            PayloadRecord(identity="user:planner", data={"entity": "asset_line_2"}),
            PayloadRecord(identity="user:auditor", data={"entity": "asset_line_1"}),
        ),
        "audit-ledger": (
            PayloadRecord(identity="user:planner", data={"event": "approve"}),
            PayloadRecord(identity="user:auditor", data={"event": "review"}),
        ),
        "object-store": (
            PayloadRecord(identity="user:planner", data={"blob": "b64:AAAA"}),
            PayloadRecord(identity="user:auditor", data={"blob": "b64:BBBB"}),
        ),
    }
    decisions = decisions or {}
    return {
        component_id: records[component_id]
        for component_id, *_rest in _COMPONENTS
        if decisions.get(component_id) != "exclude"
    }


def _manifest(
    *,
    decisions: dict[str, str] | None = None,
    rebinding: tuple[RebindingReference, ...] | None = None,
) -> PortabilityManifest:
    """Build a manifest whose restore digests match the real payloads."""

    decisions = decisions or {}
    payloads = _payloads(decisions)
    components = tuple(
        ComponentInventory(
            component_id=component_id,
            owner_layer=owner_layer,
            store=store,
            consistency=consistency,
            decision=decisions.get(component_id, "restore"),
            schema_version=ManifestVersion(major=1, minor=0),
            object_count=(
                len(payloads[component_id]) if component_id in payloads else 0
            ),
            content_digest=(
                canonical_portability_digest(
                    [record.model_dump(mode="json") for record in payloads[component_id]]
                )
                if component_id in payloads
                else None
            ),
            handler_registered=decisions.get(component_id) != "exclude",
            exclusion_reason=(
                "excluded by source profile" if decisions.get(component_id) == "exclude" else None
            ),
        )
        for component_id, owner_layer, store, consistency in _COMPONENTS
    )
    return PortabilityManifest(
        schema_version=ManifestVersion(major=1, minor=0),
        tenant_logical_id=_SOURCE_TENANT,
        source_axis_version=_AXIS_VERSION,
        consistency_point=ConsistencyPoint(
            mode="captured_watermark",
            captured_at="2026-09-15T10:00:00Z",
            per_store=(
                StoreWatermark(store="ontology", watermark="wm-1"),
                StoreWatermark(store="audit_ledger", watermark="wm-2"),
                StoreWatermark(store="object_storage", watermark="wm-3"),
            ),
            disclosures="Watermarks captured per store during export.",
        ),
        components=components,
        rebinding_references=rebinding
        if rebinding is not None
        else (
            RebindingReference(
                kind="credential",
                reference_id="credential.oidc-client",
                resolution="fresh_local_resolution_required",
            ),
            RebindingReference(
                kind="object_store",
                reference_id="store.exports",
                resolution="rebind_required",
            ),
            RebindingReference(
                kind="signing_key",
                reference_id="key.tenant-signing",
                resolution="unsupported",
                notes="HSM-bound key cannot migrate.",
            ),
        ),
    )


def _bundle(manifest: PortabilityManifest) -> PortabilityBundle:
    return PortabilityBundle(
        manifest=manifest,
        archive=BundleArchive(
            members=(
                ArchiveMember(path="manifest.json", size_bytes=4_096),
                ArchiveMember(path="components/ontology.jsonl", size_bytes=65_536),
                ArchiveMember(path="components/audit-ledger.jsonl", size_bytes=32_768),
                ArchiveMember(path="components/object-store.jsonl", size_bytes=131_072),
            )
        ),
        component_payloads=_payloads(
            {component.component_id: component.decision for component in manifest.components}
        ),
        signature=BundleSignature(
            signer_key_id=_TRUSTED_KEY,
            signed_manifest_digest=manifest.digest(),
        ),
    )


def _validated(bundle: PortabilityBundle, **overrides: object):
    values: dict[str, object] = {
        "trusted_signer_key_ids": frozenset({_TRUSTED_KEY}),
        "supported_axis_versions": (_AXIS_VERSION,),
    }
    values.update(overrides)
    return validate_bundle(bundle, **values)  # type: ignore[arg-type]


# --- AC: valid synthetic bundle → deterministic plan --------------------------


def test_valid_bundle_produces_deterministic_plan() -> None:
    plan = _validated(_bundle(_manifest()))
    # One unsupported signing key blocks full support; the rest is complete.
    assert plan.supported is False
    assert plan.blocked_by == ("signing_key:key.tenant-signing",)
    assert plan.suspended_operations == (
        "pending_actions:suspended",
        "pending_deliveries:suspended",
        "workflow_schedules:suspended",
        "credential_leases:suspended",
    )
    assert plan.excluded_components == ()
    assert {action.action for action in plan.rebinding_actions} == {
        "fresh_local_resolution_required",
        "rebind_required",
        "unsupported_blocked",
    }
    assert _validated(_bundle(_manifest())).plan_digest == plan.plan_digest


def test_plan_without_unsupported_references_is_supported() -> None:
    manifest = _manifest(
        rebinding=(
            RebindingReference(
                kind="credential",
                reference_id="credential.oidc-client",
                resolution="fresh_local_resolution_required",
            ),
        )
    )
    plan = _validated(_bundle(manifest))
    assert plan.supported is True and plan.blocked_by == ()


# --- identity mapping rules -----------------------------------------------------


def test_identity_map_produces_mapped_and_disabled_states() -> None:
    plan = _validated(
        _bundle(_manifest()),
        identity_map={"user:planner": ("user:restored-planner", "user")},
    )
    states = {item.source_subject: item.target_state for item in plan.identity_mappings}
    assert states == {"user:planner": "mapped", "user:auditor": "unmapped_disabled"}
    mapped = next(item for item in plan.identity_mappings if item.target_state == "mapped")
    assert mapped.target_subject == "user:restored-planner"
    assert mapped.source_kind == "user"


def test_group_and_service_kinds_come_from_the_operator_map() -> None:
    plan = _validated(
        _bundle(_manifest()),
        identity_map={
            "user:planner": ("group:planners", "group"),
            "user:auditor": ("service:audit-sync", "service"),
        },
    )
    kinds = {item.source_subject: item.source_kind for item in plan.identity_mappings}
    assert kinds == {"user:planner": "group", "user:auditor": "service"}


def test_ambiguous_two_to_one_mapping_is_refused() -> None:
    with pytest.raises(PortabilityValidationError) as blocked:
        _validated(
            _bundle(_manifest()),
            identity_map={
                "user:a": ("user:same", "user"),
                "user:b": ("user:same", "user"),
            },
        )
    assert blocked.value.code == PortabilityValidationError.AMBIGUOUS_IDENTITY_MAPPING


def test_unknown_principals_stay_unmapped_and_disabled() -> None:
    plan = _validated(_bundle(_manifest()))
    unmapped = [
        item for item in plan.identity_mappings if item.target_state == "unmapped_disabled"
    ]
    assert unmapped and all(item.target_subject is None for item in unmapped)


# --- AC: wrong signer, corrupt payload, duplicate, missing, version -------------


def _with_signature(bundle: PortabilityBundle, key_id: str) -> PortabilityBundle:
    return PortabilityBundle.model_validate(
        {
            **bundle.model_dump(mode="json"),
            "signature": BundleSignature(
                signer_key_id=key_id,
                signed_manifest_digest=bundle.manifest.digest(),
            ).model_dump(mode="json"),
        }
    )


def test_wrong_signer_fails_before_any_plan() -> None:
    rogue = _with_signature(_bundle(_manifest()), "signing/2026/rogue")
    with pytest.raises(PortabilityValidationError) as blocked:
        _validated(rogue)
    assert blocked.value.code == PortabilityValidationError.UNTRUSTED_SIGNER


def test_signature_over_a_different_digest_fails() -> None:
    bundle = _bundle(_manifest())
    forged = PortabilityBundle.model_validate(
        {
            **bundle.model_dump(mode="json"),
            "signature": BundleSignature(
                signer_key_id=_TRUSTED_KEY,
                signed_manifest_digest="0" * 64,
            ).model_dump(mode="json"),
        }
    )
    with pytest.raises(PortabilityValidationError) as blocked:
        _validated(
            forged,
            trusted_signer_key_ids=frozenset({_TRUSTED_KEY, "signing/2026/other"}),
        )
    assert blocked.value.code == PortabilityValidationError.UNTRUSTED_SIGNER


def test_corrupt_payload_digest_fails() -> None:
    manifest = _manifest()
    corrupt = PortabilityManifest.model_validate(
        {
            **manifest.model_dump(mode="json"),
            "components": [
                {
                    **component.model_dump(mode="json"),
                    "content_digest": "0" * 64,
                }
                if component.component_id == "ontology"
                else component.model_dump(mode="json")
                for component in manifest.components
            ],
        }
    )
    with pytest.raises(PortabilityValidationError) as blocked:
        _validated(_bundle(corrupt))
    assert blocked.value.code == PortabilityValidationError.PAYLOAD_DIGEST_MISMATCH


def test_payload_count_mismatch_fails() -> None:
    manifest = _manifest()
    slim = PortabilityManifest.model_validate(
        {
            **manifest.model_dump(mode="json"),
            "components": [
                {**component.model_dump(mode="json"), "object_count": 3}
                if component.component_id == "ontology"
                else component.model_dump(mode="json")
                for component in manifest.components
            ],
        }
    )
    with pytest.raises(PortabilityValidationError) as blocked:
        _validated(_bundle(slim))
    assert blocked.value.code == PortabilityValidationError.PAYLOAD_DIGEST_MISMATCH


def test_missing_required_component_payload_fails() -> None:
    manifest = _manifest()
    payloads = _payloads()
    payloads.pop("audit-ledger")
    hole = PortabilityBundle.model_validate(
        {
            **_bundle(manifest).model_dump(mode="json"),
            "component_payloads": {
                component_id: [record.model_dump(mode="json") for record in records]
                for component_id, records in payloads.items()
            },
        }
    )
    with pytest.raises(PortabilityValidationError) as blocked:
        _validated(hole)
    assert blocked.value.code == PortabilityValidationError.MISSING_COMPONENT_PAYLOAD


def test_duplicate_identity_in_payload_fails() -> None:
    duplicated = (
        PayloadRecord(identity="user:same", data={"entity": "x"}),
        PayloadRecord(identity="user:same", data={"entity": "y"}),
    )
    # The manifest honestly describes the duplicated payload (digest matches),
    # so the validator must catch the duplicate itself.
    manifest = _manifest()
    with_dup = PortabilityManifest.model_validate(
        {
            **manifest.model_dump(mode="json"),
            "components": [
                {
                    **component.model_dump(mode="json"),
                    "content_digest": canonical_portability_digest(
                        [record.model_dump(mode="json") for record in duplicated]
                    ),
                }
                if component.component_id == "ontology"
                else component.model_dump(mode="json")
                for component in manifest.components
            ],
        }
    )
    bundle = _bundle(with_dup)
    tampered = PortabilityBundle.model_validate(
        {
            **bundle.model_dump(mode="json"),
            "component_payloads": {
                **{
                    component_id: [record.model_dump(mode="json") for record in records]
                    for component_id, records in bundle.component_payloads.items()
                },
                "ontology": [record.model_dump(mode="json") for record in duplicated],
            },
        }
    )
    with pytest.raises(PortabilityValidationError) as blocked:
        _validated(tampered)
    assert blocked.value.code == PortabilityValidationError.DUPLICATE_IDENTITY


def test_unsupported_source_version_fails() -> None:
    with pytest.raises(PortabilityValidationError) as blocked:
        _validated(_bundle(_manifest()), supported_axis_versions=("9.9.9",))
    assert blocked.value.code == PortabilityValidationError.INCOMPATIBLE_AXIS_VERSION


# --- archive safety ---------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    ["../../etc/passwd", "/abs/path.jsonl", "back\\slash.jsonl", "scripts/payload.py", "x.so"],
)
def test_unsafe_archive_members_are_rejected(path: str) -> None:
    with pytest.raises(ValidationError, match="unsafe_archive_member"):
        BundleArchive(members=(ArchiveMember(path=path, size_bytes=10),))


def test_archive_total_size_limit() -> None:
    half_gib = 536_870_912
    members = tuple(
        ArchiveMember(path=f"components/blob-{index}.jsonl", size_bytes=half_gib)
        for index in range(5)
    )
    with pytest.raises(ValidationError, match="archive_resource_limits_exceeded"):
        BundleArchive(members=members)


def test_duplicate_member_paths_are_rejected() -> None:
    with pytest.raises(ValidationError, match="unsafe_archive_member"):
        BundleArchive(
            members=(
                ArchiveMember(path="components/ontology.jsonl", size_bytes=1),
                ArchiveMember(path="components/ontology.jsonl", size_bytes=2),
            )
        )


# --- AC: exclusions require explicit acknowledgment -------------------------------


def test_exclusions_require_acknowledgment() -> None:
    plan = _validated(_bundle(_manifest(decisions={"object-store": "exclude"})))
    assert plan.exclusions() == ("object-store",)
    with pytest.raises(TypeError):
        acknowledge_restore_plan(
            plan, acknowledged_by="operator:restore", acknowledged_at="2026-09-16T08:00:00Z"
        )
    with pytest.raises(PortabilityValidationError) as blocked:
        acknowledge_restore_plan(
            plan,
            acknowledged_exclusions=(),
            acknowledged_by="operator:restore",
            acknowledged_at="2026-09-16T08:00:00Z",
        )
    assert blocked.value.code == PortabilityValidationError.UNACKNOWLEDGED_EXCLUSION


def test_acknowledgment_requires_no_unknown_entries() -> None:
    plan = _validated(_bundle(_manifest(decisions={"object-store": "exclude"})))
    with pytest.raises(PortabilityValidationError) as blocked:
        acknowledge_restore_plan(
            plan,
            acknowledged_exclusions=("object-store", "ontology"),
            acknowledged_by="operator:restore",
            acknowledged_at="2026-09-16T08:00:00Z",
        )
    assert blocked.value.code == PortabilityValidationError.UNACKNOWLEDGED_EXCLUSION


def test_acknowledgment_covers_every_exclusion_and_binds_the_plan() -> None:
    plan = _validated(
        _bundle(_manifest(decisions={"object-store": "exclude", "ontology": "rebuild"}))
    )
    ack = acknowledge_restore_plan(
        plan,
        acknowledged_exclusions=("object-store",),
        acknowledged_by="operator:restore",
        acknowledged_at="2026-09-16T08:00:00Z",
    )
    assert ack.plan_digest == plan.plan_digest
    assert ack.acknowledged_exclusions == ("object-store",)


def test_rebuild_components_are_listed_for_the_writer() -> None:
    plan = _validated(_bundle(_manifest(decisions={"ontology": "rebuild"})))
    assert "ontology" in plan.rebuild_components


# --- offline proof -----------------------------------------------------------------


def test_validator_module_has_no_network_or_persistence_imports() -> None:
    import axis_api.portability_validator as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "import requests",
        "import httpx",
        "import urllib",
        "import socket",
        "import boto3",
        "import psycopg",
        "import sqlalchemy",
        "create_engine",
        "subprocess",
    ):
        assert forbidden not in source, forbidden
