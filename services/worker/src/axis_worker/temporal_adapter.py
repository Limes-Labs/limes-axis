from dataclasses import dataclass
from typing import Any

from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy

from axis_worker.workflow_port import WorkflowStartRequest, WorkflowState
from axis_worker.workflows.approval_workflow import ApprovalWorkflow


@dataclass(frozen=True)
class TemporalAdapterConfig:
    address: str = "localhost:7233"
    namespace: str = "default"
    task_queue: str = "axis-foundation"


class TemporalWorkflowRuntime:
    def __init__(self, config: TemporalAdapterConfig) -> None:
        self.config = config
        self._client: Client | None = None

    async def client(self) -> Client:
        if self._client is None:
            self._client = await Client.connect(
                self.config.address,
                namespace=self.config.namespace,
            )
        return self._client

    async def start_workflow(self, request: WorkflowStartRequest) -> WorkflowState:
        client = await self.client()
        handle = await client.start_workflow(
            ApprovalWorkflow.run,
            request.payload,
            id=request.workflow_id,
            task_queue=self.config.task_queue,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
        return WorkflowState(
            workflow_id=handle.id,
            status="started",
            payload={"tenant_id": request.tenant_id, "workflow_type": request.workflow_type},
        )

    async def signal_approval(self, workflow_id: str, approved: bool) -> WorkflowState:
        """Send the legacy boolean contract during rolling upgrades."""
        client = await self.client()
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal(ApprovalWorkflow.approve, approved)
        return WorkflowState(
            workflow_id=workflow_id,
            status="approval_signaled",
            payload={"approved": approved},
        )

    async def signal_approval_decision(
        self,
        workflow_id: str,
        decision_payload: dict[str, Any],
    ) -> WorkflowState:
        """Send the governed approval payload understood by current workers."""
        client = await self.client()
        handle = client.get_workflow_handle(workflow_id)
        await handle.signal(ApprovalWorkflow.approval_decided_v1, decision_payload)
        return WorkflowState(
            workflow_id=workflow_id,
            status="approval_signaled",
            payload=dict(decision_payload),
        )

    async def cancel_workflow(self, workflow_id: str, reason: str) -> WorkflowState:
        client = await self.client()
        handle = client.get_workflow_handle(workflow_id)
        await handle.cancel()
        return WorkflowState(
            workflow_id=workflow_id,
            status="cancel_requested",
            payload={"reason": reason},
        )
