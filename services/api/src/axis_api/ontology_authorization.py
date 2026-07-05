from uuid import UUID

from axis_api.audit import AuditEventCreate
from axis_api.demo import ManufacturingOntologyEntityDetail
from axis_api.identity import OidcPrincipal
from axis_api.ontology_reference import get_persisted_manufacturing_ontology_entity_detail
from axis_api.permissions import PermissionDecision, PermissionRequest, evaluate_permission
from axis_api.persistence import AxisPersistenceRepository

ONTOLOGY_GRAPH_READ_DENIED_EVENT_TYPE = "ontology.graph_read.denied"
ONTOLOGY_ENTITY_READ_DENIED_EVENT_TYPE = "ontology.entity_read.denied"
ONTOLOGY_GRAPH_RESOURCE = "ontology_graph"
ONTOLOGY_ENTITY_DETAIL_RESOURCE = "ontology_entity_detail"
TENANT_MISMATCH_REASON = "tenant_mismatch"


class OntologyReadPermissionDenied(PermissionError):
    def __init__(
        self,
        message: str,
        *,
        resource: str,
        decision: PermissionDecision,
        required_permissions: list[str],
        audit_event_id: UUID,
        audit_event_type: str,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.resource = resource
        self.decision = decision
        self.required_permissions = required_permissions
        self.audit_event_id = audit_event_id
        self.audit_event_type = audit_event_type


def authorize_ontology_graph_read(
    repository: AxisPersistenceRepository,
    *,
    tenant_id: str,
    principal: OidcPrincipal | None,
) -> None:
    if principal is None:
        return
    if principal.tenant_id != tenant_id:
        _record_denied_read_and_raise(
            repository,
            principal=principal,
            event_type=ONTOLOGY_GRAPH_READ_DENIED_EVENT_TYPE,
            message="The actor cannot read ontology graph data for this tenant.",
            resource=ONTOLOGY_GRAPH_RESOURCE,
            requested_tenant_id=tenant_id,
            decision=PermissionDecision(allowed=False, reason=TENANT_MISMATCH_REASON),
            required_permissions=[],
            node_id=None,
        )


def get_authorized_manufacturing_ontology_entity_detail(
    repository: AxisPersistenceRepository,
    node_id: str,
    *,
    tenant_id: str,
    principal: OidcPrincipal | None,
) -> ManufacturingOntologyEntityDetail | None:
    if principal is not None and principal.tenant_id != tenant_id:
        _record_denied_read_and_raise(
            repository,
            principal=principal,
            event_type=ONTOLOGY_ENTITY_READ_DENIED_EVENT_TYPE,
            message="The actor cannot read ontology entity data for this tenant.",
            resource=ONTOLOGY_ENTITY_DETAIL_RESOURCE,
            requested_tenant_id=tenant_id,
            decision=PermissionDecision(allowed=False, reason=TENANT_MISMATCH_REASON),
            required_permissions=[],
            node_id=node_id,
        )

    detail = get_persisted_manufacturing_ontology_entity_detail(
        repository,
        node_id,
        tenant_id=tenant_id,
    )
    if detail is None or principal is None:
        return detail

    decision = evaluate_permission(
        PermissionRequest(
            tenant_id=detail.tenant_id,
            actor_id=principal.actor_id,
            actor_scopes=principal.scopes,
            required_scopes=[],
            relationship_scopes=detail.required_permissions,
            attributes={
                "node_id": detail.node.node_id,
                "node_type": detail.node.node_type.value,
                "domain": detail.node.domain,
                "relationship_count": len(detail.connected_relationships),
            },
        )
    )
    if not decision.allowed:
        _record_denied_read_and_raise(
            repository,
            principal=principal,
            event_type=ONTOLOGY_ENTITY_READ_DENIED_EVENT_TYPE,
            message="The actor cannot read this ontology entity relationship context.",
            resource=ONTOLOGY_ENTITY_DETAIL_RESOURCE,
            requested_tenant_id=tenant_id,
            decision=decision,
            required_permissions=detail.required_permissions,
            node_id=node_id,
        )
    return detail


def _record_denied_read_and_raise(
    repository: AxisPersistenceRepository,
    *,
    principal: OidcPrincipal,
    event_type: str,
    message: str,
    resource: str,
    requested_tenant_id: str,
    decision: PermissionDecision,
    required_permissions: list[str],
    node_id: str | None,
) -> None:
    payload: dict[str, object] = {
        "resource": resource,
        "requested_tenant_id": requested_tenant_id,
        "required_permissions": required_permissions,
        "permission_decision": decision.model_dump(),
        "reason": decision.reason,
    }
    if node_id is not None:
        payload["node_id"] = node_id
    audit_event = repository.append_audit_event(
        AuditEventCreate(
            tenant_id=principal.tenant_id,
            actor_id=principal.actor_id,
            event_type=event_type,
            payload=payload,
        )
    )
    raise OntologyReadPermissionDenied(
        message,
        resource=resource,
        decision=decision,
        required_permissions=required_permissions,
        audit_event_id=audit_event.id,
        audit_event_type=audit_event.event_type,
    )
