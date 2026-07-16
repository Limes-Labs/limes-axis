import json
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from runpy import run_path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.agent_runs import (
    AGENT_RUN_EXECUTE_SCOPE,
    AgentRunAgentNotExecutable,
    AgentRunAgentNotFound,
    AgentRunIdempotencyConflict,
    AgentRunNotFound,
    AgentRunPermissionDenied,
    AgentRunStartRequest,
    get_agent_run_result,
    list_agent_run_results,
    parse_agent_action_proposal,
    start_agent_run,
)
from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.identity import OidcPrincipal
from axis_api.main import create_app
from axis_api.model_endpoints import (
    MODEL_ENDPOINT_ADMIN_SCOPE,
    ModelEndpointCreateRequest,
    record_model_endpoint,
)
from axis_api.model_invocations import MODEL_INVOKE_SCOPE
from axis_api.model_providers import (
    DeferredModelInvocationRuntime,
    ModelInvocationRuntimeResult,
    ModelProviderInvocationError,
)
from axis_api.models import (
    ActionRun,
    AgentRun,
    AgentRunStep,
    AuditEvent,
    Base,
    ModelInvocation,
    TenantUsageEvent,
    TenantUsageRecord,
)
from axis_api.persistence import (
    AxisPersistenceRepository,
    DemoReferenceRecordCreate,
    ManufacturingOperationRecordCreate,
    PlatformPolicyCreate,
)
from axis_api.platform_policies import PlatformPolicyEnforcementDenied

TENANT_ID = "tenant_demo_manufacturing"

DAILY_BRIEF_SCOPES = [
    AGENT_RUN_EXECUTE_SCOPE,
    MODEL_INVOKE_SCOPE,
    "agents:read",
    "audit:read",
    "workflows:read",
]
SUPPLY_SCOPES = [
    AGENT_RUN_EXECUTE_SCOPE,
    MODEL_INVOKE_SCOPE,
    "agents:read",
    "supply:read",
    "approvals:supply:request",
]

DAILY_BRIEF_PROPOSAL = {
    "action_id": "generate_daily_plant_brief",
    "summary": "Generate the governed morning brief for plant owners.",
    "payload": {
        "tenant_id": TENANT_ID,
        "scope": "daily_operations",
        "evidence_refs": ["wf_supplier_delay_review"],
    },
    "evidence_refs": ["manufacturing_operation_record:order_rush_4812"],
}
SUPPLIER_EXPEDITE_PROPOSAL = {
    "action_id": "request_supplier_expedite",
    "summary": "Expedite the delayed motors batch before Line 2 starves.",
    "payload": {
        "supplier_batch_id": "asset_motors_batch",
        "target_arrival": "2026-06-22T08:00:00+02:00",
        "reason": "Line 2 packaging risk",
        "cost_ceiling_eur": "1200",
    },
    "evidence_refs": ["manufacturing_operation_record:material_lot_motors_7741"],
}


class ProposalModelRuntime:
    """Test double that emits a canned parseable JSON proposal."""

    adapter_name = "axis-test-proposal-model-runtime"

    def __init__(self, proposal: dict, *, wrap_in_fence: bool = False) -> None:
        self.proposal = proposal
        self.wrap_in_fence = wrap_in_fence
        self.requests: list[object] = []

    async def invoke(self, request) -> ModelInvocationRuntimeResult:
        self.requests.append(request)
        output = json.dumps(self.proposal)
        if self.wrap_in_fence:
            output = f"```json\n{output}\n```"
        return ModelInvocationRuntimeResult(
            adapter=self.adapter_name,
            status="model_invocation_completed",
            output_text=output,
            input_tokens=210,
            output_tokens=64,
            latency_ms=42,
            provider_request_ref="chatcmpl-agent-test-001",
            notes=["Test proposal runtime completed the invocation."],
        )

    def describe(self) -> dict[str, str]:
        return {"adapter": self.adapter_name, "execution_mode": "test"}


class GarbageModelRuntime:
    adapter_name = "axis-test-garbage-model-runtime"

    async def invoke(self, request) -> ModelInvocationRuntimeResult:
        return ModelInvocationRuntimeResult(
            adapter=self.adapter_name,
            status="model_invocation_completed",
            output_text="Sure! I think you should probably expedite something?",
            input_tokens=210,
            output_tokens=12,
            latency_ms=18,
        )

    def describe(self) -> dict[str, str]:
        return {"adapter": self.adapter_name, "execution_mode": "test_garbage"}


