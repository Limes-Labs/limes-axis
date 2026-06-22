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
from axis_api.connector_configurations import (
    ConnectorConfigurationCreateRequest,
    ConnectorConfigurationQuery,
    ConnectorConfigurationValidationError,
    ConnectorTenantConfiguration,
    ManufacturingConnectorConfigurationRegistry,
    build_connector_configuration_registry,
    record_demo_connector_configuration,
)
from axis_api.connector_credential_handles import (
    ConnectorCredentialHandleCreateRequest,
    ConnectorCredentialHandleQuery,
    ConnectorCredentialHandleRecord,
    ConnectorCredentialHandleValidationError,
    ConnectorCredentialRotationRequest,
    ManufacturingConnectorCredentialHandleRegistry,
    build_connector_credential_handle_registry,
    record_demo_connector_credential_handle,
    record_demo_connector_credential_rotation,
)
from axis_api.connector_execution import (
    ConnectorExecutionRuntime,
    DeferredConnectorExecutionRuntime,
)
from axis_api.connector_manual_imports import (
    ConnectorManualImportCreateRequest,
    ConnectorManualImportDecisionRequest,
    ConnectorManualImportDecisionResult,
    ConnectorManualImportIdempotencyConflict,
    ConnectorManualImportNotFound,
    ConnectorManualImportPermissionDenied,
    ConnectorManualImportQuery,
    ConnectorManualImportRecord,
    ConnectorManualImportValidationError,
    ManufacturingConnectorManualImportRegistry,
    build_connector_manual_import_registry,
    record_demo_connector_manual_import,
    record_demo_connector_manual_import_decision,
)
from axis_api.connector_ontology_promotions import (
    ConnectorOntologyPromotionIdempotencyConflict,
    ConnectorOntologyPromotionNotFound,
    ConnectorOntologyPromotionPermissionDenied,
    ConnectorOntologyPromotionRequest,
    ConnectorOntologyPromotionResult,
    ConnectorOntologyPromotionValidationError,
    record_demo_connector_ontology_promotion,
)
from axis_api.connector_ontology_proposals import (
    ConnectorOntologyProposalCreateRequest,
    ConnectorOntologyProposalQuery,
    ConnectorOntologyProposalValidationError,
    ManufacturingConnectorOntologyProposalRegistry,
    build_connector_ontology_proposal_registry,
    record_demo_connector_ontology_proposals,
)
from axis_api.connector_promotion_policies import (
    ConnectorPromotionPolicyConflict,
    ConnectorPromotionPolicyCreateRequest,
    ConnectorPromotionPolicyEnableRequest,
    ConnectorPromotionPolicyNotFound,
    ConnectorPromotionPolicyPermissionDenied,
    ConnectorPromotionPolicyQuery,
    ConnectorPromotionPolicyRecord,
    ConnectorPromotionPolicyReviseRequest,
    ConnectorPromotionPolicyValidationError,
    ManufacturingConnectorPromotionPolicyRegistry,
    build_connector_promotion_policy_registry,
    enable_demo_connector_promotion_policy,
    record_demo_connector_promotion_policy,
    revise_demo_connector_promotion_policy,
)
from axis_api.connector_promotion_policy_sets import (
    ConnectorPromotionPolicySetActivateRequest,
    ConnectorPromotionPolicySetConflict,
    ConnectorPromotionPolicySetPermissionDenied,
    ConnectorPromotionPolicySetQuery,
    ConnectorPromotionPolicySetRecord,
    ConnectorPromotionPolicySetValidationError,
    ManufacturingConnectorPromotionPolicySetRegistry,
    build_connector_promotion_policy_set_registry,
    record_demo_connector_promotion_policy_set,
)
from axis_api.connector_runs import (
    ConnectorRunCreateRequest,
    ConnectorRunQuery,
    ConnectorRunRecord,
    ConnectorRunValidationError,
    ManufacturingConnectorRunRegistry,
    build_connector_run_registry,
    record_demo_connector_run,
)
from axis_api.connectors import (
    ConnectorCsvPreviewRequest,
    ConnectorCsvPreviewResult,
    ConnectorExternalDbPreviewRequest,
    ConnectorExternalDbPreviewResult,
    ManufacturingConnectorRegistry,
    get_manufacturing_connector_registry,
    preview_external_db_connector,
    preview_file_csv_connector,
)
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
from axis_api.ontology.mutations import (
    DeferredOntologyMutationRuntime,
    OntologyMutationRuntime,
    TypeDBOntologyMutationConfig,
    TypeDBOntologyMutationRuntime,
)
from axis_api.ontology.queries import (
    DeferredOntologyQueryRuntime,
    OntologyGraphQueryRequest,
    OntologyGraphQueryRuntime,
    TypeDBOntologyQueryConfig,
    TypeDBOntologyQueryRuntime,
    query_manufacturing_ontology_graph,
)
from axis_api.permissions import PermissionRequest, evaluate_permission
from axis_api.persistence import AxisPersistenceRepository
from axis_api.replay_simulation import (
    ManufacturingReplaySimulation,
    ReplaySimulationOutputConflict,
    ReplaySimulationOutputPermissionDenied,
    ReplaySimulationOutputPersistRequest,
    ReplaySimulationOutputRecord,
    ReplaySimulationOutputValidationError,
    ReplaySimulationQuery,
    build_replay_simulation,
    persist_replay_simulation_output,
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


def ontology_mutation_runtime(request: Request) -> OntologyMutationRuntime:
    return request.app.state.ontology_mutation_runtime


OntologyMutationRuntimeDependency = Annotated[
    OntologyMutationRuntime,
    Depends(ontology_mutation_runtime),
]


def ontology_query_runtime(request: Request) -> OntologyGraphQueryRuntime:
    return request.app.state.ontology_query_runtime


OntologyQueryRuntimeDependency = Annotated[
    OntologyGraphQueryRuntime,
    Depends(ontology_query_runtime),
]


def connector_execution_runtime(request: Request) -> ConnectorExecutionRuntime:
    return request.app.state.connector_execution_runtime


ConnectorExecutionRuntimeDependency = Annotated[
    ConnectorExecutionRuntime,
    Depends(connector_execution_runtime),
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


def _bind_demo_created_by(request_model, principal: OidcPrincipal | None):
    if principal is None:
        return request_model

    if principal.tenant_id != "tenant_demo_manufacturing":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": AxisErrorCode.PERMISSION_DENIED.value,
                "message": "The authenticated OIDC tenant cannot access this tenant scope.",
                "reason": "tenant_mismatch",
            },
        )

    request_actor = getattr(request_model, "created_by", None)
    if request_actor and request_actor != principal.actor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": AxisErrorCode.PERMISSION_DENIED.value,
                "message": "The request actor does not match the authenticated OIDC actor.",
                "reason": "actor_mismatch",
            },
        )

    return request_model.model_copy(
        update={
            "created_by": principal.actor_id,
            "actor_scopes": principal.scopes,
        }
    )


