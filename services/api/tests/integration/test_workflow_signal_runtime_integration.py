import os
from uuid import uuid4

import pytest
from temporalio import workflow
from temporalio.worker import Worker

from axis_api.config import Settings
from axis_api.demo import ApprovalDecision
from axis_api.workflow_runtime import (
    TemporalWorkflowSignalConfig,
    TemporalWorkflowSignalRuntime,
    WorkflowSignalRequest,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("AXIS_RUN_INTEGRATION") != "1",
        reason="set AXIS_RUN_INTEGRATION=1 with the local Docker runtime running",
    ),
]


@workflow.defn
class SignalTargetWorkflow:
    def __init__(self) -> None:
        self._approved: bool | None = None

    @workflow.run
    async def run(self, payload: dict) -> dict:
        await workflow.wait_condition(lambda: self._approved is not None)
        return {
            "approved": self._approved,
            "payload": payload,
        }

    @workflow.signal
    async def approve(self, approved: bool) -> None:
        self._approved = approved


async def test_api_temporal_signal_runtime_signals_running_workflow() -> None:
    settings = Settings()
    task_queue = f"axis-api-signal-{uuid4().hex}"
    workflow_id = f"axis-api-approval-{uuid4().hex}"
    runtime = TemporalWorkflowSignalRuntime(
        TemporalWorkflowSignalConfig(
            address=settings.temporal_address,
            namespace=settings.temporal_namespace,
        )
    )
    client = await runtime.client()

    async with Worker(client, task_queue=task_queue, workflows=[SignalTargetWorkflow]):
        handle = await client.start_workflow(
            SignalTargetWorkflow.run,
            {"tenant_id": "tenant_demo"},
            id=workflow_id,
            task_queue=task_queue,
        )
        signal_result = await runtime.signal_approval_decision(
            WorkflowSignalRequest(
                tenant_id="tenant_demo",
                workflow_id=workflow_id,
                approval_id="appr_integration_signal",
                decision=ApprovalDecision.APPROVE,
            )
        )
        workflow_result = await handle.result()

    assert signal_result.status == "approval_signaled"
    assert signal_result.adapter == "axis-temporal-adapter"
    assert signal_result.payload == {
        "approval_id": "appr_integration_signal",
        "approved": True,
        "decision": "approve",
    }
    assert workflow_result == {
        "approved": True,
        "payload": {"tenant_id": "tenant_demo"},
    }
