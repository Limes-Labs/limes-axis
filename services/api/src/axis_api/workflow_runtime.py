from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol
from uuid import UUID

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


class WorkflowActionSignalRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)
    action_run_id: UUID
    idempotency_key: str = Field(min_length=1)
    approval_id: str | None = None
    execution_mode: str = Field(min_length=1)
    signal_name: str = Field(default="action_requested", min_length=1)
    payload: dict = Field(default_factory=dict)

    @property
    def runtime_payload(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "action_id": self.action_id,
            "action_run_id": str(self.action_run_id),
            "idempotency_key": self.idempotency_key,
            "approval_id": self.approval_id,
            "execution_mode": self.execution_mode,
            "payload": self.payload,
        }

    @property
    def audit_payload(self) -> dict:
        return {
            "action_id": self.action_id,
            "action_run_id": str(self.action_run_id),
            "idempotency_key": self.idempotency_key,
            "approval_id": self.approval_id,
            "execution_mode": self.execution_mode,
            "payload_field_names": sorted(self.payload.keys()),
        }


class WorkflowConnectorManualImportSignalRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    import_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    approval_id: str = Field(min_length=1)
    import_mode: str = Field(min_length=1)
    decision: ApprovalDecision
    proposal_ids: list[str] = Field(default_factory=list)
    graph_mutation_status: str = Field(default="not_applied", min_length=1)
    signal_name: str = Field(default="connector_manual_import_decided", min_length=1)

    @property
    def approved(self) -> bool:
        return self.decision == ApprovalDecision.APPROVE

    @property
    def runtime_payload(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "connector_id": self.connector_id,
            "import_id": self.import_id,
            "idempotency_key": self.idempotency_key,
            "approval_id": self.approval_id,
            "import_mode": self.import_mode,
            "decision": self.decision.value,
            "approved": self.approved,
            "proposal_ids": self.proposal_ids,
            "graph_mutation_status": self.graph_mutation_status,
        }

    @property
    def audit_payload(self) -> dict:
        return {
            "connector_id": self.connector_id,
            "import_id": self.import_id,
            "idempotency_key": self.idempotency_key,
            "approval_id": self.approval_id,
            "import_mode": self.import_mode,
            "decision": self.decision.value,
            "approved": self.approved,
            "proposal_ids": self.proposal_ids,
            "proposal_count": len(self.proposal_ids),
            "graph_mutation_status": self.graph_mutation_status,
        }


class WorkflowConnectorEvidenceSnapshotExportSignalRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    export_request_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    approval_id: str = Field(min_length=1)
    decision: ApprovalDecision
    connector_id: str | None = None
    snapshot_id: str | None = None
    requested_snapshot_count: int = Field(ge=0)
    export_status: str = Field(min_length=1)
    storage_status: str = Field(default="not_written", min_length=1)
    redaction_policy: str = Field(min_length=1)
    signal_name: str = Field(
        default="connector_evidence_snapshot_export_decided",
        min_length=1,
    )

    @property
    def approved(self) -> bool:
        return self.decision == ApprovalDecision.APPROVE

    @property
    def runtime_payload(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "export_request_id": self.export_request_id,
            "idempotency_key": self.idempotency_key,
            "approval_id": self.approval_id,
            "decision": self.decision.value,
            "approved": self.approved,
            "connector_id": self.connector_id,
            "snapshot_id": self.snapshot_id,
            "requested_snapshot_count": self.requested_snapshot_count,
            "export_status": self.export_status,
            "storage_status": self.storage_status,
            "redaction_policy": self.redaction_policy,
        }

    @property
    def audit_payload(self) -> dict:
        return self.runtime_payload


