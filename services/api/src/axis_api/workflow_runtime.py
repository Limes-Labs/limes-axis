from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from pydantic import BaseModel, Field
from temporalio.client import Client
from temporalio.exceptions import TemporalError
from temporalio.service import RPCError

from axis_api.demo import ApprovalDecision


class WorkflowSignalRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    approval_id: str = Field(min_length=1)
    decision: ApprovalDecision
    signal_name: str = Field(default="approve", min_length=1)

    @property
    def approved(self) -> bool:
        return self.decision == ApprovalDecision.APPROVE


class WorkflowSignalResult(BaseModel):
    workflow_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    adapter: str = Field(min_length=1)
    signal_name: str = Field(min_length=1)
    payload: dict = Field(default_factory=dict)


class WorkflowSignalRuntime(Protocol):
    async def signal_approval_decision(
        self,
        request: WorkflowSignalRequest,
    ) -> WorkflowSignalResult:
        ...


class WorkflowSignalError(RuntimeError):
    pass


@dataclass(frozen=True)
class TemporalWorkflowSignalConfig:
    address: str = "localhost:7233"
    namespace: str = "default"
    signal_timeout_seconds: float = 2.0


class TemporalWorkflowSignalRuntime:
    adapter_name = "axis-temporal-adapter"

    def __init__(self, config: TemporalWorkflowSignalConfig) -> None:
        self.config = config
        self._client: Client | None = None

    async def client(self) -> Client:
        if self._client is None:
            self._client = await Client.connect(
                self.config.address,
                namespace=self.config.namespace,
            )
        return self._client

    async def signal_approval_decision(
        self,
        request: WorkflowSignalRequest,
    ) -> WorkflowSignalResult:
        try:
            client = await self.client()
            handle = client.get_workflow_handle(request.workflow_id)
            await handle.signal(
                request.signal_name,
                request.approved,
                rpc_timeout=timedelta(seconds=self.config.signal_timeout_seconds),
            )
        except (OSError, RuntimeError, TemporalError, RPCError) as exc:
            raise WorkflowSignalError(exc.__class__.__name__) from exc

        return WorkflowSignalResult(
            workflow_id=request.workflow_id,
            status="approval_signaled",
            adapter=self.adapter_name,
            signal_name=request.signal_name,
            payload={
                "approval_id": request.approval_id,
                "approved": request.approved,
                "decision": request.decision.value,
            },
        )


class DeferredWorkflowSignalRuntime:
    adapter_name = "axis-deferred-workflow-adapter"

    async def signal_approval_decision(
        self,
        request: WorkflowSignalRequest,
    ) -> WorkflowSignalResult:
        return WorkflowSignalResult(
            workflow_id=request.workflow_id,
            status="runtime_signal_deferred",
            adapter=self.adapter_name,
            signal_name=request.signal_name,
            payload={
                "approval_id": request.approval_id,
                "approved": request.approved,
                "decision": request.decision.value,
            },
        )


def workflow_signal_failure_result(
    request: WorkflowSignalRequest,
    reason: str,
    adapter: str = TemporalWorkflowSignalRuntime.adapter_name,
) -> WorkflowSignalResult:
    return WorkflowSignalResult(
        workflow_id=request.workflow_id,
        status="runtime_signal_unavailable",
        adapter=adapter,
        signal_name=request.signal_name,
        payload={
            "approval_id": request.approval_id,
            "approved": request.approved,
            "decision": request.decision.value,
            "reason": reason,
        },
    )
