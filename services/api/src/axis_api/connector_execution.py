import csv
import hashlib
import re
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

import psycopg
from psycopg import sql
from pydantic import BaseModel, Field

POSTGRESQL_SQLALCHEMY_SCHEME = "postgresql+psycopg://"
POSTGRESQL_PSYCOPG_SCHEME = "postgresql://"
POSTGRES_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DEFAULT_POSTGRES_PORT = 5432
FILE_CSV_LIVE_SYNC_CONNECTOR_ID = "file_csv_manufacturing_assets"
EXTERNAL_DB_LIVE_SYNC_CONNECTOR_ID = "external_db_operational_mirror"
LIVE_SYNC_SOURCE_FILE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
LIVE_SYNC_PLAN_READY_STATUS = "live_sync_plan_ready"
LIVE_SYNC_PLAN_BLOCKED_STATUS = "live_sync_plan_blocked"
LIVE_SYNC_PLAN_FAILED_STATUS = "live_sync_plan_failed"
LIVE_SYNC_PLAN_DEFERRED_STATUS = "live_sync_plan_deferred"
LIVE_SYNC_BATCH_READ_STATUS = "live_sync_batch_read"
LIVE_SYNC_BATCH_FAILED_STATUS = "live_sync_batch_failed"
FILE_CSV_LIVE_SYNC_SOURCE_MODE = "file_csv_live_sync"
EXTERNAL_DB_LIVE_SYNC_SOURCE_MODE = "external_db_live_sync"


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
    credential_lease_mode: str = Field(default="", min_length=0)
    credential_lease_runtime_boundary: str = Field(default="", min_length=0)
    credential_lease_result: dict = Field(default_factory=dict)
    egress_policy_evidence: dict[str, str] = Field(default_factory=dict)
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


class ExternalPostgresLiveQueryProfile(BaseModel):
    profile_id: str = Field(min_length=1)
    dsn: str = Field(min_length=1)
    schema_name: str = Field(min_length=1)
    table_name: str = Field(min_length=1)
    allowed_columns: list[str] = Field(min_length=1)
    private_endpoint_ref: str = Field(min_length=1)
    endpoint_target_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[a-f0-9]{64}$",
    )
    row_limit: int = Field(default=100, ge=1, le=1_000)
    connect_timeout_seconds: int = Field(default=3, ge=1, le=30)


class FileCsvLiveSyncProfile(BaseModel):
    profile_id: str = Field(min_length=1)
    source_root: str = Field(min_length=1)
    allowed_file_suffixes: list[str] = Field(default_factory=lambda: [".csv"])
    max_file_size_bytes: int = Field(default=1_048_576, ge=1, le=104_857_600)
    max_rows: int = Field(default=500, ge=1, le=10_000)
    batch_size: int = Field(default=100, ge=1, le=1_000)


class ConnectorLiveSyncFieldMapping(BaseModel):
    source_column: str = Field(min_length=1)
    target_field: str = Field(min_length=1)
    ontology_target: str = Field(min_length=1)


class ConnectorLiveSyncPlanRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1)
    executed_by: str = Field(min_length=1)
    credential_lease_id: str = Field(min_length=1)
    credential_lease_result: dict = Field(default_factory=dict)
    egress_policy_evidence: dict[str, str] = Field(default_factory=dict)
    field_mappings: list[ConnectorLiveSyncFieldMapping] = Field(default_factory=list)
    input_summary: dict[str, str] = Field(default_factory=dict)


class ConnectorLiveSyncPlan(BaseModel):
    adapter: str = Field(min_length=1)
    status: str = Field(min_length=1)
    source_mode: str = Field(default="", min_length=0)
    source_ref: str = Field(default="", min_length=0)
    block_reason: str = Field(default="", min_length=0)
    error_code: str = Field(default="", min_length=0)
    batch_size: int = Field(default=0, ge=0)
    max_records: int = Field(default=0, ge=0)
    external_query_required: bool = False
    notes: list[str] = Field(default_factory=list)


class ConnectorLiveSyncBatchRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    connector_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1)
    offset: int = Field(ge=0)
    batch_size: int = Field(ge=1)
    field_mappings: list[ConnectorLiveSyncFieldMapping] = Field(default_factory=list)
    input_summary: dict[str, str] = Field(default_factory=dict)


class ConnectorLiveSyncRecord(BaseModel):
    node_id: str = Field(min_length=1)
    node_type: str = Field(min_length=1)
    ontology_type: str = Field(min_length=1)
    field_summary: dict[str, str] = Field(default_factory=dict)


class ConnectorLiveSyncBatchResult(BaseModel):
    adapter: str = Field(min_length=1)
    status: str = Field(min_length=1)
    records: list[ConnectorLiveSyncRecord] = Field(default_factory=list)
    records_rejected: int = Field(default=0, ge=0)
    next_offset: int = Field(default=0, ge=0)
    source_exhausted: bool = False
    error_code: str = Field(default="", min_length=0)
    notes: list[str] = Field(default_factory=list)


