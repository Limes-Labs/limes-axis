"""Clean-room collaboration agreement contract: multi-party, time-bounded.

Contract slice of [#855](https://github.com/Limes-Labs/limes-axis/issues/855)
(parent #854). This module is pure vocabulary: no dataset binding, no query
engine, no compute. A clean room is a **time-bounded multi-party agreement**
whose purpose, participants and release rules are machine-visible enforcement
inputs, not free-text documentation:

* A versioned ``axis.clean-room.agreement`` envelope with strict round-trips;
  unknown fields and incompatible major versions are rejected.
* Agreement membership grants no dataset access: input bindings are absent
  from this contract and remain separately authorized by each party.
* Exactly one approval per party per revision, signed by that party's own
  organization — forging another party's approval, signing from outside the
  agreement, and single-party activation are all unrepresentable.
* Purpose, input classes, output classes, isolation profile and retention
  are typed, bounded enforcement inputs with canonical digests; material
  amendments create a new revision whose approvals start empty — nothing is
  silently carried forward.
* Expiry/suspension/termination block new computation authoritatively at
  contract level (`authorizes_execution`), regardless of session validity
  or lagging cleanup workers.
* Party removal preserves historical released-result and audit references
  by digest while refusing future use of that party's inputs.

The digest helper is shared so producers cannot sign non-canonical bytes.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

from axis_sdk.connector_authoring.contracts import ContractModel, Digest
from pydantic import Field, ValidationError, model_validator

AGREEMENT_FORMAT = "axis.clean-room.agreement"
CONTRACT_MAJOR = 1
CONTRACT_MINOR = 0

#: Supported schema versions for reading; major bumps change semantics.
SUPPORTED_MAJOR_VERSIONS = (CONTRACT_MAJOR,)

_MAX_PARTIES = 8
_MAX_PURPOSE_ITEMS = 12
_MAX_CLASSES = 16
_MAX_DATACLASSES = 32
_MAX_RETENTION_DAYS = 3_650
_MAX_REFERENCES = 8
_MAX_TEXT = 500
_MAX_TITLE = 200

_IDENTIFIER = r"^[a-z][a-z0-9-]{2,47}$"
_ORG = r"^[a-z][a-z0-9-]{2,31}$"
_DOMAIN = r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$"
_RESOURCE_PREFIX = r"^[a-z][a-z0-9._-]{2,63}$"
# Governance/handling citations are document paths (policy/..., legal/...).
_REF_PATH = r"^[a-z][a-z0-9._/-]{2,99}$"
_REF_PATH_OK = re.compile(_REF_PATH)
_REVISION = r"^\d+$"
_DATE = r"^\d{4}-\d{2}-\d{2}$"
_TIMESTAMP = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"

PartyRole = Literal[
    "data_contributor", "analyst", "result_reviewer", "administrator", "auditor"
]
AgreementState = Literal[
    "draft",
    "under_review",
    "approved_current",
    "suspended",
    "expired",
    "terminated",
    "archived",
]
AmendmentKind = Literal[
    "participants", "purpose", "output_policy", "isolation_profile", "retention", "analysis_classes"
]
ComputeMode = Literal["confidential_compute", "isolated_job", "federated_query"]
EgressMode = Literal["none", "review_gate", "aggregated_only"]


class CleanRoomError(ValueError):
    """Fixed contract codes; raw validation details are never rendered."""

    INCOMPATIBLE_VERSION = "incompatible_clean_room_contract_version"
    INVALID_AGREEMENT = "invalid_clean_room_agreement"
    FORGED_APPROVAL = "approval_not_by_party_owner"
    DUPLICATE_PARTY = "duplicate_clean_room_party"
    UNKNOWN_PARTY = "unknown_clean_room_party"
    NOT_EXECUTABLE = "agreement_not_executable"

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_clean_room_digest(value: object) -> Digest:
    """Deterministic digest over canonical JSON; producers must reuse this."""

    data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _parse_major(value: object) -> int:
    if not isinstance(value, dict):
        raise CleanRoomError(CleanRoomError.INVALID_AGREEMENT)
    version = value.get("schema_version")
    major = version.get("major") if isinstance(version, dict) else None
    if not isinstance(major, int) or isinstance(major, bool):
        raise CleanRoomError(CleanRoomError.INVALID_AGREEMENT)
    return major


class ManifestVersion(ContractModel):
    major: int = Field(ge=1, strict=True)
    minor: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def bounded_version(self) -> ManifestVersion:
        if self.major != CONTRACT_MAJOR or self.minor != CONTRACT_MINOR:
            raise ValueError(f"Unsupported clean-room contract version {self.major}.{self.minor}")
        return self


class Party(ContractModel):
    """One participating organization with accountable contacts and roles."""

    party_id: str = Field(pattern=_IDENTIFIER)
    organization: str = Field(pattern=_ORG)
    domain: str = Field(pattern=_DOMAIN)
    roles: tuple[PartyRole, ...] = Field(min_length=1, max_length=5)
    owner_contact: str = Field(min_length=3, max_length=_MAX_TEXT)
    contributes_inputs: bool = False

    @model_validator(mode="after")
    def coherent_party(self) -> Party:
        if len(set(self.roles)) != len(self.roles):
            raise CleanRoomError(CleanRoomError.DUPLICATE_PARTY)
        if "administrator" in self.roles and self.contributes_inputs:
            raise ValueError(
                "Administrators configure the workspace; they do not automatically "
                "contribute raw participant inputs"
            )
        return self


class PurposeScope(ContractModel):
    """Versioned purpose/use-case; an enforcement input, not prose."""

    intents: tuple[str, ...] = Field(min_length=1, max_length=_MAX_PURPOSE_ITEMS)
    prohibited_uses: tuple[str, ...] = Field(default=(), max_length=_MAX_PURPOSE_ITEMS)
    statement: str = Field(min_length=1, max_length=_MAX_TEXT)


class IsolationProfile(ContractModel):
    """Bounded compute/network/retention isolation of the workspace."""

    compute: ComputeMode
    egress: EgressMode
    tenant_boundary_refs: tuple[str, ...] = Field(min_length=1, max_length=8)
    retention_days: int = Field(ge=1, strict=True, le=_MAX_RETENTION_DAYS)
    requires_confidential_compute: bool = False

    @model_validator(mode="after")
    def coherent_isolation(self) -> IsolationProfile:
        if self.requires_confidential_compute and self.compute != "confidential_compute":
            raise ValueError("Confidential-compute requirement must match the compute mode")
        if self.egress == "none" and self.compute == "federated_query":
            raise ValueError("Federated queries imply at least aggregated egress")
        return self


class InputClass(ContractModel):
    """A permitted input class; actual bindings stay separately authorized."""

    class_id: str = Field(pattern=_IDENTIFIER)
    data_class: str = Field(pattern=_RESOURCE_PREFIX)
    handling_ref: str = Field(pattern=_REF_PATH)
    contributing_parties: tuple[str, ...] = Field(min_length=1, max_length=_MAX_PARTIES)


class OutputClass(ContractModel):
    """A permitted output class with its release requirement."""

    class_id: str = Field(pattern=_IDENTIFIER)
    shape: Literal["aggregate", "labelled_result", "report", "model_artifact"]
    reviewer_role: PartyRole
    min_reviewers: int = Field(default=1, ge=1, strict=True, le=4)


class PartyApproval(ContractModel):
    """One party's sign-off, signed by that party's own organization.

    Another organization recording an approval on this party's behalf is a
    construction failure; a lone party's signature can never activate the
    agreement because activation requires every party's record.
    """

    party_id: str = Field(pattern=_IDENTIFIER)
    decided_by_organization: str = Field(pattern=_ORG)
    decided_at: str = Field(pattern=_TIMESTAMP, min_length=20, max_length=40)
    authority_ref: str = Field(min_length=3, max_length=_MAX_TEXT)

    @model_validator(mode="after")
    def party_owned_signature(self) -> PartyApproval:
        if not self.authority_ref.startswith(self.decided_by_organization):
            raise CleanRoomError(CleanRoomError.FORGED_APPROVAL)
        return self


class AgreementRevision(ContractModel):
    """One clean-room agreement revision; approvals bind to this exact set."""

    format: Literal["axis.clean-room.agreement"] = AGREEMENT_FORMAT
    schema_version: ManifestVersion
    agreement_id: str = Field(pattern=_IDENTIFIER)
    revision: str = Field(pattern=_REVISION)
    title: str = Field(min_length=1, max_length=_MAX_TITLE)
    host_organization: str = Field(pattern=_ORG)
    parties: tuple[Party, ...] = Field(min_length=2, max_length=_MAX_PARTIES)
    purpose: PurposeScope
    input_classes: tuple[InputClass, ...] = Field(max_length=_MAX_DATACLASSES)
    output_classes: tuple[OutputClass, ...] = Field(min_length=1, max_length=_MAX_CLASSES)
    isolation: IsolationProfile
    valid_from: str = Field(pattern=_DATE, min_length=10, max_length=10)
    valid_until: str = Field(pattern=_DATE, min_length=10, max_length=10)
    governance_refs: tuple[str, ...] = Field(default=(), max_length=_MAX_REFERENCES)
    state: AgreementState
    approvals: tuple[PartyApproval, ...] = Field(default=(), max_length=_MAX_PARTIES)
    activated_at: str | None = Field(
        default=None, pattern=_TIMESTAMP, min_length=20, max_length=40
    )
    suspended_at: str | None = Field(
        default=None, pattern=_TIMESTAMP, min_length=20, max_length=40
    )
    terminated_at: str | None = Field(
        default=None, pattern=_TIMESTAMP, min_length=20, max_length=40
    )
    metadata_visibility: Literal["participants_only", "host_and_parties"] = (
        "participants_only"
    )

    @model_validator(mode="after")
    def coherent_agreement(self) -> AgreementRevision:
        party_ids = [party.party_id for party in self.parties]
        if len(set(party_ids)) != len(party_ids):
            raise CleanRoomError(CleanRoomError.DUPLICATE_PARTY)
        if self.host_organization not in {party.organization for party in self.parties}:
            raise ValueError("The host must itself be a party of the agreement")
        contributing = {party.party_id for party in self.parties if party.contributes_inputs}
        if not contributing:
            raise ValueError("A clean room without contributing parties is not a clean room")
        for input_class in self.input_classes:
            if not set(input_class.contributing_parties) <= contributing:
                raise CleanRoomError(CleanRoomError.UNKNOWN_PARTY)
        if any(not _REF_PATH_OK.match(ref) for ref in self.governance_refs):
            raise ValueError("Governance references are recorded document paths")
        if self.valid_until < self.valid_from:
            raise ValueError("Agreement validity end cannot precede its start")
        approvals_by_party = [approval.party_id for approval in self.approvals]
        if len(set(approvals_by_party)) != len(approvals_by_party):
            raise ValueError("Each party approves a revision at most once")
        parties_by_id = {party.party_id: party for party in self.parties}
        for approval in self.approvals:
            party = parties_by_id.get(approval.party_id)
            if party is None:
                raise CleanRoomError(CleanRoomError.UNKNOWN_PARTY)
            if approval.decided_by_organization != party.organization:
                raise CleanRoomError(CleanRoomError.FORGED_APPROVAL)
            if approval.decided_by_organization not in {
                member.organization for member in self.parties
            }:
                raise CleanRoomError(CleanRoomError.FORGED_APPROVAL)
        if self.state in {"approved_current", "suspended", "expired", "terminated", "archived"}:
            if self.activated_at is None:
                raise ValueError("An activated agreement records its activation timestamp")
            if self.valid_until < self.valid_from:
                raise ValueError("Invalid validity window")
        else:
            if self.activated_at is not None:
                raise ValueError("Only activated states record an activation timestamp")
        if self.state in {"suspended", "terminated", "archived"} and self.suspended_at is None:
            raise ValueError("Suspension/termination records when execution stopped")
        if self.state == "terminated" and self.terminated_at is None:
            raise ValueError("Termination records its timestamp")
        if self.state in {"draft", "under_review"} and (
            self.suspended_at is not None or self.terminated_at is not None
        ):
            raise ValueError("Pre-activation agreements carry no suspension/termination marks")
        return self

    def digest(self) -> Digest:
        return canonical_clean_room_digest(self.model_dump(mode="json"))

    def required_approvals(self) -> frozenset[str]:
        """Parties whose independent sign-off the revision still awaits."""

        return frozenset(
            party.party_id
            for party in self.parties
            if party.party_id not in {approval.party_id for approval in self.approvals}
        )


def agreement_readiness(agreement: AgreementRevision) -> tuple[Digest, bool, tuple[str, ...]]:
    """Exact readiness gaps before activation; deterministic, no side effects."""

    blocking: list[str] = []
    if agreement.state not in {"draft", "under_review"}:
        blocking.append("agreement_already_decided")
    missing = agreement.required_approvals()
    if missing:
        blocking.append(f"approvals_missing:{','.join(sorted(missing))}")
    if not agreement.input_classes:
        blocking.append("input_classes_undeclared")
    if agreement.isolation.requires_confidential_compute:
        blocking.append("confidential_compute_attestation_required")
    if not agreement.governance_refs:
        blocking.append("governance_references_recorded")
    return agreement.digest(), not blocking, tuple(blocking)


def activate_agreement(agreement: AgreementRevision, *, now: str) -> AgreementRevision:
    """Activate a revision only when every party approval is present."""

    if agreement.state not in {"draft", "under_review"}:
        raise CleanRoomError(CleanRoomError.NOT_EXECUTABLE)
    if agreement.required_approvals():
        raise CleanRoomError(CleanRoomError.NOT_EXECUTABLE)
    return AgreementRevision.model_validate(
        {
            **agreement.model_dump(mode="json"),
            "state": "approved_current",
            "activated_at": now,
        }
    )


def amend_agreement(
    agreement: AgreementRevision,
    changes: dict[str, object],
    *,
    kind: AmendmentKind,
) -> AgreementRevision:
    """Material amendment: new revision, approvals reset to empty.

    Participants, purpose, output policy, isolation, retention or analysis
    classes are enforcement inputs; changing any of them invalidates prior
    approvals instead of silently carrying them forward.
    """

    _MATERIAL = frozenset(
        {
            "parties",
            "purpose",
            "input_classes",
            "output_classes",
            "isolation",
            "valid_until",
            "governance_refs",
        }
    )
    if not _MATERIAL.intersection(changes):
        raise ValueError("Amendment must change at least one material term")
    if kind not in {
        "participants",
        "purpose",
        "output_policy",
        "isolation_profile",
        "retention",
        "analysis_classes",
    }:
        raise ValueError("Unknown amendment kind")
    payload = agreement.model_dump(mode="json")
    payload.update(changes)
    payload["revision"] = str(int(agreement.revision) + 1)
    payload["state"] = "draft"
    payload["approvals"] = ()
    payload["activated_at"] = None
    payload["suspended_at"] = None
    payload["terminated_at"] = None
    return AgreementRevision.model_validate(payload)


def suspend_agreement(agreement: AgreementRevision, *, now: str) -> AgreementRevision:
    """Suspend execution authoritatively even if cleanup workers lag."""

    if agreement.state != "approved_current":
        raise CleanRoomError(CleanRoomError.NOT_EXECUTABLE)
    return AgreementRevision.model_validate(
        {**agreement.model_dump(mode="json"), "state": "suspended", "suspended_at": now}
    )


def terminate_agreement(agreement: AgreementRevision, *, now: str) -> AgreementRevision:
    """Terminate the agreement; historical evidence stays referenced."""

    if agreement.state not in {"approved_current", "suspended"}:
        raise CleanRoomError(CleanRoomError.NOT_EXECUTABLE)
    payload = {**agreement.model_dump(mode="json"), "terminated_at": now}
    payload["state"] = "terminated"
    payload["suspended_at"] = payload.get("suspended_at") or now
    return AgreementRevision.model_validate(payload)


def remove_party(
    agreement: AgreementRevision, party_id: str
) -> tuple[AgreementRevision, Digest]:
    """Drop a party: future inputs refuse, historical evidence survives.

    Returns the amended revision plus the digest of the pre-amendment
    agreement, which released-result and audit records must keep citing.
    """

    remaining = tuple(
        party for party in agreement.parties if party.party_id != party_id
    )
    if len(remaining) == len(agreement.parties):
        raise CleanRoomError(CleanRoomError.UNKNOWN_PARTY)
    if len(remaining) < 2:
        raise ValueError("A clean room keeps at least two parties")
    historical_digest = agreement.digest()
    amended = amend_agreement(
        agreement,
        {
            "parties": remaining,
            "input_classes": input_classes_after_removal(agreement, party_id),
        },
        kind="participants",
    )
    return amended, historical_digest


def input_classes_after_removal(
    agreement: AgreementRevision, removed_party_id: str
) -> tuple[InputClass, ...]:
    """Input classes that remain usable after a party's removal."""

    usable: list[InputClass] = []
    for input_class in agreement.input_classes:
        contributors = tuple(
            party_id
            for party_id in input_class.contributing_parties
            if party_id != removed_party_id
        )
        if contributors:
            usable.append(
                InputClass.model_validate(
                    {**input_class.model_dump(mode="json"), "contributing_parties": contributors}
                )
            )
    return tuple(usable)


def authorizes_execution(agreement: AgreementRevision, *, on_date: str) -> bool:
    """Contract-level gate: only a current, unexpired, unsuspended agreement.

    Expiry and suspension block new computation authoritatively here —
    session validity, worker lag and cleanup state are irrelevant.
    """

    if agreement.state != "approved_current":
        return False
    return agreement.valid_from <= on_date <= agreement.valid_until


def parse_clean_room_agreement(value: object) -> AgreementRevision:
    """Parse an untrusted agreement payload with fixed safe error codes."""

    if isinstance(value, dict):
        major = _parse_major(value)
        if major not in SUPPORTED_MAJOR_VERSIONS:
            raise CleanRoomError(CleanRoomError.INCOMPATIBLE_VERSION)
    try:
        return AgreementRevision.model_validate(value)
    except ValidationError:
        raise CleanRoomError(CleanRoomError.INVALID_AGREEMENT) from None
