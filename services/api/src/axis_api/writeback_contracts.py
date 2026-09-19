"""Provider-neutral writeback contract for governed external mutation.

This module is vocabulary plus fail-closed resolution. It maps an existing typed
Axis action to one registered external target operation and normalizes the
remote outcome, so no connector can bypass the action, policy, approval,
credential or audit boundaries. It performs no I/O, owns no retry/outbox
lifecycle and contains no vendor business semantics.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from enum import StrEnum
from typing import Literal

from axis_sdk.connector_authoring.contracts import (
    Capability,
    ContractModel,
    Digest,
    Identifier,
)
from pydantic import (
    AwareDatetime,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from axis_api.actions import ActionDefinition

CONTRACT_VERSION = "1.0"
ADAPTER_TYPE_REST_MUTATION = "rest_mutation"
SUPPORTED_ADAPTER_VERSIONS = ("1.0",)
PUBLIC_SURFACE = "writeback-targets"

_PATH_SEGMENT = re.compile(r"^[A-Za-z0-9._~-]+$")
_AUTHORITY = re.compile(r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?(:[1-9][0-9]{0,4})?$")
_PLACEHOLDER = re.compile(r"\{([a-z][a-z0-9_]*)\}")
_SECRETISH = re.compile(r"(://|[\s?&#@]|^https?$)", re.IGNORECASE)
_SECRET_WORDS = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|bearer|private[_-]?key|credential)", re.IGNORECASE
)
_FORBIDDEN_BINDINGS = frozenset(
    {
        "body",
        "raw_body",
        "raw",
        "sql",
        "query",
        "url",
        "uri",
        "host",
        "authority",
        "headers",
        "method",
        "path",
    }
)
_ALLOWED_HEADERS = frozenset(
    {
        "authorization",
        "content-type",
        "idempotency-key",
        "if-match",
        "if-none-match",
        "x-correlation-id",
        "x-request-id",
    }
)

ProtectedHeaderName = Literal[
    "authorization",
    "content-type",
    "idempotency-key",
    "if-match",
    "if-none-match",
    "x-correlation-id",
    "x-request-id",
]
HeaderValueSource = Literal[
    "credential_lease", "approval_digest", "idempotency_key", "correlation_id", "contract_version"
]
MutationMethod = Literal["PUT", "PATCH", "POST", "DELETE"]
OperationKind = Literal["upsert", "delete"]
PreconditionKind = Literal["if_match", "if_none_match", "must_exist", "must_not_exist"]
ResultState = Literal["succeeded", "rejected", "conflict", "outcome_unknown", "not_sent"]
VerificationState = Literal["pending", "confirmed", "contradicted"]


class WritebackErrorCode(StrEnum):
    """Fixed public-safe codes. No payload, endpoint or credential detail attached."""

    INVALID_TARGET = "invalid_target"
    INVALID_OPERATION_MAPPING = "invalid_operation_mapping"
    INVALID_CONTRACT = "invalid_contract"
    TENANT_MISMATCH = "tenant_mismatch"
    TARGET_UNKNOWN = "target_unknown"
    TARGET_DISABLED = "target_disabled"
    MAPPING_UNKNOWN = "mapping_unknown"
    MAPPING_SCHEMA_MISMATCH = "mapping_schema_mismatch"
    UNSUPPORTED_OPERATION = "unsupported_operation"
    UNSUPPORTED_PRECONDITION = "unsupported_precondition"
    ADAPTER_NOT_WRITEBACK_CAPABLE = "adapter_not_writeback_capable"
    ADAPTER_NOT_READY = "adapter_not_ready"
    CREDENTIAL_LEASE_REQUIRED = "credential_lease_required"
    CREDENTIAL_REFERENCE_MISMATCH = "credential_reference_mismatch"
    EGRESS_NOT_EVALUATED = "egress_not_evaluated"
    EGRESS_BLOCKED = "egress_blocked"
    EGRESS_TARGET_MISMATCH = "egress_target_mismatch"
    APPROVAL_PAYLOAD_MISMATCH = "approval_payload_mismatch"
    INVALID_ACTION_INPUT = "invalid_action_input"
    UNBOUND_ACTION_INPUT = "unbound_action_input"
    REQUEST_TOO_LARGE = "request_too_large"
    RESOURCE_PRECONDITION_MISSING = "resource_precondition_missing"
    SECRET_MATERIAL_REJECTED = "secret_material_rejected"
    REMOTE_CONFLICT = "remote_conflict"
    REMOTE_REJECTED = "remote_rejected"
    REMOTE_OUTCOME_UNKNOWN = "remote_outcome_unknown"
    REMOTE_UNAVAILABLE = "remote_unavailable"
    RESULT_MAPPING_MISMATCH = "result_mapping_mismatch"
    EVIDENCE_INCOMPLETE = "evidence_incomplete"


class WritebackContractError(ValueError):
    """Fixed code only; validation detail stays internal."""

    def __init__(self, code: WritebackErrorCode) -> None:
        self.code = WritebackErrorCode(code)
        super().__init__(self.code.value)

    def __str__(self) -> str:  # pragma: no cover - defensive, mirrors code
        return self.code.value


def _digest(value: object) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _opaque_reference(value: str, field_name: str) -> str:
    """References identify existing owners; they never carry URLs or credentials."""

    if _SECRETISH.search(value) or _SECRET_WORDS.search(value):
        raise ValueError(f"{field_name} must be an opaque reference, not a URL or credential")
    return value


def _records(model: ContractModel) -> dict:  # type: ignore[type-arg]
    return model.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Adapter capability and readiness
# ---------------------------------------------------------------------------


class WritebackAdapterCapability(ContractModel):
    """What an adapter claims it can do. Claims do not grant invocation authority."""

    adapter_type: Identifier
    adapter_version: Identifier
    capabilities: frozenset[Capability]
    native_idempotency: Literal["supported", "unsupported", "unknown"]
    preconditions: frozenset[PreconditionKind] = frozenset()
    acknowledgement: Literal["sync_result", "accepted_only", "unknown"]
    response_schema_digest: Digest
    max_request_bytes: int = Field(default=262_144, ge=2, le=4_194_304, strict=True)

    @model_validator(mode="after")
    def writeback_capable(self) -> WritebackAdapterCapability:
        if "writeback" not in self.capabilities:
            raise ValueError("An adapter without the writeback capability cannot mutate a target")
        return self

    def digest(self) -> str:
        return _digest(_records(self))


class WritebackReadiness(ContractModel):
    """Adapter readiness observed by its owner; failure blocks instead of falling back."""

    status: Literal["ready", "degraded", "unavailable", "unknown"]
    reason: WritebackErrorCode | None = None
    evidence_ref: Identifier | None = None
    checked_at: AwareDatetime

    @model_validator(mode="after")
    def coherent_readiness(self) -> WritebackReadiness:
        if self.status == "ready" and self.reason is not None:
            raise ValueError("Ready readiness cannot carry a failure reason")
        if self.status != "ready" and self.reason is None:
            raise ValueError("Non-ready readiness requires a reason code")
        return self

    def require_ready(self) -> None:
        if self.status != "ready":
            raise WritebackContractError(WritebackErrorCode.ADAPTER_NOT_READY)


# ---------------------------------------------------------------------------
# Target definition
# ---------------------------------------------------------------------------


class WritebackTargetSpec(ContractModel):
    """Adapter-bound target definition. It references credentials; it never holds them."""

    tenant_id: Identifier
    adapter_type: Identifier
    adapter_version: Identifier
    connector_id: Identifier
    resource_kind: Identifier
    remote_authority: Identifier = Field(repr=False)
    credential_handle_ref: Identifier = Field(repr=False)
    egress_policy_ref: Identifier
    operations: frozenset[OperationKind]
    capability: WritebackAdapterCapability
    display_name: Identifier

    @field_validator("remote_authority")
    @classmethod
    def valid_authority(cls, value: str) -> str:
        if not _AUTHORITY.match(value):
            raise ValueError("remote_authority must be a bare lowercase host with an optional port")
        return value

    @field_validator("credential_handle_ref", "egress_policy_ref")
    @classmethod
    def opaque_references(cls, value: str, info) -> str:  # type: ignore[no-untyped-def]
        return _opaque_reference(value, info.field_name)

    @field_validator("adapter_version")
    @classmethod
    def supported_adapter_version(cls, value: str) -> str:
        if value not in SUPPORTED_ADAPTER_VERSIONS:
            raise ValueError("Unsupported adapter version")
        return value

    @model_validator(mode="after")
    def coherent_target(self) -> WritebackTargetSpec:
        if not self.operations:
            raise ValueError("A writeback target must declare at least one operation")
        if (self.adapter_type, self.adapter_version) != (
            self.capability.adapter_type,
            self.capability.adapter_version,
        ):
            raise ValueError("Target and adapter capability must agree on adapter type and version")
        if self.adapter_type != ADAPTER_TYPE_REST_MUTATION:
            raise ValueError("Only the registered REST mutation adapter is supported")
        return self

    def digest(self) -> str:
        return _digest(_records(self))

    def public_metadata(self, readiness: WritebackReadiness) -> WritebackTargetPublicMetadata:
        """Operator/app-authoring projection: no endpoint, path, or credential reference."""

        return WritebackTargetPublicMetadata(
            connector_id=self.connector_id,
            resource_kind=self.resource_kind,
            adapter_type=self.adapter_type,
            adapter_version=self.adapter_version,
            display_name=self.display_name,
            operations=tuple(sorted(self.operations)),
            acknowledgement=self.capability.acknowledgement,
            native_idempotency=self.capability.native_idempotency,
            preconditions=tuple(sorted(self.capability.preconditions)),
            readiness_status=readiness.status,
            readiness_reason=readiness.reason,
        )


class WritebackTargetPublicMetadata(ContractModel):
    connector_id: Identifier
    resource_kind: Identifier
    adapter_type: Identifier
    adapter_version: Identifier
    display_name: Identifier
    operations: tuple[OperationKind, ...]
    acknowledgement: Literal["sync_result", "accepted_only", "unknown"]
    native_idempotency: Literal["supported", "unsupported", "unknown"]
    preconditions: tuple[PreconditionKind, ...]
    readiness_status: Literal["ready", "degraded", "unavailable", "unknown"]
    readiness_reason: WritebackErrorCode | None = None


class WritebackTargetRecord(ContractModel):
    """Immutable, tenant-bound, append-only version record."""

    tenant_id: Identifier
    target_ref: Identifier
    version: int = Field(ge=1, strict=True)
    state: Literal["enabled", "disabled"]
    spec: WritebackTargetSpec
    spec_digest: Digest
    adapter_capability_digest: Digest
    registered_at: AwareDatetime

    def digest(self) -> str:
        return _digest(_records(self))


# ---------------------------------------------------------------------------
# Operation mapping
# ---------------------------------------------------------------------------


class WritebackParameterBinding(ContractModel):
    action_input_field: Identifier
    remote_field: Identifier
    value_type: Literal["string", "integer", "number", "boolean", "object", "array"]
    required: bool = True

    @model_validator(mode="after")
    def no_transport_escape(self) -> WritebackParameterBinding:
        if (
            self.action_input_field in _FORBIDDEN_BINDINGS
            or self.remote_field in _FORBIDDEN_BINDINGS
        ):
            raise ValueError("Mappings cannot bind transport or raw payload fields")
        return self


class WritebackProtectedHeader(ContractModel):
    """Header names are allowlisted and values are host-derived, never caller-supplied."""

    name: ProtectedHeaderName
    value_source: HeaderValueSource

    @model_validator(mode="after")
    def known_header(self) -> WritebackProtectedHeader:
        if self.name not in _ALLOWED_HEADERS:
            raise ValueError("Unsupported protected header")
        return self


class WritebackRequestTemplate(ContractModel):
    method: MutationMethod
    path_template: str = Field(min_length=1, max_length=1_024)
    protected_headers: tuple[WritebackProtectedHeader, ...] = ()
    max_request_bytes: int = Field(default=65_536, ge=2, le=4_194_304, strict=True)

    @field_validator("path_template")
    @classmethod
    def relative_path_only(cls, value: str) -> str:
        if (
            not value.startswith("/")
            or "//" in value
            or ".." in value
            or "?" in value
            or "#" in value
        ):
            raise ValueError("path_template must be an absolute path with no traversal or query")
        return value

    @model_validator(mode="after")
    def single_header_use(self) -> WritebackRequestTemplate:
        names = [header.name for header in self.protected_headers]
        if len(names) != len(set(names)):
            raise ValueError("A protected header can only be declared once")
        return self


class WritebackResponseMapping(ContractModel):
    """Bounded remote response projection; bodies are digested, never retained."""

    remote_id_field: Identifier
    remote_version_field: Identifier | None = None
    receipt_field: Identifier | None = None
    correlation_field: Identifier | None = None
    reason_code_field: Identifier | None = None
    max_response_bytes: int = Field(default=262_144, ge=2, le=4_194_304, strict=True)


class WritebackOperationMapping(ContractModel):
    mapping_ref: Identifier
    version: int = Field(ge=1, strict=True)
    action_id: Identifier
    action_input_schema_digest: Digest
    resource_kind: Identifier
    operation_kind: OperationKind
    bindings: tuple[WritebackParameterBinding, ...] = Field(min_length=1, max_length=64)
    request: WritebackRequestTemplate
    response: WritebackResponseMapping
    precondition_kind: PreconditionKind | None = None
    approved_by: Identifier

    @model_validator(mode="after")
    def coherent_mapping(self) -> WritebackOperationMapping:
        if self.operation_kind == "delete" and self.request.method != "DELETE":
            raise ValueError("Delete mappings must use DELETE")
        if self.operation_kind == "upsert" and self.request.method == "DELETE":
            raise ValueError("Upsert mappings cannot use DELETE")
        placeholders = set(_PLACEHOLDER.findall(self.request.path_template))
        remote_fields = [binding.remote_field for binding in self.bindings]
        if not placeholders <= set(remote_fields):
            raise ValueError("Every path placeholder must name a declared remote field")
        if self.operation_kind == "delete" and set(remote_fields) != placeholders:
            raise ValueError("Delete mappings may only bind path parameters")
        fields = [binding.action_input_field for binding in self.bindings]
        if len(fields) != len(set(fields)):
            raise ValueError("A mapped action input field cannot appear twice")
        if len(remote_fields) != len(set(remote_fields)):
            raise ValueError("A remote field cannot be bound twice")
        if _PLACEHOLDER.sub("", self.request.path_template).count("{"):
            raise ValueError("path_template contains an unsupported placeholder")
        return self

    def digest(self) -> str:
        return _digest(_records(self))


# ---------------------------------------------------------------------------
# Host context and evidence
# ---------------------------------------------------------------------------


class WritebackEgressEvidence(ContractModel):
    """Host evaluation of the exact resolved target, not of a declared profile."""

    policy_id: Identifier
    resolved_authority: Identifier = Field(repr=False)
    decision: Literal["allowed"]
    evaluated_at: AwareDatetime


class WritebackExecutionContext(ContractModel):
    """Host-bound facts rechecked before I/O. Constructing this model authorizes nothing."""

    tenant_id: Identifier
    actor_id: Identifier
    action_id: Identifier
    approval_id: Identifier
    approved_payload_digest: Digest
    credential_handle_ref: Identifier = Field(repr=False)
    credential_lease_ref: Identifier | None = Field(default=None, repr=False)
    egress: WritebackEgressEvidence
    target_ref: Identifier
    mapping_ref: Identifier
    idempotency_key_digest: Digest
    correlation_id: Identifier
    requested_at: AwareDatetime


class WritebackResourceRef(ContractModel):
    resource_kind: Identifier
    remote_id: Identifier = Field(repr=False)
    remote_version: Identifier | None = None


class WritebackPrecondition(ContractModel):
    kind: PreconditionKind
    remote_version: Identifier | None = None
    expected_digest: Digest | None = None

    @model_validator(mode="after")
    def coherent_precondition(self) -> WritebackPrecondition:
        if self.kind in {"if_match", "if_none_match"} and self.remote_version is None:
            raise ValueError("A version precondition requires a remote version reference")
        if self.kind in {"must_exist", "must_not_exist"} and self.remote_version is not None:
            raise ValueError("An existence precondition cannot carry a version reference")
        return self


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


class WritebackIdempotencyPlan(ContractModel):
    """Honest idempotency: absence of native support is stated, never assumed away."""

    mode: Literal["native_key", "native_key_and_precondition", "none"]
    key_source: Literal["host_derived_digest", "none"]
    repeat_safe: bool
    exactly_once: bool
    outcome_unknown_after_timeout: bool


class WritebackRemoteRequest(ContractModel):
    method: MutationMethod
    authority: Identifier = Field(repr=False)
    path: str = Field(repr=False)
    protected_headers: tuple[ProtectedHeaderName, ...]
    body: tuple[tuple[Identifier, JsonValue], ...] = Field(default=(), repr=False)
    body_digest: Digest

    @model_validator(mode="after")
    def delete_has_no_body(self) -> WritebackRemoteRequest:
        if self.method == "DELETE" and self.body:
            raise ValueError("Delete requests cannot carry a replacement body")
        return self

    def byte_size(self) -> int:
        return len(
            json.dumps(
                dict(self.body),
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )


class WritebackRequestPlan(ContractModel):
    """The complete, already-approved remote operation. Not a public-safe record."""

    contract_version: Literal["1.0"] = CONTRACT_VERSION
    tenant_id: Identifier
    actor_id: Identifier
    action_id: Identifier
    approval_id: Identifier
    target_ref: Identifier
    target_version: int = Field(ge=1, strict=True)
    mapping_ref: Identifier
    mapping_version: int = Field(ge=1, strict=True)
    capability_digest: Digest
    operation_kind: OperationKind
    resource: WritebackResourceRef
    precondition: WritebackPrecondition | None = None
    idempotency: WritebackIdempotencyPlan
    request: WritebackRemoteRequest
    response: WritebackResponseMapping
    plan_digest: Digest
    prepared_at: AwareDatetime

    def digest(self) -> str:
        return self.plan_digest

    def evidence(self) -> WritebackEvidence:
        """Audit-safe projection: counts, digests and codes only."""

        return WritebackEvidence(
            tenant_id=self.tenant_id,
            actor_id=self.actor_id,
            action_id=self.action_id,
            approval_id=self.approval_id,
            target_ref=self.target_ref,
            target_version=self.target_version,
            mapping_ref=self.mapping_ref,
            mapping_version=self.mapping_version,
            operation_kind=self.operation_kind,
            plan_digest=self.plan_digest,
            request_body_digest=self.request.body_digest,
            idempotency_mode=self.idempotency.mode,
            request_bytes=self.request.byte_size(),
        )


class WritebackEvidence(ContractModel):
    tenant_id: Identifier
    actor_id: Identifier
    action_id: Identifier
    approval_id: Identifier
    target_ref: Identifier
    target_version: int = Field(ge=1, strict=True)
    mapping_ref: Identifier
    mapping_version: int = Field(ge=1, strict=True)
    operation_kind: OperationKind
    plan_digest: Digest
    request_body_digest: Digest
    idempotency_mode: Literal["native_key", "native_key_and_precondition", "none"]
    request_bytes: int = Field(ge=0, strict=True)


# ---------------------------------------------------------------------------
# Outcome normalization (#511 states, #512 conflict evidence)
# ---------------------------------------------------------------------------


class RemoteOutcome(ContractModel):
    """What the transport observed. Bodies are digested, never carried."""

    transport: Literal["not_sent", "sent"]
    response_status: int | None = Field(default=None, ge=100, le=599, strict=True)
    response_body_digest: Digest | None = None
    remote_request_id: Identifier | None = None
    remote_correlation_id: Identifier | None = None

    @model_validator(mode="after")
    def coherent_outcome(self) -> RemoteOutcome:
        if self.transport == "not_sent" and self.response_status is not None:
            raise ValueError("A request that was not sent cannot have a response status")
        if self.transport == "sent" and self.response_status is None:
            raise ValueError("A sent request must report a response status")
        return self


class WritebackAcknowledgement(ContractModel):
    """The remote accepted or refused to process the request; not a business result."""

    accepted: bool
    remote_request_id: Identifier | None = None
    remote_correlation_id: Identifier | None = None
    remote_version: Identifier | None = None


class WritebackConflictEvidence(ContractModel):
    """#512 owns resolution; this contract only names the conflict."""

    kind: Literal["precondition_failed", "version_mismatch", "idempotency_replay"]
    remote_version: Identifier | None = None
    observed_digest: Digest | None = None