class ConnectorLiveSyncRuntime(Protocol):
    def plan(self, request: ConnectorLiveSyncPlanRequest) -> ConnectorLiveSyncPlan:
        ...

    def read_batch(
        self,
        request: ConnectorLiveSyncBatchRequest,
    ) -> ConnectorLiveSyncBatchResult:
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

    def __init__(
        self,
        *,
        external_db_sync_enabled: bool = False,
        external_db_live_query_preflight_enabled: bool = False,
        external_db_live_query_execution_enabled: bool = False,
        external_postgres_live_query_profile: ExternalPostgresLiveQueryProfile | None = None,
    ) -> None:
        self.external_db_sync_enabled = external_db_sync_enabled
        self.external_db_live_query_preflight_enabled = external_db_live_query_preflight_enabled
        self.external_db_live_query_execution_enabled = (
            external_db_live_query_execution_enabled
        )
        self.external_postgres_live_query_profile = external_postgres_live_query_profile

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
        if request.input_summary.get("live_query_requested", "false").lower() == "true":
            return self._preflight_external_db_live_query(request)

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

    def _preflight_external_db_live_query(
        self,
        request: ConnectorSyncExecutionRequest,
    ) -> ConnectorSyncExecutionResult:
        connection_profile_id = request.input_summary.get(
            "connection_profile_id",
            "unknown_profile",
        )
        schema_name = request.input_summary.get("schema_name", "unknown_schema")
        table_name = request.input_summary.get("table_name", "unknown_table")
        query_mode = request.input_summary.get("query_mode", "read_only_snapshot")
        egress_policy_id = request.input_summary.get("egress_policy_id", "")
        egress_boundary = request.input_summary.get("egress_boundary", "")
        credential_access_mode = request.input_summary.get("credential_access_mode", "")
        egress_policy_evidence = _egress_policy_evidence_from_request(
            tenant_id=request.tenant_id,
            connector_id=request.connector_id,
            connection_profile_id=connection_profile_id,
            egress_policy_id=egress_policy_id,
            evidence=request.egress_policy_evidence,
        )
        egress_policy_evidence_valid = (
            egress_policy_evidence["egress_policy_evidence_status"] == "validated"
            and egress_policy_evidence["egress_policy_result_status"]
            == "egress_policy_approved"
            and egress_policy_evidence["egress_policy_mode"]
            == "approved_private_endpoint"
            and egress_boundary == "approved_private_endpoint"
        )
        lease_result_status = str(request.credential_lease_result.get("status", "unknown"))
        credential_lease_ref = str(request.credential_lease_result.get("provider_lease_ref", ""))
        credential_lease_secret_returned = _bool_as_text(
            request.credential_lease_result.get("secret_material_returned", True)
        )
        credential_lease_evidence_valid = (
            bool(request.credential_lease_mode)
            and bool(request.credential_lease_runtime_boundary)
            and bool(credential_lease_ref)
            and lease_result_status in {"lease_executed", "lease_renewed"}
            and credential_lease_secret_returned == "false"
        )
        policy_preflight_passed = (
            self.external_db_live_query_preflight_enabled
            and egress_policy_evidence_valid
            and credential_access_mode == "lease_scoped_secret_ref"
        )
        secret_reference_evidence = _secret_reference_evidence(
            connector_id=request.connector_id,
            connection_profile_id=connection_profile_id,
            credential_access_mode=credential_access_mode,
            credential_lease_ref=credential_lease_ref,
            secret_material_returned=credential_lease_secret_returned,
            policy_preflight_passed=policy_preflight_passed,
        )
        secret_reference_evidence_valid = (
            secret_reference_evidence["secret_reference_evidence_status"]
            == "validated"
        )
        preflight_passed = (
            policy_preflight_passed
            and credential_lease_evidence_valid
            and secret_reference_evidence_valid
        )
        status = (
            "sync_execution_preflight_passed"
            if preflight_passed
            else "sync_execution_preflight_blocked"
        )
        sync_ref_scheme = (
            "postgres-external-db-preflight"
            if preflight_passed
            else "postgres-external-db-preflight-blocked"
        )
        result_summary = {
            "runtime_status": status,
            "external_sync_started": "false",
            "connector_id": request.connector_id,
            "schedule_id": request.schedule_id,
            "dispatch_id": request.dispatch_id,
            "execution_id": request.execution_id,
            "provider": "postgres",
            "connection_profile_id": connection_profile_id,
            "schema_name": schema_name,
            "table_name": table_name,
            "query_mode": query_mode,
            "records_read": "0",
            "records_accepted": "0",
            "records_rejected": "0",
            "live_query_requested": "true",
            "live_query_preflight_status": "passed" if preflight_passed else "blocked",
            "egress_policy_decision": _egress_policy_decision(
                preflight_enabled=self.external_db_live_query_preflight_enabled,
                policy_evidence_valid=egress_policy_evidence_valid,
                policy_evidence_status=egress_policy_evidence[
                    "egress_policy_evidence_status"
                ],
            ),
            "secret_retrieval_decision": (
                _secret_retrieval_decision(
                    preflight_enabled=self.external_db_live_query_preflight_enabled,
                    policy_preflight_passed=policy_preflight_passed,
                    secret_reference_evidence_valid=secret_reference_evidence_valid,
                    lease_evidence_valid=credential_lease_evidence_valid,
                    secret_material_returned=credential_lease_secret_returned,
                )
            ),
            "external_query_started": "false",
            "credential_material_returned": "false",
            "graph_mutation_started": "false",
            "source_mode": "external_db_live_preflight",
        }
        live_query_execute_requested = (
            request.input_summary.get("live_query_execute", "false").lower() == "true"
        )
        if live_query_execute_requested:
            result_summary["live_query_execute_requested"] = "true"
            result_summary["live_query_execution_status"] = (
                "blocked_preflight_not_passed"
            )
        if preflight_passed:
            result_summary["egress_policy_id"] = egress_policy_id
            result_summary["egress_boundary"] = egress_boundary
            result_summary["credential_access_mode"] = credential_access_mode
        if self.external_db_live_query_preflight_enabled:
            result_summary.update(egress_policy_evidence)
            result_summary["credential_lease_evidence_status"] = (
                "validated" if credential_lease_evidence_valid else "failed"
            )
            result_summary["credential_lease_id"] = request.credential_lease_id
            result_summary["credential_lease_mode"] = request.credential_lease_mode
            result_summary["credential_lease_runtime_boundary"] = (
                request.credential_lease_runtime_boundary
            )
            result_summary["credential_lease_result_status"] = lease_result_status
            result_summary["credential_lease_ref"] = credential_lease_ref
            result_summary["credential_lease_secret_material_returned"] = (
                credential_lease_secret_returned
            )
            result_summary.update(secret_reference_evidence)
        if preflight_passed and live_query_execute_requested:
            return self._execute_external_db_live_read(
                request,
                preflight_result_summary=result_summary,
            )
        return ConnectorSyncExecutionResult(
            adapter=self.external_db_adapter_name,
            status=status,
            sync_ref=(
                f"{sync_ref_scheme}://{request.tenant_id}/"
                f"{connection_profile_id}/{request.run_id}/{request.execution_id}"
            ),
            external_sync_started=False,
            idempotency_key=request.idempotency_key,
            result_summary=result_summary,
            notes=[
                "Postgres external DB live query preflight evaluated policy gates.",
                (
                    "No external query, raw connection string, credential material or "
                    "graph mutation was started."
                ),
            ],
        )

    def _execute_external_db_live_read(
        self,
        request: ConnectorSyncExecutionRequest,
        *,
        preflight_result_summary: dict[str, str],
    ) -> ConnectorSyncExecutionResult:
        connection_profile_id = request.input_summary.get(
            "connection_profile_id",
            "unknown_profile",
        )
        schema_name = request.input_summary.get("schema_name", "unknown_schema")
        table_name = request.input_summary.get("table_name", "unknown_table")
        profile = self.external_postgres_live_query_profile
        block_reason = _live_read_block_reason(
            request=request,
            profile=profile,
            live_query_execution_enabled=self.external_db_live_query_execution_enabled,
        )
        if block_reason is not None or profile is None:
            reason = block_reason or "profile_not_configured"
            return _blocked_external_db_live_read_result(
                request,
                preflight_result_summary=preflight_result_summary,
                connection_profile_id=connection_profile_id,
                reason=reason,
            )

        selected_columns = _requested_or_default_columns(
            request.input_summary.get("selected_columns", ""),
            profile.allowed_columns,
        )
        try:
            records_read = _read_external_postgres_rows(
                profile,
                selected_columns=selected_columns,
            )
        except psycopg.Error:
            return _blocked_external_db_live_read_result(
                request,
                preflight_result_summary=preflight_result_summary,
                connection_profile_id=connection_profile_id,
                reason="query_failed",
            )

        result_summary = {
            **preflight_result_summary,
            "runtime_status": "sync_execution_completed",
            "external_sync_started": "true",
            "schema_name": schema_name,
            "table_name": table_name,
            "records_read": str(records_read),
            "records_accepted": str(records_read),
            "records_rejected": "0",
            "live_query_preflight_status": "passed",
            "live_query_execution_status": "completed",
            "live_query_profile_id": profile.profile_id,
            "live_query_row_limit": str(profile.row_limit),
            "selected_column_count": str(len(selected_columns)),
            "external_query_started": "true",
            "credential_material_returned": "false",
            "graph_mutation_started": "false",
            "source_mode": "external_db_live_read",
        }
        return ConnectorSyncExecutionResult(
            adapter=self.external_db_adapter_name,
            status="sync_execution_completed",
            sync_ref=(
                f"postgres-external-db-live-read://{request.tenant_id}/"
                f"{connection_profile_id}/{request.run_id}/{request.execution_id}"
            ),
            external_sync_started=True,
            idempotency_key=request.idempotency_key,
            result_summary=result_summary,
            notes=[
                "Postgres external DB live read executed through an allowlisted profile.",
                (
                    "Only redacted row counts and public-safe checkpoint evidence were "
                    "persisted; no row payload, credential material or graph mutation "
                    "was stored."
                ),
            ],
        )


