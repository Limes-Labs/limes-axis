"""Per-operation scope gates on connector and data-asset governance writes.

Regression: these writes bound the verified principal's tenant/actor but never
checked a scope, so any authenticated member of a tenant could register or
replace manifests, record configurations, credential handles/rotations, egress
policies, ontology proposals, manual imports and data-asset stewardship or
contracts. Each write now requires its own scope; a principal without it gets
403 before the service layer runs, so no record or audit event is written.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.config import Settings
from axis_api.identity import OidcPrincipal
from axis_api.main import create_app
from axis_api.models import AuditEvent, Base

TENANT = "tenant_demo_manufacturing"
ACTOR = "tenant-member"
AUTH_HEADERS = {"Authorization": "Bearer valid-token"}
ASSET_ID = "source:cnc_assets:default"


class StaticIdentityVerifier:
    def __init__(self, principal: OidcPrincipal) -> None:
        self.principal = principal

    def verify_authorization_header(self, authorization: str | None) -> OidcPrincipal:
        assert authorization == "Bearer valid-token"
        return self.principal


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


MANIFEST = {
    "connector_id": "file_csv_scope_gate",
    "display_name": "Scope gate",
    "connector_type": "file_csv",
    "version": "2026-10-19",
    "source_type": "file",
    "sync_modes": ["schema_preview"],
    "runtime_boundary": "axis-connector-sandbox",
}

WRITES = [
    {
        "id": "manifest_create",
        "method": "post",
        "path": "/demo/manufacturing/connectors/manifests",
        "scope": "connectors:manifest:write",
        "body": {"tenant_id": TENANT, "registered_by": ACTOR, "manifest": MANIFEST},
    },
    {
        "id": "manifest_replace",
        "method": "put",
        "path": "/demo/manufacturing/connectors/manifests/file_csv_scope_gate",
        "scope": "connectors:manifest:write",
        "body": {
            "tenant_id": TENANT,
            "registered_by": ACTOR,
            "idempotency_key": "scope-gate-replace",
            "manifest": MANIFEST,
        },
    },
    {
        "id": "configuration_create",
        "method": "post",
        "path": "/demo/manufacturing/connectors/configurations",
        "scope": "connectors:configuration:write",
        "body": {"tenant_id": TENANT, "display_name": "Scope gate", "created_by": ACTOR},
    },
    {
        "id": "credential_handle_create",
        "method": "post",
        "path": "/demo/manufacturing/connectors/credential-handles",
        "scope": "connectors:credential_handle:write",
        "body": {
            "tenant_id": TENANT,
            "handle_id": "cred_scope_gate",
            "display_name": "Scope gate",
            "secret_provider": "external_vault",
            "secret_ref": "vault://axis/demo/connectors/scope-gate",
            "purpose": "preview_import_readonly",
            "created_by": ACTOR,
        },
    },
    {
        "id": "credential_rotation",
        "method": "post",
        "path": "/demo/manufacturing/connectors/credential-handles/cred_scope_gate/rotations",
        "scope": "connectors:credential_handle:write",
        "body": {"tenant_id": TENANT, "rotated_by": ACTOR, "evidence_ref": "test://rotation"},
    },
    {
        "id": "egress_policy_create",
        "method": "post",
        "path": "/demo/manufacturing/connectors/egress-policies",
        "scope": "connectors:egress_policy:write",
        "body": {
            "tenant_id": TENANT,
            "policy_id": "egress_scope_gate",
            "display_name": "Scope gate",
            "connection_profile_id": "profile_scope_gate",
            "egress_boundary": "private_endpoint",
            "policy_mode": "allowlist",
            "private_endpoint_ref": "private-endpoint://scope-gate",
            "created_by": ACTOR,
        },
    },
    {
        "id": "ontology_proposal_create",
        "method": "post",
        "path": "/demo/manufacturing/connectors/ontology-proposals",
        "scope": "connectors:ontology_proposal:write",
        "body": {
            "tenant_id": TENANT,
            "source_file_name": "assets.csv",
            "proposed_by": ACTOR,
            "proposed_entities": [
                {
                    "proposal_id": "proposal_scope_gate",
                    "node_id": "node_scope_gate",
                    "node_type": "asset",
                    "ontology_type": "manufacturing_asset",
                }
            ],
        },
    },
    {
        "id": "manual_import_create",
        "method": "post",
        "path": "/demo/manufacturing/connectors/manual-imports",
        "scope": "connectors:manual_import:write",
        "body": {
            "tenant_id": TENANT,
            "import_id": "import_scope_gate",
            "idempotency_key": "scope-gate-import",
            "requested_by": ACTOR,
            "owner_role": "plant-operations-owner-role",
            "risk_level": "medium",
            "approval_id": "approval_scope_gate",
            "workflow_id": "wf_scope_gate",
            "proposal_ids": ["proposal_scope_gate"],
        },
    },
    {
        "id": "data_asset_stewardship",
        "method": "put",
        "path": f"/data/assets/{ASSET_ID}/stewardship?tenant_id={TENANT}",
        "scope": "data:asset:stewardship:write",
        "body": {
            "owner": "plant-data-team",
            "classification": "internal",
            "residency": "eu",
            "retention": "P1Y",
            "idempotency_key": "scope-gate-stewardship",
        },
    },
    {
        "id": "data_asset_contract",
        "method": "put",
        "path": f"/data/assets/{ASSET_ID}/contract?tenant_id={TENANT}",
        "scope": "data:asset:contract:write",
        "body": {
            "expected_resource_name": "cnc_assets",
            "idempotency_key": "scope-gate-contract",
        },
    },
]
WRITE_IDS = [write["id"] for write in WRITES]


def _client(session_factory: sessionmaker[Session], scopes: list[str]) -> TestClient:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://", oidc_auth_required=True))
    app.state.session_factory = session_factory
    app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(actor_id=ACTOR, tenant_id=TENANT, scopes=scopes)
    )
    return TestClient(app)


def _audit_count(session_factory: sessionmaker[Session]) -> int:
    with session_factory() as session:
        return session.execute(select(func.count()).select_from(AuditEvent)).scalar_one()


@pytest.mark.parametrize("write", WRITES, ids=WRITE_IDS)
def test_governance_write_without_scope_is_denied_without_side_effect(
    session_factory: sessionmaker[Session], write: dict
) -> None:
    # The principal is a verified member of the tenant, self-asserting the
    # scope in the body where the model allows it; binding must not let that
    # body claim satisfy the gate.
    client = _client(session_factory, scopes=["openid", "connectors:read"])
    body = dict(write["body"])
    if write["path"].startswith("/demo/") and _accepts_actor_scopes(write):
        body["actor_scopes"] = [write["scope"]]

    response = getattr(client, write["method"])(
        write["path"], headers=AUTH_HEADERS, json=body
    )

    assert response.status_code == 403, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "PERMISSION_DENIED"
    assert detail["reason"] == "missing_required_scope"
    assert detail["required_permission"] == write["scope"]
    assert _audit_count(session_factory) == 0


@pytest.mark.parametrize("write", WRITES, ids=WRITE_IDS)
def test_governance_write_with_scope_clears_the_gate(
    session_factory: sessionmaker[Session], write: dict
) -> None:
    # With the scope, the request passes the gate and fails (or succeeds) on
    # its own merits; it is never the scope gate that answers.
    client = _client(session_factory, scopes=[write["scope"]])

    response = getattr(client, write["method"])(
        write["path"], headers=AUTH_HEADERS, json=write["body"]
    )

    if response.status_code == 403:
        assert response.json()["detail"].get("reason") != "missing_required_scope"


def _accepts_actor_scopes(write: dict) -> bool:
    from axis_api import (
        connector_configurations,
        connector_credential_handles,
        connector_egress_policies,
        connector_manifests,
        connector_manual_imports,
        connector_ontology_proposals,
    )

    models = {
        "manifest_create": connector_manifests.ConnectorManifestCreateRequest,
        "manifest_replace": connector_manifests.ConnectorManifestReplaceRequest,
        "configuration_create": connector_configurations.ConnectorConfigurationCreateRequest,
        "credential_handle_create": (
            connector_credential_handles.ConnectorCredentialHandleCreateRequest
        ),
        "credential_rotation": connector_credential_handles.ConnectorCredentialRotationRequest,
        "egress_policy_create": connector_egress_policies.ConnectorEgressPolicyCreateRequest,
        "ontology_proposal_create": (
            connector_ontology_proposals.ConnectorOntologyProposalCreateRequest
        ),
        "manual_import_create": connector_manual_imports.ConnectorManualImportCreateRequest,
    }
    return "actor_scopes" in models[write["id"]].model_fields
