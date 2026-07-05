"""End-to-end tests: the blocking SDK client against the real FastAPI app."""

from __future__ import annotations

import pytest
from axis_api.identity import OidcPrincipal
from conftest import (
    TENANT_ID,
    RecordingTransport,
    SyncASGITransport,
    build_app,
)
from fastapi import FastAPI

from axis_sdk import (
    AuthRequiredError,
    AxisClient,
    NotFoundError,
    PermissionDeniedError,
    PolicyViolationError,
    ValidationFailedError,
)
from axis_sdk.models import ApprovalDecision, OverviewStatus

BASE_URL = "http://axis-api.test"


def make_client(app: FastAPI, **kwargs) -> AxisClient:
    kwargs.setdefault("tenant_id", TENANT_ID)
    return AxisClient(BASE_URL, transport=SyncASGITransport(app), **kwargs)


def test_health_and_readiness(app: FastAPI) -> None:
    with make_client(app) as client:
        health = client.system.health()
        ready = client.system.ready()

    assert health.status == "ok"
    assert health.service == "axis-api"
    assert ready.status == "ready"
    assert "postgres" in ready.dependencies


def test_deployment_readiness_report(app: FastAPI) -> None:
    with make_client(app) as client:
        report = client.system.deployment_readiness()

    assert report.environment == "development"
    assert report.checks
    assert isinstance(report.production_ready, bool)


def test_list_approvals_returns_typed_inbox(app: FastAPI) -> None:
    with make_client(app) as client:
        inbox = client.approvals.list()

    assert inbox.tenant_id == TENANT_ID
    assert inbox.approvals
    approval_ids = {approval.approval_id for approval in inbox.approvals}
    assert "appr_expedite_supplier_batch" in approval_ids
    assert all(approval.decision_options for approval in inbox.approvals)


def test_get_single_approval_filters_inbox(app: FastAPI) -> None:
    with make_client(app) as client:
        approval = client.approvals.get("appr_expedite_supplier_batch")
        with pytest.raises(LookupError):
            client.approvals.get("appr_missing")

    assert approval.workflow_id == "wf_supplier_delay_review"
    assert approval.required_permission == "approvals:supply:decide"


def test_decide_approval_persists_decision(app: FastAPI) -> None:
    with make_client(app) as client:
        result = client.approvals.decide(
            "appr_shift_maintenance_window",
            decision=ApprovalDecision.APPROVE,
            actor_id="maintenance-owner-role",
            actor_scopes=["approvals:maintenance:decide"],
            note="Approved through the SDK end-to-end test.",
        )

    assert result.persisted is True
    assert result.decision == ApprovalDecision.APPROVE
    assert result.permission_decision.allowed is True
    assert result.audit_event_type == "approval.decision.recorded"
    assert result.workflow_signal_status == "approval_signaled"


def test_action_catalog_lists_typed_actions(app: FastAPI) -> None:
    with make_client(app) as client:
        catalog = client.actions.catalog()

    assert catalog.tenant_id == TENANT_ID
    action_ids = {entry.definition.action_id for entry in catalog.actions}
    assert "request_supplier_expedite" in action_ids
    entry = next(
        entry
        for entry in catalog.actions
        if entry.definition.action_id == "request_supplier_expedite"
    )
    assert entry.policy.idempotency_required is True
    assert "supply:read" in entry.definition.required_permissions


def test_create_action_run_with_idempotency_key(app: FastAPI) -> None:
    with make_client(app) as client:
        result = client.actions.create_run(
            "request_supplier_expedite",
            actor_id="agent_supply_risk",
            actor_scopes=["supply:read", "approvals:supply:request"],
            idempotency_key="sdk-e2e-supplier-run-1",
            payload={
                "supplier_batch_id": "asset_motors_batch",
                "target_arrival": "2026-06-22T08:00:00+02:00",
                "reason": "Line 2 packaging risk",
                "cost_ceiling_eur": "1200",
            },
        )

    assert result.persisted is True
    assert result.idempotency_key == "sdk-e2e-supplier-run-1"
    assert result.idempotent_replay is False
    assert result.approval_required is True
    assert result.permission_decision.allowed is True


def test_action_run_idempotent_replay_round_trip(app: FastAPI) -> None:
    payload = {
        "supplier_batch_id": "asset_motors_batch",
        "target_arrival": "2026-06-22T08:00:00+02:00",
        "reason": "Line 2 packaging risk",
        "cost_ceiling_eur": "1200",
    }
    with make_client(app) as client:
        first = client.actions.create_run(
            "request_supplier_expedite",
            actor_id="agent_supply_risk",
            actor_scopes=["supply:read", "approvals:supply:request"],
            idempotency_key="sdk-e2e-replay-key",
            payload=payload,
        )
        replay = client.actions.create_run(
            "request_supplier_expedite",
            actor_id="agent_supply_risk",
            actor_scopes=["supply:read", "approvals:supply:request"],
            idempotency_key="sdk-e2e-replay-key",
            payload=payload,
        )

    assert first.idempotent_replay is False
    assert replay.idempotent_replay is True
    assert replay.action_run_id == first.action_run_id


