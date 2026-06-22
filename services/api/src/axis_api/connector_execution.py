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
    credential_lease_mode: str = Field(default="", min_length=0)
    credential_lease_runtime_boundary: str = Field(default="", min_length=0)
    credential_lease_result: dict = Field(default_factory=dict)
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

    def __init__(
        self,
        *,
        external_db_sync_enabled: bool = False,
        external_db_live_query_preflight_enabled: bool = False,
    ) -> None:
        self.external_db_sync_enabled = external_db_sync_enabled
        self.external_db_live_query_preflight_enabled = external_db_live_query_preflight_enabled

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
        egress_policy_evidence = _external_db_egress_policy_evidence(
            tenant_id=request.tenant_id,
            connector_id=request.connector_id,
            connection_profile_id=connection_profile_id,
            egress_policy_id=egress_policy_id,
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


def _external_db_egress_policy_evidence(
    *,
    tenant_id: str,
    connector_id: str,
    connection_profile_id: str,
    egress_policy_id: str,
) -> dict[str, str]:
    expected_scope = "external_db_operational_mirror:profile_postgres_ops_readonly"
    requested_scope = f"{connector_id}:{connection_profile_id}"
    if (
        egress_policy_id == "egress_policy_private_endpoint_ops"
        and requested_scope == expected_scope
    ):
        return {
            "egress_policy_evidence_status": "validated",
            "egress_policy_runtime_boundary": "axis-egress-policy-enforcer",
            "egress_policy_result_status": "egress_policy_approved",
            "egress_policy_ref": (
                f"self-hosted-egress-policy://{tenant_id}/"
                "egress_policy_private_endpoint_ops"
            ),
            "egress_policy_scope": requested_scope,
            "egress_policy_mode": "approved_private_endpoint",
            "egress_policy_private_endpoint_ref": (
                f"private-endpoint://{tenant_id}/operations-postgres-readonly"
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