class FailingModelRuntime:
    adapter_name = "axis-test-failing-model-runtime"

    async def invoke(self, request) -> ModelInvocationRuntimeResult:
        raise ModelProviderInvocationError(
            "The model provider endpoint could not be reached.",
            "provider_unreachable",
            latency_ms=9,
        )

    def describe(self) -> dict[str, str]:
        return {"adapter": self.adapter_name, "execution_mode": "test_failing"}


class StaticIdentityVerifier:
    def __init__(self, principal: OidcPrincipal) -> None:
        self.principal = principal

    def verify_authorization_header(self, authorization: str | None) -> OidcPrincipal:
        assert authorization == "Bearer valid-token"
        return self.principal


def agent_registry_payload() -> dict:
    migration = run_path("migrations/versions/0024_agent_registry_reference.py")
    return deepcopy(migration["AGENT_REGISTRY_PAYLOAD"])


def action_registry_payload() -> dict:
    migration = run_path("migrations/versions/0025_action_registry_reference.py")
    return deepcopy(migration["ACTION_REGISTRY_PAYLOAD"])


def ontology_reference_payload() -> dict:
    migration = run_path("migrations/versions/0030_ontology_reference.py")
    return deepcopy(migration["ONTOLOGY_PAYLOAD"])


def seed_reference(
    factory: sessionmaker[Session],
    *,
    surface: str,
    reference_id: str,
    payload: dict,
    version: str = "2026-06-22",
) -> None:
    with session_scope(factory) as session:
        AxisPersistenceRepository(session).upsert_demo_reference_record(
            DemoReferenceRecordCreate(
                tenant_id=TENANT_ID,
                surface=surface,
                reference_id=reference_id,
                status="active",
                source="bootstrap",
                version=version,
                payload=payload,
            )
        )


def seed_agent_registry(factory: sessionmaker[Session], payload: dict | None = None) -> None:
    seed_reference(
        factory,
        surface="agents",
        reference_id="manufacturing-agent-registry",
        payload=payload or agent_registry_payload(),
    )


def seed_action_registry(factory: sessionmaker[Session], payload: dict | None = None) -> None:
    resolved = payload or action_registry_payload()
    seed_reference(
        factory,
        surface="actions",
        reference_id="manufacturing-action-registry",
        payload=resolved,
        version=resolved["schema_version"],
    )


def seed_ontology_reference(factory: sessionmaker[Session]) -> None:
    seed_reference(
        factory,
        surface="ontology",
        reference_id="manufacturing-ontology",
        payload=ontology_reference_payload(),
    )


def seed_model_endpoint(repository: AxisPersistenceRepository) -> None:
    record_model_endpoint(
        repository,
        ModelEndpointCreateRequest(
            tenant_id=TENANT_ID,
            endpoint_id="vllm_plant_local",
            display_name="Plant-local vLLM",
            provider_type="openai_compatible",
            hosting_boundary="self_hosted",
            base_url="http://vllm.axis-models.svc.cluster.local:8000",
            default_model="mistral-7b-instruct",
            task_types=["agent_proposal", "summarize"],
            cost_input_per_1k=Decimal("0.5"),
            cost_output_per_1k=Decimal("1.5"),
            created_by="platform-admin",
            actor_scopes=[MODEL_ENDPOINT_ADMIN_SCOPE],
        ),
    )


def seed_operation_record(repository: AxisPersistenceRepository) -> None:
    repository.create_manufacturing_operation_record(
        ManufacturingOperationRecordCreate(
            tenant_id=TENANT_ID,
            record_id="material_lot_motors_7741",
            domain="Supply",
            record_type="material_lot",
            source_system="Supplier Portal",
            status="action_required",
            owner_role="supply-planning-owner",
            related_asset="asset_motors_batch",
            workflow_id="wf_supplier_delay_review",
            risk_level="high",
            occurred_at=datetime(2026, 6, 21, 14, 5, tzinfo=UTC),
            payload={"supplier": "Adriatic Motors", "delay_hours": 18},
            evidence_refs=["supplier_portal:shipment:AM-7741"],
        )
    )


def seed_agent_run_deny_policy(repository: AxisPersistenceRepository) -> None:
    repository.create_platform_policy(
        PlatformPolicyCreate(
            tenant_id=TENANT_ID,
            policy_id="deny-agent-runs",
            revision_number=1,
            policy_version="2026-07",
            display_name="Deny agent runs",
            description="Blocks governed agent runs for this tenant.",
            scope="agent_run",
            effect="deny",
            conditions={"action_domains": ["agent_runs"]},
            status="active",
            created_by="platform-admin",
            required_authoring_scope="platform:policy:author",
            permission_decision={"allowed": True, "reason": "allowed"},
            audit_event_type="platform.policy.authored",
            notes=[],
        )
    )