def test_action_run_idempotency_conflict_maps_to_policy_violation(app: FastAPI) -> None:
    with make_client(app) as client:
        client.actions.create_run(
            "request_supplier_expedite",
            actor_id="agent_supply_risk",
            actor_scopes=["supply:read", "approvals:supply:request"],
            idempotency_key="sdk-e2e-conflict-key",
            payload={
                "supplier_batch_id": "asset_motors_batch",
                "target_arrival": "2026-06-22T08:00:00+02:00",
                "reason": "Line 2 packaging risk",
                "cost_ceiling_eur": "1200",
            },
        )
        with pytest.raises(PolicyViolationError) as excinfo:
            client.actions.create_run(
                "request_supplier_expedite",
                actor_id="agent_supply_risk",
                actor_scopes=["supply:read", "approvals:supply:request"],
                idempotency_key="sdk-e2e-conflict-key",
                payload={
                    "supplier_batch_id": "asset_motors_batch",
                    "target_arrival": "2026-06-23T08:00:00+02:00",
                    "reason": "Changed payload with the same key",
                    "cost_ceiling_eur": "1500",
                },
            )

    assert excinfo.value.status_code == 409
    assert excinfo.value.code == "POLICY_VIOLATION"
    assert excinfo.value.request_id is not None


def test_record_action_run_outcome_round_trip(app: FastAPI) -> None:
    with make_client(app) as client:
        decision = client.approvals.decide(
            "appr_expedite_supplier_batch",
            decision=ApprovalDecision.APPROVE,
            actor_id="plant-operations-owner-role",
            actor_scopes=["approvals:supply:decide"],
        )
        assert decision.action_run_recorded is True
        assert decision.action_run_id is not None
        outcome = client.actions.record_outcome(
            decision.action_run_id,
            actor_id="workflow-runtime",
            actor_scopes=["actions:result:record"],
            status="dry_run_completed",
            result_summary="Supplier expedite dry-run package generated.",
            idempotency_key="sdk-e2e-outcome-1",
            evidence_refs=["audit_supplier_expedite_preview"],
        )

    assert outcome.persisted is True
    assert outcome.idempotency_key == "sdk-e2e-outcome-1"
    assert outcome.evidence_refs == ["audit_supplier_expedite_preview"]
    assert outcome.status == "dry_run_completed"


def test_workflow_console_and_persisted_runs(app: FastAPI) -> None:
    with make_client(app) as client:
        console = client.workflows.console()
        decision = client.approvals.decide(
            "appr_expedite_supplier_batch",
            decision=ApprovalDecision.APPROVE,
            actor_id="plant-operations-owner-role",
            actor_scopes=["approvals:supply:decide"],
        )
        runs = client.workflows.list_runs()
        run = client.workflows.get_run(decision.workflow_id)

    assert console.workflow_runs
    assert any(item.workflow_id == "wf_supplier_delay_review" for item in console.workflow_runs)
    assert any(item.workflow_id == decision.workflow_id for item in runs.workflow_runs)
    assert run.workflow_id == decision.workflow_id
    assert run.timeline, "persisted run must expose its timeline"


def test_workflow_get_run_raises_lookup_error_for_unknown_run(app: FastAPI) -> None:
    with make_client(app) as client, pytest.raises(LookupError):
        client.workflows.get_run("wf_does_not_exist")


def test_audit_explorer_and_persisted_events(app: FastAPI) -> None:
    with make_client(app) as client:
        explorer = client.audit.explorer()
        client.approvals.decide(
            "appr_quality_hold_batch",
            decision=ApprovalDecision.REQUEST_CHANGES,
            actor_id="quality-owner-role",
            actor_scopes=["approvals:quality:decide"],
        )
        events = client.audit.query_events(event_type="approval.decision.recorded")

    assert explorer.tenant_id == TENANT_ID
    assert explorer.events
    assert events.ledger_status == OverviewStatus.READY
    assert events.events
    assert all(event.event_type == "approval.decision.recorded" for event in events.events)


def test_audit_export_bundle_carries_integrity_proof(app: FastAPI) -> None:
    with make_client(app) as client:
        client.approvals.decide(
            "appr_quality_hold_batch",
            decision=ApprovalDecision.APPROVE,
            actor_id="quality-owner-role",
            actor_scopes=["approvals:quality:decide"],
        )
        bundle = client.audit.export(export_reason="sdk-e2e-review", retention_days=365)

    assert bundle.tenant_id == TENANT_ID
    assert bundle.manifest.record_count == len(bundle.events)
    assert bundle.integrity_proof.verification_status
    assert len(bundle.manifest.checksum_sha256) == 64


