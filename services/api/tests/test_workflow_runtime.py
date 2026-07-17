from uuid import UUID

import pytest

from axis_api.demo import ApprovalDecision
from axis_api.workflow_runtime import (
    DeferredWorkflowSignalRuntime,
    TemporalWorkflowSignalConfig,
    TemporalWorkflowSignalRuntime,
    WorkflowSignalRequest,
)


class RecordingHandle:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object, object]] = []

    async def signal(self, name: str, payload: object, *, rpc_timeout: object) -> None:
        self.calls.append((name, payload, rpc_timeout))


class RecordingClient:
    def __init__(self, handle: RecordingHandle) -> None:
        self.handle = handle
        self.workflow_ids: list[str] = []

    def get_workflow_handle(self, workflow_id: str) -> RecordingHandle:
        self.workflow_ids.append(workflow_id)
        return self.handle


def approval_request(**updates: object) -> WorkflowSignalRequest:
    values: dict[str, object] = {
        "tenant_id": "tenant_demo",
        "workflow_id": "wf_supplier_delay",
        "approval_id": "appr_expedite",
        "decision": ApprovalDecision.REQUEST_CHANGES,
        "actor_id": "plant-operations-owner-role",
        "note": "Please attach updated supplier evidence.",
        "decided_at": None,
    }
    values.update(updates)
    return WorkflowSignalRequest.model_validate(values)


def test_approval_signal_request_generates_stable_event_id_and_full_payload() -> None:
    first = approval_request()
    second = approval_request()

    assert isinstance(first.decision_event_id, UUID)
    assert second.decision_event_id == first.decision_event_id
    assert first.runtime_payload == {
        "schema_version": "axis.approval-decision.v1",
        "decision_event_id": str(first.decision_event_id),
        "tenant_id": "tenant_demo",
        "workflow_id": "wf_supplier_delay",
        "approval_id": "appr_expedite",
        "decision": "request_changes",
        "approved": False,
        "actor_id": "plant-operations-owner-role",
        "note": "Please attach updated supplier evidence.",
        "decided_at": None,
    }


@pytest.mark.asyncio
async def test_temporal_runtime_sends_full_approval_decision_payload() -> None:
    handle = RecordingHandle()
    client = RecordingClient(handle)
    runtime = TemporalWorkflowSignalRuntime(TemporalWorkflowSignalConfig())
    runtime._client = client  # type: ignore[assignment]
    request = approval_request(decision=ApprovalDecision.REJECT)

    result = await runtime.signal_approval_decision(request)

    assert client.workflow_ids == ["wf_supplier_delay"]
    assert handle.calls[0][0] == "approval_decided_v1"
    assert handle.calls[0][1] == request.runtime_payload
    assert result.payload == request.audit_payload


@pytest.mark.asyncio
async def test_deferred_runtime_preserves_full_decision_evidence() -> None:
    request = approval_request()

    result = await DeferredWorkflowSignalRuntime().signal_approval_decision(request)

    assert result.status == "runtime_signal_deferred"
    assert result.payload == request.audit_payload
