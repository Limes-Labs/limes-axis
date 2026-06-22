from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

from axis_api.action_runs import (
    ActionPayloadValidationError,
    ActionPermissionDenied,
    ActionRunIdempotencyConflict,
    ActionRunPersistenceResult,
    ActionRunRequest,
    DemoActionNotFound,
    record_demo_action_run,
)
from axis_api.approval_decisions import (
    ApprovalDecisionPersistenceResult,
    ApprovalDecisionRequest,
    ApprovalPermissionDenied,
    DemoApprovalNotFound,
    record_demo_approval_decision,
)
from axis_api.audit_queries import (
    AuditEventQuery,
    AuditExportBundle,
    AuditExportQuery,
    export_persisted_audit_events,
    query_persisted_audit_events,
)
from axis_api.config import Settings
from axis_api.db import create_session_factory, session_scope
from axis_api.demo import (
    ManufacturingActionRegistry,
    ManufacturingAgentRegistry,
    ManufacturingApprovalInbox,
    ManufacturingAuditExplorer,
    ManufacturingModelRouting,
    ManufacturingOntology,
    ManufacturingOntologyEntityDetail,
    ManufacturingOverview,
    ManufacturingWorkflowConsole,
    get_manufacturing_action_registry,
    get_manufacturing_agent_registry,
    get_manufacturing_approval_inbox,
    get_manufacturing_audit_explorer,
    get_manufacturing_model_routing,
    get_manufacturing_ontology,
    get_manufacturing_ontology_entity_detail,
    get_manufacturing_overview,
    get_manufacturing_workflow_console,
)
from axis_api.errors import AxisErrorCode
from axis_api.identity import (
    ActorBindingError,
    OidcAuthenticationError,
    OidcPrincipal,
    RemoteJwksOidcVerifier,
    bind_request_actor,
)
from axis_api.permissions import PermissionRequest, evaluate_permission
from axis_api.persistence import AxisPersistenceRepository
from axis_api.replay_simulation import (
    ManufacturingReplaySimulation,
    ReplaySimulationQuery,
    build_replay_simulation,
)
from axis_api.workflow_queries import WorkflowRunQuery, query_persisted_workflow_runs
from axis_api.workflow_runtime import (
    DeferredWorkflowSignalRuntime,
    TemporalWorkflowSignalConfig,
    TemporalWorkflowSignalRuntime,
    WorkflowSignalRuntime,
)


def persistence_repository(request: Request) -> Generator[AxisPersistenceRepository]:
    with session_scope(request.app.state.session_factory) as session:
        yield AxisPersistenceRepository(session)


PersistenceRepository = Annotated[
    AxisPersistenceRepository,
    Depends(persistence_repository),
]


def workflow_runtime(request: Request) -> WorkflowSignalRuntime:
    return request.app.state.workflow_runtime


WorkflowRuntime = Annotated[
    WorkflowSignalRuntime,
    Depends(workflow_runtime),
]


def oidc_principal(
    request: Request,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> OidcPrincipal | None:
    settings: Settings = request.app.state.settings
    if not authorization:
        if settings.oidc_auth_required:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": AxisErrorCode.AUTH_REQUIRED.value,
                    "message": "A valid OIDC bearer token is required.",
                    "reason": "missing_authorization",
                },
            )
        return None

    try:
        return request.app.state.identity_verifier.verify_authorization_header(authorization)
    except OidcAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": AxisErrorCode.AUTH_REQUIRED.value,
                "message": "The OIDC bearer token could not be verified.",
                "reason": exc.reason,
            },
        ) from exc


OidcPrincipalDependency = Annotated[
    OidcPrincipal | None,
    Depends(oidc_principal),
]


def _oidc_jwks_url(settings: Settings) -> str:
    if settings.oidc_jwks_url:
        return settings.oidc_jwks_url
    return f"{settings.oidc_issuer.rstrip('/')}/protocol/openid-connect/certs"


def _bind_demo_actor(request_model, principal: OidcPrincipal | None):
    try:
        return bind_request_actor(
            request_model,
            principal,
            expected_tenant_id="tenant_demo_manufacturing",
        )
    except ActorBindingError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": AxisErrorCode.PERMISSION_DENIED.value,
                "message": exc.message,
                "reason": exc.reason,
            },
        ) from exc