class WritebackBusinessResult(ContractModel):
    """Normalized business outcome, not a remote acknowledgement.

    ``source_verification`` is only ever advanced by a later
    ``WritebackSourceVerification`` observation; accepting a request never
    implies the change is visible in the source.
    """

    state: ResultState
    reason_code: WritebackErrorCode | None = None
    acknowledgement: WritebackAcknowledgement | None = None
    conflict: WritebackConflictEvidence | None = None
    remote_receipt_ref: Identifier | None = Field(default=None, repr=False)
    source_verification: VerificationState = "pending"

    @model_validator(mode="after")
    def coherent_result(self) -> WritebackBusinessResult:
        if self.state == "succeeded" and self.conflict is not None:
            raise ValueError("A succeeded result cannot carry conflict evidence")
        if self.state == "conflict" and self.conflict is None:
            raise ValueError("A conflict result must carry conflict evidence")
        if (
            self.state in {"not_sent", "outcome_unknown"}
            and self.source_verification == "confirmed"
        ):
            raise ValueError("Unresolved remote state cannot be confirmed in the source")
        if self.state == "succeeded" and self.source_verification == "contradicted":
            raise ValueError("A rejected source verification contradicts a succeeded result")
        return self


class WritebackSourceVerification(ContractModel):
    """Later source-of-truth check. It is never implied by a remote acknowledgement."""

    state: VerificationState
    basis: Literal["source_observation", "unavailable"]
    observed_at: AwareDatetime | None = None
    observation_ref: Identifier | None = None
    observed_digest: Digest | None = None

    @model_validator(mode="after")
    def coherent_verification(self) -> WritebackSourceVerification:
        if self.state == "pending" and self.basis != "unavailable":
            raise ValueError("Pending verification cannot already carry an observation basis")
        if self.state != "pending" and (self.observed_at is None or self.observation_ref is None):
            raise ValueError("Decided verification requires an observation timestamp and reference")
        return self


