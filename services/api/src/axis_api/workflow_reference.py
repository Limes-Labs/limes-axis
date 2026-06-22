from pydantic import ValidationError

from axis_api.demo import ManufacturingWorkflowConsole
from axis_api.persistence import AxisPersistenceRepository

MANUFACTURING_WORKFLOW_CONSOLE_REFERENCE_ID = "manufacturing-workflow-console"
WORKFLOW_CONSOLE_SURFACE = "workflows"


class WorkflowReferenceRecordNotFound(LookupError):
    pass


class WorkflowReferenceRecordInvalid(ValueError):
    pass


def get_persisted_manufacturing_workflow_console(
    repository: AxisPersistenceRepository,
    tenant_id: str = "tenant_demo_manufacturing",
) -> ManufacturingWorkflowConsole:
    record = repository.get_demo_reference_record(
        tenant_id=tenant_id,
        surface=WORKFLOW_CONSOLE_SURFACE,
        reference_id=MANUFACTURING_WORKFLOW_CONSOLE_REFERENCE_ID,
    )
    if record is None:
        raise WorkflowReferenceRecordNotFound(
            "Manufacturing workflow console reference record not found"
        )

    try:
        console = ManufacturingWorkflowConsole.model_validate(record.payload)
    except ValidationError as exc:
        raise WorkflowReferenceRecordInvalid(
            "Manufacturing workflow console reference payload is invalid"
        ) from exc

    if console.tenant_id != tenant_id:
        raise WorkflowReferenceRecordInvalid(
            "Manufacturing workflow console tenant does not match record tenant"
        )

    return console
