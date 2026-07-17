from temporalio.common import WorkflowIDReusePolicy

from axis_worker.temporal_adapter import TemporalAdapterConfig, TemporalWorkflowRuntime
from axis_worker.workflow_port import WorkflowStartRequest


class _Handle:
    id = "workflow-enterprise-1"


class _RecordingClient:
    def __init__(self) -> None:
        self.kwargs: dict = {}

    async def start_workflow(self, workflow, payload, **kwargs):
        self.kwargs = kwargs
        return _Handle()


async def test_approval_workflow_ids_cannot_be_reused() -> None:
    client = _RecordingClient()
    runtime = TemporalWorkflowRuntime(TemporalAdapterConfig())
    runtime._client = client  # type: ignore[assignment]

    await runtime.start_workflow(
        WorkflowStartRequest(
            tenant_id="tenant-enterprise",
            workflow_type="approval",
            workflow_id="workflow-enterprise-1",
            payload={"approval_id": "approval-1"},
        )
    )

    assert client.kwargs["id_reuse_policy"] is WorkflowIDReusePolicy.REJECT_DUPLICATE
