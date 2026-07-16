"""Live dependency readiness checks for the API traffic admission boundary."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal, Protocol

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from axis_api.config import Settings
from axis_api.ontology.client import OntologyClient, OntologyClientConfig
from axis_api.usage_metering import UsageAccumulator
from axis_api.workflow_runtime import TemporalWorkflowSignalRuntime

_LOGGER = logging.getLogger(__name__)

DependencyStatus = Literal["ready", "disabled", "timeout", "unavailable"]


class DependencyReadiness(BaseModel):
    required: bool
    status: DependencyStatus
    latency_ms: float = Field(ge=0)


class RuntimeReadinessReport(BaseModel):
    status: Literal["ready", "not_ready"]
    service: str = "axis-api"
    dependencies: dict[str, DependencyReadiness]


class ReadinessProbe(Protocol):
    async def __call__(self) -> None: ...


@dataclass(frozen=True)
class _ProbeDefinition:
    name: str
    required: bool
    probe: ReadinessProbe | None


class RuntimeReadinessService:
    """Runs required dependency probes concurrently with a strict deadline."""

    def __init__(
        self,
        probes: list[_ProbeDefinition],
        *,
        timeout_seconds: float,
    ) -> None:
        self._probes = probes
        self._timeout_seconds = timeout_seconds
        self._inflight: dict[str, asyncio.Task[None]] = {}
        self._inflight_lock = asyncio.Lock()

    async def check(self) -> RuntimeReadinessReport:
        results = await asyncio.gather(*(self._check_probe(probe) for probe in self._probes))
        dependencies = {
            probe.name: result
            for probe, result in zip(self._probes, results, strict=True)
        }
        ready = all(not result.required or result.status == "ready" for result in results)
        return RuntimeReadinessReport(
            status="ready" if ready else "not_ready",
            dependencies=dependencies,
        )

    async def _check_probe(self, definition: _ProbeDefinition) -> DependencyReadiness:
        if not definition.required or definition.probe is None:
            return DependencyReadiness(required=False, status="disabled", latency_ms=0)

        started_at = time.monotonic()
        task = await self._probe_task(definition)
        try:
            await asyncio.wait_for(
                asyncio.shield(task),
                timeout=self._timeout_seconds,
            )
        except TimeoutError:
            status: DependencyStatus = "timeout"
            _LOGGER.warning("Readiness probe timed out", extra={"dependency": definition.name})
        except Exception:  # noqa: BLE001 - public response intentionally redacts details
            status = "unavailable"
            _LOGGER.warning(
                "Readiness probe failed",
                extra={"dependency": definition.name},
                exc_info=True,
            )
        else:
            status = "ready"
        finally:
            if task.done():
                async with self._inflight_lock:
                    if self._inflight.get(definition.name) is task:
                        self._inflight.pop(definition.name, None)
        latency_ms = round((time.monotonic() - started_at) * 1000, 2)
        return DependencyReadiness(
            required=definition.required,
            status=status,
            latency_ms=latency_ms,
        )

    async def _probe_task(self, definition: _ProbeDefinition) -> asyncio.Task[None]:
        assert definition.probe is not None
        async with self._inflight_lock:
            task = self._inflight.get(definition.name)
            if task is None or task.done():
                task = asyncio.create_task(definition.probe())
                task.add_done_callback(_consume_probe_exception)
                self._inflight[definition.name] = task
            return task


def _consume_probe_exception(task: asyncio.Task[None]) -> None:
    """Retrieve background probe failures after a timed-out public request."""

    if not task.cancelled():
        task.exception()


def build_runtime_readiness_service(
    settings: Settings,
    *,
    session_factory: sessionmaker[Session],
    workflow_runtime: object,
    usage_accumulator: UsageAccumulator,
) -> RuntimeReadinessService:
    async def postgres_probe() -> None:
        await asyncio.to_thread(_probe_postgres, session_factory)

    async def typedb_probe() -> None:
        await asyncio.to_thread(_probe_typedb, settings)

    async def temporal_probe() -> None:
        if not isinstance(workflow_runtime, TemporalWorkflowSignalRuntime):
            raise RuntimeError("temporal_runtime_unavailable")
        client = await workflow_runtime.client()
        await client.service_client.check_health(
            timeout=timedelta(seconds=settings.readiness_probe_timeout_seconds),
            retry=False,
        )

    async def usage_metering_probe() -> None:
        if not bool(usage_accumulator.health()["healthy"]):
            raise RuntimeError("usage_metering_degraded")

    typedb_required = settings.ontology_queries_enabled or settings.ontology_mutations_enabled
    return RuntimeReadinessService(
        [
            _ProbeDefinition("postgres", True, postgres_probe),
            _ProbeDefinition("typedb", typedb_required, typedb_probe),
            _ProbeDefinition("temporal", settings.workflow_signals_enabled, temporal_probe),
            _ProbeDefinition(
                "usage_metering",
                settings.usage_metering_enabled,
                usage_metering_probe,
            ),
        ],
        timeout_seconds=settings.readiness_probe_timeout_seconds,
    )


def static_runtime_readiness_service(
    probes: dict[str, tuple[bool, Callable[[], Awaitable[None]] | None]],
    *,
    timeout_seconds: float = 1.0,
) -> RuntimeReadinessService:
    """Build a deterministic service for tests and embedding applications."""

    return RuntimeReadinessService(
        [
            _ProbeDefinition(name=name, required=required, probe=probe)
            for name, (required, probe) in probes.items()
        ],
        timeout_seconds=timeout_seconds,
    )


def _probe_postgres(session_factory: sessionmaker[Session]) -> None:
    session = session_factory()
    try:
        if session.execute(text("SELECT 1")).scalar_one() != 1:
            raise RuntimeError("postgres_probe_invalid_response")
    finally:
        session.close()


def _probe_typedb(settings: Settings) -> None:
    client = OntologyClient(
        OntologyClientConfig(
            address=settings.typedb_address,
            username=settings.typedb_username,
            password=settings.typedb_password,
            database=settings.typedb_database,
            request_timeout_millis=max(50, int(settings.readiness_probe_timeout_seconds * 1000)),
        )
    )
    try:
        if not client.database_exists():
            raise RuntimeError("typedb_database_unavailable")
    finally:
        client.close()
