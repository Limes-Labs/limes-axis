"""Connector read routes bind actor and scopes to the verified principal.

Regression: the evidence-invariant snapshot history read evaluated the query's
``actor_scopes`` even for a verified principal (so a scope-less member could
self-assert ``connectors:evidence:snapshot:read``), and the credential-lease,
egress-policy and evidence-invariant reads wrote the query's ``actor_id`` into
append-only read-audit evidence, letting a caller attribute reads to anyone.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.identity import OidcPrincipal
from axis_api.main import create_app
from axis_api.models import AuditEvent, Base
from axis_api.persistence import AxisPersistenceRepository, TenantCreate

TENANT = "tenant_demo_manufacturing"
ACTOR = "verified-reader"
SPOOFED = "spoofed-auditor"
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
    with session_scope(factory) as session:
        AxisPersistenceRepository(session).create_tenant(
            TenantCreate(
                tenant_id=TENANT,
                display_name="Ravenna Works",
                description="Plant Operations Cockpit",
                created_by="test",
            )
        )
    yield factory
    engine.dispose()


def _client(session_factory: sessionmaker[Session], scopes: list[str]) -> TestClient:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://", oidc_auth_required=True))
    app.state.session_factory = session_factory
    app.state.identity_verifier = StaticIdentityVerifier(
        OidcPrincipal(actor_id=ACTOR, tenant_id=TENANT, scopes=scopes)
    )
    return TestClient(app)


def test_snapshot_history_ignores_query_scopes_for_principal(
    session_factory: sessionmaker[Session],
) -> None:
    client = _client(session_factory, scopes=[])

    response = client.get(
        "/demo/manufacturing/connectors/evidence-invariants/snapshots",
        headers=AUTH_HEADERS,
        params={
            "tenant_id": TENANT,
            "actor_id": SPOOFED,
            "actor_scopes": ["connectors:evidence:snapshot:read"],
        },
    )

    assert response.status_code == 403
    with session_factory() as session:
        assert session.scalars(select(AuditEvent)).all() == []


def test_snapshot_history_uses_principal_actor_and_scopes(
    session_factory: sessionmaker[Session],
) -> None:
    client = _client(session_factory, scopes=["connectors:evidence:snapshot:read"])

    response = client.get(
        "/demo/manufacturing/connectors/evidence-invariants/snapshots",
        headers=AUTH_HEADERS,
        params={"tenant_id": TENANT, "actor_id": SPOOFED},
    )

    assert response.status_code == 200, response.text
    with session_factory() as session:
        actors = {event.actor_id for event in session.scalars(select(AuditEvent)).all()}
    assert SPOOFED not in actors


@pytest.mark.parametrize(
    "path",
    [
        "/demo/manufacturing/connectors/credential-leases",
        "/demo/manufacturing/connectors/egress-policies",
        "/demo/manufacturing/connectors/evidence-invariants",
    ],
)
def test_read_audit_evidence_records_principal_actor(
    session_factory: sessionmaker[Session], path: str
) -> None:
    client = _client(session_factory, scopes=[])

    response = client.get(
        path,
        headers=AUTH_HEADERS,
        params={"tenant_id": TENANT, "actor_id": SPOOFED},
    )

    assert response.status_code == 200, response.text
    with session_factory() as session:
        events = session.scalars(select(AuditEvent)).all()
    assert events, "read must append audit evidence"
    assert {event.actor_id for event in events} == {ACTOR}
