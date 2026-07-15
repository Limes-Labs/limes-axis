"""System liveness and traffic-readiness routes."""

from collections.abc import Callable

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from axis_api.runtime_readiness import (
    DependencyReadiness,
    RuntimeReadinessReport,
    RuntimeReadinessService,
)


class SystemReadinessResponse(BaseModel):
    """Public readiness contract, including safe control-plane metadata."""

    status: str
    service: str
    dependencies: dict[str, DependencyReadiness]
    identity: dict[str, object]
    external_model_egress_enabled: bool


def build_system_router(
    *,
    identity_summary: Callable[[], dict[str, object]],
    external_model_egress_enabled: bool,
) -> APIRouter:
    router = APIRouter(tags=["system"])

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "axis-api"}

    @router.get("/ready", response_model=SystemReadinessResponse)
    async def ready(request: Request) -> JSONResponse:
        service: RuntimeReadinessService = request.app.state.runtime_readiness_service
        report: RuntimeReadinessReport = await service.check()
        payload = report.model_dump(mode="json")
        payload["identity"] = identity_summary()
        payload["external_model_egress_enabled"] = external_model_egress_enabled
        return JSONResponse(
            status_code=(
                status.HTTP_200_OK
                if report.status == "ready"
                else status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            content=payload,
        )

    return router
