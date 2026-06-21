from dataclasses import dataclass


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    actor_id: str
    request_id: str