class DeferredConnectorLiveSyncRuntime:
    adapter_name = "axis-deferred-connector-live-sync-executor"

    def plan(self, request: ConnectorLiveSyncPlanRequest) -> ConnectorLiveSyncPlan:
        return ConnectorLiveSyncPlan(
            adapter=self.adapter_name,
            status=LIVE_SYNC_PLAN_DEFERRED_STATUS,
            notes=[
                "Connector live sync execution is deferred by the Axis runtime adapter.",
                "No source read, credential retrieval or graph mutation was started.",
            ],
        )

    def read_batch(
        self,
        request: ConnectorLiveSyncBatchRequest,
    ) -> ConnectorLiveSyncBatchResult:
        return ConnectorLiveSyncBatchResult(
            adapter=self.adapter_name,
            status=LIVE_SYNC_BATCH_FAILED_STATUS,
            error_code="live_sync_execution_deferred",
            notes=["Deferred live sync runtime does not read source batches."],
        )


class SelfHostedConnectorLiveSyncRuntime:
    adapter_name = "axis-self-hosted-connector-live-sync-executor"
    file_csv_adapter_name = "axis-file-csv-live-sync-executor"
    external_db_adapter_name = "axis-postgres-external-db-live-sync-executor"

    def __init__(
        self,
        *,
        file_csv_profile: FileCsvLiveSyncProfile | None = None,
        external_db_live_sync_enabled: bool = False,
        external_postgres_profile: ExternalPostgresLiveQueryProfile | None = None,
        external_db_batch_size: int = 100,
    ) -> None:
        self.file_csv_profile = file_csv_profile
        self.external_db_live_sync_enabled = external_db_live_sync_enabled
        self.external_postgres_profile = external_postgres_profile
        self.external_db_batch_size = external_db_batch_size

    def plan(self, request: ConnectorLiveSyncPlanRequest) -> ConnectorLiveSyncPlan:
        if not request.field_mappings:
            return self._blocked_plan(
                adapter=self.adapter_name,
                reason="field_mappings_missing",
            )
        if request.connector_id == FILE_CSV_LIVE_SYNC_CONNECTOR_ID:
            return self._plan_file_csv(request)
        if request.connector_id == EXTERNAL_DB_LIVE_SYNC_CONNECTOR_ID:
            return self._plan_external_db(request)
        return self._blocked_plan(
            adapter=self.adapter_name,
            reason="live_sync_unsupported_connector",
        )

    def read_batch(
        self,
        request: ConnectorLiveSyncBatchRequest,
    ) -> ConnectorLiveSyncBatchResult:
        if request.connector_id == FILE_CSV_LIVE_SYNC_CONNECTOR_ID:
            return self._read_file_csv_batch(request)
        if request.connector_id == EXTERNAL_DB_LIVE_SYNC_CONNECTOR_ID:
            return self._read_external_db_batch(request)
        return ConnectorLiveSyncBatchResult(
            adapter=self.adapter_name,
            status=LIVE_SYNC_BATCH_FAILED_STATUS,
            error_code="live_sync_unsupported_connector",
        )

    def _plan_file_csv(self, request: ConnectorLiveSyncPlanRequest) -> ConnectorLiveSyncPlan:
        profile = self.file_csv_profile
        if profile is None:
            return self._blocked_plan(
                adapter=self.file_csv_adapter_name,
                reason="profile_not_configured",
            )
        file_name = request.input_summary.get("source_file_name", "")
        source_path = _resolved_file_csv_source_path(profile, file_name)
        if source_path is None:
            return self._blocked_plan(
                adapter=self.file_csv_adapter_name,
                reason="source_file_ref_invalid",
            )
        if not source_path.is_file():
            return ConnectorLiveSyncPlan(
                adapter=self.file_csv_adapter_name,
                status=LIVE_SYNC_PLAN_FAILED_STATUS,
                source_mode=FILE_CSV_LIVE_SYNC_SOURCE_MODE,
                source_ref=file_name,
                error_code="connector_unavailable",
                notes=["File CSV live sync source is unavailable in the dropzone."],
            )
        if source_path.stat().st_size > profile.max_file_size_bytes:
            return self._blocked_plan(
                adapter=self.file_csv_adapter_name,
                reason="source_file_too_large",
            )
        return ConnectorLiveSyncPlan(
            adapter=self.file_csv_adapter_name,
            status=LIVE_SYNC_PLAN_READY_STATUS,
            source_mode=FILE_CSV_LIVE_SYNC_SOURCE_MODE,
            source_ref=file_name,
            batch_size=profile.batch_size,
            max_records=profile.max_rows,
            external_query_required=False,
            notes=[
                "File CSV live sync reads an allowlisted local dropzone file.",
                "Row payloads feed ontology proposals; no graph mutation is started.",
            ],
        )

    def _plan_external_db(self, request: ConnectorLiveSyncPlanRequest) -> ConnectorLiveSyncPlan:
        if not self.external_db_live_sync_enabled:
            return self._blocked_plan(
                adapter=self.external_db_adapter_name,
                reason="live_sync_execution_disabled",
            )
        profile = self.external_postgres_profile
        if profile is None:
            return self._blocked_plan(
                adapter=self.external_db_adapter_name,
                reason="profile_not_configured",
            )
        egress_block_reason = _external_db_live_sync_policy_block_reason(request)
        if egress_block_reason is not None:
            return self._blocked_plan(
                adapter=self.external_db_adapter_name,
                reason=egress_block_reason,
            )
        profile_block_reason = _external_postgres_profile_block_reason(
            input_summary=request.input_summary,
            egress_policy_evidence=request.egress_policy_evidence,
            profile=profile,
        )
        if profile_block_reason is not None:
            return self._blocked_plan(
                adapter=self.external_db_adapter_name,
                reason=profile_block_reason,
            )
        schema_name = request.input_summary.get("schema_name", "")
        table_name = request.input_summary.get("table_name", "")
        return ConnectorLiveSyncPlan(
            adapter=self.external_db_adapter_name,
            status=LIVE_SYNC_PLAN_READY_STATUS,
            source_mode=EXTERNAL_DB_LIVE_SYNC_SOURCE_MODE,
            source_ref=f"{schema_name}.{table_name}",
            batch_size=min(self.external_db_batch_size, profile.row_limit),
            max_records=profile.row_limit,
            external_query_required=True,
            notes=[
                "Postgres live sync reads bounded batches from an allowlisted profile.",
                "Row payloads feed ontology proposals; no graph mutation is started.",
            ],
        )

    def _read_file_csv_batch(
        self,
        request: ConnectorLiveSyncBatchRequest,
    ) -> ConnectorLiveSyncBatchResult:
        profile = self.file_csv_profile
        if profile is None:
            return ConnectorLiveSyncBatchResult(
                adapter=self.file_csv_adapter_name,
                status=LIVE_SYNC_BATCH_FAILED_STATUS,
                error_code="profile_not_configured",
            )
        source_path = _resolved_file_csv_source_path(
            profile,
            request.input_summary.get("source_file_name", ""),
        )
        if source_path is None or not source_path.is_file():
            return ConnectorLiveSyncBatchResult(
                adapter=self.file_csv_adapter_name,
                status=LIVE_SYNC_BATCH_FAILED_STATUS,
                error_code="connector_unavailable",
            )
        try:
            headers, rows = _read_file_csv_rows(source_path)
        except (OSError, UnicodeDecodeError, csv.Error):
            return ConnectorLiveSyncBatchResult(
                adapter=self.file_csv_adapter_name,
                status=LIVE_SYNC_BATCH_FAILED_STATUS,
                error_code="connector_unavailable",
            )
        missing_columns = [
            mapping.source_column
            for mapping in request.field_mappings
            if mapping.source_column not in headers
        ]
        if missing_columns:
            return ConnectorLiveSyncBatchResult(
                adapter=self.file_csv_adapter_name,
                status=LIVE_SYNC_BATCH_FAILED_STATUS,
                error_code="source_schema_mismatch",
            )
        bounded_rows = rows[: profile.max_rows]
        batch_rows = bounded_rows[request.offset : request.offset + request.batch_size]
        records, records_rejected = _live_sync_records(request.field_mappings, batch_rows)
        next_offset = request.offset + len(batch_rows)
        return ConnectorLiveSyncBatchResult(
            adapter=self.file_csv_adapter_name,
            status=LIVE_SYNC_BATCH_READ_STATUS,
            records=records,
            records_rejected=records_rejected,
            next_offset=next_offset,
            source_exhausted=next_offset >= len(bounded_rows),
            notes=["File CSV batch read from the allowlisted local dropzone."],
        )

    def _read_external_db_batch(
        self,
        request: ConnectorLiveSyncBatchRequest,
    ) -> ConnectorLiveSyncBatchResult:
        profile = self.external_postgres_profile
        if not self.external_db_live_sync_enabled or profile is None:
            return ConnectorLiveSyncBatchResult(
                adapter=self.external_db_adapter_name,
                status=LIVE_SYNC_BATCH_FAILED_STATUS,
                error_code="live_sync_execution_disabled",
            )
        if request.offset >= profile.row_limit:
            return ConnectorLiveSyncBatchResult(
                adapter=self.external_db_adapter_name,
                status=LIVE_SYNC_BATCH_READ_STATUS,
                next_offset=request.offset,
                source_exhausted=True,
            )
        selected_columns = _requested_or_default_columns(
            request.input_summary.get("selected_columns", ""),
            profile.allowed_columns,
        )
        order_column = _live_sync_node_mapping(request.field_mappings).source_column
        if order_column not in selected_columns:
            return ConnectorLiveSyncBatchResult(
                adapter=self.external_db_adapter_name,
                status=LIVE_SYNC_BATCH_FAILED_STATUS,
                error_code="source_schema_mismatch",
            )
        batch_size = min(request.batch_size, profile.row_limit - request.offset)
        try:
            rows = _read_external_postgres_batch_rows(
                profile,
                selected_columns=selected_columns,
                order_column=order_column,
                offset=request.offset,
                batch_size=batch_size,
            )
        except psycopg.OperationalError:
            return ConnectorLiveSyncBatchResult(
                adapter=self.external_db_adapter_name,
                status=LIVE_SYNC_BATCH_FAILED_STATUS,
                error_code="connector_unavailable",
            )
        except psycopg.Error:
            return ConnectorLiveSyncBatchResult(
                adapter=self.external_db_adapter_name,
                status=LIVE_SYNC_BATCH_FAILED_STATUS,
                error_code="query_failed",
            )
        records, records_rejected = _live_sync_records(request.field_mappings, rows)
        next_offset = request.offset + len(rows)
        return ConnectorLiveSyncBatchResult(
            adapter=self.external_db_adapter_name,
            status=LIVE_SYNC_BATCH_READ_STATUS,
            records=records,
            records_rejected=records_rejected,
            next_offset=next_offset,
            source_exhausted=len(rows) < batch_size or next_offset >= profile.row_limit,
            notes=["Postgres batch read through the allowlisted profile boundary."],
        )

    def _blocked_plan(self, *, adapter: str, reason: str) -> ConnectorLiveSyncPlan:
        return ConnectorLiveSyncPlan(
            adapter=adapter,
            status=LIVE_SYNC_PLAN_BLOCKED_STATUS,
            block_reason=reason,
            notes=[
                "Connector live sync execution was blocked by Axis runtime policy.",
                "No source read, credential material or graph mutation was started.",
            ],
        )