def normalize_remote_outcome(
    outcome: RemoteOutcome,
    *,
    idempotency: WritebackIdempotencyPlan,
    precondition: WritebackPrecondition | None = None,
) -> WritebackBusinessResult:
    """Map one transport observation to a normalized state without echoing a body."""

    if outcome.transport == "not_sent":
        return WritebackBusinessResult(
            state="not_sent",
            acknowledgement=WritebackAcknowledgement(accepted=False),
            source_verification="pending",
        )

    status = outcome.response_status or 0
    acknowledgement = WritebackAcknowledgement(
        accepted=status < 500,
        remote_request_id=outcome.remote_request_id,
        remote_correlation_id=outcome.remote_correlation_id,
    )
    if status in {409, 412}:
        return WritebackBusinessResult(
            state="conflict",
            reason_code=WritebackErrorCode.REMOTE_CONFLICT,
            acknowledgement=acknowledgement,
            conflict=WritebackConflictEvidence(
                kind="precondition_failed" if precondition is not None else "idempotency_replay",
                remote_version=precondition.remote_version if precondition else None,
                observed_digest=outcome.response_body_digest,
            ),
        )
    if status == 408 or status in {425, 429, 500, 502, 503, 504}:
        # Sending happened (or its success is unobservable). Without native
        # idempotency the remote may or may not have applied the mutation, so
        # this is explicitly not "failed and safe to repeat".
        return WritebackBusinessResult(
            state="outcome_unknown",
            reason_code=WritebackErrorCode.REMOTE_OUTCOME_UNKNOWN,
            acknowledgement=acknowledgement,
            source_verification="pending",
        )
    if 200 <= status < 300:
        return WritebackBusinessResult(state="succeeded", acknowledgement=acknowledgement)
    return WritebackBusinessResult(
        state="rejected",
        reason_code=WritebackErrorCode.REMOTE_REJECTED,
        acknowledgement=acknowledgement,
        source_verification="pending",
    )


