from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from threading import Event
from time import time

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.config import Settings
from axis_api.identity import OidcPrincipal
from axis_api.main import create_app
from axis_api.models import Base, Tenant
from axis_api.public_institutional_context import READ_SCOPE, PublicContextConfig

ID = "gov_" + "a" * 32
TENANT = "synthetic-tenant"
URL = "https://govcore.example"
HEADERS = {"Authorization": "Bearer synthetic-token"}


def public_entity():
    proof = {
        "source_id": "fixture",
        "source_url": "https://official.example/entity",
        "content_sha256": "b" * 64,
        "retrieved_at": (datetime.now(UTC) - timedelta(minutes=2)).isoformat(),
        "verified_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        "verification_status": "verified",
        "valid_from": None,
        "valid_to": None,
        "scope": "institutional",
        "competences": [],
    }
    return {
        "schema_version": "1",
        "id": ID,
        "kind": "municipality",
        "name": "Synthetic municipality",
        "status": "active",
        "provenance": [proof],
        "identifiers": [],
        "aliases": [],
        "facts": [],
    }


class Verifier:
    def __init__(self):
        self.principal = OidcPrincipal(
            tenant_id=TENANT,
            actor_id="synthetic-reader",
            scopes=[READ_SCOPE],
            expires_at=int(time()) + 600,
        )

    def verify_authorization_header(self, authorization):
        assert authorization == HEADERS["Authorization"]
        return self.principal


@pytest.fixture
def host():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(Tenant(id=TENANT, name="Synthetic", status="active"))
    verifier = Verifier()
    calls = []
    active_connections = 0

    @event.listens_for(engine, "checkout")
    def checkout(*args):
        nonlocal active_connections
        active_connections += 1

    @event.listens_for(engine, "checkin")
    def checkin(*args):
        nonlocal active_connections
        active_connections -= 1

    def handler(request):
        assert active_connections == 0  # no local transaction held across egress
        calls.append(request)
        return httpx.Response(200, json=public_entity())

    config = PublicContextConfig(
        base_url=URL,
        approved_origins=frozenset({URL}),
        allowed_tenants=frozenset({TENANT}),
        enabled=True,
        transport=httpx.MockTransport(handler),
    )
    app = create_app(
        Settings(_env_file=None, postgres_dsn="sqlite+pysqlite://"), public_context=config
    )
    app.state.session_factory = factory
    app.state.identity_verifier = verifier
    yield app, factory, verifier, calls, config
    engine.dispose()


def test_default_app_has_no_route_or_optional_sdk_contract():
    app = create_app(Settings(_env_file=None, postgres_dsn="sqlite+pysqlite://"))
    assert not any(path.startswith("/institutional-context") for path in app.openapi()["paths"])


