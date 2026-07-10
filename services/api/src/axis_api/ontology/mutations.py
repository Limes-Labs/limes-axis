from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field

from axis_api.ontology.client import OntologyClient, OntologyClientConfig

# The mutation runtime returns these on the OntologyMutationResult.status field.
MUTATION_STATUS_APPLIED = "type_db_mutation_applied"
MUTATION_STATUS_DEFERRED = "type_db_mutation_deferred"
# The datastore/driver was unreachable, timed out, or refused the transaction.
MUTATION_STATUS_UNAVAILABLE = "type_db_mutation_unavailable"
# The write transaction committed but the mandatory read-back could not confirm
# the node landed (data-integrity failure). Distinct from _unavailable so
# operators can tell "TypeDB was down" apart from "TypeDB accepted a write that
# did not verify".
MUTATION_STATUS_FAILED = "type_db_mutation_failed"


class OntologyMutationError(RuntimeError):
    """A live TypeDB promotion could not be completed.

    ``status`` carries the fail-closed ``OntologyMutationResult.status`` the
    caller should surface (unavailable vs failed); the message carries a short,
    audit-safe reason.
    """

    def __init__(self, reason: str, *, status: str = MUTATION_STATUS_UNAVAILABLE) -> None:
        super().__init__(reason)
        self.status = status


def _typeql_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


# field_summary key -> axis_asset attribute label (schema.tql). Ordering is
# significant: the generated TypeQL must be deterministic for a given proposal
# so idempotency/replay comparisons and audits are stable.
_FIELD_TO_ATTRIBUTE = {
    "asset_name": "display_name",
    "domain": "domain",
    "risk_level": "risk_level",
    "station": "source_system_ref",
}


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
        """Deterministic, idempotent TypeQL for promoting this proposal.

        Uses TypeDB 3.x ``put`` (match-or-insert) stages keyed on the ``@key``
        ``axis_id`` attribute rather than a bare ``insert``. Re-running the same
        promotion is a no-op: the identity anchor matches the existing entity and
        each attribute ``put`` matches the already-owned value. One object per
        ``put`` stage (the documented safe form), pipelined so later stages bind
        ``$asset`` from the identity anchor. The whole string is submitted as one
        atomic TypeDB write transaction (see OntologyClient.execute_write).
        """
        node_id = _typeql_string(self.node_id)
        statements = [
            f'put $asset isa axis_asset, has axis_id "{node_id}";',
            f'put $asset has asset_type "{_typeql_string(self.ontology_type)}";',
        ]
        for field_name, attribute_name in _FIELD_TO_ATTRIBUTE.items():
            value = self.field_summary.get(field_name)
            if value:
                statements.append(
                    f'put $asset has {attribute_name} "{_typeql_string(value)}";'
                )
        return "\n".join(statements)

    @property
    def verification_typeql(self) -> str:
        """Read-back query confirming the promoted node exists post-commit."""
        return (
            f'match\n  $asset isa axis_asset, has axis_id "{_typeql_string(self.node_id)}";\n'
            'fetch {\n  "axis_id": $asset.axis_id\n};'
        )

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
        # 1. Atomic, idempotent write. execute_write commits or rolls back the
        #    whole put-pipeline as a single transaction; a driver/connection
        #    failure here is fail-closed and retry-safe (nothing partial lands).
        try:
            self.client.execute_write(request.typeql)
        except Exception as exc:
            raise OntologyMutationError(
                exc.__class__.__name__, status=MUTATION_STATUS_UNAVAILABLE
            ) from exc

        # 2. Mandatory read-back. We only report the proposal promoted_to_graph
        #    once we can observe the node in TypeDB. A read error is treated as
        #    the datastore being unavailable; a successful read that does not
        #    contain the node is a data-integrity failure.
        try:
            rows = self.client.execute_read(request.verification_typeql)
        except Exception as exc:
            raise OntologyMutationError(
                f"verification_read_{exc.__class__.__name__}",
                status=MUTATION_STATUS_UNAVAILABLE,
            ) from exc
        if not _verification_confirms_node(rows, request.node_id):
            raise OntologyMutationError(
                "verification_missing_node", status=MUTATION_STATUS_FAILED
            )

        return OntologyMutationResult(
            status=MUTATION_STATUS_APPLIED,
            adapter=self.adapter_name,
            mutation_ref=f"typedb://{self.client.config.database}/{request.node_id}",
            typeql=request.typeql,
            payload={**request.audit_payload, "verified": True},
        )


class DeferredOntologyMutationRuntime:
    adapter_name = "axis-deferred-ontology-adapter"

    def promote_connector_proposal(
        self,
        request: OntologyMutationRequest,
    ) -> OntologyMutationResult:
        return OntologyMutationResult(
            status=MUTATION_STATUS_DEFERRED,
            adapter=self.adapter_name,
            mutation_ref=None,
            typeql=request.typeql,
            payload=request.audit_payload,
        )


def _verification_confirms_node(rows: Sequence[object], node_id: str) -> bool:
    """True if the read-back rows observe an ``axis_id`` equal to ``node_id``."""
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        value = row.get("axis_id")
        if isinstance(value, (list, tuple)):
            if any(str(item) == node_id for item in value):
                return True
        elif value is not None and str(value) == node_id:
            return True
    return False


def ontology_mutation_failure_result(
    request: OntologyMutationRequest,
    reason: str,
    *,
    status: str = MUTATION_STATUS_UNAVAILABLE,
    adapter: str = TypeDBOntologyMutationRuntime.adapter_name,
) -> OntologyMutationResult:
    return OntologyMutationResult(
        status=status,
        adapter=adapter,
        mutation_ref=None,
        typeql=request.typeql,
        payload={**request.audit_payload, "reason": reason},
    )