# ---------------------------------------------------------------------------
# Registry: tenant-bound, versioned, explicitly enabled
# ---------------------------------------------------------------------------


class WritebackTargetCatalog(ContractModel):
    """Public-safe authoring projection of the enabled targets of one tenant."""

    tenant_id: Identifier
    surface: Literal["writeback-targets"] = PUBLIC_SURFACE
    targets: tuple[WritebackTargetPublicMetadata, ...]


class WritebackAdapterRegistration(ContractModel):
    """Adapter lifecycle entry: capability, current readiness and earned scope."""

    tenant_id: Identifier
    adapter_type: Identifier
    adapter_version: Identifier
    capability: WritebackAdapterCapability
    readiness: WritebackReadiness
    conformance_scope: Literal["contract_only", "local_wire_level", "provider_verified"]
    registered_at: AwareDatetime


class WritebackActionBinding(ContractModel):
    """Registry association answering which target an approved typed action writes to."""

    tenant_id: Identifier
    action_id: Identifier
    action_input_schema_digest: Digest
    target_ref: Identifier
    mapping_ref: Identifier
    mapping_version: int = Field(ge=1, strict=True)
    approved_by: Identifier
    enabled: bool = True


class WritebackTargetRegistry:
    """Tenant-bound registry: definitions are append-only, activation is explicit.

    The registry stores no secret material. Targets reference credential handles,
    leases and egress policies owned by their existing modules, and resolution
    rechecks those references instead of caching an authorization decision.
    """

    def __init__(self, tenant_id: str) -> None:
        self._tenant_id = tenant_id
        self._adapters: dict[tuple[str, str], WritebackAdapterRegistration] = {}
        self._records: dict[tuple[str, int], WritebackTargetRecord] = {}
        self._latest: dict[str, int] = {}
        self._enabled: dict[str, int] = {}
        self._mappings: dict[tuple[str, int], WritebackOperationMapping] = {}
        self._bindings: dict[str, WritebackActionBinding] = {}

    @property
    def tenant_id(self) -> str:
        return self._tenant_id

    def require_tenant(self, tenant_id: str) -> None:
        if tenant_id != self._tenant_id:
            raise WritebackContractError(WritebackErrorCode.TENANT_MISMATCH)

    def register_adapter(
        self, registration: WritebackAdapterRegistration
    ) -> WritebackAdapterRegistration:
        self.require_tenant(registration.tenant_id)
        key = (registration.adapter_type, registration.adapter_version)
        if key in self._adapters:
            raise WritebackContractError(WritebackErrorCode.INVALID_CONTRACT)
        self._adapters[key] = registration
        return registration

    def adapter(self, adapter_type: str, adapter_version: str) -> WritebackAdapterRegistration:
        registration = self._adapters.get((adapter_type, adapter_version))
        if registration is None:
            raise WritebackContractError(WritebackErrorCode.ADAPTER_NOT_READY)
        return registration

    def register_target(
        self, target_ref: str, spec: WritebackTargetSpec, *, registered_at: datetime
    ) -> WritebackTargetRecord:
        self.require_tenant(spec.tenant_id)
        registration = self._adapters.get((spec.adapter_type, spec.adapter_version))
        if registration is None or registration.capability.digest() != spec.capability.digest():
            raise WritebackContractError(WritebackErrorCode.INVALID_TARGET)
        version = self._latest.get(target_ref, 0) + 1
        record = WritebackTargetRecord(
            tenant_id=spec.tenant_id,
            target_ref=target_ref,
            version=version,
            state="disabled",
            spec=spec,
            spec_digest=spec.digest(),
            adapter_capability_digest=registration.capability.digest(),
            registered_at=registered_at,
        )
        self._records[(target_ref, version)] = record
        self._latest[target_ref] = version
        return record

    def set_enabled(self, target_ref: str, version: int, *, enabled: bool) -> WritebackTargetRecord:
        record = self._records.get((target_ref, version))
        if record is None:
            raise WritebackContractError(WritebackErrorCode.TARGET_UNKNOWN)
        updated = record.model_copy(update={"state": "enabled" if enabled else "disabled"})
        self._records[(target_ref, version)] = updated
        if enabled:
            self._enabled[target_ref] = version
        elif self._enabled.get(target_ref) == version:
            del self._enabled[target_ref]
        return updated

    def register_mapping(self, mapping: WritebackOperationMapping) -> WritebackOperationMapping:
        key = (mapping.mapping_ref, mapping.version)
        if key in self._mappings:
            raise WritebackContractError(WritebackErrorCode.INVALID_OPERATION_MAPPING)
        self._mappings[key] = mapping
        return mapping

    def register_action_binding(self, binding: WritebackActionBinding) -> WritebackActionBinding:
        self.require_tenant(binding.tenant_id)
        mapping = self._mappings.get((binding.mapping_ref, binding.mapping_version))
        if mapping is None:
            raise WritebackContractError(WritebackErrorCode.MAPPING_UNKNOWN)
        if mapping.action_id != binding.action_id:
            raise WritebackContractError(WritebackErrorCode.INVALID_OPERATION_MAPPING)
        if mapping.action_input_schema_digest != binding.action_input_schema_digest:
            raise WritebackContractError(WritebackErrorCode.MAPPING_SCHEMA_MISMATCH)
        self._bindings[binding.action_id] = binding
        return binding

    def action_binding(self, action_id: str) -> WritebackActionBinding:
        binding = self._bindings.get(action_id)
        if binding is None or not binding.enabled:
            raise WritebackContractError(WritebackErrorCode.MAPPING_UNKNOWN)
        return binding

    def mapping(self, mapping_ref: str, version: int) -> WritebackOperationMapping:
        mapping = self._mappings.get((mapping_ref, version))
        if mapping is None:
            raise WritebackContractError(WritebackErrorCode.MAPPING_UNKNOWN)
        return mapping

    def record(self, target_ref: str, version: int) -> WritebackTargetRecord:
        record = self._records.get((target_ref, version))
        if record is None:
            raise WritebackContractError(WritebackErrorCode.TARGET_UNKNOWN)
        return record

    def enabled_record(self, target_ref: str) -> WritebackTargetRecord:
        version = self._enabled.get(target_ref)
        if version is None:
            if target_ref not in self._latest:
                raise WritebackContractError(WritebackErrorCode.TARGET_UNKNOWN)
            raise WritebackContractError(WritebackErrorCode.TARGET_DISABLED)
        return self.record(target_ref, version)

    def catalog(self) -> WritebackTargetCatalog:
        """Public-safe authoring projection; enabled targets only, readiness included."""

        targets = []
        for target_ref in sorted(self._enabled):
            record = self.enabled_record(target_ref)
            registration = self.adapter(record.spec.adapter_type, record.spec.adapter_version)
            targets.append(record.spec.public_metadata(registration.readiness))
        return WritebackTargetCatalog(tenant_id=self._tenant_id, targets=tuple(targets))

    def resolve(
        self,
        action: ActionDefinition,
        action_input: object,
        context: WritebackExecutionContext,
        *,
        prepared_at: datetime,
    ) -> WritebackRequestPlan:
        return resolve_writeback_plan(
            self, action=action, action_input=action_input, context=context, prepared_at=prepared_at
        )


