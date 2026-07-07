import os

import pytest
from sqlalchemy import create_engine, text

from axis_api.config import Settings
from axis_api.connector_execution import (
    ConnectorLiveSyncBatchRequest,
    ConnectorLiveSyncFieldMapping,
    ConnectorLiveSyncPlanRequest,
    ConnectorSyncExecutionRequest,
    ExternalPostgresLiveQueryProfile,
    SelfHostedConnectorLiveSyncRuntime,
    SelfHostedConnectorSyncExecutionRuntime,
    postgres_endpoint_target_sha256,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("AXIS_RUN_INTEGRATION") != "1",
        reason="set AXIS_RUN_INTEGRATION=1 with the local Docker runtime running",
    ),
]


def test_external_db_live_query_runtime_reads_allowlisted_postgres_table() -> None:
    settings = Settings()
    private_endpoint_ref = (
        "private-endpoint://tenant_demo_manufacturing/persisted-operations-postgres-readonly"
    )
    endpoint_target_sha256 = postgres_endpoint_target_sha256(settings.postgres_dsn)
    engine = create_engine(settings.postgres_dsn)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS axis_live_connector_test CASCADE"))
            connection.execute(text("CREATE SCHEMA axis_live_connector_test"))
            connection.execute(
                text(
                    "CREATE TABLE axis_live_connector_test.production_orders ("
                    "order_id text PRIMARY KEY, "
                    "asset_id text NOT NULL, "
                    "work_center text NOT NULL, "
                    "status text NOT NULL, "
                    "risk_level text NOT NULL"
                    ")"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO axis_live_connector_test.production_orders "
                    "(order_id, asset_id, work_center, status, risk_level) VALUES "
                    "('po-1001', 'asset-7', 'line-a', 'scheduled', 'low'), "
                    "('po-1002', 'asset-9', 'line-b', 'blocked', 'high'), "
                    "('po-1003', 'asset-11', 'line-c', 'running', 'medium')"
                )
            )

        runtime = SelfHostedConnectorSyncExecutionRuntime(
            external_db_sync_enabled=True,
            external_db_live_query_preflight_enabled=True,
            external_db_live_query_execution_enabled=True,
            external_postgres_live_query_profile=ExternalPostgresLiveQueryProfile(
                profile_id="profile_postgres_ops_readonly",
                dsn=settings.postgres_dsn,
                schema_name="axis_live_connector_test",
                table_name="production_orders",
                allowed_columns=[
                    "order_id",
                    "asset_id",
                    "work_center",
                    "status",
                    "risk_level",
                ],
                private_endpoint_ref=private_endpoint_ref,
                endpoint_target_sha256=endpoint_target_sha256,
                row_limit=10,
            ),
        )

        result = runtime.execute(
            ConnectorSyncExecutionRequest(
                tenant_id="tenant_demo_manufacturing",
                connector_id="external_db_operational_mirror",
                run_id="run_external_db_live_runtime_integration",
                execution_id="sync_exec_external_db_live_runtime_integration",
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
                    "egress_policy_private_endpoint_ref": (
                        private_endpoint_ref
                    ),
                    "egress_policy_endpoint_target_sha256": endpoint_target_sha256,
                },
                schedule_id="schedule_external_db_orders_hourly",
                schedule_ref="deferred-sync://tenant_demo_manufacturing/schedule",
                dispatch_id="dispatch_external_db_live_runtime_integration",
                dispatch_ref="deferred-sync-dispatch://tenant/run/dispatch",
                idempotency_key="idem_sync_exec_external_db_live_runtime_integration",
                input_summary={
                    "connection_profile_id": "profile_postgres_ops_readonly",
                    "schema_name": "axis_live_connector_test",
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
        )
    finally:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS axis_live_connector_test CASCADE"))
        engine.dispose()

    summary = result.result_summary
    assert result.status == "sync_execution_completed"
    assert result.external_sync_started is True
    assert summary["source_mode"] == "external_db_live_read"
    assert summary["external_query_started"] == "true"
    assert summary["records_read"] == "3"
    assert summary["records_accepted"] == "3"
    assert summary["records_rejected"] == "0"
    assert summary["credential_material_returned"] == "false"
    assert summary["graph_mutation_started"] == "false"
    assert "dsn" not in str(summary).lower()
    assert "postgresql://" not in str(summary).lower()
    assert "po-1001" not in str(summary)


def test_external_db_live_sync_runtime_reads_batched_rows_from_postgres() -> None:
    settings = Settings()
    private_endpoint_ref = (
        "private-endpoint://tenant_demo_manufacturing/persisted-operations-postgres-readonly"
    )
    endpoint_target_sha256 = postgres_endpoint_target_sha256(settings.postgres_dsn)
    engine = create_engine(settings.postgres_dsn)
    field_mappings = [
        ConnectorLiveSyncFieldMapping(
            source_column="order_id",
            target_field="node_id",
            ontology_target="production_order",
        ),
        ConnectorLiveSyncFieldMapping(
            source_column="status",
            target_field="status",
            ontology_target="production_order",
        ),
        ConnectorLiveSyncFieldMapping(
            source_column="risk_level",
            target_field="risk_level",
            ontology_target="production_order",
        ),
    ]
    input_summary = {
        "live_sync_requested": "true",
        "connection_profile_id": "profile_postgres_ops_readonly",
        "schema_name": "axis_live_sync_test",
        "table_name": "production_orders",
        "selected_columns": "order_id,asset_id,work_center,status,risk_level",
        "query_mode": "read_only_snapshot",
        "egress_policy_id": "egress_policy_private_endpoint_ops",
        "egress_boundary": "approved_private_endpoint",
        "credential_access_mode": "lease_scoped_secret_ref",
    }
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS axis_live_sync_test CASCADE"))
            connection.execute(text("CREATE SCHEMA axis_live_sync_test"))
            connection.execute(
                text(
                    "CREATE TABLE axis_live_sync_test.production_orders ("
                    "order_id text PRIMARY KEY, "
                    "asset_id text NOT NULL, "
                    "work_center text NOT NULL, "
                    "status text NOT NULL, "
                    "risk_level text NOT NULL"
                    ")"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO axis_live_sync_test.production_orders "
                    "(order_id, asset_id, work_center, status, risk_level) VALUES "
                    "('po-1001', 'asset-7', 'line-a', 'scheduled', 'low'), "
                    "('po-1002', 'asset-9', 'line-b', 'blocked', 'high'), "
                    "('po-1003', 'asset-11', 'line-c', 'running', 'medium')"
                )
            )

        runtime = SelfHostedConnectorLiveSyncRuntime(
            external_db_live_sync_enabled=True,
            external_postgres_profile=ExternalPostgresLiveQueryProfile(
                profile_id="profile_postgres_ops_readonly",
                dsn=settings.postgres_dsn,
                schema_name="axis_live_sync_test",
                table_name="production_orders",
                allowed_columns=[
                    "order_id",
                    "asset_id",
                    "work_center",
                    "status",
                    "risk_level",
                ],
                private_endpoint_ref=private_endpoint_ref,
                endpoint_target_sha256=endpoint_target_sha256,
                row_limit=10,
            ),
            external_db_batch_size=2,
        )
        plan = runtime.plan(
            ConnectorLiveSyncPlanRequest(
                tenant_id="tenant_demo_manufacturing",
                connector_id="external_db_operational_mirror",
                run_id="run_external_db_live_sync_integration",
                execution_id="sync_exec_external_db_live_sync_integration",
                executed_by="axis-sync-worker-role",
                credential_lease_id="lease_external_db_readonly_20260622",
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
                    "egress_policy_result_status": "egress_policy_approved",
                    "egress_policy_mode": "approved_private_endpoint",
                    "egress_policy_private_endpoint_ref": private_endpoint_ref,
                    "egress_policy_endpoint_target_sha256": endpoint_target_sha256,
                },
                field_mappings=field_mappings,
                input_summary=input_summary,
            )
        )
        assert plan.status == "live_sync_plan_ready"
        assert plan.batch_size == 2

        batches = []
        offset = 0
        while True:
            batch = runtime.read_batch(
                ConnectorLiveSyncBatchRequest(
                    tenant_id="tenant_demo_manufacturing",
                    connector_id="external_db_operational_mirror",
                    run_id="run_external_db_live_sync_integration",
                    execution_id="sync_exec_external_db_live_sync_integration",
                    offset=offset,
                    batch_size=plan.batch_size,
                    field_mappings=field_mappings,
                    input_summary=input_summary,
                )
            )
            assert batch.status == "live_sync_batch_read"
            batches.append(batch)
            offset = batch.next_offset
            if batch.source_exhausted:
                break
    finally:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS axis_live_sync_test CASCADE"))
        engine.dispose()

    records = [record for batch in batches for record in batch.records]
    assert [record.node_id for record in records] == ["po-1001", "po-1002", "po-1003"]
    assert records[0].node_type == "work_order"
    assert records[0].ontology_type == "production_order"
    assert records[0].field_summary["status"] == "scheduled"
    assert len(batches) == 2
    assert batches[0].next_offset == 2
    assert batches[1].source_exhausted is True