def run_request(**overrides) -> AgentRunStartRequest:
    payload = {
        "tenant_id": TENANT_ID,
        "actor_id": "plant-operations-owner",
        "actor_scopes": list(DAILY_BRIEF_SCOPES),
        "idempotency_key": "agent-run-2026-07-10",
        "mode": "propose",
    }
    payload.update(overrides)
    return AgentRunStartRequest(**payload)


def supply_run_request(**overrides) -> AgentRunStartRequest:
    payload = {
        "actor_scopes": list(SUPPLY_SCOPES),
        "idempotency_key": "supply-agent-run-2026-07-10",
    }
    payload.update(overrides)
    return run_request(**payload)


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    seed_agent_registry(factory)
    seed_action_registry(factory)
    seed_ontology_reference(factory)
    yield factory
    engine.dispose()


async def start_run(
    repository: AxisPersistenceRepository,
    agent_id: str,
    request: AgentRunStartRequest,
    runtime,
    **overrides,
):
    kwargs = {"execution_enabled": True}
    kwargs.update(overrides)
    return await start_agent_run(repository, agent_id, request, runtime, **kwargs)


async def test_start_agent_run_unknown_agent(session_factory: sessionmaker[Session]) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        with pytest.raises(AgentRunAgentNotFound):
            await start_run(
                repository,
                "agent_missing",
                run_request(),
                ProposalModelRuntime(DAILY_BRIEF_PROPOSAL),
            )


async def test_start_agent_run_refuses_inactive_agent(
    session_factory: sessionmaker[Session],
) -> None:
    payload = agent_registry_payload()
    payload["agents"][0]["status"] = "retired"
    seed_agent_registry(session_factory, payload)
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        with pytest.raises(AgentRunAgentNotExecutable) as excinfo:
            await start_run(
                repository,
                "agent_daily_brief",
                run_request(),
                ProposalModelRuntime(DAILY_BRIEF_PROPOSAL),
            )
        assert excinfo.value.reason == "agent_not_active:retired"


@pytest.mark.parametrize("autonomy_level", ["L0", "L3", "L4"])
async def test_start_agent_run_refuses_non_executable_autonomy(
    session_factory: sessionmaker[Session],
    autonomy_level: str,
) -> None:
    payload = agent_registry_payload()
    payload["agents"][0]["policy_boundary"]["autonomy_level"] = autonomy_level
    seed_agent_registry(session_factory, payload)
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        with pytest.raises(AgentRunAgentNotExecutable) as excinfo:
            await start_run(
                repository,
                "agent_daily_brief",
                run_request(),
                ProposalModelRuntime(DAILY_BRIEF_PROPOSAL),
            )
        assert excinfo.value.reason == f"autonomy_level_not_executable:{autonomy_level}"
    with session_factory() as session:
        assert session.scalars(select(AgentRun)).first() is None


