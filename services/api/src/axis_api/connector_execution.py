from typing import Protocol

from pydantic import BaseModel, Field


class ConnectorExecutionRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    execution_mode: str = Field(min_length=1)
    runtime_boundary: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    credential_handle_ids: list[str] = Field(default_factory=list)
    input_summary: dict[str, str] = Field(default_factory=dict)


class ConnectorExecutionResult(BaseModel):
    adapter: str = Field(min_length=1)
    status: str = Field(min_length=1)
    external_sync_started: bool
    idempotency_key: str = Field(min_length=1)
    result_summary: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ConnectorExecutionRuntime(Protocol):
    def execute(self, request: ConnectorExecutionRequest) -> ConnectorExecutionResult:
        ...


class ConnectorSyncScheduleRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    execution_mode: str = Field(min_length=1)
    runtime_boundary: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    credential_handle_ids: list[str] = Field(default_factory=list)
    credential_lease_id: str = Field(min_length=1)
    schedule_id: str = Field(min_length=1)
    schedule_cadence: str = Field(min_length=1)
    schedule_timezone: str = Field(min_length=1)
    next_run_at: str = Field(min_length=1)
    input_summary: dict[str, str] = Field(default_factory=dict)


class ConnectorSyncScheduleResult(BaseModel):
    adapter: str = Field(min_length=1)
    status: str = Field(min_length=1)
    schedule_ref: str = Field(min_length=1)
    external_sync_started: bool
    idempotency_key: str = Field(min_length=1)
    result_summary: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ConnectorSyncSchedulerRuntime(Protocol):
    def schedule(self, request: ConnectorSyncScheduleRequest) -> ConnectorSyncScheduleResult:
        ...


class ConnectorSyncDispatchRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    dispatch_id: str = Field(min_length=1)
    runtime_boundary: str = Field(min_length=1)
    dispatched_by: str = Field(min_length=1)
    credential_handle_ids: list[str] = Field(default_factory=list)
    credential_lease_id: str = Field(min_length=1)
    schedule_id: str = Field(min_length=1)
    schedule_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class ConnectorSyncDispatchResult(BaseModel):
    adapter: str = Field(min_length=1)
    status: str = Field(min_length=1)
    dispatch_ref: str = Field(min_length=1)
    external_sync_started: bool
    idempotency_key: str = Field(min_length=1)
    result_summary: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ConnectorSyncDispatchRuntime(Protocol):
    def dispatch(self, request: ConnectorSyncDispatchRequest) -> ConnectorSyncDispatchResult:
        ...


class ConnectorSyncExecutionRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1)
    runtime_boundary: str = Field(min_length=1)
    executed_by: str = Field(min_length=1)
    credential_handle_ids: list[str] = Field(default_factory=list)
    credential_lease_id: str = Field(min_length=1)
    schedule_id: str = Field(min_length=1)
    schedule_ref: str = Field(min_length=1)
    dispatch_id: str = Field(min_length=1)
    dispatch_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    input_summary: dict[str, str] = Field(default_factory=dict)


class ConnectorSyncExecutionResult(BaseModel):
    adapter: str = Field(min_length=1)
    status: str = Field(min_length=1)
    sync_ref: str = Field(min_length=1)
    external_sync_started: bool
    idempotency_key: str = Field(min_length=1)
    result_summary: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ConnectorSyncExecutionRuntime(Protocol):
    def execute(self, request: ConnectorSyncExecutionRequest) -> ConnectorSyncExecutionResult:
        ...


class DeferredConnectorExecutionRuntime:
    adapter_name = "axis-deferred-connector-execution-adapter"

    def execute(self, request: ConnectorExecutionRequest) -> ConnectorExecutionResult:
        return ConnectorExecutionResult(
            adapter=self.adapter_name,
            status="execution_deferred",
            external_sync_started=False,
            idempotency_key=f"{request.tenant_id}:{request.run_id}:execution",
            result_summary={
                "runtime_status": "deferred",
                "external_sync_started": "false",
                "connector_id": request.connector_id,
                "execution_mode": request.execution_mode,
            },
            notes=[
                "Connector execution is deferred by the Axis runtime adapter.",
                "No external sync, credential retrieval or graph mutation was started.",
            ],
        )


class DeferredConnectorSyncSchedulerRuntime:
    adapter_name = "axis-deferred-connector-sync-scheduler"

    def schedule(self, request: ConnectorSyncScheduleRequest) -> ConnectorSyncScheduleResult:
        return ConnectorSyncScheduleResult(
            adapter=self.adapter_name,
            status="sync_schedule_deferred",
            schedule_ref=f"deferred-sync://{request.tenant_id}/{request.schedule_id}",
            external_sync_started=False,
            idempotency_key=(
                f"{request.tenant_id}:{request.run_id}:{request.schedule_id}:"
                "sync-schedule"
            ),
            result_summary={
                "runtime_status": "schedule_deferred",
                "external_sync_started": "false",
                "connector_id": request.connector_id,
                "schedule_id": request.schedule_id,
                "schedule_cadence": request.schedule_cadence,
                "next_run_at": request.next_run_at,
            },
            notes=[
                "Connector sync scheduling is deferred by the Axis runtime adapter.",
                "No external sync, credential retrieval or graph mutation was started.",
            ],
        )