def _bind_demo_enabled_by(request_model, principal: OidcPrincipal | None):
    if principal is None:
        return request_model

    if principal.tenant_id != "tenant_demo_manufacturing":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": AxisErrorCode.PERMISSION_DENIED.value,
                "message": "The authenticated OIDC tenant cannot access this tenant scope.",
                "reason": "tenant_mismatch",
            },
        )

    request_actor = getattr(request_model, "enabled_by", None)
    if request_actor and request_actor != principal.actor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": AxisErrorCode.PERMISSION_DENIED.value,
                "message": "The request actor does not match the authenticated OIDC actor.",
                "reason": "actor_mismatch",
            },
        )

    return request_model.model_copy(
        update={
            "enabled_by": principal.actor_id,
            "actor_scopes": principal.scopes,
        }
    )


def _bind_demo_updated_by(request_model, principal: OidcPrincipal | None):
    if principal is None:
        return request_model

    if principal.tenant_id != "tenant_demo_manufacturing":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": AxisErrorCode.PERMISSION_DENIED.value,
                "message": "The authenticated OIDC tenant cannot access this tenant scope.",
                "reason": "tenant_mismatch",
            },
        )

    request_actor = getattr(request_model, "updated_by", None)
    if request_actor and request_actor != principal.actor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": AxisErrorCode.PERMISSION_DENIED.value,
                "message": "The request actor does not match the authenticated OIDC actor.",
                "reason": "actor_mismatch",
            },
        )

    return request_model.model_copy(
        update={
            "updated_by": principal.actor_id,
            "actor_scopes": principal.scopes,
        }
    )