def _schema_fields(schema: object) -> tuple[set[str], set[str]]:
    if not isinstance(schema, dict):
        raise WritebackContractError(WritebackErrorCode.MAPPING_SCHEMA_MISMATCH)
    properties = schema.get("properties")
    required = schema.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise WritebackContractError(WritebackErrorCode.MAPPING_SCHEMA_MISMATCH)
    if not all(isinstance(name, str) for name in required) or not all(
        isinstance(name, str) for name in properties
    ):
        raise WritebackContractError(WritebackErrorCode.MAPPING_SCHEMA_MISMATCH)
    return set(properties), set(required)


def _idempotency_plan(
    capability: WritebackAdapterCapability, *, has_precondition: bool
) -> WritebackIdempotencyPlan:
    """Unsupported remote idempotency is stated plainly; it is never an exactly-once claim."""

    if capability.native_idempotency == "supported":
        return WritebackIdempotencyPlan(
            mode="native_key_and_precondition" if has_precondition else "native_key",
            key_source="host_derived_digest",
            repeat_safe=True,
            exactly_once=True,
            outcome_unknown_after_timeout=False,
        )
    return WritebackIdempotencyPlan(
        mode="none",
        key_source="none",
        repeat_safe=False,
        exactly_once=False,
        outcome_unknown_after_timeout=True,
    )


