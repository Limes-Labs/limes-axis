from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from axis_api.config import Settings
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
        "/demo/manufacturing/approvals",
        response_model=ManufacturingApprovalInbox,
        tags=["demo"],
    )
    def manufacturing_approval_inbox() -> ManufacturingApprovalInbox:
        return get_manufacturing_approval_inbox()

    @app.get(
        "/demo/manufacturing/audit",
        response_model=ManufacturingAuditExplorer,
        tags=["demo"],
    )
    def manufacturing_audit_explorer() -> ManufacturingAuditExplorer:
        return get_manufacturing_audit_explorer()

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
    ) -> ManufacturingOntologyEntityDetail:
        detail = get_manufacturing_ontology_entity_detail(node_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Ontology entity not found")
        return detail

    return app


app = create_app()