def _bind_demo_activated_by(request_model, principal: OidcPrincipal | None):
    if principal is None:
        return request_model

    if principal.tenant_id != "tenant_demo_manufacturing":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": AxisErrorCode.PERMISSION_DENIED.value,
                "message": "The authenticated OIDC tenant cannot access this tenant scope.",
                "reason": "tenant_mismatch",
            },
        )

    request_actor = getattr(request_model, "activated_by", None)
    if request_actor and request_actor != principal.actor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": AxisErrorCode.PERMISSION_DENIED.value,
                "message": "The request actor does not match the authenticated OIDC actor.",
                "reason": "actor_mismatch",
            },
        )

    return request_model.model_copy(
        update={
            "activated_by": principal.actor_id,
            "actor_scopes": principal.scopes,
        }
    )


def _bind_demo_requested_by(request_model, principal: OidcPrincipal | None):
    if principal is None:
        return request_model

    if principal.tenant_id != "tenant_demo_manufacturing":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": AxisErrorCode.PERMISSION_DENIED.value,
                "message": "The authenticated OIDC tenant cannot access this tenant scope.",
                "reason": "tenant_mismatch",
            },
        )

    request_actor = getattr(request_model, "requested_by", None)
    if request_actor and request_actor != principal.actor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": AxisErrorCode.PERMISSION_DENIED.value,
                "message": "The request actor does not match the authenticated OIDC actor.",
                "reason": "actor_mismatch",
            },
        )

    return request_model.model_copy(
        update={
            "requested_by": principal.actor_id,
            "actor_scopes": principal.scopes,
        }
    )


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
    app.state.ontology_mutation_runtime = (
        TypeDBOntologyMutationRuntime(
            TypeDBOntologyMutationConfig(
                address=resolved_settings.typedb_address,
                username=resolved_settings.typedb_username,
                password=resolved_settings.typedb_password,
                database=resolved_settings.typedb_database,
            )
        )
        if resolved_settings.ontology_mutations_enabled
        else DeferredOntologyMutationRuntime()
    )
    app.state.ontology_query_runtime = (
        TypeDBOntologyQueryRuntime(
            TypeDBOntologyQueryConfig(
                address=resolved_settings.typedb_address,
                username=resolved_settings.typedb_username,
                password=resolved_settings.typedb_password,
                database=resolved_settings.typedb_database,
            )
        )
        if resolved_settings.ontology_queries_enabled
        else DeferredOntologyQueryRuntime()
    )
    app.state.connector_execution_runtime = DeferredConnectorExecutionRuntime()
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
                "typedb_queries": resolved_settings.ontology_queries_enabled,
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
        retention_days: int = Query(default=365, ge=1, le=3650),
        legal_hold: bool = Query(default=False),
    ) -> ManufacturingReplaySimulation:
        return build_replay_simulation(
            repository,
            ReplaySimulationQuery(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                limit=limit,
                retention_days=retention_days,
                legal_hold=legal_hold,
            ),
        )

    @app.post(
        "/demo/manufacturing/simulation/replay/outputs",
        response_model=ReplaySimulationOutputRecord,
        responses={
            403: {"description": "Replay simulation output permission denied"},
            409: {"description": "Replay simulation output already exists or conflicts"},
            422: {"description": "Replay simulation output validation failed"},
        },
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_replay_simulation_output_create(
        replay_output_request: ReplaySimulationOutputPersistRequest,
        repository: PersistenceRepository,
        principal: OidcPrincipalDependency,
        response: Response,
    ) -> ReplaySimulationOutputRecord:
        try:
            bound_request = _bind_demo_requested_by(replay_output_request, principal)
            result = persist_replay_simulation_output(repository, bound_request)
        except ReplaySimulationOutputPermissionDenied as exc:
            reason = (
                "missing_required_scope"
                if exc.decision.reason.startswith("missing_scope:")
                else exc.decision.reason
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot persist replay simulation outputs.",
                    "required_permission": exc.required_permission,
                    "reason": reason,
                    "permission_reason": exc.decision.reason,
                },
            ) from exc
        except ReplaySimulationOutputConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": AxisErrorCode.POLICY_VIOLATION.value,
                    "message": "The replay simulation output conflicts with existing state.",
                    "reason": exc.reason,
                    "simulation_output_id": exc.simulation_output_id,
                },
            ) from exc
        except ReplaySimulationOutputValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

        if result.idempotent_replay:
            response.status_code = status.HTTP_200_OK
        return result

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

    @app.get(
        "/demo/manufacturing/connectors",
        response_model=ManufacturingConnectorRegistry,
        tags=["demo"],
    )
    def manufacturing_connector_registry() -> ManufacturingConnectorRegistry:
        return get_manufacturing_connector_registry()

    @app.get(
        "/demo/manufacturing/connectors/configurations",
        response_model=ManufacturingConnectorConfigurationRegistry,
        tags=["demo"],
    )
    def manufacturing_connector_configurations(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
        connector_id: str | None = Query(default=None, min_length=1),
        status: str | None = Query(default=None, min_length=1),
        limit: int = Query(default=100, ge=1, le=200),
    ) -> ManufacturingConnectorConfigurationRegistry:
        return build_connector_configuration_registry(
            repository,
            ConnectorConfigurationQuery(
                tenant_id=tenant_id,
                connector_id=connector_id,
                status=status,
                limit=limit,
            ),
        )

    @app.post(
        "/demo/manufacturing/connectors/configurations",
        response_model=ConnectorTenantConfiguration,
        responses={422: {"description": "Connector configuration validation failed"}},
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_connector_configuration_create(
        configuration: ConnectorConfigurationCreateRequest,
        repository: PersistenceRepository,
    ) -> ConnectorTenantConfiguration:
        try:
            return record_demo_connector_configuration(repository, configuration)
        except ConnectorConfigurationValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

    @app.get(
        "/demo/manufacturing/connectors/credential-handles",
        response_model=ManufacturingConnectorCredentialHandleRegistry,
        tags=["demo"],
    )
    def manufacturing_connector_credential_handles(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
        connector_id: str | None = Query(default=None, min_length=1),
        status: str | None = Query(default=None, min_length=1),
        limit: int = Query(default=100, ge=1, le=200),
    ) -> ManufacturingConnectorCredentialHandleRegistry:
        return build_connector_credential_handle_registry(
            repository,
            ConnectorCredentialHandleQuery(
                tenant_id=tenant_id,
                connector_id=connector_id,
                status=status,
                limit=limit,
            ),
        )

    @app.post(
        "/demo/manufacturing/connectors/credential-handles",
        response_model=ConnectorCredentialHandleRecord,
        responses={422: {"description": "Connector credential handle validation failed"}},
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_connector_credential_handle_create(
        credential_handle: ConnectorCredentialHandleCreateRequest,
        repository: PersistenceRepository,
    ) -> ConnectorCredentialHandleRecord:
        try:
            return record_demo_connector_credential_handle(repository, credential_handle)
        except ConnectorCredentialHandleValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

    @app.post(
        "/demo/manufacturing/connectors/credential-handles/{handle_id}/rotations",
        response_model=ConnectorCredentialHandleRecord,
        responses={422: {"description": "Connector credential rotation validation failed"}},
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_connector_credential_handle_rotation(
        handle_id: str,
        rotation: ConnectorCredentialRotationRequest,
        repository: PersistenceRepository,
    ) -> ConnectorCredentialHandleRecord:
        try:
            return record_demo_connector_credential_rotation(repository, handle_id, rotation)
        except ConnectorCredentialHandleValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

    @app.get(
        "/demo/manufacturing/connectors/runs",
        response_model=ManufacturingConnectorRunRegistry,
        tags=["demo"],
    )
    def manufacturing_connector_runs(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
        connector_id: str | None = Query(default=None, min_length=1),
        status: str | None = Query(default=None, min_length=1),
        limit: int = Query(default=100, ge=1, le=200),
    ) -> ManufacturingConnectorRunRegistry:
        return build_connector_run_registry(
            repository,
            ConnectorRunQuery(
                tenant_id=tenant_id,
                connector_id=connector_id,
                status=status,
                limit=limit,
            ),
        )

    @app.post(
        "/demo/manufacturing/connectors/runs",
        response_model=ConnectorRunRecord,
        responses={422: {"description": "Connector run validation failed"}},
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_connector_run_create(
        connector_run: ConnectorRunCreateRequest,
        repository: PersistenceRepository,
        execution_runtime: ConnectorExecutionRuntimeDependency,
    ) -> ConnectorRunRecord:
        try:
            return record_demo_connector_run(repository, connector_run, execution_runtime)
        except ConnectorRunValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

    @app.get(
        "/demo/manufacturing/connectors/ontology-proposals",
        response_model=ManufacturingConnectorOntologyProposalRegistry,
        tags=["demo"],
    )
    def manufacturing_connector_ontology_proposals(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
        connector_id: str | None = Query(default=None, min_length=1),
        status: str | None = Query(default=None, min_length=1),
        limit: int = Query(default=100, ge=1, le=200),
    ) -> ManufacturingConnectorOntologyProposalRegistry:
        return build_connector_ontology_proposal_registry(
            repository,
            ConnectorOntologyProposalQuery(
                tenant_id=tenant_id,
                connector_id=connector_id,
                status=status,
                limit=limit,
            ),
        )

    @app.post(
        "/demo/manufacturing/connectors/ontology-proposals",
        response_model=ManufacturingConnectorOntologyProposalRegistry,
        responses={422: {"description": "Connector ontology proposal validation failed"}},
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_connector_ontology_proposal_create(
        proposal_request: ConnectorOntologyProposalCreateRequest,
        repository: PersistenceRepository,
    ) -> ManufacturingConnectorOntologyProposalRegistry:
        try:
            return record_demo_connector_ontology_proposals(repository, proposal_request)
        except ConnectorOntologyProposalValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

    @app.post(
        "/demo/manufacturing/connectors/ontology-proposals/promotions",
        response_model=ConnectorOntologyPromotionResult,
        responses={
            403: {"description": "Connector ontology promotion permission denied"},
            404: {"description": "Connector ontology proposal not found"},
            409: {"description": "Connector ontology promotion idempotency conflict"},
            422: {"description": "Connector ontology promotion validation failed"},
        },
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_connector_ontology_promotion(
        promotion_request: ConnectorOntologyPromotionRequest,
        repository: PersistenceRepository,
        ontology_runtime: OntologyMutationRuntimeDependency,
        principal: OidcPrincipalDependency,
        response: Response,
    ) -> ConnectorOntologyPromotionResult:
        try:
            bound_promotion = _bind_demo_actor(promotion_request, principal)
            result = record_demo_connector_ontology_promotion(
                repository,
                bound_promotion,
                ontology_runtime,
            )
        except ConnectorOntologyPromotionNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail="Connector ontology proposal not found",
            ) from exc
        except ConnectorOntologyPromotionPermissionDenied as exc:
            reason = (
                "missing_required_scope"
                if exc.decision.reason.startswith("missing_scope:")
                else exc.decision.reason
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot promote this connector ontology proposal.",
                    "required_permission": exc.required_permission,
                    "reason": reason,
                    "permission_reason": exc.decision.reason,
                },
            ) from exc
        except ConnectorOntologyPromotionIdempotencyConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": AxisErrorCode.POLICY_VIOLATION.value,
                    "message": "The idempotency key already exists with a different payload.",
                    "reason": "idempotency_conflict",
                    "promotion_id": exc.promotion_id,
                },
            ) from exc
        except ConnectorOntologyPromotionValidationError as exc:
            detail = {
                "code": AxisErrorCode.VALIDATION_FAILED.value,
                "message": exc.message,
                "reason": exc.reason,
            }
            if exc.audit_event_id is not None:
                repository.session.commit()
                detail["audit_event_id"] = str(exc.audit_event_id)
            if exc.audit_event_type is not None:
                detail["audit_event_type"] = exc.audit_event_type
            raise HTTPException(
                status_code=422,
                detail=detail,
            ) from exc

        if result.idempotent_replay:
            response.status_code = status.HTTP_200_OK

        return result

    @app.get(
        "/demo/manufacturing/connectors/promotion-policies",
        response_model=ManufacturingConnectorPromotionPolicyRegistry,
        tags=["demo"],
    )
    def manufacturing_connector_promotion_policies(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
        connector_id: str | None = Query(default=None, min_length=1),
        status: str | None = Query(default=None, min_length=1),
        limit: int = Query(default=100, ge=1, le=200),
    ) -> ManufacturingConnectorPromotionPolicyRegistry:
        query = ConnectorPromotionPolicyQuery(
            tenant_id=tenant_id,
            connector_id=connector_id,
            status=status,
            limit=limit,
        )
        return build_connector_promotion_policy_registry(
            repository,
            tenant_id=query.tenant_id,
            connector_id=query.connector_id,
            status=query.status,
            limit=query.limit,
        )

    @app.post(
        "/demo/manufacturing/connectors/promotion-policies",
        response_model=ConnectorPromotionPolicyRecord,
        responses={
            403: {"description": "Connector promotion policy permission denied"},
            409: {"description": "Connector promotion policy already exists"},
            422: {"description": "Connector promotion policy validation failed"},
        },
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_connector_promotion_policy_create(
        policy_request: ConnectorPromotionPolicyCreateRequest,
        repository: PersistenceRepository,
        principal: OidcPrincipalDependency,
    ) -> ConnectorPromotionPolicyRecord:
        try:
            bound_policy = _bind_demo_created_by(policy_request, principal)
            return record_demo_connector_promotion_policy(repository, bound_policy)
        except ConnectorPromotionPolicyPermissionDenied as exc:
            reason = (
                "missing_required_scope"
                if exc.decision.reason.startswith("missing_scope:")
                else exc.decision.reason
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot author connector promotion policies.",
                    "required_permission": exc.required_permission,
                    "reason": reason,
                    "permission_reason": exc.decision.reason,
                },
            ) from exc
        except ConnectorPromotionPolicyConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": AxisErrorCode.POLICY_VIOLATION.value,
                    "message": "The connector promotion policy already exists.",
                    "reason": "policy_already_exists",
                    "policy_id": exc.policy_id,
                },
            ) from exc
        except ConnectorPromotionPolicyValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

    @app.post(
        "/demo/manufacturing/connectors/promotion-policies/{policy_id}/enable",
        response_model=ConnectorPromotionPolicyRecord,
        responses={
            403: {"description": "Connector promotion policy enable permission denied"},
            404: {"description": "Connector promotion policy not found"},
            422: {"description": "Connector promotion policy enable validation failed"},
        },
        tags=["demo"],
    )
    def manufacturing_connector_promotion_policy_enable(
        policy_id: str,
        enable_request: ConnectorPromotionPolicyEnableRequest,
        repository: PersistenceRepository,
        principal: OidcPrincipalDependency,
    ) -> ConnectorPromotionPolicyRecord:
        if policy_id != enable_request.policy_id:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "The path policy_id must match the request policy_id.",
                    "reason": "policy_id_mismatch",
                },
            )
        try:
            bound_request = _bind_demo_enabled_by(enable_request, principal)
            return enable_demo_connector_promotion_policy(repository, bound_request)
        except ConnectorPromotionPolicyNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail="Connector promotion policy not found",
            ) from exc
        except ConnectorPromotionPolicyPermissionDenied as exc:
            reason = (
                "missing_required_scope"
                if exc.decision.reason.startswith("missing_scope:")
                else exc.decision.reason
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot enable connector promotion policies.",
                    "required_permission": exc.required_permission,
                    "reason": reason,
                    "permission_reason": exc.decision.reason,
                },
            ) from exc
        except ConnectorPromotionPolicyValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

    @app.post(
        "/demo/manufacturing/connectors/promotion-policies/{policy_id}/revise",
        response_model=ConnectorPromotionPolicyRecord,
        responses={
            403: {"description": "Connector promotion policy revision permission denied"},
            404: {"description": "Connector promotion policy not found"},
            409: {"description": "Connector promotion policy revision conflict"},
            422: {"description": "Connector promotion policy revision validation failed"},
        },
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_connector_promotion_policy_revise(
        policy_id: str,
        revise_request: ConnectorPromotionPolicyReviseRequest,
        response: Response,
        repository: PersistenceRepository,
        principal: OidcPrincipalDependency,
    ) -> ConnectorPromotionPolicyRecord:
        if policy_id != revise_request.revises_policy_id:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "The path policy_id must match the request revises_policy_id.",
                    "reason": "policy_revision_target_mismatch",
                },
            )
        try:
            bound_request = _bind_demo_updated_by(revise_request, principal)
            result = revise_demo_connector_promotion_policy(repository, bound_request)
        except ConnectorPromotionPolicyNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail="Connector promotion policy not found",
            ) from exc
        except ConnectorPromotionPolicyPermissionDenied as exc:
            reason = (
                "missing_required_scope"
                if exc.decision.reason.startswith("missing_scope:")
                else exc.decision.reason
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot revise connector promotion policies.",
                    "required_permission": exc.required_permission,
                    "reason": reason,
                    "permission_reason": exc.decision.reason,
                },
            ) from exc
        except ConnectorPromotionPolicyConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": AxisErrorCode.POLICY_VIOLATION.value,
                    "message": "The connector promotion policy already exists.",
                    "reason": "policy_already_exists",
                    "policy_id": exc.policy_id,
                },
            ) from exc
        except ConnectorPromotionPolicyValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

        if result.idempotent_replay:
            response.status_code = status.HTTP_200_OK
        return result

    @app.get(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        response_model=ManufacturingConnectorPromotionPolicySetRegistry,
        tags=["demo"],
    )
    def manufacturing_connector_promotion_policy_sets(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
        connector_id: str | None = Query(default=None, min_length=1),
        status: str | None = Query(default=None, min_length=1),
        limit: int = Query(default=100, ge=1, le=200),
    ) -> ManufacturingConnectorPromotionPolicySetRegistry:
        query = ConnectorPromotionPolicySetQuery(
            tenant_id=tenant_id,
            connector_id=connector_id,
            status=status,
            limit=limit,
        )
        return build_connector_promotion_policy_set_registry(
            repository,
            tenant_id=query.tenant_id,
            connector_id=query.connector_id,
            status=query.status,
            limit=query.limit,
        )

    @app.post(
        "/demo/manufacturing/connectors/promotion-policy-sets",
        response_model=ConnectorPromotionPolicySetRecord,
        responses={
            403: {"description": "Connector promotion policy set permission denied"},
            409: {"description": "Connector promotion policy set already exists or active"},
            422: {"description": "Connector promotion policy set validation failed"},
        },
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_connector_promotion_policy_set_create(
        policy_set_request: ConnectorPromotionPolicySetActivateRequest,
        repository: PersistenceRepository,
        principal: OidcPrincipalDependency,
    ) -> ConnectorPromotionPolicySetRecord:
        try:
            bound_request = _bind_demo_activated_by(policy_set_request, principal)
            return record_demo_connector_promotion_policy_set(repository, bound_request)
        except ConnectorPromotionPolicySetPermissionDenied as exc:
            reason = (
                "missing_required_scope"
                if exc.decision.reason.startswith("missing_scope:")
                else exc.decision.reason
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot activate connector promotion policy sets.",
                    "required_permission": exc.required_permission,
                    "reason": reason,
                    "permission_reason": exc.decision.reason,
                },
            ) from exc
        except ConnectorPromotionPolicySetConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": AxisErrorCode.POLICY_VIOLATION.value,
                    "message": "The connector promotion policy set conflicts with existing state.",
                    "reason": exc.reason,
                    "policy_set_id": exc.policy_set_id,
                },
            ) from exc
        except ConnectorPromotionPolicySetValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

    @app.get(
        "/demo/manufacturing/connectors/manual-imports",
        response_model=ManufacturingConnectorManualImportRegistry,
        tags=["demo"],
    )
    def manufacturing_connector_manual_imports(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
        connector_id: str | None = Query(default=None, min_length=1),
        status: str | None = Query(default=None, min_length=1),
        limit: int = Query(default=100, ge=1, le=200),
    ) -> ManufacturingConnectorManualImportRegistry:
        return build_connector_manual_import_registry(
            repository,
            ConnectorManualImportQuery(
                tenant_id=tenant_id,
                connector_id=connector_id,
                status=status,
                limit=limit,
            ),
        )

    @app.post(
        "/demo/manufacturing/connectors/manual-imports",
        response_model=ConnectorManualImportRecord,
        responses={
            409: {"description": "Connector manual import idempotency conflict"},
            422: {"description": "Connector manual import validation failed"},
        },
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_connector_manual_import_create(
        manual_import_request: ConnectorManualImportCreateRequest,
        repository: PersistenceRepository,
        response: Response,
    ) -> ConnectorManualImportRecord:
        try:
            result = record_demo_connector_manual_import(repository, manual_import_request)
        except ConnectorManualImportIdempotencyConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": AxisErrorCode.POLICY_VIOLATION.value,
                    "message": "The idempotency key already exists with a different payload.",
                    "reason": "idempotency_conflict",
                    "import_id": exc.import_id,
                },
            ) from exc
        except ConnectorManualImportValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

        if result.idempotent_replay:
            response.status_code = status.HTTP_200_OK

        return result

    @app.post(
        "/demo/manufacturing/connectors/manual-imports/{import_id}/decision",
        response_model=ConnectorManualImportDecisionResult,
        responses={
            403: {"description": "Connector manual import decision permission denied"},
            404: {"description": "Connector manual import request not found"},
        },
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    async def manufacturing_connector_manual_import_decision(
        import_id: str,
        decision: ConnectorManualImportDecisionRequest,
        repository: PersistenceRepository,
        runtime: WorkflowRuntime,
        principal: OidcPrincipalDependency,
    ) -> ConnectorManualImportDecisionResult:
        try:
            bound_decision = _bind_demo_actor(decision, principal)
            return await record_demo_connector_manual_import_decision(
                repository,
                import_id,
                bound_decision,
                runtime,
            )
        except ConnectorManualImportNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail="Connector manual import not found",
            ) from exc
        except ConnectorManualImportPermissionDenied as exc:
            reason = (
                "missing_required_scope"
                if exc.decision.reason.startswith("missing_scope:")
                else exc.decision.reason
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot decide this connector manual import.",
                    "required_permission": exc.required_permission,
                    "reason": reason,
                    "permission_reason": exc.decision.reason,
                },
            ) from exc

    @app.post(
        "/demo/manufacturing/connectors/file-csv/preview",
        response_model=ConnectorCsvPreviewResult,
        tags=["demo"],
    )
    def manufacturing_file_csv_connector_preview(
        preview_request: ConnectorCsvPreviewRequest,
    ) -> ConnectorCsvPreviewResult:
        return preview_file_csv_connector(preview_request)

    @app.post(
        "/demo/manufacturing/connectors/external-db/preview",
        response_model=ConnectorExternalDbPreviewResult,
        tags=["demo"],
    )
    def manufacturing_external_db_connector_preview(
        preview_request: ConnectorExternalDbPreviewRequest,
    ) -> ConnectorExternalDbPreviewResult:
        return preview_external_db_connector(preview_request)

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
    def manufacturing_ontology(
        principal: OidcPrincipalDependency,
        ontology_query_runtime: OntologyQueryRuntimeDependency,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
        limit: int = Query(default=200, ge=1, le=500),
    ) -> ManufacturingOntology:
        if principal is not None and principal.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot read ontology graph data for this tenant.",
                    "reason": "tenant_mismatch",
                },
            )

        return query_manufacturing_ontology_graph(
            ontology_query_runtime,
            OntologyGraphQueryRequest(
                tenant_id=tenant_id,
                actor_id=principal.actor_id if principal is not None else "public-demo-reader",
                actor_scopes=principal.scopes if principal is not None else [],
                enforce_relationship_scopes=principal is not None,
                limit=limit,
            ),
        )

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
