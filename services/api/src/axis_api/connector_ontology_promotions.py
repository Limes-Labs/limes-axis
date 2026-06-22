from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from axis_api.audit import AuditEventCreate
from axis_api.connector_ontology_proposals import ConnectorOntologyProposalRecord
from axis_api.ontology.mutations import (
    DeferredOntologyMutationRuntime,
    OntologyMutationError,
    OntologyMutationRequest,
    OntologyMutationResult,
    OntologyMutationRuntime,
    ontology_mutation_failure_result,
)
from axis_api.permissions import PermissionDecision, PermissionRequest, evaluate_permission
from axis_api.persistence import (
    AxisPersistenceRepository,
    ConnectorOntologyPromotionCreate,
    ConnectorOntologyPromotionResultRecord,
)


class ConnectorOntologyPromotionNotFound(LookupError):
    pass


class ConnectorOntologyPromotionValidationError(ValueError):
    def __init__(self, message: str, reason: str) -> None:
        super().__init__(message)
        self.message = message
        self.reason = reason


class ConnectorOntologyPromotionPermissionDenied(PermissionError):
    def __init__(self, required_permission: str, decision: PermissionDecision) -> None:
        super().__init__(decision.reason)
        self.required_permission = required_permission
        self.decision = decision


class ConnectorOntologyPromotionIdempotencyConflict(ValueError):
    def __init__(self, promotion_id: str) -> None:
        super().__init__("Idempotency key already exists with a different payload")
        self.promotion_id = promotion_id


class ConnectorOntologyPromotionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    promotion_id: str = Field(min_length=1, max_length=180, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    idempotency_key: str = Field(min_length=1, max_length=200)
    proposal_id: str = Field(min_length=1, max_length=180)
    manual_import_id: str = Field(min_length=1, max_length=180)
    actor_id: str = Field(min_length=1, max_length=160)
    actor_scopes: list[str] = Field(default_factory=list)
    promotion_mode: str = Field(default="approved_manual_import", min_length=1, max_length=80)
    note: str | None = Field(default=None, max_length=600)


class ConnectorOntologyPromotionRecord(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    promotion_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    manual_import_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    promotion_mode: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    graph_mutation_status: str = Field(min_length=1)
    ontology_mutation: OntologyMutationResult
    audit_event_id: UUID | None = None
    audit_event_type: str = Field(min_length=1)
    notes: list[str] = Field(default_factory=list)
    created_at: datetime


class ConnectorOntologyPromotionResult(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    promotion_id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    manual_import_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    graph_mutation_status: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    proposal: ConnectorOntologyProposalRecord
    promotion: ConnectorOntologyPromotionRecord
    permission_decision: PermissionDecision
    ontology_mutation: OntologyMutationResult
    audit_event_id: UUID
    audit_event_type: str = Field(min_length=1)
    idempotent_replay: bool = False


REQUIRED_PROMOTION_SCOPE = "connectors:ontology:promote"
PROMOTION_MODE = "approved_manual_import"
APPLIED_AUDIT_EVENT_TYPE = "connector.ontology_promotion.applied"
DEFERRED_AUDIT_EVENT_TYPE = "connector.ontology_promotion.deferred"
FAILED_AUDIT_EVENT_TYPE = "connector.ontology_promotion.failed"


def record_demo_connector_ontology_promotion(
    repository: AxisPersistenceRepository,
    request: ConnectorOntologyPromotionRequest,
    ontology_mutation_runtime: OntologyMutationRuntime | None = None,
) -> ConnectorOntologyPromotionResult:
    if request.promotion_mode != PROMOTION_MODE:
        raise ConnectorOntologyPromotionValidationError(
            "Connector ontology promotions require approved_manual_import mode.",
            "unsupported_promotion_mode",
        )

    existing = repository.get_connector_ontology_promotion_by_idempotency_key(
        request.tenant_id,
        request.idempotency_key,
    )
    if existing is not None:
        if _fingerprint_from_existing(existing) != _fingerprint_from_request(request):
            raise ConnectorOntologyPromotionIdempotencyConflict(existing.promotion_id)
        proposal = repository.get_connector_ontology_proposal(
            existing.tenant_id,
            existing.proposal_id,
        )
        if proposal is None:
            raise ConnectorOntologyPromotionNotFound("Connector ontology proposal not found")
        return _result_from_existing(existing, proposal, idempotent_replay=True)

    proposal = repository.get_connector_ontology_proposal(request.tenant_id, request.proposal_id)
    if proposal is None:
        raise ConnectorOntologyPromotionNotFound("Connector ontology proposal not found")
    _validate_proposal_promotable(proposal)
    manual_import = repository.get_connector_manual_import_request(
        request.tenant_id,
        request.manual_import_id,
    )
    _validate_manual_import_for_promotion(manual_import, request.proposal_id)
    permission_decision = _evaluate_promotion_permission(request, proposal, manual_import)

    mutation_request = OntologyMutationRequest(
        tenant_id=proposal.tenant_id,
        connector_id=proposal.connector_id,
        promotion_id=request.promotion_id,
        proposal_id=proposal.proposal_id,
        manual_import_id=manual_import.import_id,
        actor_id=request.actor_id,
        node_id=proposal.node_id,
        node_type=proposal.node_type,
        ontology_type=proposal.ontology_type,
        field_summary=proposal.field_summary,
        evidence_refs=proposal.evidence_refs,
    )
    runtime = ontology_mutation_runtime or DeferredOntologyMutationRuntime()
    try:
        ontology_mutation = runtime.promote_connector_proposal(mutation_request)
    except OntologyMutationError as exc:
        ontology_mutation = ontology_mutation_failure_result(mutation_request, reason=str(exc))

    promotion_status = _promotion_status(ontology_mutation)
    audit_event_type = _audit_event_type(ontology_mutation)
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            event_type=audit_event_type,
            payload={
                "connector_id": proposal.connector_id,
                "promotion_id": request.promotion_id,
                "proposal_id": proposal.proposal_id,
                "manual_import_id": manual_import.import_id,
                "promotion_mode": request.promotion_mode,
                "status": promotion_status,
                "graph_mutation_status": ontology_mutation.status,
                "required_permission": REQUIRED_PROMOTION_SCOPE,
                "permission_decision": permission_decision.model_dump(),
                "ontology_mutation": ontology_mutation.model_dump(),
                "node_id": proposal.node_id,
                "node_type": proposal.node_type,
                "ontology_type": proposal.ontology_type,
                "field_summary_keys": sorted(proposal.field_summary.keys()),
                "decision_note_recorded": str(request.note is not None).lower(),
            },
        )
    )
    promotion = repository.create_connector_ontology_promotion(
        ConnectorOntologyPromotionCreate(
            tenant_id=request.tenant_id,
            connector_id=proposal.connector_id,
            promotion_id=request.promotion_id,
            idempotency_key=request.idempotency_key,
            proposal_id=proposal.proposal_id,
            manual_import_id=manual_import.import_id,
            status=promotion_status,
            promotion_mode=request.promotion_mode,
            requested_by=request.actor_id,
            graph_mutation_status=ontology_mutation.status,
            ontology_mutation=ontology_mutation.model_dump(),
            permission_decision=permission_decision.model_dump(),
            audit_event_id=audit_event.id,
            audit_event_type=audit_event.event_type,
            notes=[request.note] if request.note else [],
        )
    )

    if ontology_mutation.status == "type_db_mutation_applied":
        proposal = repository.record_connector_ontology_proposal_promotion(
            ConnectorOntologyPromotionResultRecord(
                tenant_id=proposal.tenant_id,
                proposal_id=proposal.proposal_id,
                status=promotion_status,
                graph_mutation_status=ontology_mutation.status,
                promotion_id=request.promotion_id,
                promoted_by=request.actor_id,
                ontology_mutation=ontology_mutation.model_dump(),
                audit_event_id=audit_event.id,
                audit_event_type=audit_event.event_type,
            )
        )

    return ConnectorOntologyPromotionResult(
        tenant_id=request.tenant_id,
        connector_id=proposal.connector_id,
        promotion_id=request.promotion_id,
        proposal_id=proposal.proposal_id,
        manual_import_id=manual_import.import_id,
        status=promotion_status,
        graph_mutation_status=ontology_mutation.status,
        actor_id=request.actor_id,
        proposal=_proposal_from_record(proposal),
        promotion=_promotion_from_record(promotion),
        permission_decision=permission_decision,
        ontology_mutation=ontology_mutation,
        audit_event_id=audit_event.id,
        audit_event_type=audit_event.event_type,
        idempotent_replay=False,
    )


def _validate_proposal_promotable(proposal) -> None:
    if proposal.status == "promoted_to_graph":
        raise ConnectorOntologyPromotionValidationError(
            "Connector ontology proposal has already been promoted.",
            "proposal_already_promoted",
        )
    if proposal.status != "proposed_from_preview":
        raise ConnectorOntologyPromotionValidationError(
            "Connector ontology proposal is not waiting for promotion.",
            "proposal_not_promotable",
        )
    if proposal.graph_mutation_status != "not_applied":
        raise ConnectorOntologyPromotionValidationError(
            "Connector ontology proposal graph mutation status is not promotable.",
            "proposal_graph_status_not_promotable",
        )


def _validate_manual_import_for_promotion(manual_import, proposal_id: str) -> None:
    if manual_import is None:
        raise ConnectorOntologyPromotionValidationError(
            "Manual import approval evidence is required before promotion.",
            "manual_import_not_found",
        )
    if proposal_id not in manual_import.proposal_ids:
        raise ConnectorOntologyPromotionValidationError(
            "Manual import does not reference this ontology proposal.",
            "manual_import_proposal_mismatch",
        )
    if manual_import.status != "approval_approved" or manual_import.decision != "approve":
        raise ConnectorOntologyPromotionValidationError(
            "Manual import must be approved before ontology promotion.",
            "manual_import_not_approved",
        )
    if manual_import.workflow_signal is None:
        raise ConnectorOntologyPromotionValidationError(
            "Manual import workflow signal evidence is required before promotion.",
            "manual_import_missing_workflow_signal",
        )
    if manual_import.workflow_signal_status == "runtime_signal_unavailable":
        raise ConnectorOntologyPromotionValidationError(
            "Manual import workflow signal must not be unavailable before promotion.",
            "manual_import_workflow_signal_unavailable",
        )


def _evaluate_promotion_permission(request, proposal, manual_import) -> PermissionDecision:
    decision = evaluate_permission(
        PermissionRequest(
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            actor_scopes=request.actor_scopes,
            required_scopes=[REQUIRED_PROMOTION_SCOPE],
            attributes={
                "connector_id": proposal.connector_id,
                "proposal_id": proposal.proposal_id,
                "manual_import_id": manual_import.import_id,
                "node_id": proposal.node_id,
                "node_type": proposal.node_type,
                "ontology_type": proposal.ontology_type,
                "risk_level": proposal.field_summary.get("risk_level"),
            },
        )
    )
    if not decision.allowed:
        raise ConnectorOntologyPromotionPermissionDenied(REQUIRED_PROMOTION_SCOPE, decision)
    return decision


def _promotion_status(ontology_mutation: OntologyMutationResult) -> str:
    if ontology_mutation.status == "type_db_mutation_applied":
        return "promoted_to_graph"
    if ontology_mutation.status == "type_db_mutation_deferred":
        return "promotion_deferred"
    return "promotion_failed"


def _audit_event_type(ontology_mutation: OntologyMutationResult) -> str:
    if ontology_mutation.status == "type_db_mutation_applied":
        return APPLIED_AUDIT_EVENT_TYPE
    if ontology_mutation.status == "type_db_mutation_deferred":
        return DEFERRED_AUDIT_EVENT_TYPE
    return FAILED_AUDIT_EVENT_TYPE


def _proposal_from_record(record) -> ConnectorOntologyProposalRecord:
    return ConnectorOntologyProposalRecord(
        tenant_id=record.tenant_id,
        connector_id=record.connector_id,
        proposal_id=record.proposal_id,
        source_run_id=record.source_run_id,
        source_file_name=record.source_file_name,
        mapping_profile=record.mapping_profile,
        status=record.status,
        write_mode=record.write_mode,
        graph_mutation_status=record.graph_mutation_status,
        proposed_by=record.proposed_by,
        node_id=record.node_id,
        node_type=record.node_type,
        ontology_type=record.ontology_type,
        field_summary=record.field_summary,
        evidence_refs=record.evidence_refs,
        promotion_id=record.promotion_id,
        promoted_by=record.promoted_by,
        promoted_at=record.promoted_at,
        ontology_mutation=record.ontology_mutation,
        audit_event_id=record.audit_event_id,
        audit_event_type=record.audit_event_type,
        notes=record.notes,
        created_at=record.created_at,
    )


def _promotion_from_record(record) -> ConnectorOntologyPromotionRecord:
    return ConnectorOntologyPromotionRecord(
        tenant_id=record.tenant_id,
        connector_id=record.connector_id,
        promotion_id=record.promotion_id,
        idempotency_key=record.idempotency_key,
        proposal_id=record.proposal_id,
        manual_import_id=record.manual_import_id,
        status=record.status,
        promotion_mode=record.promotion_mode,
        requested_by=record.requested_by,
        graph_mutation_status=record.graph_mutation_status,
        ontology_mutation=record.ontology_mutation,
        audit_event_id=record.audit_event_id,
        audit_event_type=record.audit_event_type,
        notes=record.notes,
        created_at=record.created_at,
    )


def _result_from_existing(
    existing, proposal, idempotent_replay: bool
) -> ConnectorOntologyPromotionResult:
    ontology_mutation = OntologyMutationResult.model_validate(existing.ontology_mutation)
    return ConnectorOntologyPromotionResult(
        tenant_id=existing.tenant_id,
        connector_id=existing.connector_id,
        promotion_id=existing.promotion_id,
        proposal_id=existing.proposal_id,
        manual_import_id=existing.manual_import_id,
        status=existing.status,
        graph_mutation_status=existing.graph_mutation_status,
        actor_id=existing.requested_by,
        proposal=_proposal_from_record(proposal),
        promotion=_promotion_from_record(existing),
        permission_decision=PermissionDecision.model_validate(existing.permission_decision),
        ontology_mutation=ontology_mutation,
        audit_event_id=existing.audit_event_id,
        audit_event_type=existing.audit_event_type,
        idempotent_replay=idempotent_replay,
    )


def _fingerprint_from_request(request: ConnectorOntologyPromotionRequest) -> dict:
    return {
        "promotion_id": request.promotion_id,
        "proposal_id": request.proposal_id,
        "manual_import_id": request.manual_import_id,
        "promotion_mode": request.promotion_mode,
        "requested_by": request.actor_id,
        "notes": [request.note] if request.note else [],
    }


def _fingerprint_from_existing(record) -> dict:
    return {
        "promotion_id": record.promotion_id,
        "proposal_id": record.proposal_id,
        "manual_import_id": record.manual_import_id,
        "promotion_mode": record.promotion_mode,
        "requested_by": record.requested_by,
        "notes": record.notes,
    }
