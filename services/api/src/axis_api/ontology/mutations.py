from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field

from axis_api.ontology.client import OntologyClient, OntologyClientConfig


class OntologyMutationError(RuntimeError):
    pass


def _typeql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


class OntologyMutationRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    promotion_id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    manual_import_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    node_type: str = Field(min_length=1)
    ontology_type: str = Field(min_length=1)
    field_summary: dict[str, str] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)

    @property
    def typeql(self) -> str:
        clauses = [
            "$asset isa axis_asset",
            f'has axis_id "{_typeql_string(self.node_id)}"',
            f'has asset_type "{_typeql_string(self.ontology_type)}"',
        ]
        field_to_attribute = {
            "asset_name": "display_name",
            "domain": "domain",
            "risk_level": "risk_level",
            "station": "source_system_ref",
        }
        for field_name, attribute_name in field_to_attribute.items():
            value = self.field_summary.get(field_name)
            if value:
                clauses.append(f'has {attribute_name} "{_typeql_string(value)}"')

        return "insert\n" + ",\n  ".join(clauses) + ";"

    @property
    def audit_payload(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "connector_id": self.connector_id,
            "promotion_id": self.promotion_id,
            "proposal_id": self.proposal_id,
            "manual_import_id": self.manual_import_id,
            "actor_id": self.actor_id,
            "node_id": self.node_id,
            "node_type": self.node_type,
            "ontology_type": self.ontology_type,
            "field_summary_keys": sorted(self.field_summary.keys()),
            "evidence_refs": self.evidence_refs,
        }


class OntologyMutationResult(BaseModel):
    status: str = Field(min_length=1)
    adapter: str = Field(min_length=1)
    mutation_ref: str | None = None
    typeql: str | None = None
    payload: dict = Field(default_factory=dict)


class OntologyMutationRuntime(Protocol):
    def promote_connector_proposal(
        self,
        request: OntologyMutationRequest,
    ) -> OntologyMutationResult:
        ...


@dataclass(frozen=True)
class TypeDBOntologyMutationConfig:
    address: str = "localhost:1729"
    username: str = "admin"
    password: str = "password"
    database: str = "axis"
    tls_enabled: bool = False


class TypeDBOntologyMutationRuntime:
    adapter_name = "axis-typedb-ontology-adapter"

    def __init__(self, config: TypeDBOntologyMutationConfig) -> None:
        self.client = OntologyClient(
            OntologyClientConfig(
                address=config.address,
                username=config.username,
                password=config.password,
                database=config.database,
                tls_enabled=config.tls_enabled,
            )
        )

    def promote_connector_proposal(
        self,
        request: OntologyMutationRequest,
    ) -> OntologyMutationResult:
        try:
            self.client.execute_write(request.typeql)
        except Exception as exc:
            raise OntologyMutationError(exc.__class__.__name__) from exc

        return OntologyMutationResult(
            status="type_db_mutation_applied",
            adapter=self.adapter_name,
            mutation_ref=f"typedb://{self.client.config.database}/{request.node_id}",
            typeql=request.typeql,
            payload=request.audit_payload,
        )


class DeferredOntologyMutationRuntime:
    adapter_name = "axis-deferred-ontology-adapter"

    def promote_connector_proposal(
        self,
        request: OntologyMutationRequest,
    ) -> OntologyMutationResult:
        return OntologyMutationResult(
            status="type_db_mutation_deferred",
            adapter=self.adapter_name,
            mutation_ref=None,
            typeql=request.typeql,
            payload=request.audit_payload,
        )


def ontology_mutation_failure_result(
    request: OntologyMutationRequest,
    reason: str,
    adapter: str = TypeDBOntologyMutationRuntime.adapter_name,
) -> OntologyMutationResult:
    return OntologyMutationResult(
        status="type_db_mutation_unavailable",
        adapter=adapter,
        mutation_ref=None,
        typeql=request.typeql,
        payload={**request.audit_payload, "reason": reason},
    )
