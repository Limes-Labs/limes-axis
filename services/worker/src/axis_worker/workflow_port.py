from typing import Protocol

from pydantic import BaseModel, Field


class WorkflowStartRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    workflow_type: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    payload: dict


class WorkflowState(BaseModel):
    workflow_id: str
    status: str
    payload: dict


class WorkflowRuntimePort(Protocol):
    async def start_workflow(self, request: WorkflowStartRequest) -> WorkflowState:
        ...

    async def signal_approval(self, workflow_id: str, approved: bool) -> WorkflowState:
        ...

    async def cancel_workflow(self, workflow_id: str, reason: str) -> WorkflowState:
        ...
