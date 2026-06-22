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
        return (
            "match\n"
            "  $entity isa $entity_type, has axis_id $axis_id;\n"
            f"limit {self.limit};"
        )


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
    ) -> "ManufacturingOntology":
        ...


class DeferredOntologyQueryRuntime:
    adapter_name = "axis-deferred-ontology-query-adapter"

    def query_manufacturing_graph(
        self,
        request: OntologyGraphQueryRequest,
    ) -> "ManufacturingOntology":
        from axis_api.demo import get_manufacturing_ontology

        ontology = get_manufacturing_ontology()
        return _apply_graph_query_metadata(
            ontology,
            request,
            adapter=self.adapter_name,
            source="demo-seed",
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

    def __init__(self, config: TypeDBOntologyQueryConfig) -> None:
        self.client = OntologyClient(
            OntologyClientConfig(
                address=config.address,
                username=config.username,
                password=config.password,
                database=config.database,
                tls_enabled=config.tls_enabled,
            )
        )

    def query_manufacturing_graph(
        self,
        request: OntologyGraphQueryRequest,
    ) -> "ManufacturingOntology":
        from axis_api.demo import get_manufacturing_ontology

        try:
            self.client.execute_read(request.typeql)
        except Exception as exc:
            raise OntologyQueryError(exc.__class__.__name__) from exc

        ontology = get_manufacturing_ontology()
        return _apply_graph_query_metadata(
            ontology,
            request,
            adapter=self.adapter_name,
            source="typedb-read-boundary",
        )


def query_manufacturing_ontology_graph(
    runtime: OntologyGraphQueryRuntime,
    request: OntologyGraphQueryRequest,
) -> "ManufacturingOntology":
    return runtime.query_manufacturing_graph(request)


def _apply_graph_query_metadata(
    ontology: "ManufacturingOntology",
    request: OntologyGraphQueryRequest,
    *,
    adapter: str,
    source: str,
) -> "ManufacturingOntology":
    relationships = ontology.relationships
    denied_relationship_count = 0
    query_mode = "unfiltered_public_seed"
    permission_decision = PermissionDecision(allowed=True, reason="public_seed")

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

    node_ids = {
        relationship.source_id
        for relationship in relationships
    } | {
        relationship.target_id
        for relationship in relationships
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
                        else "Public demo graph is unfiltered when no OIDC principal is bound."
                    ),
                    "TypeDB live result mapping remains behind the ontology query runtime.",
                ],
            ),
        }
    )
