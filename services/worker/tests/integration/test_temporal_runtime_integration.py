import os
from uuid import uuid4

import pytest
from temporalio.worker import Worker

from axis_worker.temporal_adapter import TemporalAdapterConfig, TemporalWorkflowRuntime
from axis_worker.workflow_port import WorkflowStartRequest
from axis_worker.workflows.approval_workflow import ApprovalWorkflow

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("AXIS_RUN_INTEGRATION") != "1",
        reason="set AXIS_RUN_INTEGRATION=1 with the local Docker runtime running",
    ),
]


async def test_temporal_adapter_runs_approval_workflow_to_completion() -> None:
    task_queue = f"axis-integration-{uuid4().hex}"
    workflow_id = f"axis-approval-{uuid4().hex}"
    runtime = TemporalWorkflowRuntime(TemporalAdapterConfig(task_queue=task_queue))
    client = await runtime.client()

    async with Worker(client, task_queue=task_queue, workflows=[ApprovalWorkflow]):
        start_state = await runtime.start_workflow(
            WorkflowStartRequest(
                tenant_id="tenant_demo",
                workflow_type="approval",
                workflow_id=workflow_id,
                payload={"operation_id": "quality.release", "risk_level": "high"},
            )
        )
        signal_state = await runtime.signal_approval(workflow_id, approved=True)
        result = await client.get_workflow_handle(workflow_id).result()

    assert start_state.status == "started"
    assert signal_state.status == "approval_signaled"
    assert result == {
        "status": "approved",
        "payload": {"operation_id": "quality.release", "risk_level": "high"},
    }