def _external_db_live_sync_policy_block_reason(
    request: ConnectorLiveSyncPlanRequest,
) -> str | None:
    evidence = request.egress_policy_evidence
    egress_policy_evidence_valid = (
        evidence.get("egress_policy_evidence_status", "") == "validated"
        and evidence.get("egress_policy_result_status", "") == "egress_policy_approved"
        and evidence.get("egress_policy_mode", "") == "approved_private_endpoint"
        and request.input_summary.get("egress_boundary", "") == "approved_private_endpoint"
    )
    if not egress_policy_evidence_valid:
        return "egress_policy_not_approved"
    if request.input_summary.get("credential_access_mode", "") != "lease_scoped_secret_ref":
        return "unsupported_credential_access_mode"
    lease_result = request.credential_lease_result
    lease_status = str(lease_result.get("status", "unknown"))
    lease_ref = str(lease_result.get("provider_lease_ref", ""))
    secret_material_returned = _bool_as_text(
        lease_result.get("secret_material_returned", True)
    )
    if (
        lease_status not in {"lease_executed", "lease_renewed"}
        or not lease_ref
        or secret_material_returned != "false"
    ):
        return "credential_lease_evidence_invalid"
    return None


def _resolved_file_csv_source_path(
    profile: FileCsvLiveSyncProfile,
    file_name: str,
) -> Path | None:
    if not file_name or not LIVE_SYNC_SOURCE_FILE_NAME_PATTERN.fullmatch(file_name):
        return None
    if not any(file_name.endswith(suffix) for suffix in profile.allowed_file_suffixes):
        return None
    source_root = Path(profile.source_root).resolve()
    source_path = (source_root / file_name).resolve()
    if source_path.parent != source_root:
        return None
    return source_path


