from pydantic import ValidationError

from axis_api.demo import ManufacturingModelRouting
from axis_api.persistence import AxisPersistenceRepository

MANUFACTURING_MODEL_ROUTING_REFERENCE_ID = "manufacturing-model-routing"
MODEL_ROUTING_SURFACE = "model-routing"


class ModelRoutingReferenceRecordNotFound(LookupError):
    pass


class ModelRoutingReferenceRecordInvalid(ValueError):
    pass


def get_persisted_manufacturing_model_routing(
    repository: AxisPersistenceRepository,
    tenant_id: str = "tenant_demo_manufacturing",
) -> ManufacturingModelRouting:
    record = repository.get_demo_reference_record(
        tenant_id=tenant_id,
        surface=MODEL_ROUTING_SURFACE,
        reference_id=MANUFACTURING_MODEL_ROUTING_REFERENCE_ID,
    )
    if record is None:
        raise ModelRoutingReferenceRecordNotFound(
            "Manufacturing model routing reference record not found"
        )

    try:
        routing = ManufacturingModelRouting.model_validate(record.payload)
    except ValidationError as exc:
        raise ModelRoutingReferenceRecordInvalid(
            "Manufacturing model routing reference payload is invalid"
        ) from exc

    if routing.tenant_id != tenant_id:
        raise ModelRoutingReferenceRecordInvalid(
            "Manufacturing model routing tenant does not match record tenant"
        )

    return routing
