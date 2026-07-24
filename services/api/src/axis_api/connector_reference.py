from pydantic import ValidationError

from axis_api.connectors import ManufacturingConnectorRegistry
from axis_api.manufacturing_empty import empty_manufacturing_connector_registry
from axis_api.manufacturing_metadata import (
    ManufacturingResponseProvenance,
    ManufacturingTenantNotFound,
    get_manufacturing_tenant_metadata,
)
from axis_api.persistence import AxisPersistenceRepository

MANUFACTURING_CONNECTOR_REGISTRY_REFERENCE_ID = "manufacturing-connector-registry"
CONNECTOR_REGISTRY_SURFACE = "connectors"


class ConnectorReferenceRecordNotFound(LookupError):
    pass


class ConnectorReferenceRecordInvalid(ValueError):
    pass


def get_persisted_manufacturing_connector_registry(
    repository: AxisPersistenceRepository,
    tenant_id: str,
) -> ManufacturingConnectorRegistry:
    tenant_metadata = get_manufacturing_tenant_metadata(repository, tenant_id)
    record = repository.get_demo_reference_record(
        tenant_id=tenant_id,
        surface=CONNECTOR_REGISTRY_SURFACE,
        reference_id=MANUFACTURING_CONNECTOR_REGISTRY_REFERENCE_ID,
    )
    if record is None:
        return empty_manufacturing_connector_registry(tenant_id, tenant_metadata)

    try:
        registry = ManufacturingConnectorRegistry.model_validate(record.payload)
    except ValidationError as exc:
        raise ConnectorReferenceRecordInvalid(
            "Manufacturing connector registry reference payload is invalid"
        ) from exc

    if registry.tenant_id != tenant_id:
        raise ConnectorReferenceRecordInvalid(
            "Manufacturing connector registry tenant does not match record tenant"
        )

    return registry.model_copy(
        update={"provenance": ManufacturingResponseProvenance.REFERENCE_SCENARIO}
    )


def require_persisted_manufacturing_connector_registry(
    repository: AxisPersistenceRepository,
    tenant_id: str,
) -> ManufacturingConnectorRegistry:
    try:
        registry = get_persisted_manufacturing_connector_registry(repository, tenant_id)
    except ManufacturingTenantNotFound as exc:
        raise ConnectorReferenceRecordNotFound(
            "Manufacturing connector registry reference record not found"
        ) from exc
    if registry.provenance == ManufacturingResponseProvenance.EMPTY:
        raise ConnectorReferenceRecordNotFound(
            "Manufacturing connector registry reference record not found"
        )
    return registry