def _read_file_csv_rows(source_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with source_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        rows = [
            {key: (value or "").strip() for key, value in row.items() if key is not None}
            for row in reader
        ]
    return headers, rows


def _live_sync_node_mapping(
    field_mappings: list[ConnectorLiveSyncFieldMapping],
) -> ConnectorLiveSyncFieldMapping:
    return next(
        (mapping for mapping in field_mappings if mapping.target_field == "node_id"),
        field_mappings[0],
    )


def _live_sync_node_type(ontology_target: str) -> str:
    if ontology_target.endswith("_asset"):
        return "asset"
    if ontology_target.endswith("_order"):
        return "work_order"
    return ontology_target


def _live_sync_records(
    field_mappings: list[ConnectorLiveSyncFieldMapping],
    rows: list[dict[str, str]],
) -> tuple[list[ConnectorLiveSyncRecord], int]:
    node_mapping = _live_sync_node_mapping(field_mappings)
    records: list[ConnectorLiveSyncRecord] = []
    records_rejected = 0
    for row in rows:
        node_id = row.get(node_mapping.source_column, "")
        if not node_id:
            records_rejected += 1
            continue
        field_summary = {
            mapping.source_column: row[mapping.source_column]
            for mapping in field_mappings
            if mapping.source_column in row and mapping.target_field != "node_id"
        }
        records.append(
            ConnectorLiveSyncRecord(
                node_id=node_id,
                node_type=_live_sync_node_type(node_mapping.ontology_target),
                ontology_type=node_mapping.ontology_target,
                field_summary=field_summary,
            )
        )
    return records, records_rejected


def _read_external_postgres_batch_rows(
    profile: ExternalPostgresLiveQueryProfile,
    *,
    selected_columns: list[str],
    order_column: str,
    offset: int,
    batch_size: int,
) -> list[dict[str, str]]:
    query = sql.SQL(
        "SELECT {columns} FROM {schema}.{table} ORDER BY {order_column} "
        "LIMIT {limit} OFFSET {offset}"
    ).format(
        columns=sql.SQL(", ").join(sql.Identifier(column) for column in selected_columns),
        schema=sql.Identifier(profile.schema_name),
        table=sql.Identifier(profile.table_name),
        order_column=sql.Identifier(order_column),
        limit=sql.Literal(batch_size),
        offset=sql.Literal(offset),
    )
    with psycopg.connect(
        _psycopg_dsn(profile.dsn),
        connect_timeout=profile.connect_timeout_seconds,
    ) as connection, connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.execute(query)
        rows = cursor.fetchall()
    return [
        {
            column: "" if value is None else str(value)
            for column, value in zip(selected_columns, row, strict=True)
        }
        for row in rows
    ]


def _blocked_external_db_live_read_result(
    request: ConnectorSyncExecutionRequest,
    *,
    preflight_result_summary: dict[str, str],
    connection_profile_id: str,
    reason: str,
) -> ConnectorSyncExecutionResult:
    result_summary = {
        **preflight_result_summary,
        "runtime_status": "sync_execution_live_query_blocked",
        "external_sync_started": "false",
        "records_read": "0",
        "records_accepted": "0",
        "records_rejected": "0",
        "live_query_execution_status": f"blocked_{reason}",
        "external_query_started": "false",
        "credential_material_returned": "false",
        "graph_mutation_started": "false",
        "source_mode": "external_db_live_read_blocked",
    }
    return ConnectorSyncExecutionResult(
        adapter=SelfHostedConnectorSyncExecutionRuntime.external_db_adapter_name,
        status="sync_execution_live_query_blocked",
        sync_ref=(
            f"postgres-external-db-live-read-blocked://{request.tenant_id}/"
            f"{connection_profile_id}/{request.run_id}/{request.execution_id}"
        ),
        external_sync_started=False,
        idempotency_key=request.idempotency_key,
        result_summary=result_summary,
        notes=[
            "Postgres external DB live read was blocked by Axis runtime policy.",
            "No external query, credential material or graph mutation was started.",
        ],
    )


def _live_read_block_reason(
    *,
    request: ConnectorSyncExecutionRequest,
    profile: ExternalPostgresLiveQueryProfile | None,
    live_query_execution_enabled: bool,
) -> str | None:
    if not live_query_execution_enabled:
        return "execution_disabled"
    if profile is None:
        return "profile_not_configured"
    return _external_postgres_profile_block_reason(
        input_summary=request.input_summary,
        egress_policy_evidence=request.egress_policy_evidence,
        profile=profile,
    )


def _external_postgres_profile_block_reason(
    *,
    input_summary: dict[str, str],
    egress_policy_evidence: dict[str, str],
    profile: ExternalPostgresLiveQueryProfile,
) -> str | None:
    if input_summary.get("query_mode", "") != "read_only_snapshot":
        return "unsupported_query_mode"
    if input_summary.get("connection_profile_id", "") != profile.profile_id:
        return "profile_mismatch"
    if (
        egress_policy_evidence.get("egress_policy_private_endpoint_ref", "")
        != profile.private_endpoint_ref
    ):
        return "private_endpoint_mismatch"
    if (
        egress_policy_evidence.get("egress_policy_endpoint_target_sha256", "")
        != profile.endpoint_target_sha256
    ):
        return "endpoint_target_mismatch"
    if input_summary.get("schema_name", "") != profile.schema_name:
        return "schema_mismatch"
    if input_summary.get("table_name", "") != profile.table_name:
        return "table_mismatch"
    identifiers = [profile.schema_name, profile.table_name, *profile.allowed_columns]
    if not all(POSTGRES_IDENTIFIER_PATTERN.fullmatch(identifier) for identifier in identifiers):
        return "invalid_profile_identifier"
    selected_columns = _requested_or_default_columns(
        input_summary.get("selected_columns", ""),
        profile.allowed_columns,
    )
    if not selected_columns:
        return "selected_columns_missing"
    allowed_columns = set(profile.allowed_columns)
    if any(column not in allowed_columns for column in selected_columns):
        return "selected_columns_not_allowlisted"
    if not all(POSTGRES_IDENTIFIER_PATTERN.fullmatch(column) for column in selected_columns):
        return "invalid_selected_column"
    return None


def _requested_or_default_columns(
    selected_columns: str,
    allowed_columns: list[str],
) -> list[str]:
    requested = [
        column.strip()
        for column in selected_columns.split(",")
        if column.strip()
    ]
    return requested or list(allowed_columns)


def _read_external_postgres_rows(
    profile: ExternalPostgresLiveQueryProfile,
    *,
    selected_columns: list[str],
) -> int:
    bounded_read = sql.SQL(
        "SELECT {columns} FROM {schema}.{table} LIMIT {limit}"
    ).format(
        columns=sql.SQL(", ").join(sql.Identifier(column) for column in selected_columns),
        schema=sql.Identifier(profile.schema_name),
        table=sql.Identifier(profile.table_name),
        limit=sql.Literal(profile.row_limit),
    )
    query = sql.SQL("SELECT count(*) FROM ({bounded_read}) AS axis_live_read_probe").format(
        bounded_read=bounded_read,
    )
    with psycopg.connect(
        _psycopg_dsn(profile.dsn),
        connect_timeout=profile.connect_timeout_seconds,
    ) as connection, connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.execute(query)
        row = cursor.fetchone()
    return int(row[0]) if row is not None else 0


def _psycopg_dsn(dsn: str) -> str:
    if dsn.startswith(POSTGRESQL_SQLALCHEMY_SCHEME):
        return f"{POSTGRESQL_PSYCOPG_SCHEME}{dsn[len(POSTGRESQL_SQLALCHEMY_SCHEME):]}"
    return dsn


def postgres_endpoint_target_sha256(dsn: str) -> str:
    parsed = urlparse(_psycopg_dsn(dsn))
    if not parsed.hostname:
        raise ValueError("Postgres live query DSN must include a hostname.")
    try:
        port = parsed.port or DEFAULT_POSTGRES_PORT
    except ValueError as exc:
        raise ValueError("Postgres live query DSN must include a valid port.") from exc
    endpoint_target = f"{parsed.hostname.lower()}:{port}"
    return hashlib.sha256(endpoint_target.encode("utf-8")).hexdigest()


def _egress_policy_evidence_from_request(
    *,
    tenant_id: str,
    connector_id: str,
    connection_profile_id: str,
    egress_policy_id: str,
    evidence: dict[str, str],
) -> dict[str, str]:
    requested_scope = f"{connector_id}:{connection_profile_id}"
    if evidence:
        return {
            "egress_policy_evidence_status": evidence.get(
                "egress_policy_evidence_status",
                "failed",
            ),
            "egress_policy_runtime_boundary": evidence.get(
                "egress_policy_runtime_boundary",
                "unknown",
            ),
            "egress_policy_result_status": evidence.get(
                "egress_policy_result_status",
                "egress_policy_evidence_missing",
            ),
            "egress_policy_ref": evidence.get(
                "egress_policy_ref",
                f"self-hosted-egress-policy://{tenant_id}/"
                f"{egress_policy_id or 'missing'}",
            ),
            "egress_policy_scope": evidence.get("egress_policy_scope", requested_scope),
            "egress_policy_mode": evidence.get("egress_policy_mode", "unknown"),
            "egress_policy_private_endpoint_ref": evidence.get(
                "egress_policy_private_endpoint_ref",
                "",
            ),
            "egress_policy_endpoint_target_sha256": evidence.get(
                "egress_policy_endpoint_target_sha256",
                "",
            ),
        }
    return {
        "egress_policy_evidence_status": "missing",
        "egress_policy_runtime_boundary": "axis-egress-policy-enforcer",
        "egress_policy_result_status": "egress_policy_not_found",
        "egress_policy_ref": (
            f"self-hosted-egress-policy://{tenant_id}/"
            f"{egress_policy_id or 'missing'}"
        ),
        "egress_policy_scope": requested_scope,
        "egress_policy_mode": "unknown",
        "egress_policy_private_endpoint_ref": "",
        "egress_policy_endpoint_target_sha256": "",
    }


def _secret_reference_evidence(
    *,
    connector_id: str,
    connection_profile_id: str,
    credential_access_mode: str,
    credential_lease_ref: str,
    secret_material_returned: str,
    policy_preflight_passed: bool,
) -> dict[str, str]:
    scope = f"{connector_id}:{connection_profile_id}"
    base = {
        "secret_reference_runtime_boundary": "axis-secret-reference-resolver",
        "secret_reference_scope": scope,
        "secret_reference_access_mode": credential_access_mode,
        "secret_reference_lease_ref": credential_lease_ref,
        "secret_reference_material_returned": secret_material_returned,
    }
    if not policy_preflight_passed:
        return {
            **base,
            "secret_reference_evidence_status": "not_started",
            "secret_reference_result_status": "policy_preflight_not_passed",
        }
    if credential_access_mode != "lease_scoped_secret_ref":
        return {
            **base,
            "secret_reference_evidence_status": "failed",
            "secret_reference_result_status": "unsupported_secret_access_mode",
        }
    if secret_material_returned == "true":
        return {
            **base,
            "secret_reference_evidence_status": "failed",
            "secret_reference_result_status": "secret_material_returned",
        }
    if not credential_lease_ref:
        return {
            **base,
            "secret_reference_evidence_status": "failed",
            "secret_reference_result_status": "secret_reference_missing_lease_ref",
        }
    return {
        **base,
        "secret_reference_evidence_status": "validated",
        "secret_reference_result_status": "secret_reference_validated",
    }


def _egress_policy_decision(
    *,
    preflight_enabled: bool,
    policy_evidence_valid: bool,
    policy_evidence_status: str,
) -> str:
    if not preflight_enabled:
        return "blocked_by_default"
    if policy_evidence_valid:
        return "approved_private_endpoint"
    if policy_evidence_status == "missing":
        return "blocked_policy_not_found"
    return "blocked_policy_mismatch"


def _bool_as_text(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).lower()


def _secret_retrieval_decision(
    *,
    preflight_enabled: bool,
    policy_preflight_passed: bool,
    secret_reference_evidence_valid: bool,
    lease_evidence_valid: bool,
    secret_material_returned: str,
) -> str:
    if not preflight_enabled:
        return "not_started"
    if not policy_preflight_passed:
        return "not_started"
    if secret_material_returned == "true":
        return "blocked_secret_material_returned"
    if not secret_reference_evidence_valid:
        return "blocked_secret_reference_evidence"
    if lease_evidence_valid:
        return "lease_scoped_reference_only"
    return "blocked_credential_lease_evidence"
