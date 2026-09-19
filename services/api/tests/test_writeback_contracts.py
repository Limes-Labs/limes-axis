"""Contract tests for the #510 governed writeback target/operation/adapter contract."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from axis_api.actions import ActionDefinition, ActionRiskLevel, ApprovalMode
from axis_api.writeback_contracts import (
    ADAPTER_TYPE_REST_MUTATION,
    RemoteOutcome,
    WritebackActionBinding,
    WritebackAdapterCapability,
    WritebackAdapterRegistration,
    WritebackBusinessResult,
    WritebackConformanceObservation,
    WritebackContractError,
    WritebackEgressEvidence,
    WritebackErrorCode,
    WritebackExecutionContext,
    WritebackIdempotencyPlan,
    WritebackOperationMapping,
    WritebackParameterBinding,
    WritebackPrecondition,
    WritebackProtectedHeader,
    WritebackReadiness,
    WritebackRemoteRequest,
    WritebackRequestTemplate,
    WritebackResponseMapping,
    WritebackSourceVerification,
    WritebackTargetRegistry,
    WritebackTargetSpec,
    compute_plan_digest,
    normalize_remote_outcome,
    run_adapter_conformance,
)

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
TENANT = "tenant_demo"


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "incident_id": {"type": "string"},
        "status": {"type": "string"},
        "current_version": {"type": "string"},
    },
    "required": ["incident_id", "status", "current_version"],
}

# The real typed action model: no new action schema is introduced for writeback.
ACTION = ActionDefinition(
    action_id="place_quality_hold",
    display_name="Place quality hold",
    domain="quality",
    risk_level=ActionRiskLevel.MEDIUM,
    approval_mode=ApprovalMode.REQUIRED,
    input_schema=INPUT_SCHEMA,
    output_schema={},
    required_permissions=["actions:execute"],
)
ACTION_INPUT = {"incident_id": "INC-9", "status": "on hold", "current_version": "7"}


def capability(**overrides: Any) -> WritebackAdapterCapability:
    base: dict[str, Any] = {
        "adapter_type": ADAPTER_TYPE_REST_MUTATION,
        "adapter_version": "1.0",
        "capabilities": frozenset({"writeback"}),
        "native_idempotency": "supported",
        "preconditions": frozenset({"if_match"}),
        "acknowledgement": "sync_result",
        "response_schema_digest": "a" * 64,
    }
    base.update(overrides)
    return WritebackAdapterCapability(**base)


def readiness(**overrides: Any) -> WritebackReadiness:
    base: dict[str, Any] = {"status": "ready", "checked_at": NOW}
    base.update(overrides)
    return WritebackReadiness(**base)


def mapping(**overrides: Any) -> WritebackOperationMapping:
    base: dict[str, Any] = {
        "mapping_ref": "itsm-incident-upsert",
        "version": 1,
        "action_id": ACTION.action_id,
        "action_input_schema_digest": digest(INPUT_SCHEMA),
        "resource_kind": "incident",
        "operation_kind": "upsert",
        "bindings": (
            WritebackParameterBinding(
                action_input_field="incident_id", remote_field="incident_id", value_type="string"
            ),
            WritebackParameterBinding(
                action_input_field="status", remote_field="state", value_type="string"
            ),
            WritebackParameterBinding(
                action_input_field="current_version", remote_field="version", value_type="string"
            ),
        ),
        "request": WritebackRequestTemplate(
            method="PUT",
            path_template="/v1/incidents/{incident_id}",
            protected_headers=(
                WritebackProtectedHeader(name="authorization", value_source="credential_lease"),
                WritebackProtectedHeader(name="idempotency-key", value_source="idempotency_key"),
                WritebackProtectedHeader(name="if-match", value_source="approval_digest"),
            ),
            max_request_bytes=65_536,
        ),
        "response": WritebackResponseMapping(
            remote_id_field="incident_id", remote_version_field="version", receipt_field="receipt"
        ),
        "precondition_kind": "if_match",
        "approved_by": "operator@example.com",
    }
    base.update(overrides)
    return WritebackOperationMapping(**base)


@dataclass
class Host:
    registry: WritebackTargetRegistry
    record: Any
    mapping: WritebackOperationMapping
    adapter: WritebackAdapterRegistration

    def context(self, **overrides: Any) -> WritebackExecutionContext:
        body_digest = digest({"state": "on hold"})
        precondition = WritebackPrecondition(
            kind="if_match", remote_version="7", expected_digest=body_digest
        )
        expected = compute_plan_digest(
            tenant_id=TENANT,
            actor_id="actor-1",
            action_id=ACTION.action_id,
            approval_id="approval-1",
            target_ref="itsm-incidents",
            target_version=1,
            spec_digest=self.record.spec_digest,
            mapping=self.mapping,
            resource_kind="incident",
            remote_id="INC-9",
            precondition=precondition,
            method="PUT",
            path="/v1/incidents/INC-9",
            body_digest=body_digest,
        )
        base: dict[str, Any] = {
            "tenant_id": TENANT,
            "actor_id": "actor-1",
            "action_id": ACTION.action_id,
            "approval_id": "approval-1",
            "approved_payload_digest": expected,
            "credential_handle_ref": "cred-itsm-1",
            "credential_lease_ref": "lease-1",
            "egress": WritebackEgressEvidence(
                policy_id="egress-itsm",
                resolved_authority="itsm.internal:443",
                decision="allowed",
                evaluated_at=NOW,
            ),
            "target_ref": "itsm-incidents",
            "mapping_ref": "itsm-incident-upsert",
            "idempotency_key_digest": "b" * 64,
            "correlation_id": "corr-1",
            "requested_at": NOW,
        }
        base.update(overrides)
        return WritebackExecutionContext(**base)


def build_host(*, spec_overrides: dict[str, Any] | None = None) -> Host:
    adapter_capability = capability()
    registration = WritebackAdapterRegistration(
        tenant_id=TENANT,
        adapter_type=ADAPTER_TYPE_REST_MUTATION,
        adapter_version="1.0",
        capability=adapter_capability,
        readiness=readiness(),
        conformance_scope="local_wire_level",
        registered_at=NOW,
    )
    spec_fields: dict[str, Any] = {
        "tenant_id": TENANT,
        "adapter_type": ADAPTER_TYPE_REST_MUTATION,
        "adapter_version": "1.0",
        "connector_id": "itsm_rest",
        "resource_kind": "incident",
        "remote_authority": "itsm.internal:443",
        "credential_handle_ref": "cred-itsm-1",
        "egress_policy_ref": "egress-itsm",
        "operations": frozenset({"upsert"}),
        "capability": adapter_capability,
        "display_name": "ITSM incidents",
    }
    spec_fields.update(spec_overrides or {})
    spec = WritebackTargetSpec(**spec_fields)
    registry = WritebackTargetRegistry(TENANT)
    registry.register_adapter(registration)
    record = registry.register_target("itsm-incidents", spec, registered_at=NOW)
    registry.set_enabled("itsm-incidents", 1, enabled=True)
    operation_mapping = mapping()
    registry.register_mapping(operation_mapping)
    registry.register_action_binding(
        WritebackActionBinding(
            tenant_id=TENANT,
            action_id=ACTION.action_id,
            action_input_schema_digest=digest(INPUT_SCHEMA),
            target_ref="itsm-incidents",
            mapping_ref="itsm-incident-upsert",
            mapping_version=1,
            approved_by="operator@example.com",
        )
    )
    return Host(registry=registry, record=record, mapping=operation_mapping, adapter=registration)


@pytest.fixture
def host() -> Host:
    return build_host()


def resolve(host: Host, *, action_input: dict[str, Any] | None = None, **context_overrides: Any):
    return host.registry.resolve(
        ACTION,
        ACTION_INPUT if action_input is None else action_input,
        host.context(**context_overrides),
        prepared_at=NOW,
    )


def code_of(exc: pytest.ExceptionInfo[WritebackContractError]) -> WritebackErrorCode:
    return exc.value.code


# ---------------------------------------------------------------------------
# AC 1, 3, 5: one typed action resolves to one registered target operation
# ---------------------------------------------------------------------------


def test_typed_action_resolves_to_registered_target_operation(host: Host) -> None:
    plan = resolve(host)
    assert plan.operation_kind == "upsert"
    assert plan.request.method == "PUT"
    assert plan.request.authority == "itsm.internal:443"
    assert plan.request.path == "/v1/incidents/INC-9"
    assert dict(plan.request.body) == {"state": "on hold"}
    assert plan.resource.remote_id == "INC-9"
    assert plan.resource.remote_version == "7"
    assert plan.precondition is not None
    assert plan.precondition.kind == "if_match"
    assert plan.precondition.remote_version == "7"
    assert plan.precondition.expected_digest == plan.request.body_digest
    assert plan.target_version == 1
    assert plan.mapping_ref == "itsm-incident-upsert"
    assert plan.plan_digest == host.context().approved_payload_digest


def test_plan_evidence_carries_digests_and_codes_only(host: Host) -> None:
    evidence = resolve(host).evidence().model_dump(mode="json")
    serialized = json.dumps(evidence)
    assert evidence["request_body_digest"]
    assert "on hold" not in serialized
    assert "itsm.internal" not in serialized
    assert "/v1/incidents" not in serialized
    assert evidence["idempotency_mode"] == "native_key_and_precondition"


def test_plan_repr_does_not_leak_payload_or_endpoint(host: Host) -> None:
    rendered = repr(resolve(host))
    assert "on hold" not in rendered
    assert "itsm.internal" not in rendered


def test_catalog_is_public_safe_and_reflects_readiness(host: Host) -> None:
    catalog = host.registry.catalog()
    assert catalog.tenant_id == TENANT
    entry = catalog.targets[0].model_dump(mode="json")
    assert entry["connector_id"] == "itsm_rest"
    assert entry["operations"] == ["upsert"]
    assert entry["readiness_status"] == "ready"
    serialized = json.dumps(entry)
    for leaked in (
        "itsm.internal",
        "cred-itsm-1",
        "egress-itsm",
        "/v1/incidents",
        "itsm-incidents",
    ):
        assert leaked not in serialized


# ---------------------------------------------------------------------------
# AC 2: tenant-bound registry with immutable versions and explicit activation
# ---------------------------------------------------------------------------


def test_registry_versions_are_append_only(host: Host) -> None:
    spec = host.record.spec
    second = host.registry.register_target("itsm-incidents", spec, registered_at=NOW)
    assert (host.record.version, second.version) == (1, 2)
    assert host.registry.record("itsm-incidents", 1).spec_digest == host.record.spec_digest
    assert host.registry.enabled_record("itsm-incidents").version == 1


def test_activation_is_explicit_and_reversible(host: Host) -> None:
    assert host.registry.catalog().targets
    host.registry.set_enabled("itsm-incidents", 1, enabled=False)
    assert host.registry.catalog().targets == ()
    with pytest.raises(WritebackContractError) as exc:
        resolve(host)
    assert code_of(exc) is WritebackErrorCode.TARGET_DISABLED


def test_registry_rejects_unknown_tenant_and_unknown_target(host: Host) -> None:
    other = WritebackTargetRegistry("tenant_other")
    with pytest.raises(WritebackContractError) as exc:
        other.register_adapter(host.adapter)
    assert code_of(exc) is WritebackErrorCode.TENANT_MISMATCH
    with pytest.raises(WritebackContractError) as unknown:
        host.registry.enabled_record("missing-target")
    assert code_of(unknown) is WritebackErrorCode.TARGET_UNKNOWN


def test_duplicate_mapping_version_is_rejected(host: Host) -> None:
    with pytest.raises(WritebackContractError) as exc:
        host.registry.register_mapping(host.mapping)
    assert code_of(exc) is WritebackErrorCode.INVALID_OPERATION_MAPPING


def test_binding_requires_a_registered_mapping_with_the_declared_schema(host: Host) -> None:
    with pytest.raises(WritebackContractError) as unknown:
        host.registry.register_action_binding(
            WritebackActionBinding(
                tenant_id=TENANT,
                action_id="other_action",
                action_input_schema_digest=digest(INPUT_SCHEMA),
                target_ref="itsm-incidents",
                mapping_ref="itsm-incident-upsert",
                mapping_version=1,
                approved_by="operator@example.com",
            )
        )
    assert code_of(unknown) is WritebackErrorCode.INVALID_OPERATION_MAPPING
    with pytest.raises(WritebackContractError) as schema:
        host.registry.register_action_binding(
            WritebackActionBinding(
                tenant_id=TENANT,
                action_id=ACTION.action_id,
                action_input_schema_digest="c" * 64,
                target_ref="itsm-incidents",
                mapping_ref="itsm-incident-upsert",
                mapping_version=1,
                approved_by="operator@example.com",
            )
        )
    assert code_of(schema) is WritebackErrorCode.MAPPING_SCHEMA_MISMATCH


# ---------------------------------------------------------------------------
# AC 7: negatives that must fail before transport
# ---------------------------------------------------------------------------


def test_changed_payload_fails_the_approved_digest_before_transport(host: Host) -> None:
    with pytest.raises(WritebackContractError) as exc:
        resolve(host, action_input={**ACTION_INPUT, "status": "escalated"})
    assert code_of(exc) is WritebackErrorCode.APPROVAL_PAYLOAD_MISMATCH


def test_revoked_lease_and_wrong_credential_reference_block(host: Host) -> None:
    with pytest.raises(WritebackContractError) as missing:
        resolve(host, credential_lease_ref=None)
    assert code_of(missing) is WritebackErrorCode.CREDENTIAL_LEASE_REQUIRED
    with pytest.raises(WritebackContractError) as mismatch:
        resolve(host, credential_handle_ref="cred-other")
    assert code_of(mismatch) is WritebackErrorCode.CREDENTIAL_REFERENCE_MISMATCH


def test_wrong_tenant_blocks_before_transport(host: Host) -> None:
    with pytest.raises(WritebackContractError) as exc:
        resolve(host, tenant_id="tenant_other")
    assert code_of(exc) is WritebackErrorCode.TENANT_MISMATCH


def test_egress_must_be_evaluated_against_this_target(host: Host) -> None:
    with pytest.raises(WritebackContractError) as policy:
        resolve(
            host,
            egress=WritebackEgressEvidence(
                policy_id="egress-other",
                resolved_authority="itsm.internal:443",
                decision="allowed",
                evaluated_at=NOW,
            ),
        )
    assert code_of(policy) is WritebackErrorCode.EGRESS_NOT_EVALUATED
    with pytest.raises(WritebackContractError) as authority:
        resolve(
            host,
            egress=WritebackEgressEvidence(
                policy_id="egress-itsm",
                resolved_authority="itsm.evil:443",
                decision="allowed",
                evaluated_at=NOW,
            ),
        )
    assert code_of(authority) is WritebackErrorCode.EGRESS_TARGET_MISMATCH


def test_unknown_and_unbound_action_input_are_rejected(host: Host) -> None:
    with pytest.raises(WritebackContractError) as unknown:
        resolve(host, action_input={**ACTION_INPUT, "comment": "override"})
    assert code_of(unknown) is WritebackErrorCode.INVALID_ACTION_INPUT
    with pytest.raises(WritebackContractError) as missing:
        resolve(host, action_input={"incident_id": "INC-9"})
    assert code_of(missing) is WritebackErrorCode.INVALID_ACTION_INPUT


def test_path_values_cannot_escape_the_declared_segment(host: Host) -> None:
    with pytest.raises(WritebackContractError) as exc:
        resolve(host, action_input={**ACTION_INPUT, "incident_id": "../../admin"})
    assert code_of(exc) is WritebackErrorCode.INVALID_ACTION_INPUT


def test_resource_precondition_requires_a_declared_remote_version(host: Host) -> None:
    registry = WritebackTargetRegistry(TENANT)
    registry.register_adapter(
        WritebackAdapterRegistration(
            tenant_id=TENANT,
            adapter_type=ADAPTER_TYPE_REST_MUTATION,
            adapter_version="1.0",
            capability=capability(),
            readiness=readiness(),
            conformance_scope="contract_only",
            registered_at=NOW,
        )
    )
    spec = WritebackTargetSpec(
        tenant_id=TENANT,
        adapter_type=ADAPTER_TYPE_REST_MUTATION,
        adapter_version="1.0",
        connector_id="itsm_rest",
        resource_kind="incident",
        remote_authority="itsm.internal:443",
        credential_handle_ref="cred-itsm-1",
        egress_policy_ref="egress-itsm",
        operations=frozenset({"upsert"}),
        capability=capability(),
        display_name="ITSM incidents",
    )
    registry.register_target("itsm-incidents", spec, registered_at=NOW)
    registry.set_enabled("itsm-incidents", 1, enabled=True)
    versionless = mapping(
        response=WritebackResponseMapping(remote_id_field="incident_id"),
    )
    registry.register_mapping(versionless)
    registry.register_action_binding(
        WritebackActionBinding(
            tenant_id=TENANT,
            action_id=ACTION.action_id,
            action_input_schema_digest=digest(INPUT_SCHEMA),
            target_ref="itsm-incidents",
            mapping_ref=versionless.mapping_ref,
            mapping_version=1,
            approved_by="operator@example.com",
        )
    )
    with pytest.raises(WritebackContractError) as exc:
        registry.resolve(
            ACTION,
            ACTION_INPUT,
            Host(
                registry=registry,
                record=registry.record("itsm-incidents", 1),
                mapping=versionless,
                adapter=None,
            ).context(),
            prepared_at=NOW,
        )
    assert code_of(exc) is WritebackErrorCode.RESOURCE_PRECONDITION_MISSING


def test_unsupported_operation_and_precondition_block(host: Host) -> None:
    delete_mapping = mapping(
        mapping_ref="itsm-incident-delete",
        operation_kind="delete",
        bindings=(
            WritebackParameterBinding(
                action_input_field="incident_id", remote_field="incident_id", value_type="string"
            ),
        ),
        request=WritebackRequestTemplate(
            method="DELETE", path_template="/v1/incidents/{incident_id}"
        ),
        precondition_kind=None,
    )
    host.registry.register_mapping(delete_mapping)
    host.registry.register_action_binding(
        WritebackActionBinding(
            tenant_id=TENANT,
            action_id=ACTION.action_id,
            action_input_schema_digest=digest(INPUT_SCHEMA),
            target_ref="itsm-incidents",
            mapping_ref="itsm-incident-delete",
            mapping_version=1,
            approved_by="operator@example.com",
        )
    )
    with pytest.raises(WritebackContractError) as exc:
        resolve(host, action_input={"incident_id": "INC-9", "status": "x", "current_version": "7"})
    assert code_of(exc) is WritebackErrorCode.UNSUPPORTED_OPERATION


def test_unsupported_precondition_blocks(host: Host) -> None:
    read_only_adapter = capability(preconditions=frozenset())
    registry = WritebackTargetRegistry(TENANT)
    registry.register_adapter(
        WritebackAdapterRegistration(
            tenant_id=TENANT,
            adapter_type=ADAPTER_TYPE_REST_MUTATION,
            adapter_version="1.0",
            capability=read_only_adapter,
            readiness=readiness(),
            conformance_scope="contract_only",
            registered_at=NOW,
        )
    )
    spec = WritebackTargetSpec(
        tenant_id=TENANT,
        adapter_type=ADAPTER_TYPE_REST_MUTATION,
        adapter_version="1.0",
        connector_id="itsm_rest",
        resource_kind="incident",
        remote_authority="itsm.internal:443",
        credential_handle_ref="cred-itsm-1",
        egress_policy_ref="egress-itsm",
        operations=frozenset({"upsert"}),
        capability=read_only_adapter,
        display_name="ITSM incidents",
    )
    registry.register_target("itsm-incidents", spec, registered_at=NOW)
    registry.set_enabled("itsm-incidents", 1, enabled=True)
    registry.register_mapping(mapping())
    registry.register_action_binding(
        WritebackActionBinding(
            tenant_id=TENANT,
            action_id=ACTION.action_id,
            action_input_schema_digest=digest(INPUT_SCHEMA),
            target_ref="itsm-incidents",
            mapping_ref="itsm-incident-upsert",
            mapping_version=1,
            approved_by="operator@example.com",
        )
    )
    with pytest.raises(WritebackContractError) as exc:
        registry.resolve(
            ACTION,
            ACTION_INPUT,
            Host(
                registry=registry,
                record=registry.record("itsm-incidents", 1),
                mapping=mapping(),
                adapter=None,
            ).context(),
            prepared_at=NOW,
        )
    assert code_of(exc) is WritebackErrorCode.UNSUPPORTED_PRECONDITION


# ---------------------------------------------------------------------------
# AC 7: malformed mappings, overrides and secret material
# ---------------------------------------------------------------------------


def test_mapping_rejects_raw_payload_and_transport_bindings() -> None:
    for field in ("raw_body", "sql", "host", "headers", "method"):
        with pytest.raises(ValidationError):
            WritebackParameterBinding(
                action_input_field=field, remote_field="anything", value_type="string"
            )


def test_mapping_rejects_unknown_or_absolute_paths_and_escaping_headers() -> None:
    with pytest.raises(ValidationError):
        WritebackRequestTemplate(method="PUT", path_template="https://evil.example/v1")
    with pytest.raises(ValidationError):
        WritebackRequestTemplate(method="PUT", path_template="/v1/../admin")
    with pytest.raises(ValidationError):
        WritebackProtectedHeader(name="host", value_source="contract_version")
    with pytest.raises(ValidationError):
        WritebackRequestTemplate(
            method="PUT",
            path_template="/v1/incidents/{incident_id}",
            protected_headers=(
                WritebackProtectedHeader(name="authorization", value_source="credential_lease"),
                WritebackProtectedHeader(name="authorization", value_source="approval_digest"),
            ),
        )


def test_mapping_requires_bound_placeholders_and_delete_path_only_bindings() -> None:
    with pytest.raises(ValidationError):
        mapping(
            request=WritebackRequestTemplate(method="PUT", path_template="/v1/incidents/{unknown}")
        )
    with pytest.raises(ValidationError):
        mapping(
            operation_kind="delete",
            request=WritebackRequestTemplate(
                method="DELETE", path_template="/v1/incidents/{incident_id}"
            ),
            precondition_kind=None,
        )
    with pytest.raises(ValidationError):
        mapping(
            operation_kind="delete",
            request=WritebackRequestTemplate(method="DELETE", path_template="/v1/incidents"),
        )


def test_target_rejects_urls_and_credentials_in_references() -> None:
    for bad in ("https://vault.example/secret", "lease?token=abc", "user@host", "cred itsm"):
        with pytest.raises(ValidationError):
            WritebackTargetSpec(
                tenant_id=TENANT,
                adapter_type=ADAPTER_TYPE_REST_MUTATION,
                adapter_version="1.0",
                connector_id="itsm_rest",
                resource_kind="incident",
                remote_authority="itsm.internal:443",
                credential_handle_ref=bad,
                egress_policy_ref="egress-itsm",
                operations=frozenset({"upsert"}),
                capability=capability(),
                display_name="ITSM incidents",
            )
    with pytest.raises(ValidationError):
        WritebackTargetSpec(
            tenant_id=TENANT,
            adapter_type=ADAPTER_TYPE_REST_MUTATION,
            adapter_version="1.0",
            connector_id="itsm_rest",
            resource_kind="incident",
            remote_authority="https://itsm.internal",
            credential_handle_ref="cred-itsm-1",
            egress_policy_ref="egress-itsm",
            operations=frozenset({"upsert"}),
            capability=capability(),
            display_name="ITSM incidents",
        )


def test_a_read_only_adapter_cannot_declare_writeback() -> None:
    with pytest.raises(ValidationError):
        capability(capabilities=frozenset({"read", "discovery"}))


# ---------------------------------------------------------------------------
# AC 4: readiness and idempotency metadata
# ---------------------------------------------------------------------------


def test_adapter_availability_failure_blocks_instead_of_falling_back() -> None:
    for status, reason in (
        ("degraded", WritebackErrorCode.ADAPTER_NOT_READY),
        ("unavailable", WritebackErrorCode.ADAPTER_NOT_READY),
    ):
        observed = readiness(status=status, reason=reason)
        with pytest.raises(WritebackContractError) as exc:
            observed.require_ready()
        assert code_of(exc) is WritebackErrorCode.ADAPTER_NOT_READY
    with pytest.raises(ValidationError):
        WritebackReadiness(
            status="ready", reason=WritebackErrorCode.ADAPTER_NOT_READY, checked_at=NOW
        )
    with pytest.raises(ValidationError):
        WritebackReadiness(status="degraded", checked_at=NOW)


def test_idempotency_metadata_is_explicit_about_unsupported_remotes() -> None:
    honest = WritebackIdempotencyPlan(
        mode="none",
        key_source="none",
        repeat_safe=False,
        exactly_once=False,
        outcome_unknown_after_timeout=True,
    )
    assert honest.exactly_once is False
    assert honest.repeat_safe is False
    assert honest.outcome_unknown_after_timeout is True
    assert (
        WritebackIdempotencyPlan(
            mode="native_key",
            key_source="host_derived_digest",
            repeat_safe=True,
            exactly_once=True,
            outcome_unknown_after_timeout=False,
        ).exactly_once
        is True
    )


def test_native_idempotency_claim_requires_the_declared_header() -> None:
    no_header = mapping(
        mapping_ref="itsm-incident-noheader",
        request=WritebackRequestTemplate(
            method="PUT",
            path_template="/v1/incidents/{incident_id}",
            protected_headers=(
                WritebackProtectedHeader(name="authorization", value_source="credential_lease"),
            ),
        ),
    )
    host = build_host()
    host.registry.register_mapping(no_header)
    host.registry.register_action_binding(
        WritebackActionBinding(
            tenant_id=TENANT,
            action_id=ACTION.action_id,
            action_input_schema_digest=digest(INPUT_SCHEMA),
            target_ref="itsm-incidents",
            mapping_ref=no_header.mapping_ref,
            mapping_version=1,
            approved_by="operator@example.com",
        )
    )
    with pytest.raises(WritebackContractError) as exc:
        host.registry.resolve(ACTION, ACTION_INPUT, host.context(), prepared_at=NOW)
    assert code_of(exc) is WritebackErrorCode.INVALID_OPERATION_MAPPING


# ---------------------------------------------------------------------------
# AC 4: result mapping, conflicts and source verification
# ---------------------------------------------------------------------------


def native_plan() -> WritebackIdempotencyPlan:
    return WritebackIdempotencyPlan(
        mode="native_key_and_precondition",
        key_source="host_derived_digest",
        repeat_safe=True,
        exactly_once=True,
        outcome_unknown_after_timeout=False,
    )


def non_native_plan() -> WritebackIdempotencyPlan:
    return WritebackIdempotencyPlan(
        mode="none",
        key_source="none",
        repeat_safe=False,
        exactly_once=False,
        outcome_unknown_after_timeout=True,
    )


def test_outcome_normalization_maps_success_validation_and_conflict() -> None:
    precondition = WritebackPrecondition(kind="if_match", remote_version="7")
    succeeded = normalize_remote_outcome(
        outcome(status=200), idempotency=native_plan(), precondition=precondition
    )
    assert succeeded.state == "succeeded"
    rejected = normalize_remote_outcome(
        outcome(status=422), idempotency=native_plan(), precondition=precondition
    )
    assert rejected.state == "rejected"
    assert rejected.reason_code is WritebackErrorCode.REMOTE_REJECTED
    conflict = normalize_remote_outcome(
        outcome(status=412), idempotency=native_plan(), precondition=precondition
    )
    assert conflict.state == "conflict"
    assert conflict.conflict is not None
    assert conflict.conflict.kind == "precondition_failed"
    assert conflict.conflict.remote_version == "7"


def test_timeout_after_send_is_outcome_unknown_and_not_repeat_safe() -> None:
    unknown = normalize_remote_outcome(
        outcome(status=504, transport="sent"), idempotency=non_native_plan()
    )
    assert unknown.state == "outcome_unknown"
    assert unknown.reason_code is WritebackErrorCode.REMOTE_OUTCOME_UNKNOWN
    assert unknown.source_verification == "pending"


def test_not_sent_is_not_a_verification() -> None:
    never = normalize_remote_outcome(
        outcome(status=None, transport="not_sent"), idempotency=native_plan()
    )
    assert never.state == "not_sent"
    assert never.acknowledgement is not None
    assert never.acknowledgement.accepted is False
    assert never.source_verification == "pending"


def test_business_result_and_verification_stay_coherent() -> None:
    with pytest.raises(ValidationError):
        WritebackBusinessResult(state="conflict")
    with pytest.raises(ValidationError):
        WritebackBusinessResult(state="succeeded", source_verification="contradicted")
    with pytest.raises(ValidationError):
        WritebackBusinessResult(state="outcome_unknown", source_verification="confirmed")
    with pytest.raises(ValidationError):
        WritebackSourceVerification(state="confirmed", basis="unavailable")
    assert WritebackSourceVerification(state="pending", basis="unavailable").state == "pending"


def outcome(*, status: int | None, transport: str = "sent") -> RemoteOutcome:
    return RemoteOutcome(transport=transport, response_status=status)


# ---------------------------------------------------------------------------
# AC 4: adapter conformance report
# ---------------------------------------------------------------------------


def test_adapter_conformance_passes_on_a_consistent_declaration(host: Host) -> None:
    report = run_adapter_conformance(
        host.adapter,
        spec=host.record.spec,
        mapping=host.mapping,
        observations=(
            WritebackConformanceObservation(
                case="success", outcome=outcome(status=200), expected_state="succeeded"
            ),
            WritebackConformanceObservation(
                case="conflict",
                outcome=outcome(status=412),
                expected_state="conflict",
                expected_reason=WritebackErrorCode.REMOTE_CONFLICT,
            ),
            WritebackConformanceObservation(
                case="timeout_after_send",
                outcome=outcome(status=504),
                expected_state="outcome_unknown",
                expected_reason=WritebackErrorCode.REMOTE_OUTCOME_UNKNOWN,
            ),
        ),
    )
    assert report.passed
    assert report.failed_checks() == ()


def test_adapter_conformance_reports_each_violation(host: Host) -> None:
    # Statements without an exercised observation are reported as not run, never
    # as passed: an unevidenced result mapping cannot earn a clean report.
    unobserved = run_adapter_conformance(host.adapter, spec=host.record.spec, mapping=host.mapping)
    assert not unobserved.passed
    assert unobserved.failed_checks() == ()
    statuses = {finding.check: finding.status for finding in unobserved.findings}
    assert statuses["result_mapping"] == "not_run"
    assert statuses["error_taxonomy"] == "not_run"

    collapsed = run_adapter_conformance(
        host.adapter,
        spec=host.record.spec,
        mapping=host.mapping,
        observations=(
            WritebackConformanceObservation(
                case="success", outcome=outcome(status=200), expected_state="succeeded"
            ),
            WritebackConformanceObservation(
                case="conflict",
                outcome=outcome(status=412),
                expected_state="rejected",
                expected_reason=WritebackErrorCode.REMOTE_REJECTED,
            ),
        ),
    )
    assert "result_mapping" in collapsed.failed_checks()

    idempotent_claim = mapping(
        request=WritebackRequestTemplate(method="PUT", path_template="/v1/incidents/{incident_id}")
    )
    report = run_adapter_conformance(host.adapter, spec=host.record.spec, mapping=idempotent_claim)
    assert "idempotency_declaration" in report.failed_checks()


def test_conformance_requires_declared_reason_codes(host: Host) -> None:
    report = run_adapter_conformance(
        host.adapter,
        spec=host.record.spec,
        mapping=host.mapping,
        observations=(
            WritebackConformanceObservation(
                case="conflict", outcome=outcome(status=412), expected_state="conflict"
            ),
        ),
    )
    reasons = {finding.check: finding.reason for finding in report.findings}
    assert reasons["result_mapping"] is WritebackErrorCode.RESULT_MAPPING_MISMATCH
    assert reasons["error_taxonomy"] is WritebackErrorCode.EVIDENCE_INCOMPLETE


def test_conformance_scope_is_declared_not_inferred(host: Host) -> None:
    report = run_adapter_conformance(
        host.adapter, spec=host.record.spec, mapping=host.mapping, observations=()
    )
    assert report.scope == "local_wire_level"


# ---------------------------------------------------------------------------
# Request bounds
# ---------------------------------------------------------------------------


def test_oversized_request_is_blocked() -> None:
    host = build_host()
    tiny = mapping(
        mapping_ref="itsm-incident-tiny",
        request=WritebackRequestTemplate(
            method="PUT",
            path_template="/v1/incidents/{incident_id}",
            protected_headers=(
                WritebackProtectedHeader(name="authorization", value_source="credential_lease"),
                WritebackProtectedHeader(name="idempotency-key", value_source="idempotency_key"),
            ),
            max_request_bytes=2,
        ),
    )
    host.registry.register_mapping(tiny)
    host.registry.register_action_binding(
        WritebackActionBinding(
            tenant_id=TENANT,
            action_id=ACTION.action_id,
            action_input_schema_digest=digest(INPUT_SCHEMA),
            target_ref="itsm-incidents",
            mapping_ref=tiny.mapping_ref,
            mapping_version=1,
            approved_by="operator@example.com",
        )
    )
    with pytest.raises(WritebackContractError) as exc:
        host.registry.resolve(ACTION, ACTION_INPUT, host.context(), prepared_at=NOW)
    assert code_of(exc) is WritebackErrorCode.REQUEST_TOO_LARGE


def test_delete_requests_never_carry_a_replacement_body() -> None:
    with pytest.raises(ValidationError):
        WritebackRemoteRequest(
            method="DELETE",
            authority="itsm.internal:443",
            path="/v1/incidents/INC-9",
            protected_headers=(),
            body=(("state", "on hold"),),
            body_digest="d" * 64,
        )