def test_ontology_graph_and_entity_detail(app: FastAPI) -> None:
    with make_client(app) as client:
        graph = client.ontology.graph()
        node_id = graph.nodes[0].node_id
        detail = client.ontology.entity(node_id)

    assert graph.nodes and graph.relationships
    assert graph.graph_query is not None
    assert graph.graph_query.permission_decision.allowed is True
    assert detail.node.node_id == node_id
    assert detail.inbound_count + detail.outbound_count >= 0


def test_agent_registry_lists_governed_agents(app: FastAPI) -> None:
    with make_client(app) as client:
        registry = client.agents.registry()

    assert registry.tenant_id == TENANT_ID
    assert registry.agents
    assert all(agent.policy_boundary.autonomy_level for agent in registry.agents)


def test_missing_approval_maps_to_not_found(app: FastAPI) -> None:
    with make_client(app) as client, pytest.raises(NotFoundError) as excinfo:
        client.approvals.decide(
            "appr_unknown",
            decision="approve",
            actor_id="plant-operations-owner-role",
            actor_scopes=["approvals:supply:decide"],
        )

    assert excinfo.value.status_code == 404
    assert excinfo.value.message == "Approval not found"


def test_missing_ontology_entity_maps_to_not_found(app: FastAPI) -> None:
    with make_client(app) as client, pytest.raises(NotFoundError) as excinfo:
        client.ontology.entity("node_does_not_exist")

    assert excinfo.value.status_code == 404


def test_invalid_action_payload_maps_to_validation_failed(app: FastAPI) -> None:
    with make_client(app) as client, pytest.raises(ValidationFailedError) as excinfo:
        client.actions.create_run(
            "request_supplier_expedite",
            actor_id="agent_supply_risk",
            actor_scopes=["supply:read", "approvals:supply:request"],
            idempotency_key="sdk-e2e-invalid-payload",
            payload={"unexpected_field": "value"},
        )

    assert excinfo.value.status_code == 422
    assert excinfo.value.code == "VALIDATION_FAILED"


def test_invalid_decision_enum_maps_to_validation_failed(app: FastAPI) -> None:
    with make_client(app) as client, pytest.raises(ValidationFailedError) as excinfo:
        client.approvals.decide(
            "appr_expedite_supplier_batch",
            decision="escalate",
            actor_id="plant-operations-owner-role",
        )

    assert excinfo.value.status_code == 422
    assert excinfo.value.code == "VALIDATION_FAILED"


def test_missing_token_maps_to_auth_required(session_factory) -> None:
    app = build_app(session_factory, oidc_auth_required=True)
    with make_client(app) as client, pytest.raises(AuthRequiredError) as excinfo:
        client.approvals.decide(
            "appr_expedite_supplier_batch",
            decision="approve",
            actor_id="plant-operations-owner-role",
            actor_scopes=["approvals:supply:decide"],
        )

    assert excinfo.value.status_code == 401
    assert excinfo.value.code == "AUTH_REQUIRED"
    assert excinfo.value.request_id is not None


def test_tenant_mismatch_maps_to_permission_denied(session_factory) -> None:
    app = build_app(
        session_factory,
        oidc_auth_required=True,
        principal=OidcPrincipal(
            actor_id="plant-operations-owner-role",
            tenant_id="tenant_other",
            scopes=["approvals:supply:decide"],
        ),
    )
    with (
        make_client(app, token="sdk-test-token") as client,
        pytest.raises(PermissionDeniedError) as excinfo,
    ):
        client.approvals.decide(
            "appr_expedite_supplier_batch",
            decision="approve",
            actor_id="plant-operations-owner-role",
            actor_scopes=["approvals:supply:decide"],
        )

    assert excinfo.value.status_code == 403
    assert excinfo.value.code == "PERMISSION_DENIED"
    assert excinfo.value.detail["detail"]["reason"] == "tenant_mismatch"


def test_bearer_token_flows_to_oidc_actor_binding(session_factory) -> None:
    app = build_app(
        session_factory,
        oidc_auth_required=True,
        principal=OidcPrincipal(
            actor_id="plant-operations-owner-role",
            tenant_id=TENANT_ID,
            scopes=["approvals:supply:decide"],
        ),
    )
    with make_client(app, token="sdk-test-token") as client:
        result = client.approvals.decide(
            "appr_expedite_supplier_batch",
            decision=ApprovalDecision.APPROVE,
            actor_id="plant-operations-owner-role",
        )

    assert result.actor_id == "plant-operations-owner-role"
    assert result.permission_decision.allowed is True


def test_errors_are_never_retried_on_4xx(app: FastAPI) -> None:
    recording = RecordingTransport(SyncASGITransport(app))
    with (
        AxisClient(BASE_URL, tenant_id=TENANT_ID, transport=recording) as client,
        pytest.raises(NotFoundError),
    ):
        client.ontology.entity("node_does_not_exist")

    assert len(recording.requests) == 1
