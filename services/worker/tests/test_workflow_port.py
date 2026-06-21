from axis_worker.workflow_port import WorkflowStartRequest


def test_workflow_start_request_carries_tenant_context() -> None:
    request = WorkflowStartRequest(
        tenant_id="tenant_demo",
        workflow_type="approval_demo",
        workflow_id="wf_123",
        payload={"action_id": "create_risk"},
    )
    assert request.tenant_id == "tenant_demo"
    assert request.workflow_type == "approval_demo"
