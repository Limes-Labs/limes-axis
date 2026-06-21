from pydantic import BaseModel, Field


class AuditEventCreate(BaseModel):
    tenant_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    payload: dict
