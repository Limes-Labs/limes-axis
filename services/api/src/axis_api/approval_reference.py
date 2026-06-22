from pydantic import ValidationError

from axis_api.demo import ManufacturingApprovalInbox
from axis_api.persistence import AxisPersistenceRepository

MANUFACTURING_APPROVAL_INBOX_REFERENCE_ID = "manufacturing-approval-inbox"
APPROVAL_INBOX_SURFACE = "approvals"


class ApprovalReferenceRecordNotFound(LookupError):
    pass


class ApprovalReferenceRecordInvalid(ValueError):
    pass


def get_persisted_manufacturing_approval_inbox(
    repository: AxisPersistenceRepository,
    tenant_id: str = "tenant_demo_manufacturing",
) -> ManufacturingApprovalInbox:
    record = repository.get_demo_reference_record(
        tenant_id=tenant_id,
        surface=APPROVAL_INBOX_SURFACE,
        reference_id=MANUFACTURING_APPROVAL_INBOX_REFERENCE_ID,
    )
    if record is None:
        raise ApprovalReferenceRecordNotFound(
            "Manufacturing approval inbox reference record not found"
        )

    try:
        inbox = ManufacturingApprovalInbox.model_validate(record.payload)
    except ValidationError as exc:
        raise ApprovalReferenceRecordInvalid(
            "Manufacturing approval inbox reference payload is invalid"
        ) from exc

    if inbox.tenant_id != tenant_id:
        raise ApprovalReferenceRecordInvalid(
            "Manufacturing approval inbox tenant does not match record tenant"
        )

    return inbox
