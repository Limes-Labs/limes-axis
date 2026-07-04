from axis_api.connector_execution import (
    ConnectorSyncExecutionRequest,
    ExternalPostgresLiveQueryProfile,
    SelfHostedConnectorSyncExecutionRuntime,
    postgres_endpoint_target_sha256,
)
from axis_api.connector_runs import _sync_checkpoint_result_is_public_safe

APPROVED_DSN = "postgresql://readonly.local/axis_external"
UNAPPROVED_DSN = "postgresql://unapproved.local/axis_external"
PRIVATE_ENDPOINT_REF = (
    "private-endpoint://tenant_demo_manufacturing/persisted-operations-postgres-readonly"
)


def live_query_request(*, endpoint_target_sha256: str) -> ConnectorSyncExecutionRequest:
    return ConnectorSyncExecutionRequest(
        tenant_id="tenant_demo_manufacturing",
        connector_id="external_db_operational_mirror",
        run_id="run_external_db_live_runtime_policy",
        execution_id="sync_exec_external_db_live_runtime_policy",
        runtime_boundary="axis-connector-sandbox",
        executed_by="axis-sync-worker-role",
        credential_handle_ids=["cred_external_db_readonly"],
        credential_lease_id="lease_external_db_readonly_20260622",
        credential_lease_mode="self_hosted_vault_kms_lease",
        credential_lease_runtime_boundary="axis-credential-lease-broker",
        credential_lease_result={
            "status": "lease_executed",
            "provider_lease_ref": (
                "self-hosted-vault-kms://tenant_demo_manufacturing/"
                "lease_external_db_readonly_20260622"
            ),
            "secret_material_returned": False,
        },
        egress_policy_evidence={
            "egress_policy_evidence_status": "validated",
            "egress_policy_runtime_boundary": "axis-egress-policy-enforcer",
            "egress_policy_result_status": "egress_policy_approved",
            "egress_policy_ref": (
                "self-hosted-egress-policy://tenant_demo_manufacturing/"
                "egress_policy_private_endpoint_ops"
            ),
            "egress_policy_scope": (
                "external_db_operational_mirror:profile_postgres_ops_readonly"
            ),
            "egress_policy_mode": "approved_private_endpoint",
            "egress_policy_private_endpoint_ref": PRIVATE_ENDPOINT_REF,
            "egress_policy_endpoint_target_sha256": endpoint_target_sha256,
        },
        schedule_id="schedule_external_db_orders_hourly",
        schedule_ref="deferred-sync://tenant_demo_manufacturing/schedule",
        dispatch_id="dispatch_external_db_live_runtime_policy",
        dispatch_ref="deferred-sync-dispatch://tenant/run/dispatch",
        idempotency_key="idem_sync_exec_external_db_live_runtime_policy",
        input_summary={
            "connection_profile_id": "profile_postgres_ops_readonly",
            "schema_name": "operations",
            "table_name": "production_orders",
            "selected_columns": "order_id,asset_id,work_center,status,risk_level",
            "live_query_requested": "true",
            "live_query_execute": "true",
            "query_mode": "read_only_snapshot",
            "egress_policy_id": "egress_policy_private_endpoint_ops",
            "egress_boundary": "approved_private_endpoint",
            "credential_access_mode": "lease_scoped_secret_ref",
        },
    )


def test_external_db_live_read_blocks_unbound_egress_endpoint_target() -> None:
    runtime = SelfHostedConnectorSyncExecutionRuntime(
        external_db_sync_enabled=True,
        external_db_live_query_preflight_enabled=True,
        external_db_live_query_execution_enabled=True,
        external_postgres_live_query_profile=ExternalPostgresLiveQueryProfile(
            profile_id="profile_postgres_ops_readonly",
            dsn=APPROVED_DSN,
            schema_name="operations",
            table_name="production_orders",
            allowed_columns=["order_id", "asset_id", "work_center", "status", "risk_level"],
            private_endpoint_ref=PRIVATE_ENDPOINT_REF,
            endpoint_target_sha256=postgres_endpoint_target_sha256(APPROVED_DSN),
        ),
    )

    result = runtime.execute(
        live_query_request(
            endpoint_target_sha256=postgres_endpoint_target_sha256(UNAPPROVED_DSN),
        )
    )

    assert result.status == "sync_execution_live_query_blocked"
    assert result.external_sync_started is False
    assert result.result_summary["live_query_execution_status"] == (
        "blocked_endpoint_target_mismatch"
    )
    assert result.result_summary["external_query_started"] == "false"
    assert "dsn" not in str(result.model_dump(mode="json")).lower()


def test_live_read_checkpoint_public_safety_rejects_unallowlisted_payload_fields() -> None:
    summary = {
        "runtime_status": "sync_execution_completed",
        "external_sync_started": "true",
        "connector_id": "external_db_operational_mirror",
        "schedule_id": "schedule_external_db_orders_hourly",
        "dispatch_id": "dispatch_external_db_live_runtime_policy",
        "execution_id": "sync_exec_external_db_live_runtime_policy",
        "provider": "postgres",
        "connection_profile_id": "profile_postgres_ops_readonly",
        "schema_name": "operations",
        "table_name": "production_orders",
        "query_mode": "read_only_snapshot",
        "records_read": "1",
        "records_accepted": "1",
        "records_rejected": "0",
        "live_query_requested": "true",
        "live_query_preflight_status": "passed",
        "live_query_execute_requested": "true",
        "live_query_execution_status": "completed",
        "live_query_profile_id": "profile_postgres_ops_readonly",
        "live_query_row_limit": "100",
        "selected_column_count": "5",
        "egress_policy_decision": "approved_private_endpoint",
        "secret_retrieval_decision": "lease_scoped_reference_only",
        "external_query_started": "true",
        "credential_material_returned": "false",
        "graph_mutation_started": "false",
        "source_mode": "external_db_live_read",
        "rows": [{"order_id": "po-1001"}],
    }

    assert _sync_checkpoint_result_is_public_safe(summary) is False
