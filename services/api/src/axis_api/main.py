from collections.abc import Generator
from datetime import datetime
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

from axis_api.action_reference import (
    ActionReferenceRecordInvalid,
    ActionReferenceRecordNotFound,
    get_persisted_manufacturing_action_registry,
)
from axis_api.action_runs import (
    ActionPayloadValidationError,
    ActionPermissionDenied,
    ActionRunIdempotencyConflict,
    ActionRunPersistenceResult,
    ActionRunRequest,
    DemoActionNotFound,
    record_demo_action_run,
)
from axis_api.agent_reference import (
    AgentReferenceRecordInvalid,
    AgentReferenceRecordNotFound,
    get_persisted_manufacturing_agent_registry,
)
from axis_api.approval_decisions import (
    ApprovalDecisionPersistenceResult,
    ApprovalDecisionRequest,
    ApprovalPermissionDenied,
    DemoApprovalNotFound,
    record_demo_approval_decision,
)
from axis_api.approval_reference import (
    ApprovalReferenceRecordInvalid,
    ApprovalReferenceRecordNotFound,
    get_persisted_manufacturing_approval_inbox,
)
from axis_api.audit_queries import (
    AuditEventQuery,
    AuditExportBundle,
    AuditExportQuery,
    AuditLegalHoldConflict,
    AuditLegalHoldCreateRequest,
    AuditLegalHoldNotFound,
    AuditLegalHoldPermissionDenied,
    AuditLegalHoldRecord,
    AuditLegalHoldReleaseRequest,
    AuditRetentionDeletionPermissionDenied,
    AuditRetentionDeletionRequest,
    AuditRetentionDeletionResult,
    create_audit_legal_hold,
    execute_audit_retention_deletion,
    export_persisted_audit_events,
    list_audit_legal_holds,
    query_persisted_audit_events,
    release_audit_legal_hold,
)
from axis_api.audit_reference import (
    AuditReferenceRecordInvalid,
    AuditReferenceRecordNotFound,
    get_persisted_manufacturing_audit_explorer,
)
from axis_api.audit_signing import SelfHostedAuditLedgerSigner
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
from axis_api.connector_credential_leases import (
    ConnectorCredentialLeaseConflict,
    ConnectorCredentialLeasePermissionDenied,
    ConnectorCredentialLeaseQuery,
    ConnectorCredentialLeaseRecord,
    ConnectorCredentialLeaseRenewRequest,
    ConnectorCredentialLeaseRequest,
    ConnectorCredentialLeaseRevokeRequest,
    ConnectorCredentialLeaseValidationError,
    CredentialLeaseRuntime,
    DeferredCredentialLeaseRuntime,
    ManufacturingConnectorCredentialLeaseRegistry,
    ProviderSpecificVaultKmsLeaseRuntime,
    SelfHostedVaultKmsLeaseRuntime,
    read_connector_credential_lease_registry,
    record_demo_connector_credential_lease,
    renew_demo_connector_credential_lease,
    revoke_demo_connector_credential_lease,
)
from axis_api.connector_egress_policies import (
    ConnectorEgressPolicyCreateRequest,
    ConnectorEgressPolicyQuery,
    ConnectorEgressPolicyRecord,
    ConnectorEgressPolicyValidationError,
    ManufacturingConnectorEgressPolicyRegistry,
    build_connector_egress_policy_registry,
    record_demo_connector_egress_policy,
)
from axis_api.connector_execution import (
    ConnectorExecutionRuntime,
    ConnectorSyncDispatchRuntime,
    ConnectorSyncExecutionRuntime,
    ConnectorSyncSchedulerRuntime,
    DeferredConnectorExecutionRuntime,
    DeferredConnectorSyncDispatchRuntime,
    DeferredConnectorSyncExecutionRuntime,
    DeferredConnectorSyncSchedulerRuntime,
    SelfHostedConnectorSyncExecutionRuntime,
)
from axis_api.connector_manifests import (
    ConnectorManifestConflict,
    ConnectorManifestCreateRequest,
    ConnectorManifestLifecycleRequest,
    ConnectorManifestLifecycleValidationError,
    ConnectorManifestQuery,
    ConnectorManifestRecordView,
    ConnectorManifestValidationError,
    ManufacturingConnectorManifestRegistry,
    build_connector_manifest_registry,
    record_demo_connector_manifest,
    transition_demo_connector_manifest_lifecycle,
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
from axis_api.connector_reference import (
    ConnectorReferenceRecordInvalid,
    ConnectorReferenceRecordNotFound,
    get_persisted_manufacturing_connector_registry,
)
from axis_api.connector_runs import (
    SYNC_CHECKPOINT_CLAIM_READ_SCOPE,
    SYNC_CHECKPOINT_READ_SCOPE,
    ConnectorRunCreateRequest,
    ConnectorRunDispatchConflict,
    ConnectorRunDispatchRequest,
    ConnectorRunNotFound,
    ConnectorRunPermissionDenied,
    ConnectorRunQuery,
    ConnectorRunRecord,
    ConnectorRunSyncExecutionConflict,
    ConnectorRunSyncExecutionRequest,
    ConnectorRunValidationError,
    ConnectorSyncCheckpointClaimConflict,
    ConnectorSyncCheckpointClaimQuery,
    ConnectorSyncCheckpointClaimRecord,
    ConnectorSyncCheckpointClaimReleaseRequest,
    ConnectorSyncCheckpointClaimRenewRequest,
    ConnectorSyncCheckpointClaimRequest,
    ConnectorSyncCheckpointQuery,
    ManufacturingConnectorRunRegistry,
    ManufacturingConnectorSyncCheckpointClaimRegistry,
    ManufacturingConnectorSyncCheckpointRegistry,
    build_connector_run_registry,
    claim_connector_sync_checkpoint,
    dispatch_demo_connector_sync,
    execute_demo_connector_sync,
    read_connector_sync_checkpoint_claim_registry,
    read_connector_sync_checkpoint_registry,
    record_demo_connector_run,
    release_connector_sync_checkpoint_claim,
    renew_connector_sync_checkpoint_claim,
)
from axis_api.connectors import (
    ConnectorCsvPreviewRequest,
    ConnectorCsvPreviewResult,
    ConnectorExternalDbPreviewRequest,
    ConnectorExternalDbPreviewResult,
    ManufacturingConnectorRegistry,
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
)
from axis_api.demo_reference import (
    DemoReferenceRecordInvalid,
    DemoReferenceRecordNotFound,
    get_persisted_manufacturing_overview,
)
from axis_api.errors import AxisErrorCode
from axis_api.identity import (
    ActorBindingError,
    OidcAuthenticationError,
    OidcPrincipal,
    RemoteJwksOidcVerifier,
    bind_request_actor,
)
from axis_api.manufacturing_operations import (
    DailyPlantBriefIdempotencyConflict,
    DailyPlantBriefPermissionDenied,
    DailyPlantBriefRecord,
    DailyPlantBriefRequest,
    DailyPlantBriefValidationError,
    MaintenanceRiskScenarioIdempotencyConflict,
    MaintenanceRiskScenarioPermissionDenied,
    MaintenanceRiskScenarioRecord,
    MaintenanceRiskScenarioRequest,
    MaintenanceRiskScenarioValidationError,
    ManufacturingOperationQuery,
    ManufacturingOperationsDataset,
    ManufacturingOperationsSnapshot,
    ManufacturingOperationsSnapshotQuery,
    QualityRiskScenarioIdempotencyConflict,
    QualityRiskScenarioPermissionDenied,
    QualityRiskScenarioRecord,
    QualityRiskScenarioRequest,
    QualityRiskScenarioValidationError,
    SupplierDelayScenarioIdempotencyConflict,
    SupplierDelayScenarioPermissionDenied,
    SupplierDelayScenarioRecord,
    SupplierDelayScenarioRequest,
    SupplierDelayScenarioValidationError,
    build_manufacturing_operations_snapshot,
    generate_daily_plant_brief,
    generate_maintenance_risk_scenario,
    generate_quality_risk_scenario,
    generate_supplier_delay_scenario,
    query_manufacturing_operations_dataset,
)
from axis_api.model_routing_reference import (
    ModelRoutingReferenceRecordInvalid,
    ModelRoutingReferenceRecordNotFound,
    get_persisted_manufacturing_model_routing,
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
from axis_api.ontology_reference import (
    OntologyReferenceRecordInvalid,
    OntologyReferenceRecordNotFound,
    get_persisted_manufacturing_ontology,
    get_persisted_manufacturing_ontology_entity_detail,
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
from axis_api.workflow_reference import (
    WorkflowReferenceRecordInvalid,
    WorkflowReferenceRecordNotFound,
    get_persisted_manufacturing_workflow_console,
)
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


def connector_sync_scheduler_runtime(request: Request) -> ConnectorSyncSchedulerRuntime:
    return request.app.state.connector_sync_scheduler_runtime


ConnectorSyncSchedulerRuntimeDependency = Annotated[
    ConnectorSyncSchedulerRuntime,
    Depends(connector_sync_scheduler_runtime),
]


def connector_sync_dispatch_runtime(request: Request) -> ConnectorSyncDispatchRuntime:
    return request.app.state.connector_sync_dispatch_runtime


ConnectorSyncDispatchRuntimeDependency = Annotated[
    ConnectorSyncDispatchRuntime,
    Depends(connector_sync_dispatch_runtime),
]


def connector_sync_execution_runtime(request: Request) -> ConnectorSyncExecutionRuntime:
    return request.app.state.connector_sync_execution_runtime


ConnectorSyncExecutionRuntimeDependency = Annotated[
    ConnectorSyncExecutionRuntime,
    Depends(connector_sync_execution_runtime),
]


def credential_lease_runtime(request: Request) -> CredentialLeaseRuntime:
    return request.app.state.credential_lease_runtime


CredentialLeaseRuntimeDependency = Annotated[
    CredentialLeaseRuntime,
    Depends(credential_lease_runtime),
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
CheckpointActorScopesQuery = Query(default_factory=list)
CheckpointCreatedAfterQuery = Query(default=None)
CheckpointCreatedBeforeQuery = Query(default=None)


def _audit_ledger_signer_from_settings(settings: Settings) -> SelfHostedAuditLedgerSigner | None:
    if settings.audit_ledger_signing_secret is None:
        return None
    return SelfHostedAuditLedgerSigner(
        key_id=settings.audit_ledger_signing_key_id,
        secret_key=settings.audit_ledger_signing_secret,
    )


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


def _authorize_connector_sync_checkpoint_read(
    tenant_id: str,
    actor_scopes: list[str],
    principal: OidcPrincipal | None,
) -> None:
    if principal is not None and principal.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": AxisErrorCode.PERMISSION_DENIED.value,
                "message": "The authenticated OIDC tenant cannot access connector checkpoints.",
                "required_permission": SYNC_CHECKPOINT_READ_SCOPE,
                "reason": "tenant_mismatch",
            },
        )

    decision = evaluate_permission(
        PermissionRequest(
            tenant_id=tenant_id,
            actor_id=(
                principal.actor_id
                if principal is not None
                else "connector-sync-checkpoint-reader"
            ),
            actor_scopes=principal.scopes if principal is not None else actor_scopes,
            required_scopes=[SYNC_CHECKPOINT_READ_SCOPE],
            attributes={
                "surface": "connectors",
                "resource": "connector_sync_checkpoints",
            },
        )
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": AxisErrorCode.PERMISSION_DENIED.value,
                "message": "The actor cannot read connector sync checkpoints.",
                "required_permission": SYNC_CHECKPOINT_READ_SCOPE,
                "reason": "missing_required_scope"
                if decision.reason.startswith("missing_scope:")
                else decision.reason,
                "permission_reason": decision.reason,
            },
        )


def _authorize_connector_sync_checkpoint_claim_read(
    tenant_id: str,
    actor_scopes: list[str],
    principal: OidcPrincipal | None,
) -> None:
    if principal is not None and principal.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": AxisErrorCode.PERMISSION_DENIED.value,
                "message": (
                    "The authenticated OIDC tenant cannot access connector "
                    "checkpoint claims."
                ),
                "required_permission": SYNC_CHECKPOINT_CLAIM_READ_SCOPE,
                "reason": "tenant_mismatch",
            },
        )

    decision = evaluate_permission(
        PermissionRequest(
            tenant_id=tenant_id,
            actor_id=(
                principal.actor_id
                if principal is not None
                else "connector-sync-checkpoint-claim-reader"
            ),
            actor_scopes=principal.scopes if principal is not None else actor_scopes,
            required_scopes=[SYNC_CHECKPOINT_CLAIM_READ_SCOPE],
            attributes={
                "surface": "connectors",
                "resource": "connector_sync_checkpoint_claims",
            },
        )
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": AxisErrorCode.PERMISSION_DENIED.value,
                "message": "The actor cannot read connector sync checkpoint claims.",
                "required_permission": SYNC_CHECKPOINT_CLAIM_READ_SCOPE,
                "reason": "missing_required_scope"
                if decision.reason.startswith("missing_scope:")
                else decision.reason,
                "permission_reason": decision.reason,
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
    app.state.connector_sync_scheduler_runtime = DeferredConnectorSyncSchedulerRuntime()
    app.state.connector_sync_dispatch_runtime = DeferredConnectorSyncDispatchRuntime()
    app.state.connector_sync_execution_runtime = (
        SelfHostedConnectorSyncExecutionRuntime(
            external_db_sync_enabled=resolved_settings.external_db_sync_execution_enabled,
            external_db_live_query_preflight_enabled=(
                resolved_settings.external_db_live_query_preflight_enabled
            ),
        )
        if resolved_settings.connector_sync_execution_enabled
        else DeferredConnectorSyncExecutionRuntime()
    )
    if resolved_settings.credential_lease_provider_adapters_enabled:
        app.state.credential_lease_runtime = ProviderSpecificVaultKmsLeaseRuntime()
    elif resolved_settings.credential_lease_execution_enabled:
        app.state.credential_lease_runtime = SelfHostedVaultKmsLeaseRuntime()
    else:
        app.state.credential_lease_runtime = DeferredCredentialLeaseRuntime()
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
        responses={
            404: {"description": "Manufacturing overview reference record not found"},
            422: {"description": "Manufacturing overview reference payload invalid"},
        },
        tags=["demo"],
    )
    def manufacturing_overview(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
    ) -> ManufacturingOverview:
        try:
            return get_persisted_manufacturing_overview(repository, tenant_id=tenant_id)
        except DemoReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing overview reference record not found.",
                    "tenant_id": tenant_id,
                    "surface": "overview",
                },
            ) from exc
        except DemoReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing overview reference payload is invalid.",
                    "tenant_id": tenant_id,
                    "surface": "overview",
                },
            ) from exc

    @app.get(
        "/demo/manufacturing/workflows",
        response_model=ManufacturingWorkflowConsole,
        responses={
            404: {"description": "Workflow console reference record not found"},
            422: {"description": "Workflow console reference payload invalid"},
        },
        tags=["demo"],
    )
    def manufacturing_workflow_console(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
    ) -> ManufacturingWorkflowConsole:
        try:
            return get_persisted_manufacturing_workflow_console(
                repository,
                tenant_id=tenant_id,
            )
        except WorkflowReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing workflow console reference record not found.",
                    "tenant_id": tenant_id,
                    "surface": "workflows",
                },
            ) from exc
        except WorkflowReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing workflow console reference payload is invalid.",
                    "tenant_id": tenant_id,
                    "surface": "workflows",
                },
            ) from exc

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
        "/demo/manufacturing/operations",
        response_model=ManufacturingOperationsDataset,
        tags=["demo"],
    )
    def manufacturing_operations_dataset(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
        domain: str | None = Query(default=None, min_length=1),
        status: str | None = Query(default=None, min_length=1),
        record_type: str | None = Query(default=None, min_length=1),
        source_system: str | None = Query(default=None, min_length=1),
        limit: int = Query(default=100, ge=1, le=200),
    ) -> ManufacturingOperationsDataset:
        return query_manufacturing_operations_dataset(
            repository,
            ManufacturingOperationQuery(
                tenant_id=tenant_id,
                domain=domain,
                status=status,
                record_type=record_type,
                source_system=source_system,
                limit=limit,
            ),
        )

    @app.get(
        "/demo/manufacturing/operations/snapshot",
        response_model=ManufacturingOperationsSnapshot,
        tags=["demo"],
    )
    def manufacturing_operations_snapshot(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
        operation_limit: int = Query(default=100, ge=1, le=200),
        workflow_limit: int = Query(default=25, ge=1, le=100),
        approval_limit: int = Query(default=25, ge=1, le=100),
        artifact_limit: int = Query(default=10, ge=1, le=50),
        audit_limit: int = Query(default=25, ge=1, le=100),
    ) -> ManufacturingOperationsSnapshot:
        return build_manufacturing_operations_snapshot(
            repository,
            ManufacturingOperationsSnapshotQuery(
                tenant_id=tenant_id,
                operation_limit=operation_limit,
                workflow_limit=workflow_limit,
                approval_limit=approval_limit,
                artifact_limit=artifact_limit,
                audit_limit=audit_limit,
            ),
        )

    @app.post(
        "/demo/manufacturing/operations/daily-brief",
        response_model=DailyPlantBriefRecord,
        responses={
            403: {"description": "Daily plant brief permission denied"},
            409: {"description": "Daily plant brief idempotency conflict"},
            422: {"description": "Daily plant brief validation failed"},
        },
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_daily_plant_brief(
        brief_request: DailyPlantBriefRequest,
        repository: PersistenceRepository,
        response: Response,
    ) -> DailyPlantBriefRecord:
        try:
            result = generate_daily_plant_brief(repository, brief_request)
        except DailyPlantBriefPermissionDenied as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot generate a daily plant brief.",
                    "required_permissions": [
                        "briefs:generate",
                        "audit:read",
                        "workflows:read",
                    ],
                    "reason": exc.decision.reason,
                },
            ) from exc
        except DailyPlantBriefIdempotencyConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": AxisErrorCode.POLICY_VIOLATION.value,
                    "message": "The daily plant brief idempotency key conflicts.",
                    "brief_id": exc.brief_id,
                },
            ) from exc
        except DailyPlantBriefValidationError as exc:
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
        "/demo/manufacturing/operations/risk-scenarios/quality",
        response_model=QualityRiskScenarioRecord,
        responses={
            403: {"description": "Quality risk scenario permission denied"},
            409: {"description": "Quality risk scenario idempotency conflict"},
            422: {"description": "Quality risk scenario validation failed"},
        },
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_quality_risk_scenario(
        scenario_request: QualityRiskScenarioRequest,
        repository: PersistenceRepository,
        response: Response,
    ) -> QualityRiskScenarioRecord:
        try:
            result = generate_quality_risk_scenario(repository, scenario_request)
        except QualityRiskScenarioPermissionDenied as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot generate a quality risk scenario.",
                    "required_permissions": [
                        "quality:read",
                        "workflows:read",
                        "audit:read",
                    ],
                    "reason": exc.decision.reason,
                },
            ) from exc
        except QualityRiskScenarioIdempotencyConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": AxisErrorCode.POLICY_VIOLATION.value,
                    "message": "The quality risk scenario idempotency key conflicts.",
                    "scenario_id": exc.scenario_id,
                },
            ) from exc
        except QualityRiskScenarioValidationError as exc:
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
        "/demo/manufacturing/operations/risk-scenarios/maintenance",
        response_model=MaintenanceRiskScenarioRecord,
        responses={
            403: {"description": "Maintenance risk scenario permission denied"},
            409: {"description": "Maintenance risk scenario idempotency conflict"},
            422: {"description": "Maintenance risk scenario validation failed"},
        },
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_maintenance_risk_scenario(
        scenario_request: MaintenanceRiskScenarioRequest,
        repository: PersistenceRepository,
        response: Response,
    ) -> MaintenanceRiskScenarioRecord:
        try:
            result = generate_maintenance_risk_scenario(repository, scenario_request)
        except MaintenanceRiskScenarioPermissionDenied as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot generate a maintenance risk scenario.",
                    "required_permissions": [
                        "maintenance:read",
                        "workflows:read",
                        "audit:read",
                    ],
                    "reason": exc.decision.reason,
                },
            ) from exc
        except MaintenanceRiskScenarioIdempotencyConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": AxisErrorCode.POLICY_VIOLATION.value,
                    "message": (
                        "The maintenance risk scenario idempotency key conflicts."
                    ),
                    "scenario_id": exc.scenario_id,
                },
            ) from exc
        except MaintenanceRiskScenarioValidationError as exc:
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
        "/demo/manufacturing/operations/risk-scenarios/supplier-delay",
        response_model=SupplierDelayScenarioRecord,
        responses={
            403: {"description": "Supplier delay scenario permission denied"},
            409: {"description": "Supplier delay scenario idempotency conflict"},
            422: {"description": "Supplier delay scenario validation failed"},
        },
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_supplier_delay_scenario(
        scenario_request: SupplierDelayScenarioRequest,
        repository: PersistenceRepository,
        response: Response,
    ) -> SupplierDelayScenarioRecord:
        try:
            result = generate_supplier_delay_scenario(repository, scenario_request)
        except SupplierDelayScenarioPermissionDenied as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot generate a supplier delay scenario.",
                    "required_permissions": [
                        "supply:read",
                        "workflows:read",
                        "audit:read",
                    ],
                    "reason": exc.decision.reason,
                },
            ) from exc
        except SupplierDelayScenarioIdempotencyConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": AxisErrorCode.POLICY_VIOLATION.value,
                    "message": "The supplier delay scenario idempotency key conflicts.",
                    "scenario_id": exc.scenario_id,
                },
            ) from exc
        except SupplierDelayScenarioValidationError as exc:
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
        responses={
            404: {"description": "Agent registry reference record not found"},
            422: {"description": "Agent registry reference payload invalid"},
        },
        tags=["demo"],
    )
    def manufacturing_agent_registry(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
    ) -> ManufacturingAgentRegistry:
        try:
            return get_persisted_manufacturing_agent_registry(
                repository,
                tenant_id=tenant_id,
            )
        except AgentReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing agent registry reference record not found.",
                    "tenant_id": tenant_id,
                    "surface": "agents",
                },
            ) from exc
        except AgentReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing agent registry reference payload is invalid.",
                    "tenant_id": tenant_id,
                    "surface": "agents",
                },
            ) from exc

    @app.get(
        "/demo/manufacturing/actions",
        response_model=ManufacturingActionRegistry,
        responses={
            404: {"description": "Action registry reference record not found"},
            422: {"description": "Action registry reference payload invalid"},
        },
        tags=["demo"],
    )
    def manufacturing_action_registry(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
    ) -> ManufacturingActionRegistry:
        try:
            return get_persisted_manufacturing_action_registry(
                repository,
                tenant_id=tenant_id,
            )
        except ActionReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing action registry reference record not found.",
                    "tenant_id": tenant_id,
                    "surface": "actions",
                },
            ) from exc
        except ActionReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing action registry reference payload is invalid.",
                    "tenant_id": tenant_id,
                    "surface": "actions",
                },
            ) from exc

    @app.get(
        "/demo/manufacturing/connectors",
        response_model=ManufacturingConnectorRegistry,
        responses={
            404: {"description": "Connector registry reference record not found"},
            422: {"description": "Connector registry reference payload invalid"},
        },
        tags=["demo"],
    )
    def manufacturing_connector_registry(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
    ) -> ManufacturingConnectorRegistry:
        try:
            return get_persisted_manufacturing_connector_registry(
                repository,
                tenant_id=tenant_id,
            )
        except ConnectorReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing connector registry reference record not found.",
                    "tenant_id": tenant_id,
                    "surface": "connectors",
                },
            ) from exc
        except ConnectorReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing connector registry reference payload is invalid.",
                    "tenant_id": tenant_id,
                    "surface": "connectors",
                },
            ) from exc

    @app.get(
        "/demo/manufacturing/connectors/manifests",
        response_model=ManufacturingConnectorManifestRegistry,
        tags=["demo"],
    )
    def manufacturing_connector_manifests(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
        connector_id: str | None = Query(default=None, min_length=1),
        status: str | None = Query(default=None, min_length=1),
        limit: int = Query(default=100, ge=1, le=200),
    ) -> ManufacturingConnectorManifestRegistry:
        return build_connector_manifest_registry(
            repository,
            ConnectorManifestQuery(
                tenant_id=tenant_id,
                connector_id=connector_id,
                status=status,
                limit=limit,
            ),
        )

    @app.post(
        "/demo/manufacturing/connectors/manifests",
        response_model=ConnectorManifestRecordView,
        responses={
            409: {"description": "Connector manifest already exists"},
            422: {"description": "Connector manifest validation failed"},
        },
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_connector_manifest_create(
        manifest: ConnectorManifestCreateRequest,
        repository: PersistenceRepository,
    ) -> ConnectorManifestRecordView:
        try:
            return record_demo_connector_manifest(repository, manifest)
        except ConnectorManifestConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": AxisErrorCode.POLICY_VIOLATION.value,
                    "message": "The connector manifest already exists.",
                    "reason": "manifest_already_exists",
                    "connector_id": exc.connector_id,
                },
            ) from exc
        except ConnectorManifestValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

    @app.post(
        "/demo/manufacturing/connectors/manifests/{connector_id}/lifecycle",
        response_model=ConnectorManifestRecordView,
        responses={
            403: {"description": "Connector manifest lifecycle permission denied"},
            422: {"description": "Connector manifest lifecycle validation failed"},
        },
        tags=["demo"],
    )
    def manufacturing_connector_manifest_lifecycle(
        connector_id: str,
        lifecycle_request: ConnectorManifestLifecycleRequest,
        repository: PersistenceRepository,
    ) -> ConnectorManifestRecordView:
        try:
            return transition_demo_connector_manifest_lifecycle(
                repository,
                connector_id,
                lifecycle_request,
            )
        except ConnectorManifestLifecycleValidationError as exc:
            status_code = (
                403
                if exc.reason == "missing_manifest_lifecycle_scope"
                else 422
            )
            raise HTTPException(
                status_code=status_code,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

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
        responses={
            404: {"description": "Connector registry reference record not found"},
            422: {"description": "Connector configuration or registry reference validation failed"},
        },
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_connector_configuration_create(
        configuration: ConnectorConfigurationCreateRequest,
        repository: PersistenceRepository,
    ) -> ConnectorTenantConfiguration:
        try:
            return record_demo_connector_configuration(repository, configuration)
        except ConnectorReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing connector registry reference record not found.",
                    "surface": "connectors",
                },
            ) from exc
        except ConnectorReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing connector registry reference payload is invalid.",
                    "surface": "connectors",
                },
            ) from exc
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
        responses={
            404: {"description": "Connector registry reference record not found"},
            422: {"description": "Connector credential handle or registry validation failed"},
        },
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_connector_credential_handle_create(
        credential_handle: ConnectorCredentialHandleCreateRequest,
        repository: PersistenceRepository,
    ) -> ConnectorCredentialHandleRecord:
        try:
            return record_demo_connector_credential_handle(repository, credential_handle)
        except ConnectorReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing connector registry reference record not found.",
                    "surface": "connectors",
                },
            ) from exc
        except ConnectorReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing connector registry reference payload is invalid.",
                    "surface": "connectors",
                },
            ) from exc
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
        "/demo/manufacturing/connectors/credential-leases",
        response_model=ManufacturingConnectorCredentialLeaseRegistry,
        tags=["demo"],
    )
    def manufacturing_connector_credential_leases(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
        connector_id: str | None = Query(default=None, min_length=1),
        handle_id: str | None = Query(default=None, min_length=1),
        status: str | None = Query(default=None, min_length=1),
        limit: int = Query(default=100, ge=1, le=200),
        actor_id: str = Query(default="connector-credential-lease-reader", min_length=1),
    ) -> ManufacturingConnectorCredentialLeaseRegistry:
        return read_connector_credential_lease_registry(
            repository,
            ConnectorCredentialLeaseQuery(
                tenant_id=tenant_id,
                connector_id=connector_id,
                handle_id=handle_id,
                status=status,
                limit=limit,
            ),
            actor_id=actor_id,
        )

    @app.post(
        "/demo/manufacturing/connectors/credential-leases",
        response_model=ConnectorCredentialLeaseRecord,
        responses={
            403: {"description": "Connector credential lease permission denied"},
            404: {"description": "Connector registry reference record not found"},
            409: {"description": "Connector credential lease already exists"},
            422: {"description": "Connector credential lease validation failed"},
        },
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_connector_credential_lease_create(
        lease_request: ConnectorCredentialLeaseRequest,
        repository: PersistenceRepository,
        lease_runtime: CredentialLeaseRuntimeDependency,
    ) -> ConnectorCredentialLeaseRecord:
        try:
            return record_demo_connector_credential_lease(
                repository,
                lease_request,
                lease_runtime,
            )
        except ConnectorReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing connector registry reference record not found.",
                    "surface": "connectors",
                },
            ) from exc
        except ConnectorReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing connector registry reference payload is invalid.",
                    "surface": "connectors",
                },
            ) from exc
        except ConnectorCredentialLeasePermissionDenied as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot request connector credential leases.",
                    "required_permission": exc.required_permission,
                    "reason": "missing_required_scope",
                    "permission_reason": exc.decision.reason,
                },
            ) from exc
        except ConnectorCredentialLeaseConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": AxisErrorCode.POLICY_VIOLATION.value,
                    "message": "The connector credential lease already exists.",
                    "reason": "credential_lease_already_exists",
                    "lease_id": exc.lease_id,
                },
            ) from exc
        except ConnectorCredentialLeaseValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

    @app.post(
        "/demo/manufacturing/connectors/credential-leases/{lease_id}/renew",
        response_model=ConnectorCredentialLeaseRecord,
        responses={
            403: {"description": "Connector credential lease permission denied"},
            422: {"description": "Connector credential lease renewal validation failed"},
        },
        tags=["demo"],
    )
    def manufacturing_connector_credential_lease_renew(
        lease_id: str,
        renew_request: ConnectorCredentialLeaseRenewRequest,
        repository: PersistenceRepository,
        lease_runtime: CredentialLeaseRuntimeDependency,
    ) -> ConnectorCredentialLeaseRecord:
        try:
            return renew_demo_connector_credential_lease(
                repository,
                lease_id,
                renew_request,
                lease_runtime,
            )
        except ConnectorCredentialLeasePermissionDenied as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot renew connector credential leases.",
                    "required_permission": exc.required_permission,
                    "reason": "missing_required_scope",
                    "permission_reason": exc.decision.reason,
                },
            ) from exc
        except ConnectorCredentialLeaseValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

    @app.post(
        "/demo/manufacturing/connectors/credential-leases/{lease_id}/revoke",
        response_model=ConnectorCredentialLeaseRecord,
        responses={
            403: {"description": "Connector credential lease permission denied"},
            422: {"description": "Connector credential lease revocation validation failed"},
        },
        tags=["demo"],
    )
    def manufacturing_connector_credential_lease_revoke(
        lease_id: str,
        revoke_request: ConnectorCredentialLeaseRevokeRequest,
        repository: PersistenceRepository,
        lease_runtime: CredentialLeaseRuntimeDependency,
    ) -> ConnectorCredentialLeaseRecord:
        try:
            return revoke_demo_connector_credential_lease(
                repository,
                lease_id,
                revoke_request,
                lease_runtime,
            )
        except ConnectorCredentialLeasePermissionDenied as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot revoke connector credential leases.",
                    "required_permission": exc.required_permission,
                    "reason": "missing_required_scope",
                    "permission_reason": exc.decision.reason,
                },
            ) from exc
        except ConnectorCredentialLeaseValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

    @app.get(
        "/demo/manufacturing/connectors/egress-policies",
        response_model=ManufacturingConnectorEgressPolicyRegistry,
        tags=["demo"],
    )
    def manufacturing_connector_egress_policies(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
        connector_id: str | None = Query(default=None, min_length=1),
        status: str | None = Query(default=None, min_length=1),
        limit: int = Query(default=100, ge=1, le=200),
    ) -> ManufacturingConnectorEgressPolicyRegistry:
        return build_connector_egress_policy_registry(
            repository,
            ConnectorEgressPolicyQuery(
                tenant_id=tenant_id,
                connector_id=connector_id,
                status=status,
                limit=limit,
            ),
        )

    @app.post(
        "/demo/manufacturing/connectors/egress-policies",
        response_model=ConnectorEgressPolicyRecord,
        responses={422: {"description": "Connector egress policy validation failed"}},
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_connector_egress_policy_create(
        egress_policy: ConnectorEgressPolicyCreateRequest,
        repository: PersistenceRepository,
    ) -> ConnectorEgressPolicyRecord:
        try:
            return record_demo_connector_egress_policy(repository, egress_policy)
        except ConnectorEgressPolicyValidationError as exc:
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
        responses={
            404: {"description": "Connector registry reference record not found"},
            422: {"description": "Connector run or registry validation failed"},
        },
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_connector_run_create(
        connector_run: ConnectorRunCreateRequest,
        repository: PersistenceRepository,
        execution_runtime: ConnectorExecutionRuntimeDependency,
        sync_scheduler_runtime: ConnectorSyncSchedulerRuntimeDependency,
    ) -> ConnectorRunRecord:
        try:
            return record_demo_connector_run(
                repository,
                connector_run,
                execution_runtime,
                sync_scheduler_runtime,
            )
        except ConnectorReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing connector registry reference record not found.",
                    "surface": "connectors",
                },
            ) from exc
        except ConnectorReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing connector registry reference payload is invalid.",
                    "surface": "connectors",
                },
            ) from exc
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
        "/demo/manufacturing/connectors/runs/checkpoints",
        response_model=ManufacturingConnectorSyncCheckpointRegistry,
        responses={
            403: {"description": "Connector sync checkpoint read permission denied"},
            422: {"description": "Connector sync checkpoint query validation failed"},
        },
        tags=["demo"],
    )
    def manufacturing_connector_run_checkpoints(
        repository: PersistenceRepository,
        principal: OidcPrincipalDependency,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
        connector_id: str | None = Query(default=None, min_length=1),
        run_id: str | None = Query(default=None, min_length=1),
        status: str | None = Query(default=None, min_length=1),
        created_after: datetime | None = CheckpointCreatedAfterQuery,
        created_before: datetime | None = CheckpointCreatedBeforeQuery,
        actor_scopes: list[str] = CheckpointActorScopesQuery,
        limit: int = Query(default=100, ge=1, le=200),
    ) -> ManufacturingConnectorSyncCheckpointRegistry:
        _authorize_connector_sync_checkpoint_read(tenant_id, actor_scopes, principal)
        try:
            return read_connector_sync_checkpoint_registry(
                repository,
                ConnectorSyncCheckpointQuery(
                    tenant_id=tenant_id,
                    connector_id=connector_id,
                    run_id=run_id,
                    status=status,
                    created_after=created_after,
                    created_before=created_before,
                    limit=limit,
                ),
                actor_id=(
                    principal.actor_id
                    if principal is not None
                    else "connector-sync-checkpoint-reader"
                ),
                read_scope_source=(
                    "oidc_principal" if principal is not None else "demo_actor_scopes"
                ),
            )
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
        "/demo/manufacturing/connectors/runs/checkpoints/claims",
        response_model=ManufacturingConnectorSyncCheckpointClaimRegistry,
        responses={
            403: {"description": "Connector sync checkpoint claim read permission denied"},
            422: {"description": "Connector sync checkpoint claim query validation failed"},
        },
        tags=["demo"],
    )
    def manufacturing_connector_run_checkpoint_claims(
        repository: PersistenceRepository,
        principal: OidcPrincipalDependency,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
        checkpoint_id: str | None = Query(default=None, min_length=1),
        connector_id: str | None = Query(default=None, min_length=1),
        run_id: str | None = Query(default=None, min_length=1),
        status: str | None = Query(default=None, min_length=1),
        claimed_by: str | None = Query(default=None, min_length=1),
        created_after: datetime | None = CheckpointCreatedAfterQuery,
        created_before: datetime | None = CheckpointCreatedBeforeQuery,
        cursor: str | None = Query(default=None, min_length=1, max_length=600),
        actor_scopes: list[str] = CheckpointActorScopesQuery,
        limit: int = Query(default=100, ge=1, le=200),
    ) -> ManufacturingConnectorSyncCheckpointClaimRegistry:
        _authorize_connector_sync_checkpoint_claim_read(
            tenant_id,
            actor_scopes,
            principal,
        )
        try:
            return read_connector_sync_checkpoint_claim_registry(
                repository,
                ConnectorSyncCheckpointClaimQuery(
                    tenant_id=tenant_id,
                    checkpoint_id=checkpoint_id,
                    connector_id=connector_id,
                    run_id=run_id,
                    status=status,
                    claimed_by=claimed_by,
                    created_after=created_after,
                    created_before=created_before,
                    cursor=cursor,
                    limit=limit,
                ),
                actor_id=(
                    principal.actor_id
                    if principal is not None
                    else "connector-sync-checkpoint-claim-reader"
                ),
                read_scope_source=(
                    "oidc_principal" if principal is not None else "demo_actor_scopes"
                ),
            )
        except ConnectorRunValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

    @app.post(
        "/demo/manufacturing/connectors/runs/checkpoints/{checkpoint_id}/claims",
        response_model=ConnectorSyncCheckpointClaimRecord,
        status_code=status.HTTP_201_CREATED,
        responses={
            403: {"description": "Connector sync checkpoint claim permission denied"},
            404: {"description": "Connector sync checkpoint not found"},
            409: {"description": "Connector sync checkpoint claim conflict"},
            422: {"description": "Connector sync checkpoint claim validation failed"},
        },
        tags=["demo"],
    )
    def manufacturing_connector_run_checkpoint_claim(
        checkpoint_id: str,
        claim_request: ConnectorSyncCheckpointClaimRequest,
        repository: PersistenceRepository,
        response: Response,
    ) -> ConnectorSyncCheckpointClaimRecord:
        try:
            claim, created = claim_connector_sync_checkpoint(
                repository,
                checkpoint_id,
                claim_request,
            )
            if not created:
                response.status_code = status.HTTP_200_OK
            return claim
        except ConnectorRunPermissionDenied as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot claim connector sync checkpoints.",
                    "required_permission": exc.required_permission,
                    "reason": "missing_required_scope",
                },
            ) from exc
        except ConnectorRunNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "The connector sync checkpoint was not found.",
                    "reason": "connector_sync_checkpoint_not_found",
                },
            ) from exc
        except ConnectorSyncCheckpointClaimConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": AxisErrorCode.CONFLICT.value,
                    "message": (
                        "The connector sync checkpoint claim conflicts with "
                        "existing evidence."
                    ),
                    "reason": exc.reason,
                    "active_claim_id": exc.active_claim_id,
                },
            ) from exc
        except ConnectorRunValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

    @app.post(
        "/demo/manufacturing/connectors/runs/checkpoints/{checkpoint_id}/claims/{claim_id}/renew",
        response_model=ConnectorSyncCheckpointClaimRecord,
        responses={
            403: {"description": "Connector sync checkpoint claim renew permission denied"},
            404: {"description": "Connector sync checkpoint claim not found"},
            422: {"description": "Connector sync checkpoint claim renew validation failed"},
        },
        tags=["demo"],
    )
    def manufacturing_connector_run_checkpoint_claim_renew(
        checkpoint_id: str,
        claim_id: str,
        renew_request: ConnectorSyncCheckpointClaimRenewRequest,
        repository: PersistenceRepository,
    ) -> ConnectorSyncCheckpointClaimRecord:
        try:
            return renew_connector_sync_checkpoint_claim(
                repository,
                checkpoint_id,
                claim_id,
                renew_request,
            )
        except ConnectorRunPermissionDenied as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot renew connector sync checkpoint claims.",
                    "required_permission": exc.required_permission,
                    "reason": "missing_required_scope",
                },
            ) from exc
        except ConnectorRunNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "The connector sync checkpoint claim was not found.",
                    "reason": "connector_sync_checkpoint_claim_not_found",
                },
            ) from exc
        except ConnectorRunValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

    @app.post(
        "/demo/manufacturing/connectors/runs/checkpoints/{checkpoint_id}/claims/{claim_id}/release",
        response_model=ConnectorSyncCheckpointClaimRecord,
        responses={
            403: {"description": "Connector sync checkpoint claim release permission denied"},
            404: {"description": "Connector sync checkpoint claim not found"},
            422: {"description": "Connector sync checkpoint claim release validation failed"},
        },
        tags=["demo"],
    )
    def manufacturing_connector_run_checkpoint_claim_release(
        checkpoint_id: str,
        claim_id: str,
        release_request: ConnectorSyncCheckpointClaimReleaseRequest,
        repository: PersistenceRepository,
    ) -> ConnectorSyncCheckpointClaimRecord:
        try:
            return release_connector_sync_checkpoint_claim(
                repository,
                checkpoint_id,
                claim_id,
                release_request,
            )
        except ConnectorRunPermissionDenied as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot release connector sync checkpoint claims.",
                    "required_permission": exc.required_permission,
                    "reason": "missing_required_scope",
                },
            ) from exc
        except ConnectorRunNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "The connector sync checkpoint claim was not found.",
                    "reason": "connector_sync_checkpoint_claim_not_found",
                },
            ) from exc
        except ConnectorRunValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

    @app.post(
        "/demo/manufacturing/connectors/runs/{run_id}/dispatch",
        response_model=ConnectorRunRecord,
        responses={
            403: {"description": "Connector sync dispatch permission denied"},
            404: {"description": "Connector run not found"},
            409: {"description": "Connector sync dispatch idempotency conflict"},
            422: {"description": "Connector sync dispatch validation failed"},
        },
        tags=["demo"],
    )
    def manufacturing_connector_run_dispatch(
        run_id: str,
        dispatch_request: ConnectorRunDispatchRequest,
        repository: PersistenceRepository,
        sync_dispatch_runtime: ConnectorSyncDispatchRuntimeDependency,
    ) -> ConnectorRunRecord:
        try:
            return dispatch_demo_connector_sync(
                repository,
                run_id,
                dispatch_request,
                sync_dispatch_runtime,
            )
        except ConnectorRunPermissionDenied as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot dispatch scheduled connector sync.",
                    "required_permission": exc.required_permission,
                    "reason": "missing_required_scope",
                },
            ) from exc
        except ConnectorRunNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "The connector run was not found.",
                    "reason": "connector_run_not_found",
                },
            ) from exc
        except ConnectorRunDispatchConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": AxisErrorCode.CONFLICT.value,
                    "message": "The connector sync dispatch conflicts with existing evidence.",
                    "reason": exc.reason,
                },
            ) from exc
        except ConnectorRunValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": exc.message,
                    "reason": exc.reason,
                },
            ) from exc

    @app.post(
        "/demo/manufacturing/connectors/runs/{run_id}/execute-sync",
        response_model=ConnectorRunRecord,
        responses={
            403: {"description": "Connector sync execution permission denied"},
            404: {"description": "Connector run not found"},
            409: {"description": "Connector sync execution idempotency conflict"},
            422: {"description": "Connector sync execution validation failed"},
        },
        tags=["demo"],
    )
    def manufacturing_connector_run_execute_sync(
        run_id: str,
        execution_request: ConnectorRunSyncExecutionRequest,
        repository: PersistenceRepository,
        sync_execution_runtime: ConnectorSyncExecutionRuntimeDependency,
    ) -> ConnectorRunRecord:
        try:
            return execute_demo_connector_sync(
                repository,
                run_id,
                execution_request,
                sync_execution_runtime,
            )
        except ConnectorRunPermissionDenied as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot execute scheduled connector sync.",
                    "required_permission": exc.required_permission,
                    "reason": "missing_required_scope",
                },
            ) from exc
        except ConnectorRunNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "The connector run was not found.",
                    "reason": "connector_run_not_found",
                },
            ) from exc
        except ConnectorRunSyncExecutionConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": AxisErrorCode.CONFLICT.value,
                    "message": "The connector sync execution conflicts with existing evidence.",
                    "reason": exc.reason,
                },
            ) from exc
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
        responses={
            404: {"description": "Connector registry reference record not found"},
            422: {"description": "Connector ontology proposal or registry validation failed"},
        },
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_connector_ontology_proposal_create(
        proposal_request: ConnectorOntologyProposalCreateRequest,
        repository: PersistenceRepository,
    ) -> ManufacturingConnectorOntologyProposalRegistry:
        try:
            return record_demo_connector_ontology_proposals(repository, proposal_request)
        except ConnectorReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing connector registry reference record not found.",
                    "surface": "connectors",
                },
            ) from exc
        except ConnectorReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing connector registry reference payload is invalid.",
                    "surface": "connectors",
                },
            ) from exc
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
        except ConnectorReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing connector registry reference record not found.",
                    "surface": "connectors",
                },
            ) from exc
        except ConnectorReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing connector registry reference payload is invalid.",
                    "surface": "connectors",
                },
            ) from exc
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
            404: {"description": "Connector registry reference record not found"},
            409: {"description": "Connector promotion policy already exists"},
            422: {"description": "Connector promotion policy or registry validation failed"},
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
        except ConnectorReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing connector registry reference record not found.",
                    "surface": "connectors",
                },
            ) from exc
        except ConnectorReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing connector registry reference payload is invalid.",
                    "surface": "connectors",
                },
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
            404: {"description": "Connector promotion policy or registry reference not found"},
            422: {"description": "Connector promotion policy enable or registry validation failed"},
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
        except ConnectorReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing connector registry reference record not found.",
                    "surface": "connectors",
                },
            ) from exc
        except ConnectorReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing connector registry reference payload is invalid.",
                    "surface": "connectors",
                },
            ) from exc
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
            404: {"description": "Connector promotion policy or registry reference not found"},
            409: {"description": "Connector promotion policy revision conflict"},
            422: {
                "description": (
                    "Connector promotion policy revision or registry validation failed"
                )
            },
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
        except ConnectorReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing connector registry reference record not found.",
                    "surface": "connectors",
                },
            ) from exc
        except ConnectorReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing connector registry reference payload is invalid.",
                    "surface": "connectors",
                },
            ) from exc
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
            404: {"description": "Connector registry reference record not found"},
            409: {"description": "Connector promotion policy set already exists or active"},
            422: {"description": "Connector promotion policy set or registry validation failed"},
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
        except ConnectorReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing connector registry reference record not found.",
                    "surface": "connectors",
                },
            ) from exc
        except ConnectorReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing connector registry reference payload is invalid.",
                    "surface": "connectors",
                },
            ) from exc
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
            404: {"description": "Connector registry reference record not found"},
            409: {"description": "Connector manual import idempotency conflict"},
            422: {"description": "Connector manual import or registry validation failed"},
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
        except ConnectorReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing connector registry reference record not found.",
                    "surface": "connectors",
                },
            ) from exc
        except ConnectorReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing connector registry reference payload is invalid.",
                    "surface": "connectors",
                },
            ) from exc
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
        responses={
            404: {"description": "Connector registry reference record not found"},
            422: {"description": "Connector registry reference payload invalid"},
        },
        tags=["demo"],
    )
    def manufacturing_file_csv_connector_preview(
        preview_request: ConnectorCsvPreviewRequest,
        repository: PersistenceRepository,
    ) -> ConnectorCsvPreviewResult:
        try:
            registry = get_persisted_manufacturing_connector_registry(
                repository,
                tenant_id=preview_request.tenant_id,
            )
            return preview_file_csv_connector(registry, preview_request)
        except ConnectorReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing connector registry reference record not found.",
                    "surface": "connectors",
                },
            ) from exc
        except ConnectorReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing connector registry reference payload is invalid.",
                    "surface": "connectors",
                },
            ) from exc

    @app.post(
        "/demo/manufacturing/connectors/external-db/preview",
        response_model=ConnectorExternalDbPreviewResult,
        responses={
            404: {"description": "Connector registry reference record not found"},
            422: {"description": "Connector registry reference payload invalid"},
        },
        tags=["demo"],
    )
    def manufacturing_external_db_connector_preview(
        preview_request: ConnectorExternalDbPreviewRequest,
        repository: PersistenceRepository,
    ) -> ConnectorExternalDbPreviewResult:
        try:
            registry = get_persisted_manufacturing_connector_registry(
                repository,
                tenant_id=preview_request.tenant_id,
            )
            return preview_external_db_connector(registry, preview_request)
        except ConnectorReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing connector registry reference record not found.",
                    "surface": "connectors",
                },
            ) from exc
        except ConnectorReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing connector registry reference payload is invalid.",
                    "surface": "connectors",
                },
            ) from exc

    @app.post(
        "/demo/manufacturing/actions/{action_id}/runs",
        response_model=ActionRunPersistenceResult,
        responses={
            404: {
                "description": (
                    "Action, action registry reference, or ontology reference record not found"
                )
            },
            403: {"description": "Action run permission denied"},
            409: {"description": "Action run idempotency conflict"},
            422: {
                "description": (
                    "Action payload, action registry reference, or ontology reference invalid"
                )
            },
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
        except ActionReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing action registry reference record not found.",
                    "surface": "actions",
                },
            ) from exc
        except ActionReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing action registry reference payload is invalid.",
                    "surface": "actions",
                },
            ) from exc
        except OntologyReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing ontology reference record not found.",
                    "surface": "ontology",
                },
            ) from exc
        except OntologyReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing ontology reference payload is invalid.",
                    "surface": "ontology",
                },
            ) from exc
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
        responses={
            404: {"description": "Approval inbox reference record not found"},
            422: {"description": "Approval inbox reference payload invalid"},
        },
        tags=["demo"],
    )
    def manufacturing_approval_inbox(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
    ) -> ManufacturingApprovalInbox:
        try:
            return get_persisted_manufacturing_approval_inbox(
                repository,
                tenant_id=tenant_id,
            )
        except ApprovalReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing approval inbox reference record not found.",
                    "tenant_id": tenant_id,
                    "surface": "approvals",
                },
            ) from exc
        except ApprovalReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing approval inbox reference payload is invalid.",
                    "tenant_id": tenant_id,
                    "surface": "approvals",
                },
            ) from exc

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
        except ApprovalReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing approval inbox reference record not found.",
                    "surface": "approvals",
                },
            ) from exc
        except ApprovalReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing approval inbox reference payload is invalid.",
                    "surface": "approvals",
                },
            ) from exc
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
        responses={
            404: {"description": "Audit explorer reference record not found"},
            422: {"description": "Audit explorer reference payload invalid"},
        },
        tags=["demo"],
    )
    def manufacturing_audit_explorer(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
    ) -> ManufacturingAuditExplorer:
        try:
            return get_persisted_manufacturing_audit_explorer(
                repository,
                tenant_id=tenant_id,
            )
        except AuditReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing audit explorer reference record not found.",
                    "tenant_id": tenant_id,
                    "surface": "audit",
                },
            ) from exc
        except AuditReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing audit explorer reference payload is invalid.",
                    "tenant_id": tenant_id,
                    "surface": "audit",
                },
            ) from exc

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
            ledger_signer=_audit_ledger_signer_from_settings(app.state.settings),
        )

    @app.post(
        "/demo/manufacturing/audit/retention/delete",
        response_model=AuditRetentionDeletionResult,
        responses={403: {"description": "Audit retention deletion permission denied"}},
        tags=["demo"],
    )
    def manufacturing_audit_retention_delete(
        deletion_request: AuditRetentionDeletionRequest,
        repository: PersistenceRepository,
    ) -> AuditRetentionDeletionResult:
        try:
            return execute_audit_retention_deletion(repository, deletion_request)
        except AuditRetentionDeletionPermissionDenied as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot execute audit retention deletion.",
                    "required_permissions": ["audit:retention:delete"],
                    "reason": exc.decision.reason,
                },
            ) from exc

    @app.get(
        "/demo/manufacturing/audit/legal-holds",
        response_model=list[AuditLegalHoldRecord],
        tags=["demo"],
    )
    def manufacturing_audit_legal_holds(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
    ) -> list[AuditLegalHoldRecord]:
        return list_audit_legal_holds(repository, tenant_id)

    @app.post(
        "/demo/manufacturing/audit/legal-holds",
        response_model=AuditLegalHoldRecord,
        responses={
            403: {"description": "Audit legal hold permission denied"},
            409: {"description": "Audit legal hold already active"},
        },
        status_code=status.HTTP_201_CREATED,
        tags=["demo"],
    )
    def manufacturing_audit_legal_hold_create(
        legal_hold_request: AuditLegalHoldCreateRequest,
        repository: PersistenceRepository,
    ) -> AuditLegalHoldRecord:
        try:
            return create_audit_legal_hold(repository, legal_hold_request)
        except AuditLegalHoldPermissionDenied as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot manage audit legal holds.",
                    "required_permissions": ["audit:legal_hold:write"],
                    "reason": exc.decision.reason,
                },
            ) from exc
        except AuditLegalHoldConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": AxisErrorCode.POLICY_VIOLATION.value,
                    "message": "The audit legal hold conflicts with existing state.",
                    "hold_id": exc.hold_id,
                    "reason": exc.reason,
                },
            ) from exc

    @app.post(
        "/demo/manufacturing/audit/legal-holds/{hold_id}/release",
        response_model=AuditLegalHoldRecord,
        responses={
            403: {"description": "Audit legal hold permission denied"},
            404: {"description": "Audit legal hold not found"},
            409: {"description": "Audit legal hold is not active"},
        },
        tags=["demo"],
    )
    def manufacturing_audit_legal_hold_release(
        hold_id: str,
        release_request: AuditLegalHoldReleaseRequest,
        repository: PersistenceRepository,
    ) -> AuditLegalHoldRecord:
        if release_request.hold_id != hold_id:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Path hold_id must match request hold_id.",
                },
            )
        try:
            return release_audit_legal_hold(repository, release_request)
        except AuditLegalHoldPermissionDenied as exc:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot manage audit legal holds.",
                    "required_permissions": ["audit:legal_hold:write"],
                    "reason": exc.decision.reason,
                },
            ) from exc
        except AuditLegalHoldNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Audit legal hold record not found.",
                    "hold_id": hold_id,
                },
            ) from exc
        except AuditLegalHoldConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": AxisErrorCode.POLICY_VIOLATION.value,
                    "message": "The audit legal hold conflicts with existing state.",
                    "hold_id": exc.hold_id,
                    "reason": exc.reason,
                },
            ) from exc

    @app.get(
        "/demo/manufacturing/model-routing",
        response_model=ManufacturingModelRouting,
        responses={
            404: {"description": "Model routing reference record not found"},
            422: {"description": "Model routing reference payload invalid"},
        },
        tags=["demo"],
    )
    def manufacturing_model_routing(
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
    ) -> ManufacturingModelRouting:
        try:
            return get_persisted_manufacturing_model_routing(
                repository,
                tenant_id=tenant_id,
            )
        except ModelRoutingReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing model routing reference record not found.",
                    "tenant_id": tenant_id,
                    "surface": "model-routing",
                },
            ) from exc
        except ModelRoutingReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing model routing reference payload is invalid.",
                    "tenant_id": tenant_id,
                    "surface": "model-routing",
                },
            ) from exc

    @app.get(
        "/demo/manufacturing/ontology",
        response_model=ManufacturingOntology,
        responses={
            404: {"description": "Manufacturing ontology reference record not found"},
            422: {"description": "Manufacturing ontology reference payload invalid"},
        },
        tags=["demo"],
    )
    def manufacturing_ontology(
        principal: OidcPrincipalDependency,
        repository: PersistenceRepository,
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

        try:
            ontology = get_persisted_manufacturing_ontology(repository, tenant_id=tenant_id)
        except OntologyReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing ontology reference record not found.",
                    "tenant_id": tenant_id,
                    "surface": "ontology",
                },
            ) from exc
        except OntologyReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing ontology reference payload is invalid.",
                    "tenant_id": tenant_id,
                    "surface": "ontology",
                },
            ) from exc

        return query_manufacturing_ontology_graph(
            ontology_query_runtime,
            OntologyGraphQueryRequest(
                tenant_id=tenant_id,
                actor_id=principal.actor_id if principal is not None else "public-demo-reader",
                actor_scopes=principal.scopes if principal is not None else [],
                enforce_relationship_scopes=principal is not None,
                limit=limit,
            ),
            ontology,
        )

    @app.get(
        "/demo/manufacturing/ontology/entities/{node_id}",
        response_model=ManufacturingOntologyEntityDetail,
        responses={
            404: {"description": "Manufacturing ontology entity or reference record not found"},
            422: {"description": "Manufacturing ontology reference payload invalid"},
        },
        tags=["demo"],
    )
    def manufacturing_ontology_entity_detail(
        node_id: str,
        principal: OidcPrincipalDependency,
        repository: PersistenceRepository,
        tenant_id: str = Query(default="tenant_demo_manufacturing", min_length=1),
    ) -> ManufacturingOntologyEntityDetail:
        if principal is not None and principal.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": AxisErrorCode.PERMISSION_DENIED.value,
                    "message": "The actor cannot read ontology entity data for this tenant.",
                    "reason": "tenant_mismatch",
                },
            )

        try:
            detail = get_persisted_manufacturing_ontology_entity_detail(
                repository,
                node_id,
                tenant_id=tenant_id,
            )
        except OntologyReferenceRecordNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": AxisErrorCode.NOT_FOUND.value,
                    "message": "Manufacturing ontology reference record not found.",
                    "tenant_id": tenant_id,
                    "surface": "ontology",
                },
            ) from exc
        except OntologyReferenceRecordInvalid as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": AxisErrorCode.VALIDATION_FAILED.value,
                    "message": "Manufacturing ontology reference payload is invalid.",
                    "tenant_id": tenant_id,
                    "surface": "ontology",
                },
            ) from exc
        if detail is None:
            raise HTTPException(status_code=404, detail="Ontology entity not found")
        _authorize_demo_ontology_detail(detail, principal)
        return detail

    return app


app = create_app()
