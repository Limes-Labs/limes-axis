from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, Field

from axis_api.ontology.client import OntologyClient, OntologyClientConfig
from axis_api.permissions import PermissionDecision

if TYPE_CHECKING:
    from axis_api.demo import ManufacturingOntology


class OntologyQueryError(RuntimeError):
    pass


class OntologyGraphQueryRequest(BaseModel):
    tenant_id: str = Field(default="tenant_demo_manufacturing", min_length=1)
    actor_id: str = Field(default="public-demo-reader", min_length=1)
    actor_scopes: list[str] = Field(default_factory=list)
    enforce_relationship_scopes: bool = False
    limit: int = Field(default=200, ge=1, le=500)

    @property
    def typeql(self) -> str:
        return f"match\n  $entity isa $entity_type, has axis_id $axis_id;\nlimit {self.limit};"


class OntologyGraphQueryMetadata(BaseModel):
    adapter: str = Field(min_length=1)
    source: str = Field(min_length=1)
    query_mode: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    permission_decision: PermissionDecision
    requested_scopes: list[str] = Field(default_factory=list)
    applied_relationship_scopes: list[str] = Field(default_factory=list)
    denied_relationship_count: int = Field(ge=0)
    returned_node_count: int = Field(ge=0)
    returned_relationship_count: int = Field(ge=0)
    typeql: str | None = None
    notes: list[str] = Field(default_factory=list)


class OntologyGraphQueryRuntime(Protocol):
    def query_manufacturing_graph(
        self,
        request: OntologyGraphQueryRequest,
        ontology: "ManufacturingOntology",
    ) -> "ManufacturingOntology": ...


class OntologyReadClient(Protocol):
    def execute_read(self, query_text: str) -> Sequence[object]: ...


class DeferredOntologyQueryRuntime:
    adapter_name = "axis-deferred-ontology-query-adapter"

    def query_manufacturing_graph(
        self,
        request: OntologyGraphQueryRequest,
        ontology: "ManufacturingOntology",
    ) -> "ManufacturingOntology":
        return _apply_graph_query_metadata(
            ontology,
            request,
            adapter=self.adapter_name,
            source="persisted-reference",
        )


@dataclass(frozen=True)
class TypeDBOntologyQueryConfig:
    address: str = "localhost:1729"
    username: str = "admin"
    password: str = "password"
    database: str = "axis"
    tls_enabled: bool = False


class TypeDBOntologyQueryRuntime:
    adapter_name = "axis-typedb-ontology-query-adapter"

    def __init__(
        self,
        config: TypeDBOntologyQueryConfig,
        client: OntologyReadClient | None = None,
    ) -> None:
        self.client = (
            client
            if client is not None
            else OntologyClient(
                OntologyClientConfig(
                    address=config.address,
                    username=config.username,
                    password=config.password,
                    database=config.database,
                    tls_enabled=config.tls_enabled,
                )
            )
        )

    def query_manufacturing_graph(
        self,
        request: OntologyGraphQueryRequest,
        ontology: "ManufacturingOntology",
    ) -> "ManufacturingOntology":
        try:
            rows = self.client.execute_read(request.typeql)
            ontology = _map_typedb_rows_to_ontology(ontology, rows)
        except Exception as exc:
            raise OntologyQueryError(exc.__class__.__name__) from exc

        return _apply_graph_query_metadata(
            ontology,
            request,
            adapter=self.adapter_name,
            source="typedb-read-boundary",
        )