def resolve_writeback_plan(
    registry: WritebackTargetRegistry,
    *,
    action: ActionDefinition,
    action_input: object,
    context: WritebackExecutionContext,
    prepared_at: datetime,
) -> WritebackRequestPlan:
    """Recheck every host fact and return one already-approved remote operation.

    Nothing here performs I/O: binding, lease, egress, readiness, mapping,
    approval payload and size are all validated before any transport exists.
    """

    action_id = action.action_id
    input_schema = action.input_schema
    registry.require_tenant(context.tenant_id)
    if action_id != context.action_id:
        raise WritebackContractError(WritebackErrorCode.INVALID_ACTION_INPUT)
    binding = registry.action_binding(action_id)
    properties, required_fields = _schema_fields(input_schema)
    if _digest(input_schema) != binding.action_input_schema_digest:
        raise WritebackContractError(WritebackErrorCode.MAPPING_SCHEMA_MISMATCH)

    record = registry.enabled_record(binding.target_ref)
    mapping = registry.mapping(binding.mapping_ref, binding.mapping_version)
    registration = registry.adapter(record.spec.adapter_type, record.spec.adapter_version)
    if registration.capability.digest() != record.adapter_capability_digest:
        raise WritebackContractError(WritebackErrorCode.ADAPTER_NOT_READY)
    registration.readiness.require_ready()

    spec = record.spec
    capability = registration.capability
    if mapping.resource_kind != spec.resource_kind:
        raise WritebackContractError(WritebackErrorCode.INVALID_OPERATION_MAPPING)
    if mapping.operation_kind not in spec.operations:
        raise WritebackContractError(WritebackErrorCode.UNSUPPORTED_OPERATION)
    if (
        mapping.precondition_kind is not None
        and mapping.precondition_kind not in capability.preconditions
    ):
        raise WritebackContractError(WritebackErrorCode.UNSUPPORTED_PRECONDITION)
    if context.credential_lease_ref is None:
        raise WritebackContractError(WritebackErrorCode.CREDENTIAL_LEASE_REQUIRED)
    if context.credential_handle_ref != spec.credential_handle_ref:
        raise WritebackContractError(WritebackErrorCode.CREDENTIAL_REFERENCE_MISMATCH)
    if context.egress.policy_id != spec.egress_policy_ref:
        raise WritebackContractError(WritebackErrorCode.EGRESS_NOT_EVALUATED)
    if context.egress.resolved_authority != spec.remote_authority:
        raise WritebackContractError(WritebackErrorCode.EGRESS_TARGET_MISMATCH)
    header_names = {header.name for header in mapping.request.protected_headers}
    if capability.native_idempotency == "supported" and "idempotency-key" not in header_names:
        raise WritebackContractError(WritebackErrorCode.INVALID_OPERATION_MAPPING)

    if not isinstance(action_input, dict):
        raise WritebackContractError(WritebackErrorCode.INVALID_ACTION_INPUT)
    bound_fields = {binding_.action_input_field for binding_ in mapping.bindings}
    if not set(action_input) <= properties or not set(action_input) <= bound_fields:
        raise WritebackContractError(WritebackErrorCode.INVALID_ACTION_INPUT)
    if required_fields - bound_fields:
        raise WritebackContractError(WritebackErrorCode.MAPPING_SCHEMA_MISMATCH)
    if any(
        binding_.required and binding_.action_input_field not in action_input
        for binding_ in mapping.bindings
    ):
        raise WritebackContractError(WritebackErrorCode.INVALID_ACTION_INPUT)

    remote_values = {
        binding_.remote_field: action_input[binding_.action_input_field]
        for binding_ in mapping.bindings
        if binding_.action_input_field in action_input
    }

    def _substitute(match: re.Match[str]) -> str:
        value = remote_values.get(match.group(1))
        if not isinstance(value, str) or not _PATH_SEGMENT.match(value):
            raise WritebackContractError(WritebackErrorCode.INVALID_ACTION_INPUT)
        return value

    path = _PLACEHOLDER.sub(_substitute, mapping.request.path_template)
    remote_id = remote_values.get(mapping.response.remote_id_field)
    if not isinstance(remote_id, str) or not remote_id:
        raise WritebackContractError(WritebackErrorCode.RESOURCE_PRECONDITION_MISSING)
    remote_version = (
        remote_values.get(mapping.response.remote_version_field)
        if mapping.response.remote_version_field
        else None
    )
    precondition = None
    if mapping.precondition_kind is not None:
        if mapping.precondition_kind in {"if_match", "if_none_match"}:
            if not isinstance(remote_version, str) or not remote_version:
                raise WritebackContractError(WritebackErrorCode.RESOURCE_PRECONDITION_MISSING)
            precondition = WritebackPrecondition(
                kind=mapping.precondition_kind, remote_version=remote_version
            )
        else:
            precondition = WritebackPrecondition(kind=mapping.precondition_kind)

    identifier_fields = {mapping.response.remote_id_field}
    if mapping.response.remote_version_field:
        identifier_fields.add(mapping.response.remote_version_field)
    body: tuple[tuple[str, JsonValue], ...] = (
        ()
        if mapping.operation_kind == "delete"
        else tuple(
            sorted(
                (field, value)
                for field, value in remote_values.items()
                if field not in identifier_fields
            )
        )
    )
    request = WritebackRemoteRequest(
        method=mapping.request.method,
        authority=spec.remote_authority,
        path=path,
        protected_headers=tuple(header.name for header in mapping.request.protected_headers),
        body=body,
        body_digest=_digest(dict(body)),
    )
    if precondition is not None and body:
        # Bind the precondition to the exact approved replacement payload.
        precondition = precondition.model_copy(update={"expected_digest": request.body_digest})
    if request.byte_size() > min(mapping.request.max_request_bytes, capability.max_request_bytes):
        raise WritebackContractError(WritebackErrorCode.REQUEST_TOO_LARGE)

    plan_digest = compute_plan_digest(
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        action_id=action_id,
        approval_id=context.approval_id,
        target_ref=record.target_ref,
        target_version=record.version,
        spec_digest=record.spec_digest,
        mapping=mapping,
        resource_kind=spec.resource_kind,
        remote_id=remote_id,
        precondition=precondition,
        method=request.method,
        path=request.path,
        body_digest=request.body_digest,
    )
    if plan_digest != context.approved_payload_digest:
        raise WritebackContractError(WritebackErrorCode.APPROVAL_PAYLOAD_MISMATCH)

    return WritebackRequestPlan(
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        action_id=action_id,
        approval_id=context.approval_id,
        target_ref=record.target_ref,
        target_version=record.version,
        mapping_ref=mapping.mapping_ref,
        mapping_version=mapping.version,
        capability_digest=capability.digest(),
        operation_kind=mapping.operation_kind,
        resource=WritebackResourceRef(
            resource_kind=spec.resource_kind, remote_id=remote_id, remote_version=remote_version
        ),
        precondition=precondition,
        idempotency=_idempotency_plan(capability, has_precondition=precondition is not None),
        request=request,
        response=mapping.response,
        plan_digest=plan_digest,
        prepared_at=prepared_at,
    )


