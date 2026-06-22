from pydantic import ValidationError

from axis_api.demo import (
    ManufacturingOntology,
    ManufacturingOntologyEntityDetail,
    build_manufacturing_ontology_entity_detail,
)
from axis_api.persistence import AxisPersistenceRepository

MANUFACTURING_ONTOLOGY_REFERENCE_ID = "manufacturing-ontology"
ONTOLOGY_SURFACE = "ontology"


class OntologyReferenceRecordNotFound(LookupError):
    pass


class OntologyReferenceRecordInvalid(ValueError):
    pass


def get_persisted_manufacturing_ontology(
    repository: AxisPersistenceRepository,
    tenant_id: str = "tenant_demo_manufacturing",
) -> ManufacturingOntology:
    record = repository.get_demo_reference_record(
        tenant_id=tenant_id,
        surface=ONTOLOGY_SURFACE,
        reference_id=MANUFACTURING_ONTOLOGY_REFERENCE_ID,
    )
    if record is None:
        raise OntologyReferenceRecordNotFound("Manufacturing ontology reference record not found")

    try:
        ontology = ManufacturingOntology.model_validate(record.payload)
    except ValidationError as exc:
        raise OntologyReferenceRecordInvalid(
            "Manufacturing ontology reference payload is invalid"
        ) from exc

    if ontology.tenant_id != tenant_id:
        raise OntologyReferenceRecordInvalid(
            "Manufacturing ontology tenant does not match record tenant"
        )

    return ontology


def get_persisted_manufacturing_ontology_entity_detail(
    repository: AxisPersistenceRepository,
    node_id: str,
    tenant_id: str = "tenant_demo_manufacturing",
) -> ManufacturingOntologyEntityDetail | None:
    ontology = get_persisted_manufacturing_ontology(repository, tenant_id=tenant_id)
    return build_manufacturing_ontology_entity_detail(ontology, node_id)
