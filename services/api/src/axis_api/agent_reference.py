from pydantic import ValidationError

from axis_api.demo import ManufacturingAgentRegistry
from axis_api.persistence import AxisPersistenceRepository

MANUFACTURING_AGENT_REGISTRY_REFERENCE_ID = "manufacturing-agent-registry"
AGENT_REGISTRY_SURFACE = "agents"


class AgentReferenceRecordNotFound(LookupError):
    pass


class AgentReferenceRecordInvalid(ValueError):
    pass


def get_persisted_manufacturing_agent_registry(
    repository: AxisPersistenceRepository,
    tenant_id: str = "tenant_demo_manufacturing",
) -> ManufacturingAgentRegistry:
    record = repository.get_demo_reference_record(
        tenant_id=tenant_id,
        surface=AGENT_REGISTRY_SURFACE,
        reference_id=MANUFACTURING_AGENT_REGISTRY_REFERENCE_ID,
    )
    if record is None:
        raise AgentReferenceRecordNotFound(
            "Manufacturing agent registry reference record not found"
        )

    try:
        registry = ManufacturingAgentRegistry.model_validate(record.payload)
    except ValidationError as exc:
        raise AgentReferenceRecordInvalid(
            "Manufacturing agent registry reference payload is invalid"
        ) from exc

    if registry.tenant_id != tenant_id:
        raise AgentReferenceRecordInvalid(
            "Manufacturing agent registry tenant does not match record tenant"
        )

    return registry
