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
    WorkflowActionSignalRequest,
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


@workflow.defn
class ActionSignalTargetWorkflow:
    def __init__(self) -> None:
        self._action_payload: dict | None = None

    @workflow.run
    async def run(self, payload: dict) -> dict:
        await workflow.wait_condition(lambda: self._action_payload is not None)
        return {
            "action_payload": self._action_payload,
            "payload": payload,
        }

    @workflow.signal
    async def action_requested(self, payload: dict) -> None:
        self._action_payload = payload


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


async def test_api_temporal_signal_runtime_signals_action_payload() -> None:
    settings = Settings()
    task_queue = f"axis-api-action-signal-{uuid4().hex}"
    workflow_id = f"axis-api-action-{uuid4().hex}"
    runtime = TemporalWorkflowSignalRuntime(
        TemporalWorkflowSignalConfig(
            address=settings.temporal_address,
            namespace=settings.temporal_namespace,
        )
    )
    client = await runtime.client()

    async with Worker(client, task_queue=task_queue, workflows=[ActionSignalTargetWorkflow]):
        handle = await client.start_workflow(
            ActionSignalTargetWorkflow.run,
            {"tenant_id": "tenant_demo"},
            id=workflow_id,
            task_queue=task_queue,
        )
        signal_result = await runtime.signal_action_run(
            WorkflowActionSignalRequest(
                tenant_id="tenant_demo",
                workflow_id=workflow_id,
                action_id="request_supplier_expedite",
                action_run_id=uuid4(),
                idempotency_key="tenant_demo:request_supplier_expedite:test",
                approval_id="appr_expedite_supplier_batch",
                execution_mode="approval_gated_dry_run",
                payload={"supplier_batch_id": "asset_motors_batch", "reason": "Line 2 risk"},
            )
        )
        workflow_result = await handle.result()

    assert signal_result.status == "action_signal_requested"
    assert signal_result.adapter == "axis-temporal-adapter"
    assert signal_result.signal_name == "action_requested"
    assert signal_result.payload["action_id"] == "request_supplier_expedite"
    assert signal_result.payload["payload_field_names"] == ["reason", "supplier_batch_id"]
    assert "payload" not in signal_result.payload
    assert workflow_result["action_payload"]["payload"] == {
        "supplier_batch_id": "asset_motors_batch",
        "reason": "Line 2 risk",
    }
