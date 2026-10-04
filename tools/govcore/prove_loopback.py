"""Explicit local HTTP acceptance; synthetic Axis tenant, no tenant DB or IdP."""

import hashlib
import json
import sys
from pathlib import Path
from time import time

import httpx
from axis_api.config import Settings
from axis_api.identity import OidcPrincipal
from axis_api.main import create_app
from axis_api.models import Base, Tenant
from axis_api.public_institutional_context import READ_SCOPE, PublicContextConfig
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ORIGIN = "http://127.0.0.1:8041"
ENTITY = "gov_5228b607e4a354b6aadefebabd85f1d1"  # Cassano all'Ionio, ISTAT 078029
TENANT = "synthetic-loopback-axis"


class SyntheticVerifier:
    def verify_authorization_header(self, authorization):
        if authorization != "Bearer synthetic-loopback":
            raise AssertionError("Only synthetic acceptance identity is permitted")
        return OidcPrincipal(
            tenant_id=TENANT,
            actor_id="synthetic-reader",
            scopes=[READ_SCOPE],
            expires_at=int(time()) + 600,
        )


class CapturingLocalTransport(httpx.BaseTransport):
    def __init__(self):
        self.requests = []
        self.inner = httpx.HTTPTransport(trust_env=False)

    def handle_request(self, request):
        assert str(request.url) == f"{ORIGIN}/v1/entities/{ENTITY}"
        assert request.method == "GET" and not request.content
        assert (
            "authorization" not in request.headers and "cookie" not in request.headers
        )
        self.requests.append(
            {"method": request.method, "url": str(request.url), "body_bytes": 0}
        )
        return self.inner.handle_request(request)

    def close(self):
        self.inner.close()


def main():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # This acceptance database exists only in memory; it is not a tenant migration.
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(Tenant(id=TENANT, name="Synthetic acceptance", status="active"))
    transport = CapturingLocalTransport()
    config = PublicContextConfig(
        base_url=ORIGIN,
        approved_origins=frozenset({ORIGIN}),
        allowed_tenants=frozenset({TENANT}),
        enabled=True,
        transport=transport,
    )
    app = create_app(
        Settings(_env_file=None, postgres_dsn="sqlite+pysqlite://"),
        public_context=config,
    )
    app.state.session_factory = factory
    app.state.identity_verifier = SyntheticVerifier()
    try:
        response = TestClient(app).get(
            f"/institutional-context/entities/{ENTITY}",
            headers={"Authorization": "Bearer synthetic-loopback"},
        )
        result = {
            "status": "PASS" if response.status_code == 200 else "FAIL",
            "http_status": response.status_code,
            "host_identity": "synthetic verifier through actual OIDC dependency/scope gate",
            "host_db": "disposable in-memory SQLite synthetic tenant only",
            "core_transport": "actual loopback HTTP; public GovCore PostgreSQL service",
            "requests": transport.requests,
            "external_requests": 0,
            "ontology_mutations": 0,
            "core_db_writes": 0,
            "live_idp": "NOT RUN",
            "response_sha256": hashlib.sha256(response.content).hexdigest(),
        }
        if response.status_code == 200:
            result["gov_entity_id"] = response.json()["entity"]["id"]
            result["public_name"] = response.json()["entity"]["name"]
        else:
            result["reason"] = response.json().get("detail")
        destination = Path(__file__).with_name("loopback-proof.json")
        destination.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
        return 0 if result["status"] == "PASS" else 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
