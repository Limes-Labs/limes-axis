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


async def test_temporal_adapter_preserves_governed_request_changes_payload() -> None:
    task_queue = f"axis-integration-{uuid4().hex}"
    workflow_id = f"axis-approval-{uuid4().hex}"
    decision_event_id = str(uuid4())
    runtime = TemporalWorkflowRuntime(TemporalAdapterConfig(task_queue=task_queue))
    client = await runtime.client()
    decision_payload = {
        "schema_version": "axis.approval-decision.v1",
        "decision_event_id": decision_event_id,
        "tenant_id": "tenant_demo",
        "workflow_id": workflow_id,
        "approval_id": "appr_quality_release",
        "decision": "request_changes",
        "approved": False,
        "actor_id": "quality-owner-role",
        "note": "Attach the updated inspection evidence.",
        "decided_at": "2026-07-18T14:00:00+00:00",
    }

    async with Worker(client, task_queue=task_queue, workflows=[ApprovalWorkflow]):
        await runtime.start_workflow(
            WorkflowStartRequest(
                tenant_id="tenant_demo",
                workflow_type="approval",
                workflow_id=workflow_id,
                payload={"operation_id": "quality.release", "risk_level": "high"},
            )
        )
        signal_state = await runtime.signal_approval_decision(
            workflow_id,
            decision_payload,
        )
        result = await client.get_workflow_handle(workflow_id).result()

    assert signal_state.payload == decision_payload
    assert result["status"] == "changes_requested"
    assert result["decision"] == decision_payload
    assert result["delivery"] == {
        "duplicate_count": 0,
        "conflict_count": 0,
        "invalid_count": 0,
    }