class WorkflowSignalRuntime(Protocol):
    async def signal_approval_decision(
        self,
        request: WorkflowSignalRequest,
    ) -> WorkflowSignalResult:
        ...

    async def signal_action_run(
        self,
        request: WorkflowActionSignalRequest,
    ) -> WorkflowSignalResult:
        ...

    async def signal_connector_manual_import(
        self,
        request: WorkflowConnectorManualImportSignalRequest,
    ) -> WorkflowSignalResult:
        ...

    async def signal_connector_evidence_snapshot_export(
        self,
        request: WorkflowConnectorEvidenceSnapshotExportSignalRequest,
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

    async def signal_action_run(
        self,
        request: WorkflowActionSignalRequest,
    ) -> WorkflowSignalResult:
        try:
            client = await self.client()
            handle = client.get_workflow_handle(request.workflow_id)
            await handle.signal(
                request.signal_name,
                request.runtime_payload,
                rpc_timeout=timedelta(seconds=self.config.signal_timeout_seconds),
            )
        except (OSError, RuntimeError, TemporalError, RPCError) as exc:
            raise WorkflowSignalError(exc.__class__.__name__) from exc

        return WorkflowSignalResult(
            workflow_id=request.workflow_id,
            status="action_signal_requested",
            adapter=self.adapter_name,
            signal_name=request.signal_name,
            payload=request.audit_payload,
        )

    async def signal_connector_manual_import(
        self,
        request: WorkflowConnectorManualImportSignalRequest,
    ) -> WorkflowSignalResult:
        try:
            client = await self.client()
            handle = client.get_workflow_handle(request.workflow_id)
            await handle.signal(
                request.signal_name,
                request.runtime_payload,
                rpc_timeout=timedelta(seconds=self.config.signal_timeout_seconds),
            )
        except (OSError, RuntimeError, TemporalError, RPCError) as exc:
            raise WorkflowSignalError(exc.__class__.__name__) from exc

        return WorkflowSignalResult(
            workflow_id=request.workflow_id,
            status="manual_import_signal_requested",
            adapter=self.adapter_name,
            signal_name=request.signal_name,
            payload=request.audit_payload,
        )

    async def signal_connector_evidence_snapshot_export(
        self,
        request: WorkflowConnectorEvidenceSnapshotExportSignalRequest,
    ) -> WorkflowSignalResult:
        try:
            client = await self.client()
            handle = client.get_workflow_handle(request.workflow_id)
            await handle.signal(
                request.signal_name,
                request.runtime_payload,
                rpc_timeout=timedelta(seconds=self.config.signal_timeout_seconds),
            )
        except (OSError, RuntimeError, TemporalError, RPCError) as exc:
            raise WorkflowSignalError(exc.__class__.__name__) from exc

        return WorkflowSignalResult(
            workflow_id=request.workflow_id,
            status="export_request_signal_requested",
            adapter=self.adapter_name,
            signal_name=request.signal_name,
            payload=request.audit_payload,
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

    async def signal_action_run(
        self,
        request: WorkflowActionSignalRequest,
    ) -> WorkflowSignalResult:
        return WorkflowSignalResult(
            workflow_id=request.workflow_id,
            status="runtime_signal_deferred",
            adapter=self.adapter_name,
            signal_name=request.signal_name,
            payload=request.audit_payload,
        )

    async def signal_connector_manual_import(
        self,
        request: WorkflowConnectorManualImportSignalRequest,
    ) -> WorkflowSignalResult:
        return WorkflowSignalResult(
            workflow_id=request.workflow_id,
            status="runtime_signal_deferred",
            adapter=self.adapter_name,
            signal_name=request.signal_name,
            payload=request.audit_payload,
        )

    async def signal_connector_evidence_snapshot_export(
        self,
        request: WorkflowConnectorEvidenceSnapshotExportSignalRequest,
    ) -> WorkflowSignalResult:
        return WorkflowSignalResult(
            workflow_id=request.workflow_id,
            status="runtime_signal_deferred",
            adapter=self.adapter_name,
            signal_name=request.signal_name,
            payload=request.audit_payload,
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


def workflow_action_signal_failure_result(
    request: WorkflowActionSignalRequest,
    reason: str,
    adapter: str = TemporalWorkflowSignalRuntime.adapter_name,
) -> WorkflowSignalResult:
    return WorkflowSignalResult(
        workflow_id=request.workflow_id,
        status="runtime_signal_unavailable",
        adapter=adapter,
        signal_name=request.signal_name,
        payload={**request.audit_payload, "reason": reason},
    )


def workflow_connector_manual_import_signal_failure_result(
    request: WorkflowConnectorManualImportSignalRequest,
    reason: str,
    adapter: str = TemporalWorkflowSignalRuntime.adapter_name,
) -> WorkflowSignalResult:
    return WorkflowSignalResult(
        workflow_id=request.workflow_id,
        status="runtime_signal_unavailable",
        adapter=adapter,
        signal_name=request.signal_name,
        payload={**request.audit_payload, "reason": reason},
    )


def workflow_connector_evidence_snapshot_export_signal_failure_result(
    request: WorkflowConnectorEvidenceSnapshotExportSignalRequest,
    reason: str,
    adapter: str = TemporalWorkflowSignalRuntime.adapter_name,
) -> WorkflowSignalResult:
    return WorkflowSignalResult(
        workflow_id=request.workflow_id,
        status="runtime_signal_unavailable",
        adapter=adapter,
        signal_name=request.signal_name,
        payload={**request.audit_payload, "reason": reason},
    )