async def test_start_agent_run_requires_execute_scope(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        with pytest.raises(AgentRunPermissionDenied) as excinfo:
            await start_run(
                repository,
                "agent_daily_brief",
                run_request(actor_scopes=["agents:read", "audit:read", "workflows:read"]),
                ProposalModelRuntime(DAILY_BRIEF_PROPOSAL),
            )
        assert excinfo.value.decision.reason == (
            f"missing_scope:{AGENT_RUN_EXECUTE_SCOPE}"
        )
        assert AGENT_RUN_EXECUTE_SCOPE in excinfo.value.required_permissions


async def test_start_agent_run_requires_agent_registry_permissions(
    session_factory: sessionmaker[Session],
) -> None:
    scopes = [scope for scope in DAILY_BRIEF_SCOPES if scope != "workflows:read"]
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        with pytest.raises(AgentRunPermissionDenied) as excinfo:
            await start_run(
                repository,
                "agent_daily_brief",
                run_request(actor_scopes=scopes),
                ProposalModelRuntime(DAILY_BRIEF_PROPOSAL),
            )
        assert excinfo.value.decision.reason == "missing_scope:workflows:read"


async def test_start_agent_run_flag_off_defers_without_context_read(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        result = await start_agent_run(
            repository,
            "agent_daily_brief",
            run_request(),
            ProposalModelRuntime(DAILY_BRIEF_PROPOSAL),
            execution_enabled=False,
        )

        assert result.status == "deferred"
        assert result.error_reason == "agent_run_execution_disabled"
        assert result.context_refs == []
        assert result.model_invocation_ids == []
        assert result.steps == []

    with session_factory() as session:
        assert session.scalars(select(AgentRunStep)).first() is None
        assert session.scalars(select(ModelInvocation)).first() is None
        event_types = {event.event_type for event in session.scalars(select(AuditEvent))}
        assert "agent.run.requested" in event_types
        assert "agent.run.deferred" in event_types
        assert "agent.run.context_read" not in event_types


async def test_start_agent_run_idempotent_replay(
    session_factory: sessionmaker[Session],
) -> None:
    runtime = ProposalModelRuntime(DAILY_BRIEF_PROPOSAL)
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        first = await start_run(repository, "agent_daily_brief", run_request(), runtime)
        second = await start_run(repository, "agent_daily_brief", run_request(), runtime)

        assert first.idempotent_replay is False
        assert second.idempotent_replay is True
        assert second.run_id == first.run_id
        assert second.status == first.status
        assert len(runtime.requests) == 1

    with session_factory() as session:
        assert len(list(session.scalars(select(AgentRun)))) == 1


async def test_start_agent_run_idempotency_payload_conflict(
    session_factory: sessionmaker[Session],
) -> None:
    runtime = ProposalModelRuntime(DAILY_BRIEF_PROPOSAL)
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        first = await start_run(repository, "agent_daily_brief", run_request(), runtime)
        with pytest.raises(AgentRunIdempotencyConflict) as excinfo:
            await start_run(
                repository,
                "agent_daily_brief",
                run_request(mode="dry_run"),
                runtime,
            )
        assert excinfo.value.run_id == first.run_id


async def test_start_agent_run_platform_policy_denies_fail_closed(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        seed_agent_run_deny_policy(repository)
        with pytest.raises(PlatformPolicyEnforcementDenied) as excinfo:
            await start_run(
                repository,
                "agent_daily_brief",
                run_request(),
                ProposalModelRuntime(DAILY_BRIEF_PROPOSAL),
            )
        assert excinfo.value.decision.effect == "deny"
        assert session.scalars(select(AgentRun)).first() is None
        assert session.scalars(select(ModelInvocation)).first() is None


async def test_start_agent_run_fails_closed_on_unknown_data_access(
    session_factory: sessionmaker[Session],
) -> None:
    payload = agent_registry_payload()
    payload["agents"][0]["data_access"] = ["unrestricted source-system records"]
    seed_agent_registry(session_factory, payload)
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        result = await start_run(
            repository,
            "agent_daily_brief",
            run_request(),
            ProposalModelRuntime(DAILY_BRIEF_PROPOSAL),
        )

        assert result.status == "failed_context_read"
        assert result.error_reason == (
            "unknown_data_access_surface:unrestricted source-system records"
        )
        assert result.context_refs == []
        assert result.model_invocation_ids == []
        assert [step.step_type for step in result.steps] == ["context_read"]
        assert result.steps[0].status == "failed"

    with session_factory() as session:
        assert session.scalars(select(ModelInvocation)).first() is None


async def test_context_read_respects_agent_data_access(
    session_factory: sessionmaker[Session],
) -> None:
    payload = agent_registry_payload()
    supply_agent = payload["agents"][1]
    assert supply_agent["agent_id"] == "agent_supply_risk"
    supply_agent["data_access"] = ["supply approval history"]
    seed_agent_registry(session_factory, payload)
    runtime = ProposalModelRuntime(SUPPLIER_EXPEDITE_PROPOSAL)
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        seed_operation_record(repository)
        result = await start_run(
            repository,
            "agent_supply_risk",
            supply_run_request(),
            runtime,
        )

        # The seeded operation record exists, but this agent's data_access only
        # grants the risk_scenarios surface, so no operation record is read.
        assert all(
            not ref.startswith("manufacturing_operation_record:")
            for ref in result.context_refs
        )
        context_step = result.steps[0]
        assert context_step.step_type == "context_read"
        assert set(context_step.evidence["surfaces"].keys()) == {"risk_scenarios"}
        prompt = runtime.requests[0].prompt
        assert "material_lot_motors_7741" not in prompt


async def test_start_agent_run_model_failure(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        result = await start_run(
            repository,
            "agent_daily_brief",
            run_request(),
            FailingModelRuntime(),
        )

        assert result.status == "failed_model_invocation"
        assert result.error_reason == "model_invocation_failed:provider_unreachable"
        assert len(result.model_invocation_ids) == 1
        assert [step.step_type for step in result.steps] == [
            "context_read",
            "model_invocation",
        ]
        assert result.steps[1].status == "failed"

    with session_factory() as session:
        invocation = session.scalars(select(ModelInvocation)).one()
        assert invocation.status == "failed"
        assert session.scalars(select(ActionRun)).first() is None


async def test_start_agent_run_model_deferred_propagates_honestly(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        result = await start_run(
            repository,
            "agent_daily_brief",
            run_request(),
            DeferredModelInvocationRuntime(),
        )

        assert result.status == "deferred"
        assert result.error_reason == "model_invocation_deferred"
        assert result.proposal_payload is None
        assert result.proposed_action_run_id is None
        assert result.steps[1].status == "deferred"

    with session_factory() as session:
        assert session.scalars(select(ActionRun)).first() is None


async def test_start_agent_run_blocked_when_no_model_endpoint(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        result = await start_run(
            repository,
            "agent_daily_brief",
            run_request(),
            ProposalModelRuntime(DAILY_BRIEF_PROPOSAL),
        )

        assert result.status == "blocked"
        assert result.error_reason == "no_matching_endpoint"
        assert result.model_invocation_ids == []


async def test_start_agent_run_model_call_budget_fails_closed(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        result = await start_run(
            repository,
            "agent_daily_brief",
            run_request(),
            ProposalModelRuntime(DAILY_BRIEF_PROPOSAL),
            max_model_calls=0,
        )

        assert result.status == "failed_model_invocation"
        assert result.error_reason == "model_call_budget_exhausted"
        assert result.model_invocation_ids == []


async def test_start_agent_run_garbage_output_never_fabricates_proposal(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        result = await start_run(
            repository,
            "agent_daily_brief",
            run_request(),
            GarbageModelRuntime(),
        )

        assert result.status == "failed_invalid_proposal"
        assert result.error_reason == "model_output_not_json"
        assert result.proposal_payload is None
        assert result.proposed_action_run_id is None
        proposal_step = result.steps[2]
        assert proposal_step.step_type == "proposal"
        assert proposal_step.status == "failed"

    with session_factory() as session:
        assert session.scalars(select(ActionRun)).first() is None


async def test_start_agent_run_blocks_unregistered_action(
    session_factory: sessionmaker[Session],
) -> None:
    proposal = dict(DAILY_BRIEF_PROPOSAL, action_id="delete_all_records")
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        result = await start_run(
            repository,
            "agent_daily_brief",
            run_request(),
            ProposalModelRuntime(proposal),
        )

        assert result.status == "blocked"
        assert result.error_reason == "action_not_registered"

    with session_factory() as session:
        assert session.scalars(select(ActionRun)).first() is None


async def test_start_agent_run_blocks_agent_blocked_action(
    session_factory: sessionmaker[Session],
) -> None:
    payload = agent_registry_payload()
    supply_agent = payload["agents"][1]
    supply_agent["blocked_actions"].append("Request supplier expedite")
    seed_agent_registry(session_factory, payload)
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        result = await start_run(
            repository,
            "agent_supply_risk",
            supply_run_request(),
            ProposalModelRuntime(SUPPLIER_EXPEDITE_PROPOSAL),
        )

        assert result.status == "blocked"
        assert result.error_reason == "action_blocked_for_agent"

    with session_factory() as session:
        assert session.scalars(select(ActionRun)).first() is None


async def test_start_agent_run_blocks_action_not_allowed_for_agent(
    session_factory: sessionmaker[Session],
) -> None:
    proposal = {
        "action_id": "place_quality_hold",
        "summary": "Hold the suspect batch.",
        "payload": {},
        "evidence_refs": [],
    }
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        result = await start_run(
            repository,
            "agent_supply_risk",
            supply_run_request(),
            ProposalModelRuntime(proposal),
        )

        assert result.status == "blocked"
        assert result.error_reason == "action_not_allowed_for_agent"

    with session_factory() as session:
        assert session.scalars(select(ActionRun)).first() is None


async def test_start_agent_run_blocks_action_autonomy_above_agent_ceiling(
    session_factory: sessionmaker[Session],
) -> None:
    action_payload = action_registry_payload()
    for action in action_payload["actions"]:
        if action["definition"]["action_id"] == "request_supplier_expedite":
            action["connected_agents"].append("agent_daily_brief")
    seed_action_registry(session_factory, action_payload)
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        result = await start_run(
            repository,
            "agent_daily_brief",
            run_request(),
            ProposalModelRuntime(SUPPLIER_EXPEDITE_PROPOSAL),
        )

        assert result.status == "blocked"
        assert result.error_reason == "action_autonomy_above_agent_ceiling"


async def test_start_agent_run_blocks_risk_above_autonomy_ceiling(
    session_factory: sessionmaker[Session],
) -> None:
    action_payload = action_registry_payload()
    for action in action_payload["actions"]:
        if action["definition"]["action_id"] == "generate_daily_plant_brief":
            action["definition"]["risk_level"] = "medium"
    seed_action_registry(session_factory, action_payload)
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        result = await start_run(
            repository,
            "agent_daily_brief",
            run_request(),
            ProposalModelRuntime(DAILY_BRIEF_PROPOSAL),
        )

        assert result.status == "blocked"
        assert result.error_reason == "action_risk_above_autonomy_ceiling"

    with session_factory() as session:
        assert session.scalars(select(ActionRun)).first() is None


async def test_l1_agent_records_proposal_without_action_run(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        result = await start_run(
            repository,
            "agent_daily_brief",
            run_request(),
            ProposalModelRuntime(DAILY_BRIEF_PROPOSAL, wrap_in_fence=True),
        )

        assert result.status == "proposal_recorded"
        assert result.autonomy_level == "L1"
        assert result.proposal_payload == DAILY_BRIEF_PROPOSAL
        assert result.proposed_action_run_id is None
        assert len(result.model_invocation_ids) == 1
        assert [step.step_type for step in result.steps] == [
            "context_read",
            "model_invocation",
            "proposal",
        ]
        assert result.audit_event_type == "agent.run.proposal_recorded"

    with session_factory() as session:
        assert session.scalars(select(ActionRun)).first() is None
        events = {event.event_type: event for event in session.scalars(select(AuditEvent))}
        final_event = events["agent.run.proposal_recorded"]
        assert final_event.payload["model_invocation_ids"] == result.model_invocation_ids
        assert final_event.payload["proposed_action_id"] == "generate_daily_plant_brief"


async def test_l2_agent_creates_action_run_with_approval_required(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        result = await start_run(
            repository,
            "agent_supply_risk",
            supply_run_request(),
            ProposalModelRuntime(SUPPLIER_EXPEDITE_PROPOSAL),
        )

        assert result.status == "proposal_created"
        assert result.autonomy_level == "L2"
        assert result.proposed_action_run_id is not None
        assert result.proposal_payload == SUPPLIER_EXPEDITE_PROPOSAL

    with session_factory() as session:
        action_run = session.scalars(select(ActionRun)).one()
        assert action_run.id == result.proposed_action_run_id
        # The proposal lands in the untouched human approval pipeline.
        assert action_run.status == "approval_required"
        assert action_run.action_id == "request_supplier_expedite"
        assert action_run.approval_id == "appr_expedite_supplier_batch"
        assert action_run.payload["input"] == SUPPLIER_EXPEDITE_PROPOSAL["payload"]

        events = {event.event_type: event for event in session.scalars(select(AuditEvent))}
        final_event = events["agent.run.proposal_created"]
        assert final_event.payload["action_run_id"] == str(action_run.id)
        assert final_event.payload["approval_required"] is True
        assert final_event.payload["model_invocation_ids"] == result.model_invocation_ids
        # The existing action-run pipeline still emits its own audit event.
        assert "action.proposal.created" in events


async def test_l2_agent_invalid_proposal_payload_fails_without_action_run(
    session_factory: sessionmaker[Session],
) -> None:
    proposal = dict(
        SUPPLIER_EXPEDITE_PROPOSAL,
        payload={"supplier_batch_id": "asset_motors_batch"},
    )
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        result = await start_run(
            repository,
            "agent_supply_risk",
            supply_run_request(),
            ProposalModelRuntime(proposal),
        )

        assert result.status == "failed_invalid_proposal"
        assert result.error_reason == "proposal_payload_schema_invalid"

    with session_factory() as session:
        assert session.scalars(select(ActionRun)).first() is None


async def test_dry_run_records_proposal_without_action_run(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        result = await start_run(
            repository,
            "agent_supply_risk",
            supply_run_request(mode="dry_run"),
            ProposalModelRuntime(SUPPLIER_EXPEDITE_PROPOSAL),
        )

        assert result.status == "dry_run_completed"
        assert result.mode == "dry_run"
        assert result.proposal_payload == SUPPLIER_EXPEDITE_PROPOSAL
        assert result.proposed_action_run_id is None
        assert result.audit_event_type == "agent.run.dry_run_completed"

    with session_factory() as session:
        assert session.scalars(select(ActionRun)).first() is None


async def test_agent_run_step_timeline_is_persisted_append_only(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        result = await start_run(
            repository,
            "agent_daily_brief",
            run_request(),
            ProposalModelRuntime(DAILY_BRIEF_PROPOSAL),
        )
        fetched = get_agent_run_result(
            repository, TENANT_ID, "agent_daily_brief", result.run_id
        )

        assert [step.seq for step in fetched.steps] == [1, 2, 3]
        assert [step.step_type for step in fetched.steps] == [
            "context_read",
            "model_invocation",
            "proposal",
        ]
        assert all(step.status == "completed" for step in fetched.steps)

    with session_factory() as session:
        steps = list(session.scalars(select(AgentRunStep)))
        assert len(steps) == 3
        # Steps carry evidence references, never bulk payload dumps.
        serialized = json.dumps([step.evidence for step in steps])
        assert "Adriatic Motors" not in serialized


async def test_agent_run_records_usage_metering(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        await start_run(
            repository,
            "agent_daily_brief",
            run_request(),
            ProposalModelRuntime(DAILY_BRIEF_PROPOSAL),
            usage_metering_enabled=True,
        )

    with session_factory() as session:
        usage = {
            record.metric_key: record
            for record in session.scalars(select(TenantUsageRecord))
        }
        agent_usage = usage["agent_runs"]
        assert agent_usage.tenant_id == TENANT_ID
        assert agent_usage.quantity == 1
        assert agent_usage.dimensions == {}
        agent_event = session.scalars(
            select(TenantUsageEvent).where(
                TenantUsageEvent.metric_key == "agent_runs"
            )
        ).one()
        assert agent_event.dimensions == {"agent_id": "agent_daily_brief"}
        # Model consumption is metered by the router, not duplicated here.
        assert usage["model_invocations"].quantity == 1


async def test_agent_run_flag_off_records_no_usage(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        await start_agent_run(
            repository,
            "agent_daily_brief",
            run_request(),
            ProposalModelRuntime(DAILY_BRIEF_PROPOSAL),
            execution_enabled=False,
            usage_metering_enabled=True,
        )

    with session_factory() as session:
        assert session.scalars(select(TenantUsageRecord)).first() is None


async def test_get_agent_run_result_scopes_by_agent(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        result = await start_run(
            repository,
            "agent_daily_brief",
            run_request(),
            ProposalModelRuntime(DAILY_BRIEF_PROPOSAL),
        )

        with pytest.raises(AgentRunNotFound):
            get_agent_run_result(repository, TENANT_ID, "agent_supply_risk", result.run_id)
        with pytest.raises(AgentRunNotFound):
            get_agent_run_result(repository, TENANT_ID, "agent_daily_brief", "not-a-uuid")


async def test_list_agent_runs_cursor_pagination(
    session_factory: sessionmaker[Session],
) -> None:
    from axis_api.agent_runs import decode_agent_run_cursor, encode_agent_run_cursor

    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        seed_model_endpoint(repository)
        for index in range(3):
            await start_run(
                repository,
                "agent_daily_brief",
                run_request(idempotency_key=f"agent-run-page-{index}"),
                ProposalModelRuntime(DAILY_BRIEF_PROPOSAL),
            )

        first_page = list_agent_run_results(
            repository, TENANT_ID, "agent_daily_brief", limit=2
        )
        assert len(first_page) == 2
        cursor = encode_agent_run_cursor(first_page[-1])
        cursor_created_at, cursor_row_id = decode_agent_run_cursor(cursor)
        second_page = list_agent_run_results(
            repository,
            TENANT_ID,
            "agent_daily_brief",
            cursor_created_at=cursor_created_at,
            cursor_row_id=cursor_row_id,
            limit=2,
        )
        assert len(second_page) == 1
        listed_ids = {run.run_id for run in [*first_page, *second_page]}
        assert len(listed_ids) == 3
        # Listing is scoped to the agent.
        assert list_agent_run_results(repository, TENANT_ID, "agent_supply_risk") == []


def test_parse_agent_action_proposal_strictness() -> None:
    from axis_api.agent_runs import AgentRunProposalParseError

    with pytest.raises(AgentRunProposalParseError) as excinfo:
        parse_agent_action_proposal("")
    assert excinfo.value.reason == "empty_model_output"

    with pytest.raises(AgentRunProposalParseError) as excinfo:
        parse_agent_action_proposal("[1, 2, 3]")
    assert excinfo.value.reason == "model_output_not_json_object"

    with pytest.raises(AgentRunProposalParseError) as excinfo:
        parse_agent_action_proposal(
            json.dumps({"action_id": "x", "summary": "y", "extra_field": True})
        )
    assert excinfo.value.reason == "model_output_schema_invalid"

    draft = parse_agent_action_proposal(
        "```json\n" + json.dumps(DAILY_BRIEF_PROPOSAL) + "\n```"
    )
    assert draft.action_id == "generate_daily_plant_brief"


def build_client(
    session_factory: sessionmaker[Session],
    *,
    principal: OidcPrincipal | None = None,
    model_runtime=None,
    execution_enabled: bool = True,
) -> TestClient:
    app = create_app(
        Settings(
            postgres_dsn="sqlite+pysqlite://",
            agent_run_execution_enabled=execution_enabled,
        )
    )
    app.state.session_factory = session_factory
    if model_runtime is not None:
        app.state.model_invocation_runtime = model_runtime
    if principal is not None:
        app.state.identity_verifier = StaticIdentityVerifier(principal)
    return TestClient(app)


def test_agent_run_routes_execute_and_read_back(
    session_factory: sessionmaker[Session],
) -> None:
    with session_scope(session_factory) as session:
        seed_model_endpoint(AxisPersistenceRepository(session))
    principal = OidcPrincipal(
        actor_id="plant-operations-owner",
        tenant_id=TENANT_ID,
        scopes=list(DAILY_BRIEF_SCOPES),
    )
    client = build_client(
        session_factory,
        principal=principal,
        model_runtime=ProposalModelRuntime(DAILY_BRIEF_PROPOSAL),
    )
    headers = {"Authorization": "Bearer valid-token"}
    payload = {
        "actor_id": "plant-operations-owner",
        "actor_scopes": [],
        "idempotency_key": "agent-run-http-1",
        "mode": "propose",
    }

    created = client.post(
        "/demo/manufacturing/agents/agent_daily_brief/runs",
        json=payload,
        headers=headers,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "proposal_recorded"
    assert body["requested_by"] == "plant-operations-owner"
    assert len(body["steps"]) == 3

    replay = client.post(
        "/demo/manufacturing/agents/agent_daily_brief/runs",
        json=payload,
        headers=headers,
    )
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True

    listing = client.get(
        "/demo/manufacturing/agents/agent_daily_brief/runs",
        headers=headers,
    )
    assert listing.status_code == 200
    listing_body = listing.json()
    assert listing_body["agent_id"] == "agent_daily_brief"
    assert len(listing_body["runs"]) == 1

    detail = client.get(
        f"/demo/manufacturing/agents/agent_daily_brief/runs/{body['run_id']}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["run_id"] == body["run_id"]

    missing = client.get(
        "/demo/manufacturing/agents/agent_daily_brief/runs/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert missing.status_code == 404


def test_agent_run_route_translates_typed_errors(
    session_factory: sessionmaker[Session],
) -> None:
    principal = OidcPrincipal(
        actor_id="plant-operations-owner",
        tenant_id=TENANT_ID,
        scopes=["agents:read"],
    )
    client = build_client(
        session_factory,
        principal=principal,
        model_runtime=ProposalModelRuntime(DAILY_BRIEF_PROPOSAL),
    )
    headers = {"Authorization": "Bearer valid-token"}
    payload = {
        "actor_id": "plant-operations-owner",
        "actor_scopes": [],
        "idempotency_key": "agent-run-http-2",
        "mode": "propose",
    }

    unknown = client.post(
        "/demo/manufacturing/agents/agent_missing/runs",
        json=payload,
        headers=headers,
    )
    assert unknown.status_code == 404
    assert unknown.json()["detail"]["reason"] == "agent_not_found"

    denied = client.post(
        "/demo/manufacturing/agents/agent_daily_brief/runs",
        json=payload,
        headers=headers,
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "PERMISSION_DENIED"

    invalid_cursor = client.get(
        "/demo/manufacturing/agents/agent_daily_brief/runs",
        params={"cursor": "not-a-cursor"},
        headers=headers,
    )
    assert invalid_cursor.status_code == 422
    assert invalid_cursor.json()["detail"]["reason"] == "invalid_agent_run_cursor"

    cross_tenant_body = dict(payload, tenant_id="tenant_other")
    cross_tenant = client.post(
        "/demo/manufacturing/agents/agent_daily_brief/runs",
        json=cross_tenant_body,
        headers=headers,
    )
    assert cross_tenant.status_code == 403
    assert cross_tenant.json()["detail"]["reason"] == "tenant_mismatch"

    cross_tenant_read = client.get(
        "/demo/manufacturing/agents/agent_daily_brief/runs",
        params={"tenant_id": "tenant_other"},
        headers=headers,
    )
    assert cross_tenant_read.status_code == 403
    assert cross_tenant_read.json()["detail"]["reason"] == "tenant_mismatch"