def compute_plan_digest(
    *,
    tenant_id: str,
    actor_id: str,
    action_id: str,
    approval_id: str,
    target_ref: str,
    target_version: int,
    spec_digest: str,
    mapping: WritebackOperationMapping,
    resource_kind: str,
    remote_id: str,
    precondition: WritebackPrecondition | None,
    method: str,
    path: str,
    body_digest: str,
) -> str:
    """Canonical digest of the exact approved operation; the host owns the approval."""

    return _digest(
        {
            "contract_version": CONTRACT_VERSION,
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "action_id": action_id,
            "approval_id": approval_id,
            "target_ref": target_ref,
            "target_version": target_version,
            "spec_digest": spec_digest,
            "mapping_ref": mapping.mapping_ref,
            "mapping_version": mapping.version,
            "mapping_digest": mapping.digest(),
            "operation_kind": mapping.operation_kind,
            "resource": {"resource_kind": resource_kind, "remote_id": remote_id},
            "precondition": precondition.model_dump(mode="json") if precondition else None,
            "method": method,
            "path": path,
            "body_digest": body_digest,
        }
    )


# ---------------------------------------------------------------------------
# Adapter lifecycle conformance
# ---------------------------------------------------------------------------

ConformanceCheck = Literal[
    "writeback_capability",
    "idempotency_declaration",
    "precondition_support",
    "response_mapping_bounded",
    "result_mapping",
    "error_taxonomy",
]