class DeferredConnectorSyncDispatchRuntime:
    adapter_name = "axis-deferred-connector-sync-dispatcher"

    def dispatch(self, request: ConnectorSyncDispatchRequest) -> ConnectorSyncDispatchResult:
        return ConnectorSyncDispatchResult(
            adapter=self.adapter_name,
            status="sync_dispatch_deferred",
            dispatch_ref=(
                f"deferred-sync-dispatch://{request.tenant_id}/"
                f"{request.run_id}/{request.dispatch_id}"
            ),
            external_sync_started=False,
            idempotency_key=request.idempotency_key,
            result_summary={
                "runtime_status": "dispatch_deferred",
                "external_sync_started": "false",
                "connector_id": request.connector_id,
                "schedule_id": request.schedule_id,
                "dispatch_id": request.dispatch_id,
            },
            notes=[
                "Connector sync dispatch is deferred by the Axis runtime adapter.",
                "No external sync, credential retrieval or graph mutation was started.",
            ],
        )


class DeferredConnectorSyncExecutionRuntime:
    adapter_name = "axis-deferred-connector-sync-executor"

    def execute(self, request: ConnectorSyncExecutionRequest) -> ConnectorSyncExecutionResult:
        return ConnectorSyncExecutionResult(
            adapter=self.adapter_name,
            status="sync_execution_deferred",
            sync_ref=(
                f"deferred-sync-execution://{request.tenant_id}/"
                f"{request.run_id}/{request.execution_id}"
            ),
            external_sync_started=False,
            idempotency_key=request.idempotency_key,
            result_summary={
                "runtime_status": "sync_execution_deferred",
                "external_sync_started": "false",
                "connector_id": request.connector_id,
                "schedule_id": request.schedule_id,
                "dispatch_id": request.dispatch_id,
                "execution_id": request.execution_id,
            },
            notes=[
                "Connector sync execution is deferred by the Axis runtime adapter.",
                "No external sync, credential retrieval or graph mutation was started.",
            ],
        )


class SelfHostedConnectorSyncExecutionRuntime:
    adapter_name = "axis-self-hosted-connector-sync-executor"
    external_db_adapter_name = "axis-postgres-external-db-sync-executor"

    def __init__(self, *, external_db_sync_enabled: bool = False) -> None:
        self.external_db_sync_enabled = external_db_sync_enabled

    def execute(self, request: ConnectorSyncExecutionRequest) -> ConnectorSyncExecutionResult:
        if (
            self.external_db_sync_enabled
            and request.connector_id == "external_db_operational_mirror"
        ):
            return self._execute_external_db_sync(request)

        records_read = request.input_summary.get("record_count", "0")
        return ConnectorSyncExecutionResult(
            adapter=self.adapter_name,
            status="sync_execution_completed",
            sync_ref=(
                f"self-hosted-sync-execution://{request.tenant_id}/"
                f"{request.run_id}/{request.execution_id}"
            ),
            external_sync_started=False,
            idempotency_key=request.idempotency_key,
            result_summary={
                "runtime_status": "sync_execution_completed",
                "external_sync_started": "false",
                "connector_id": request.connector_id,
                "schedule_id": request.schedule_id,
                "dispatch_id": request.dispatch_id,
                "execution_id": request.execution_id,
                "records_read": records_read,
                "records_accepted": records_read,
                "records_rejected": "0",
                "graph_mutation_started": "false",
                "source_mode": "self_hosted_demo",
            },
            notes=[
                "Connector sync executed through the self-hosted demo runtime.",
                "No external egress, credential material or graph mutation was started.",
            ],
        )

    def _execute_external_db_sync(
        self,
        request: ConnectorSyncExecutionRequest,
    ) -> ConnectorSyncExecutionResult:
        records_read = request.input_summary.get("record_count", "0")
        connection_profile_id = request.input_summary.get(
            "connection_profile_id",
            "unknown_profile",
        )
        schema_name = request.input_summary.get("schema_name", "unknown_schema")
        table_name = request.input_summary.get("table_name", "unknown_table")
        return ConnectorSyncExecutionResult(
            adapter=self.external_db_adapter_name,
            status="sync_execution_completed",
            sync_ref=(
                f"postgres-external-db-sync://{request.tenant_id}/"
                f"{connection_profile_id}/{request.run_id}/{request.execution_id}"
            ),
            external_sync_started=False,
            idempotency_key=request.idempotency_key,
            result_summary={
                "runtime_status": "sync_execution_completed",
                "external_sync_started": "false",
                "connector_id": request.connector_id,
                "schedule_id": request.schedule_id,
                "dispatch_id": request.dispatch_id,
                "execution_id": request.execution_id,
                "provider": "postgres",
                "connection_profile_id": connection_profile_id,
                "schema_name": schema_name,
                "table_name": table_name,
                "records_read": records_read,
                "records_accepted": records_read,
                "records_rejected": "0",
                "external_query_started": "false",
                "credential_material_returned": "false",
                "graph_mutation_started": "false",
                "source_mode": "external_db_profile",
            },
            notes=[
                "Postgres external DB sync executed through the profile adapter boundary.",
                (
                    "No raw connection string, credential material, external query or "
                    "graph mutation was started."
                ),
            ],
        )