def _map_typedb_rows_to_ontology(
    ontology: "ManufacturingOntology",
    rows: Sequence[object],
) -> "ManufacturingOntology":
    structured_rows = [row for row in rows if isinstance(row, Mapping)]
    if not structured_rows:
        return ontology

    from axis_api.demo import OntologyNode, OntologyRelationship

    nodes: list[OntologyNode] = []
    relationships: list[OntologyRelationship] = []
    for row in structured_rows:
        kind = str(row.get("kind", "")).lower()
        if kind == "node":
            nodes.append(
                OntologyNode.model_validate(
                    {
                        "node_id": row.get("node_id"),
                        "label": row.get("label"),
                        "node_type": row.get("node_type"),
                        "domain": row.get("domain"),
                        "status": row.get("status"),
                        "source_system": row.get("source_system"),
                        "summary": row.get("summary"),
                    }
                )
            )
        elif kind == "relationship":
            relationships.append(
                OntologyRelationship.model_validate(
                    {
                        "relationship_id": row.get("relationship_id"),
                        "source_id": row.get("source_id"),
                        "target_id": row.get("target_id"),
                        "relation_type": row.get("relation_type"),
                        "summary": row.get("summary"),
                        "permission_scope": row.get("permission_scope"),
                        "metadata": row.get("metadata"),
                    }
                )
            )

    if not nodes and not relationships:
        return ontology

    source_systems = sorted({node.source_system for node in nodes})
    return ontology.model_copy(
        update={
            "nodes": nodes,
            "relationships": relationships,
            "source_systems": source_systems or ontology.source_systems,
        }
    )


def query_manufacturing_ontology_graph(
    runtime: OntologyGraphQueryRuntime,
    request: OntologyGraphQueryRequest,
    ontology: "ManufacturingOntology",
) -> "ManufacturingOntology":
    return runtime.query_manufacturing_graph(request, ontology)


def _apply_graph_query_metadata(
    ontology: "ManufacturingOntology",
    request: OntologyGraphQueryRequest,
    *,
    adapter: str,
    source: str,
) -> "ManufacturingOntology":
    relationships = ontology.relationships
    denied_relationship_count = 0
    query_mode = "unfiltered_reference"
    permission_decision = PermissionDecision(allowed=True, reason="public_reference")

    if request.enforce_relationship_scopes:
        actor_scopes = set(request.actor_scopes)
        relationships = [
            relationship
            for relationship in ontology.relationships
            if relationship.permission_scope in actor_scopes
        ]
        denied_relationship_count = len(ontology.relationships) - len(relationships)
        query_mode = "permission_filtered"
        permission_decision = PermissionDecision(
            allowed=True,
            reason="relationship_filter_applied",
        )

    node_ids = {relationship.source_id for relationship in relationships} | {
        relationship.target_id for relationship in relationships
    }
    nodes = [
        node
        for node in ontology.nodes
        if not request.enforce_relationship_scopes or node.node_id in node_ids
    ]
    applied_relationship_scopes = sorted(
        {relationship.permission_scope for relationship in relationships}
    )

    return ontology.model_copy(
        update={
            "nodes": nodes,
            "relationships": relationships,
            "source_systems": sorted({node.source_system for node in nodes}) or ["Axis"],
            "graph_query": OntologyGraphQueryMetadata(
                adapter=adapter,
                source=source,
                query_mode=query_mode,
                tenant_id=request.tenant_id,
                actor_id=request.actor_id,
                permission_decision=permission_decision,
                requested_scopes=request.actor_scopes,
                applied_relationship_scopes=applied_relationship_scopes,
                denied_relationship_count=denied_relationship_count,
                returned_node_count=len(nodes),
                returned_relationship_count=len(relationships),
                typeql=request.typeql,
                notes=[
                    "Ontology graph reads pass through the Axis graph query adapter.",
                    (
                        "Relationship scopes filtered this graph response."
                        if request.enforce_relationship_scopes
                        else "Public reference graph is unfiltered when no OIDC principal is bound."
                    ),
                    (
                        "Structured TypeDB read-boundary rows are mapped before "
                        "relationship-scope filtering."
                        if source == "typedb-read-boundary"
                        else "Deferred runtime serves the persisted reference graph "
                        "until TypeDB reads are enabled."
                    ),
                ],
            ),
        }
    )