def _authorize_demo_ontology_detail(
    detail: ManufacturingOntologyEntityDetail,
    principal: OidcPrincipal | None,
) -> None:
    if principal is None:
        return

    if principal.tenant_id != detail.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": AxisErrorCode.PERMISSION_DENIED.value,
                "message": "The authenticated OIDC tenant cannot access this tenant scope.",
                "required_permissions": detail.required_permissions,
                "reason": "tenant_mismatch",
            },
        )

    decision = evaluate_permission(
        PermissionRequest(
            tenant_id=detail.tenant_id,
            actor_id=principal.actor_id,
            actor_scopes=principal.scopes,
            required_scopes=[],
            relationship_scopes=detail.required_permissions,
            attributes={
                "node_id": detail.node.node_id,
                "node_type": detail.node.node_type.value,
                "domain": detail.node.domain,
                "relationship_count": len(detail.connected_relationships),
            },
        )
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": AxisErrorCode.PERMISSION_DENIED.value,
                "message": "The actor cannot read this ontology entity relationship context.",
                "required_permissions": detail.required_permissions,
                "reason": decision.reason,
            },
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()
    app = FastAPI(
        title="Limes Axis API",
        description="Core API for the sovereign AI control plane for European operations.",
        version="0.0.0",
        license_info={
            "name": "Apache-2.0",
            "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
        },
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Axis-Tenant", "X-Axis-Actor"],
    )
    app.state.settings = resolved_settings
    app.state.session_factory = create_session_factory(resolved_settings)
    app.state.workflow_runtime = (
        TemporalWorkflowSignalRuntime(
            TemporalWorkflowSignalConfig(
                address=resolved_settings.temporal_address,
                namespace=resolved_settings.temporal_namespace,
                signal_timeout_seconds=resolved_settings.temporal_signal_timeout_seconds,
            )
        )
        if resolved_settings.workflow_signals_enabled
        else DeferredWorkflowSignalRuntime()
    )
    app.state.identity_verifier = RemoteJwksOidcVerifier(
        issuer=resolved_settings.oidc_issuer,
        audience=resolved_settings.oidc_audience,
        algorithms=resolved_settings.oidc_algorithms,
        jwks_url=_oidc_jwks_url(resolved_settings),
        cache_seconds=resolved_settings.oidc_jwks_cache_seconds,
        actor_claim=resolved_settings.oidc_actor_claim,
        tenant_claim=resolved_settings.oidc_tenant_claim,
    )

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "axis-api"}

    @app.get("/ready", tags=["system"])
    def ready() -> dict[str, object]:
        return {
            "status": "ready",
            "service": "axis-api",
            "dependencies": {
                "postgres": bool(resolved_settings.postgres_dsn),
                "typedb": bool(resolved_settings.typedb_address),
                "temporal": bool(resolved_settings.temporal_address),
            },
            "external_model_egress_enabled": resolved_settings.external_model_egress_enabled,
        }

    @app.get(
        "/demo/manufacturing/overview",
        response_model=ManufacturingOverview,
        tags=["demo"],
    )
    def manufacturing_overview() -> ManufacturingOverview:
        return get_manufacturing_overview()

    @app.get(
        "/demo/manufacturing/workflows",
        response_model=ManufacturingWorkflowConsole,
        tags=["demo"],
    )
    def manufacturing_workflow_console() -> ManufacturingWorkflowConsole:
        return get_manufacturing_workflow_console()

    @app.get(
        "/demo/manufacturing/workflows/runs",
        response_model=ManufacturingWorkflowConsole,
        tags=["demo"],
    )
    def manufacturing_persisted_workflow_runs(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
        state: str | None = Query(default=None, min_length=1),
        limit: int = Query(default=100, ge=1, le=200),
    ) -> ManufacturingWorkflowConsole:
        return query_persisted_workflow_runs(
            repository,
            WorkflowRunQuery(tenant_id=tenant_id, state=state, limit=limit),
        )

    @app.get(
        "/demo/manufacturing/simulation/replay",
        response_model=ManufacturingReplaySimulation,
        tags=["demo"],
    )
    def manufacturing_replay_simulation(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
        workflow_id: str | None = Query(default=None, min_length=1),
        limit: int = Query(default=20, ge=1, le=100),
    ) -> ManufacturingReplaySimulation:
        return build_replay_simulation(
            repository,
            ReplaySimulationQuery(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                limit=limit,
            ),
        )

    @app.get(
        "/demo/manufacturing/agents",
        response_model=ManufacturingAgentRegistry,
        tags=["demo"],
    )
    def manufacturing_agent_registry() -> ManufacturingAgentRegistry:
        return get_manufacturing_agent_registry()

    @app.get(
        "/demo/manufacturing/actions",
        response_model=ManufacturingActionRegistry,
        tags=["demo"],
    )
    def manufacturing_action_registry() -> ManufacturingActionRegistry:
        return get_manufacturing_action_registry()

    @app.post(
        "/demo/manufacturing/actions/{action_id}/runs",
        response_model=ActionRunPersistenceResult,
        responses={
            403: {"description": "Action run permission denied"},
            409: {"description": "Action run idempotency conflict"},
            422: {"description": "Action payload validation failed"},
        },
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    async def manufacturing_action_run(
        action_id: str,
        action_run: ActionRunRequest,
        repository: PersistenceRepository,
        runtime: WorkflowRuntime,
        principal: OidcPrincipalDependency,
        response: Response,
    ) -> ActionRunPersistenceResult:
        try:
            bound_action_run = _bind_demo_actor(action_run, principal)
            result = await record_demo_action_run(repository, action_id, bound_action_run, runtime)
        except DemoActionNotFound as exc:
            raise HTTPException(status_code=404, detail="Action not found") from exc
        except ActionPermissionDenied as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot request this action run.",
                    "required_permissions": exc.required_permissions,
                    "reason": exc.decision.reason,
                },
            ) from exc
        except ActionRunIdempotencyConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": AxisErrorCode.POLICY_VIOLATION.value,
                    "message": "The idempotency key already exists with a different payload.",
                    "action_run_id": str(exc.action_run_id),
                },
            ) from exc
        except ActionPayloadValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "The action payload does not match the typed input schema.",
                    "issues": exc.issues,
                },
            ) from exc

        if result.idempotent_replay:
            response.status_code = status.HTTP_200_OK

        return result

    @app.get(
        "/demo/manufacturing/approvals",
        response_model=ManufacturingApprovalInbox,
        tags=["demo"],
    )
    def manufacturing_approval_inbox() -> ManufacturingApprovalInbox:
        return get_manufacturing_approval_inbox()

    @app.post(
        "/demo/manufacturing/approvals/{approval_id}/decision",
        response_model=ApprovalDecisionPersistenceResult,
        responses={403: {"description": "Approval decision permission denied"}},
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    async def manufacturing_approval_decision(
        approval_id: str,
        decision: ApprovalDecisionRequest,
        repository: PersistenceRepository,
        runtime: WorkflowRuntime,
        principal: OidcPrincipalDependency,
    ) -> ApprovalDecisionPersistenceResult:
        try:
            bound_decision = _bind_demo_actor(decision, principal)
            return await record_demo_approval_decision(
                repository,
                approval_id,
                bound_decision,
                runtime,
            )
        except DemoApprovalNotFound as exc:
            raise HTTPException(status_code=404, detail="Approval not found") from exc
        except ApprovalPermissionDenied as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot decide this approval.",
                    "required_permission": exc.required_permission,
                    "reason": exc.decision.reason,
                },
            ) from exc

    @app.get(
        "/demo/manufacturing/audit",
        response_model=ManufacturingAuditExplorer,
        tags=["demo"],
    )
    def manufacturing_audit_explorer() -> ManufacturingAuditExplorer:
        return get_manufacturing_audit_explorer()

    @app.get(
        "/demo/manufacturing/audit/events",
        response_model=ManufacturingAuditExplorer,
        tags=["demo"],
    )
    def manufacturing_persisted_audit_events(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
        event_type: str | None = Query(default=None, min_length=1),
        actor_id: str | None = Query(default=None, min_length=1),
        scope: str | None = Query(default=None, min_length=1),
        limit: int = Query(default=100, ge=1, le=200),
    ) -> ManufacturingAuditExplorer:
        return query_persisted_audit_events(
            repository,
            AuditEventQuery(
                tenant_id=tenant_id,
                event_type=event_type,
                actor_id=actor_id,
                scope=scope,
                limit=limit,
            ),
        )

    @app.get(
        "/demo/manufacturing/audit/export",
        response_model=AuditExportBundle,
        tags=["demo"],
    )
    def manufacturing_persisted_audit_export(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
        event_type: str | None = Query(default=None, min_length=1),
        actor_id: str | None = Query(default=None, min_length=1),
        scope: str | None = Query(default=None, min_length=1),
        limit: int = Query(default=100, ge=1, le=200),
        export_reason: str = Query(default="governance-review", min_length=1, max_length=120),
        retention_days: int = Query(default=365, ge=30, le=3650),
        legal_hold: bool = Query(default=False),
        format: str = Query(default="json", pattern="^json$"),
    ) -> AuditExportBundle:
        return export_persisted_audit_events(
            repository,
            AuditExportQuery(
                tenant_id=tenant_id,
                event_type=event_type,
                actor_id=actor_id,
                scope=scope,
                limit=limit,
                export_reason=export_reason,
                retention_days=retention_days,
                legal_hold=legal_hold,
                format=format,
            ),
        )

    @app.get(
        "/demo/manufacturing/model-routing",
        response_model=ManufacturingModelRouting,
        tags=["demo"],
    )
    def manufacturing_model_routing() -> ManufacturingModelRouting:
        return get_manufacturing_model_routing()

    @app.get(
        "/demo/manufacturing/ontology",
        response_model=ManufacturingOntology,
        tags=["demo"],
    )
    def manufacturing_ontology() -> ManufacturingOntology:
        return get_manufacturing_ontology()

    @app.get(
        "/demo/manufacturing/ontology/entities/{node_id}",
        response_model=ManufacturingOntologyEntityDetail,
        tags=["demo"],
    )
    def manufacturing_ontology_entity_detail(
        node_id: str,
        principal: OidcPrincipalDependency,
    ) -> ManufacturingOntologyEntityDetail:
        detail = get_manufacturing_ontology_entity_detail(node_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Ontology entity not found")
        _authorize_demo_ontology_detail(detail, principal)
        return detail

    return app


app = create_app()
