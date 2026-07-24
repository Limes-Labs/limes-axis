from sqlalchemy import event
from sqlalchemy.orm import Session

from axis_api.models import DemoReferenceRecord, Tenant


@event.listens_for(Session, "before_flush")
def seed_tenant_registry_for_legacy_fixtures(
    session: Session,
    _flush_context,
    _instances,
) -> None:
    pending_tenant_ids = {
        record.id for record in session.new if isinstance(record, Tenant)
    }
    tenant_ids = {
        tenant_id
        for record in session.new
        if isinstance(record, DemoReferenceRecord)
        if isinstance((tenant_id := getattr(record, "tenant_id", None)), str)
        and tenant_id
    }
    for tenant_id in tenant_ids - pending_tenant_ids:
        if session.get(Tenant, tenant_id) is None:
            session.add(
                Tenant(
                    id=tenant_id,
                    name=tenant_id,
                    description="",
                    created_by="test-fixture",
                )
            )