def test_real_host_gate_and_only_public_id_egress(host):
    app, _, _, calls, _ = host
    response = TestClient(app).get(
        f"/institutional-context/entities/{ID}?tenant_id=other&notes=private",
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["namespace"] == "public_institutional"
    assert response.headers["Cache-Control"] == "no-store"
    assert TENANT not in response.text
    assert len(calls) == 1
    assert str(calls[0].url) == f"{URL}/v1/entities/{ID}"
    assert calls[0].method == "GET" and not calls[0].content
    assert "authorization" not in calls[0].headers and "cookie" not in calls[0].headers


@pytest.mark.parametrize("denial", ["anonymous", "scope", "tenant", "policy", "expiry", "id"])
def test_denied_host_or_invalid_id_performs_no_egress(host, denial):
    app, factory, verifier, calls, config = host
    headers = HEADERS
    entity_id = ID
    if denial == "anonymous":
        headers = {}
    elif denial == "scope":
        verifier.principal.scopes = []
    elif denial == "tenant":
        with factory.begin() as session:
            session.get(Tenant, TENANT).status = "suspended"
    elif denial == "policy":
        app.state.public_context_config = replace(config, enabled=False)
    elif denial == "expiry":
        verifier.principal.expires_at = int(time()) - 1
    else:
        entity_id = "private-record-id"
    response = TestClient(app).get(f"/institutional-context/entities/{entity_id}", headers=headers)
    assert response.status_code in {401, 403, 422}
    assert calls == []


@pytest.mark.parametrize("revocation", ["scope", "tenant", "policy", "identity"])
def test_current_authorization_revoked_during_network_blocks_response(host, revocation):
    app, factory, verifier, calls, config = host

    def revoke(request):
        calls.append(request)
        if revocation == "scope":
            verifier.principal = verifier.principal.model_copy(update={"scopes": []})
        elif revocation == "tenant":
            with factory.begin() as session:
                session.get(Tenant, TENANT).status = "suspended"
        elif revocation == "policy":
            app.state.public_context_config = replace(config, enabled=False)
        else:
            verifier.principal = verifier.principal.model_copy(update={"tenant_id": "other"})
        return httpx.Response(200, json=public_entity())

    # Config captured by the route controls transport; runtime policy remains separate.
    changed = replace(config, transport=httpx.MockTransport(revoke))
    new_app = create_app(
        Settings(_env_file=None, postgres_dsn="sqlite+pysqlite://"), public_context=changed
    )
    new_app.state.session_factory = factory
    new_app.state.identity_verifier = verifier
    app = new_app
    response = TestClient(app).get(f"/institutional-context/entities/{ID}", headers=HEADERS)
    assert response.status_code == 403
    assert len(calls) == 1
    assert "entity" not in response.json()


@pytest.mark.parametrize("response", [httpx.Response(503), httpx.Response(200, json={"id": ID})])
def test_unavailable_or_malformed_core_fails_closed(host, response):
    _, factory, verifier, _, config = host
    changed = replace(config, transport=httpx.MockTransport(lambda request: response))
    app = create_app(
        Settings(_env_file=None, postgres_dsn="sqlite+pysqlite://"), public_context=changed
    )
    app.state.session_factory = factory
    app.state.identity_verifier = verifier
    result = TestClient(app).get(f"/institutional-context/entities/{ID}", headers=HEADERS)
    assert result.status_code == 503 and "entity" not in result.json()


@pytest.mark.parametrize(
    "url",
    ["https://govcore.example:bad", "https://govcore.example:70000", "https://govcore.example:0"],
)
def test_invalid_origin_port_is_rejected_even_if_allowlisted(url):
    with pytest.raises(ValueError):
        PublicContextConfig(
            base_url=url, approved_origins=frozenset({url}), allowed_tenants=frozenset({TENANT})
        )


def test_unapproved_or_credentialled_origin_is_rejected():
    for url in [
        "https://other.example",
        "https://user:pass@govcore.example",
        URL + "/path",
        "http://remote.example",
    ]:
        with pytest.raises(ValueError):
            PublicContextConfig(
                base_url=url, approved_origins=frozenset({URL}), allowed_tenants=frozenset({TENANT})
            )


def test_concurrent_policy_revocation_blocks_inflight_response(host):
    _, factory, verifier, calls, config = host
    entered, release = Event(), Event()

    def paused_response(request):
        calls.append(request)
        entered.set()
        assert release.wait(5)
        return httpx.Response(200, json=public_entity())

    changed = replace(config, transport=httpx.MockTransport(paused_response))
    app = create_app(
        Settings(_env_file=None, postgres_dsn="sqlite+pysqlite://"),
        public_context=changed,
    )
    app.state.session_factory = factory
    app.state.identity_verifier = verifier
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(
            TestClient(app).get,
            f"/institutional-context/entities/{ID}",
            headers=HEADERS,
        )
        try:
            assert entered.wait(5)
            app.state.public_context_config = replace(changed, allowed_tenants=frozenset())
        finally:
            release.set()
        result = pending.result(timeout=5)
    assert result.status_code == 403 and len(calls) == 1
