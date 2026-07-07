"""OIDC-principal binding tests for the connector-run route family.

These mirror the audit/ontology/policy OIDC-binding tests (PR #240 and
follow-ups). They assert that the connector-run mutation routes derive the
tenant/actor/scopes from the verified OIDC principal instead of trusting the
request body, closing the self-asserted scope/tenant/actor impersonation gap
while preserving the ``AXIS_OIDC_AUTH_REQUIRED`` demo-mode convention.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.config import Settings
from axis_api.identity import OidcPrincipal
from axis_api.main import create_app
from axis_api.models import Base

TENANT = "tenant_demo_manufacturing"
OTHER_TENANT = "tenant_other"
ACTOR = "connector-sync-operator"
AUTH_HEADERS = {"Authorization": "Bearer valid-token"}


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


# Each entry describes one connector-run mutation route: the concrete request
# path, the body actor field that must be bound to the principal, the scope the
# service enforces (``None`` for the create route, which carries no scope), and
# the remaining required body fields.
ROUTES = [
    {
        "id": "create_run",
        "path": "/demo/manufacturing/connectors/runs",
        "actor_field": "requested_by",
        "required_scope": None,
        "extra": {
            "run_id": "run_oidc_binding",
            "connector_id": "file_csv_manufacturing_assets",
        },
    },
    {
        "id": "claim_checkpoint",
        "path": "/demo/manufacturing/connectors/runs/checkpoints/cp_oidc_binding/claims",
        "actor_field": "claimed_by",
        "required_scope": "connectors:sync:checkpoint:claim",
        "extra": {
            "claim_id": "claim_oidc_binding",
            "idempotency_key": "idem_oidc_binding",
        },
    },
    {
        "id": "renew_claim",
        "path": (
            "/demo/manufacturing/connectors/runs/checkpoints/cp_oidc_binding/"
            "claims/claim_oidc_binding/renew"
        ),
        "actor_field": "renewed_by",
        "required_scope": "connectors:sync:checkpoint:claim:renew",
        "extra": {"renewal_reason": "oidc-binding-test"},
    },
    {
        "id": "release_claim",
        "path": (
            "/demo/manufacturing/connectors/runs/checkpoints/cp_oidc_binding/"
            "claims/claim_oidc_binding/release"
        ),
        "actor_field": "released_by",
        "required_scope": "connectors:sync:checkpoint:claim:release",
        "extra": {"release_reason": "oidc-binding-test"},
    },
    {
        "id": "dispatch_run",
        "path": "/demo/manufacturing/connectors/runs/run_oidc_binding/dispatch",
        "actor_field": "dispatched_by",
        "required_scope": "connectors:sync:dispatch",
        "extra": {
            "dispatch_id": "dispatch_oidc_binding",
            "credential_lease_id": "lease_oidc_binding",
            "idempotency_key": "idem_oidc_binding",
        },
    },
    {
        "id": "execute_sync",
        "path": "/demo/manufacturing/connectors/runs/run_oidc_binding/execute-sync",
        "actor_field": "executed_by",
        "required_scope": "connectors:sync:execute",
        "extra": {
            "execution_id": "exec_oidc_binding",
            "credential_lease_id": "lease_oidc_binding",
            "idempotency_key": "idem_oidc_binding",
        },
    },
]

ROUTE_IDS = [route["id"] for route in ROUTES]
SCOPE_ROUTES = [route for route in ROUTES if route["required_scope"] is not None]
SCOPE_ROUTE_IDS = [route["id"] for route in SCOPE_ROUTES]


def _make_client(
    session_factory: sessionmaker[Session],
    *,
    oidc_auth_required: bool = False,
    principal: OidcPrincipal | None = None,
) -> TestClient:
    app = create_app(
        Settings(postgres_dsn="sqlite+pysqlite://", oidc_auth_required=oidc_auth_required)
    )
    app.state.session_factory = session_factory
    if principal is not None:
        app.state.identity_verifier = StaticIdentityVerifier(principal)
    return TestClient(app)


def _body(
    route: dict,
    *,
    actor_id: str,
    tenant: str = TENANT,
    scopes: list[str] | None = None,
) -> dict:
    body = {"tenant_id": tenant, route["actor_field"]: actor_id, **route["extra"]}
    if route["required_scope"] is not None:
        body["actor_scopes"] = list(scopes or [])
    return body


def _self_asserted_scopes(route: dict) -> list[str] | None:
    if route["required_scope"] is None:
        return None
    return [route["required_scope"]]


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
def test_connector_run_route_requires_oidc_when_configured(
    session_factory: sessionmaker[Session], route: dict
) -> None:
    client = _make_client(session_factory, oidc_auth_required=True)

    response = client.post(
        route["path"],
        json=_body(route, actor_id=ACTOR, scopes=_self_asserted_scopes(route)),
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_REQUIRED"


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
def test_connector_run_route_rejects_actor_impersonation(
    session_factory: sessionmaker[Session], route: dict
) -> None:
    principal = OidcPrincipal(
        actor_id=ACTOR,
        tenant_id=TENANT,
        scopes=_self_asserted_scopes(route) or [],
    )
    client = _make_client(session_factory, oidc_auth_required=True, principal=principal)

    response = client.post(
        route["path"],
        headers=AUTH_HEADERS,
        json=_body(
            route,
            actor_id="impersonated-other-actor",
            scopes=_self_asserted_scopes(route),
        ),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "actor_mismatch"


@pytest.mark.parametrize("route", ROUTES, ids=ROUTE_IDS)
def test_connector_run_route_rejects_cross_tenant(
    session_factory: sessionmaker[Session], route: dict
) -> None:
    principal = OidcPrincipal(
        actor_id=ACTOR,
        tenant_id=TENANT,
        scopes=_self_asserted_scopes(route) or [],
    )
    client = _make_client(session_factory, oidc_auth_required=True, principal=principal)

    response = client.post(
        route["path"],
        headers=AUTH_HEADERS,
        json=_body(
            route,
            actor_id=ACTOR,
            tenant=OTHER_TENANT,
            scopes=_self_asserted_scopes(route),
        ),
    )

    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "tenant_mismatch"


@pytest.mark.parametrize("route", SCOPE_ROUTES, ids=SCOPE_ROUTE_IDS)
def test_connector_run_route_enforces_principal_scopes_over_body(
    session_factory: sessionmaker[Session], route: dict
) -> None:
    # The principal holds no scopes; the body self-asserts the required scope.
    # Binding must overwrite the body scopes with the principal's, so the
    # service rejects the request for the missing scope.
    principal = OidcPrincipal(actor_id=ACTOR, tenant_id=TENANT, scopes=[])
    client = _make_client(session_factory, oidc_auth_required=True, principal=principal)

    response = client.post(
        route["path"],
        headers=AUTH_HEADERS,
        json=_body(route, actor_id=ACTOR, scopes=[route["required_scope"]]),
    )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["reason"] == "missing_required_scope"
    assert detail["required_permission"] == route["required_scope"]


@pytest.mark.parametrize("route", SCOPE_ROUTES, ids=SCOPE_ROUTE_IDS)
def test_connector_run_route_authorized_principal_passes_scope_gate(
    session_factory: sessionmaker[Session], route: dict
) -> None:
    # The principal holds the required scope while the body self-asserts none.
    # Binding must supply the principal's scopes, so the request clears the
    # scope gate and only fails later because the resource is not seeded (404).
    principal = OidcPrincipal(actor_id=ACTOR, tenant_id=TENANT, scopes=[route["required_scope"]])
    client = _make_client(session_factory, oidc_auth_required=True, principal=principal)

    response = client.post(
        route["path"],
        headers=AUTH_HEADERS,
        json=_body(route, actor_id=ACTOR, scopes=[]),
    )

    assert response.status_code == 404


@pytest.mark.parametrize("route", SCOPE_ROUTES, ids=SCOPE_ROUTE_IDS)
def test_connector_run_route_demo_mode_preserves_self_asserted_scopes(
    session_factory: sessionmaker[Session], route: dict
) -> None:
    # With OIDC disabled (demo mode, principal=None) the body-supplied scopes
    # remain authoritative, matching the convention used across the demo surface.
    client = _make_client(session_factory, oidc_auth_required=False)

    allowed = client.post(
        route["path"],
        json=_body(route, actor_id=ACTOR, scopes=[route["required_scope"]]),
    )
    assert allowed.status_code == 404

    denied = client.post(
        route["path"],
        json=_body(route, actor_id=ACTOR, scopes=[]),
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["required_permission"] == route["required_scope"]