class WritebackConformanceObservation(ContractModel):
    """One observed remote case and the normalized state its owner claims it maps to."""

    case: Literal["success", "validation_error", "conflict", "timeout_after_send", "not_sent"]
    outcome: RemoteOutcome
    expected_state: ResultState
    expected_reason: WritebackErrorCode | None = None


class WritebackConformanceFinding(ContractModel):
    check: ConformanceCheck
    status: Literal["passed", "failed", "not_run"]
    reason: WritebackErrorCode | None = None


class WritebackAdapterConformanceReport(ContractModel):
    adapter_type: Identifier
    adapter_version: Identifier
    scope: Literal["contract_only", "local_wire_level", "provider_verified"]
    findings: tuple[WritebackConformanceFinding, ...]

    @property
    def passed(self) -> bool:
        return bool(self.findings) and all(finding.status == "passed" for finding in self.findings)

    def failed_checks(self) -> tuple[ConformanceCheck, ...]:
        return tuple(finding.check for finding in self.findings if finding.status == "failed")


def run_adapter_conformance(
    registration: WritebackAdapterRegistration,
    *,
    spec: WritebackTargetSpec,
    mapping: WritebackOperationMapping,
    observations: tuple[WritebackConformanceObservation, ...] = (),
) -> WritebackAdapterConformanceReport:
    """Check an adapter's declared claims against its registration and mapping.

    This is a bounded declaration check, never a live-provider certification:
    the caller states the scope it actually exercised.
    """

    capability = registration.capability
    findings: list[WritebackConformanceFinding] = []

    def _fail(check: ConformanceCheck, reason: WritebackErrorCode) -> None:
        findings.append(WritebackConformanceFinding(check=check, status="failed", reason=reason))

    if "writeback" not in capability.capabilities or mapping.operation_kind not in spec.operations:
        _fail("writeback_capability", WritebackErrorCode.ADAPTER_NOT_WRITEBACK_CAPABLE)
    else:
        findings.append(WritebackConformanceFinding(check="writeback_capability", status="passed"))

    header_names = {header.name for header in mapping.request.protected_headers}
    plan = _idempotency_plan(capability, has_precondition=mapping.precondition_kind is not None)
    if capability.native_idempotency == "supported" and "idempotency-key" not in header_names:
        _fail("idempotency_declaration", WritebackErrorCode.INVALID_OPERATION_MAPPING)
    elif capability.native_idempotency != "supported" and plan.exactly_once:
        _fail("idempotency_declaration", WritebackErrorCode.INVALID_CONTRACT)
    else:
        findings.append(
            WritebackConformanceFinding(check="idempotency_declaration", status="passed")
        )

    if (
        mapping.precondition_kind is not None
        and mapping.precondition_kind not in capability.preconditions
    ):
        _fail("precondition_support", WritebackErrorCode.UNSUPPORTED_PRECONDITION)
    else:
        findings.append(WritebackConformanceFinding(check="precondition_support", status="passed"))

    bounded = mapping.response.max_response_bytes <= 1_048_576
    version_declared = mapping.precondition_kind not in {"if_match", "if_none_match"} or bool(
        mapping.response.remote_version_field
    )
    if not bounded or not version_declared:
        _fail("response_mapping_bounded", WritebackErrorCode.INVALID_OPERATION_MAPPING)
    else:
        findings.append(
            WritebackConformanceFinding(check="response_mapping_bounded", status="passed")
        )

    if not observations:
        findings.append(WritebackConformanceFinding(check="result_mapping", status="not_run"))
        findings.append(WritebackConformanceFinding(check="error_taxonomy", status="not_run"))
    else:
        mismatched = [
            observation
            for observation in observations
            if (
                normalized := normalize_remote_outcome(
                    observation.outcome,
                    idempotency=plan,
                    precondition=WritebackPrecondition(
                        kind=mapping.precondition_kind, remote_version="observed"
                    )
                    if mapping.precondition_kind in {"if_match", "if_none_match"}
                    else None,
                )
            ).state
            != observation.expected_state
            or normalized.reason_code != observation.expected_reason
        ]
        if mismatched:
            _fail("result_mapping", WritebackErrorCode.RESULT_MAPPING_MISMATCH)
        else:
            findings.append(WritebackConformanceFinding(check="result_mapping", status="passed"))

        declared: dict[ResultState, WritebackErrorCode] = {}
        incomplete = False
        for observation in observations:
            if observation.expected_state == "succeeded":
                continue
            if observation.expected_reason is None:
                incomplete = True
                continue
            declared[observation.expected_state] = observation.expected_reason
        if incomplete:
            _fail("error_taxonomy", WritebackErrorCode.EVIDENCE_INCOMPLETE)
        elif len(set(declared.values())) != len(declared):
            _fail("error_taxonomy", WritebackErrorCode.RESULT_MAPPING_MISMATCH)
        else:
            findings.append(WritebackConformanceFinding(check="error_taxonomy", status="passed"))

    return WritebackAdapterConformanceReport(
        adapter_type=registration.adapter_type,
        adapter_version=registration.adapter_version,
        scope=registration.conformance_scope,
        findings=tuple(findings),
    )
