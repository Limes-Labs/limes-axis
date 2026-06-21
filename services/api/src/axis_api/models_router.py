from pydantic import BaseModel, Field


class ModelEgressBlocked(RuntimeError):
    pass


class ModelRouteRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    prompt: str = Field(min_length=1)


class ModelRouter:
    def __init__(self, external_egress_enabled: bool) -> None:
        self.external_egress_enabled = external_egress_enabled

    def route(self, request: ModelRouteRequest) -> str:
        if request.provider.startswith("external-") and not self.external_egress_enabled:
            raise ModelEgressBlocked("External model egress is disabled for this tenant.")
        return request.provider
