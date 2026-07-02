from __future__ import annotations

import json
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from jose import jwt
from jose.utils import base64url_encode
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.config import Settings
from axis_api.identity import StaticJwksOidcVerifier
from axis_api.main import create_app
from axis_api.models import AuditEvent, Base
from axis_api.oidc_code_flow import read_session_cookie


def _oct_jwks(secret: str) -> dict:
    return {
        "keys": [
            {
                "kty": "oct",
                "kid": "axis-test",
                "k": base64url_encode(secret.encode()).decode(),
            }
        ]
    }


def _token(secret: str, settings: Settings) -> str:
    return jwt.encode(
        {
            "iss": settings.oidc_issuer,
            "aud": settings.oidc_audience,
            "sub": "plant-operations-owner-role",
            "axis_tenant": "tenant_demo_manufacturing",
            "scope": "audit:read approvals:supply:decide",
            "exp": 4102444800,
        },
        secret,
        algorithm="HS256",
        headers={"kid": "axis-test"},
    )


def _settings(**overrides: object) -> Settings:
    values = {
        "postgres_dsn": "sqlite+pysqlite://",
        "api_base_url": "https://api.axis.example",
        "public_base_url": "https://console.axis.example",
        "oidc_auth_required": True,
        "oidc_issuer": "https://idp.example/realms/axis",
        "oidc_audience": "limes-axis-api",
        "oidc_jwks_url": "https://idp.example/realms/axis/protocol/openid-connect/certs",
        "oidc_algorithms": ["HS256"],
        "oidc_client_id": "axis-console",
        "oidc_client_secret": "axis-client-secret",
        "oidc_authorization_url": (
            "https://idp.example/realms/axis/protocol/openid-connect/auth"
        ),
        "oidc_token_url": "https://idp.example/realms/axis/protocol/openid-connect/token",
        "oidc_session_cookie_signing_secret": "a-secure-cookie-signing-secret",
        "oidc_session_cookie_secure": True,
    }
    values.update(overrides)
    return Settings(**values)


def _session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _app_with_static_oidc(
    settings: Settings,
    *,
    token_secret: str,
) -> tuple[TestClient, sessionmaker[Session], list[dict[str, str]]]:
    app = create_app(settings)
    factory = _session_factory()
    app.state.session_factory = factory
    app.state.identity_verifier = StaticJwksOidcVerifier(
        issuer=settings.oidc_issuer,
        audience=settings.oidc_audience,
        algorithms=settings.oidc_algorithms,
        jwks=_oct_jwks(token_secret),
        tenant_claim=settings.oidc_tenant_claim,
    )
    token_requests: list[dict[str, str]] = []

    def exchange_token(form: dict[str, str], _settings: Settings) -> dict[str, object]:
        token_requests.append(form)
        return {
            "access_token": _token(token_secret, settings),
            "expires_in": 900,
            "token_type": "Bearer",
        }

    app.state.oidc_token_exchanger = exchange_token
    return TestClient(app, follow_redirects=False), factory, token_requests


def _one_oidc_browser_session(session: Session) -> dict:
    assert inspect(session.bind).has_table("oidc_browser_sessions")
    row = dict(
        session.execute(text("SELECT * FROM oidc_browser_sessions")).mappings().one()
    )
    if isinstance(row.get("scopes"), str):
        row["scopes"] = json.loads(row["scopes"])
    return row


def test_oidc_authorize_redirects_with_pkce_and_http_only_login_cookie() -> None:
    settings = _settings()
    client = TestClient(create_app(settings), follow_redirects=False)

    response = client.get("/identity/oidc/authorize?return_to=/connectors")

    assert response.status_code == 307
    location = response.headers["location"]
    parsed = urlparse(location)
    params = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "idp.example"
    assert parsed.path.endswith("/protocol/openid-connect/auth")
    assert params["response_type"] == ["code"]
    assert params["client_id"] == ["axis-console"]
    assert params["redirect_uri"] == ["https://api.axis.example/identity/oidc/callback"]
    assert params["scope"] == ["openid profile email"]
    assert params["code_challenge_method"] == ["S256"]
    assert len(params["code_challenge"][0]) >= 43
    assert len(params["state"][0]) >= 32
    assert len(params["nonce"][0]) >= 32
    assert "code_verifier" not in location
    assert "axis-client-secret" not in location

    cookie = SimpleCookie(response.headers["set-cookie"])
    login_cookie = cookie["axis_oidc_login"]
    assert login_cookie["httponly"] is True
    assert login_cookie["secure"] is True
    assert login_cookie["samesite"] == "lax"
    assert "axis-client-secret" not in login_cookie.value


def test_oidc_callback_exchanges_code_and_sets_api_validated_session_cookie() -> None:
    secret = "axis-test-secret"
    settings = _settings(oidc_session_cookie_secure=False)
    client, factory, token_requests = _app_with_static_oidc(settings, token_secret=secret)
    authorize = client.get("/identity/oidc/authorize?return_to=/settings")
    state = parse_qs(urlparse(authorize.headers["location"]).query)["state"][0]

    callback = client.get(f"/identity/oidc/callback?code=valid-code&state={state}")

    assert callback.status_code == 307
    assert callback.headers["location"] == "https://console.axis.example/settings"
    assert token_requests == [
        {
            "grant_type": "authorization_code",
            "code": "valid-code",
            "redirect_uri": "https://api.axis.example/identity/oidc/callback",
            "client_id": "axis-console",
            "client_secret": "axis-client-secret",
            "code_verifier": token_requests[0]["code_verifier"],
        }
    ]
    assert len(token_requests[0]["code_verifier"]) >= 43
    set_cookie = callback.headers["set-cookie"]
    assert "axis_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "valid-code" not in set_cookie
    assert token_requests[0]["code_verifier"] not in set_cookie
    assert "access_token" not in set_cookie
    session_cookie = SimpleCookie(set_cookie)["axis_session"].value
    session_claims = read_session_cookie(session_cookie, settings)
    assert len(session_claims.session_id) >= 43
    assert session_claims.actor_id == "plant-operations-owner-role"
    assert session_claims.tenant_id == "tenant_demo_manufacturing"
    assert session_claims.scopes == ("approvals:supply:decide", "audit:read")

    with factory() as session:
        persisted_session = _one_oidc_browser_session(session)
        assert persisted_session["status"] == "active"
        assert persisted_session["session_id_hash"] != session_claims.session_id
        assert persisted_session["actor_id"] == "plant-operations-owner-role"
        assert persisted_session["tenant_id"] == "tenant_demo_manufacturing"
        assert persisted_session["scopes"] == ["approvals:supply:decide", "audit:read"]
        assert "access_token" not in str(persisted_session).lower()
        assert "refresh_token" not in str(persisted_session).lower()
        audit_events = list(session.scalars(select(AuditEvent)))
        assert [event.event_type for event in audit_events] == [
            "identity.oidc_session.created"
        ]

    session_response = client.get("/identity/session")

    assert session_response.status_code == 200
    body = session_response.json()
    assert body["authenticated"] is True
    assert body["mode"] == "secure_oidc_cookie"
    assert body["actor_id"] == "plant-operations-owner-role"
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["session_boundary"] == "http_only_cookie_verified_by_axis_api"
    assert "access_token" not in str(body).lower()
    assert "refresh_token" not in str(body).lower()
    assert "axis-test-secret" not in str(body)


def test_oidc_callback_rejects_state_mismatch_without_token_exchange() -> None:
    settings = _settings(oidc_session_cookie_secure=False)
    app = create_app(settings)
    token_requests: list[dict[str, str]] = []
    app.state.oidc_token_exchanger = lambda form, _settings: token_requests.append(form)
    client = TestClient(app, follow_redirects=False)
    client.get("/identity/oidc/authorize?return_to=/")

    response = client.get("/identity/oidc/callback?code=valid-code&state=wrong-state")

    assert response.status_code == 401
    assert response.json()["detail"]["reason"] == "oidc_state_mismatch"
    assert token_requests == []


def test_identity_session_rejects_tampered_session_cookie_when_auth_required() -> None:
    settings = _settings(oidc_session_cookie_secure=False)
    client = TestClient(create_app(settings))
    client.cookies.set("axis_session", "tampered")

    response = client.get("/identity/session")

    assert response.status_code == 401
    assert response.json()["detail"]["reason"] == "invalid_session_cookie"


def test_oidc_session_logout_revokes_persisted_session_and_deletes_cookie() -> None:
    settings = _settings(oidc_session_cookie_secure=False)
    client, factory, _token_requests = _app_with_static_oidc(
        settings,
        token_secret="axis-test-secret",
    )
    authorize = client.get("/identity/oidc/authorize?return_to=/")
    state = parse_qs(urlparse(authorize.headers["location"]).query)["state"][0]
    callback = client.get(f"/identity/oidc/callback?code=valid-code&state={state}")
    assert callback.status_code == 307

    logout = client.post("/identity/session/logout")

    assert logout.status_code == 204
    assert "axis_session=" in logout.headers["set-cookie"]
    assert "Max-Age=0" in logout.headers["set-cookie"]
    with factory() as session:
        persisted_session = _one_oidc_browser_session(session)
        assert persisted_session["status"] == "revoked"
        assert persisted_session["revoked_by"] == "plant-operations-owner-role"
        assert persisted_session["revocation_reason"] == "user_logout"
        assert persisted_session["revoked_at"] is not None
        audit_events = list(session.scalars(select(AuditEvent)))
        assert [event.event_type for event in audit_events] == [
            "identity.oidc_session.created",
            "identity.oidc_session.revoked",
        ]

    response = client.get("/identity/session")

    assert response.status_code == 401
    assert response.json()["detail"]["reason"] == "missing_authorization"


def test_oidc_federated_logout_revokes_session_and_redirects_to_idp_without_tokens() -> None:
    settings = _settings(
        oidc_session_cookie_secure=False,
        oidc_end_session_url="https://idp.example/realms/axis/protocol/openid-connect/logout",
        oidc_post_logout_redirect_uri="https://console.axis.example/signed-out",
    )
    client, factory, _token_requests = _app_with_static_oidc(
        settings,
        token_secret="axis-test-secret",
    )
    authorize = client.get("/identity/oidc/authorize?return_to=/")
    state = parse_qs(urlparse(authorize.headers["location"]).query)["state"][0]
    callback = client.get(f"/identity/oidc/callback?code=valid-code&state={state}")
    assert callback.status_code == 307

    logout = client.get("/identity/oidc/logout?return_to=/settings")

    assert logout.status_code == 307
    parsed = urlparse(logout.headers["location"])
    params = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "idp.example"
    assert parsed.path.endswith("/protocol/openid-connect/logout")
    assert params["client_id"] == ["axis-console"]
    assert params["post_logout_redirect_uri"] == [
        "https://console.axis.example/signed-out"
    ]
    rendered_location = logout.headers["location"].lower()
    assert "access_token" not in rendered_location
    assert "refresh_token" not in rendered_location
    assert "id_token" not in rendered_location
    assert "axis-client-secret" not in rendered_location
    assert "axis_session=" in logout.headers["set-cookie"]
    assert "Max-Age=0" in logout.headers["set-cookie"]
    with factory() as session:
        persisted_session = _one_oidc_browser_session(session)
        assert persisted_session["status"] == "revoked"
        assert persisted_session["revoked_by"] == "plant-operations-owner-role"
        assert persisted_session["revocation_reason"] == "federated_logout"
        audit_events = list(session.scalars(select(AuditEvent)))
        assert [event.event_type for event in audit_events] == [
            "identity.oidc_session.created",
            "identity.oidc_session.revoked",
        ]
        assert audit_events[-1].payload["revocation_reason"] == "federated_logout"
        assert audit_events[-1].payload["federated_logout"] is True


def test_oidc_federated_logout_uses_safe_local_return_when_post_logout_uri_is_not_set() -> None:
    settings = _settings(oidc_session_cookie_secure=False)
    client = TestClient(create_app(settings), follow_redirects=False)

    logout = client.get("/identity/oidc/logout?return_to=https://evil.example/steal")

    assert logout.status_code == 307
    parsed = urlparse(logout.headers["location"])
    params = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "idp.example"
    assert params["client_id"] == ["axis-console"]
    assert params["post_logout_redirect_uri"] == ["https://console.axis.example/"]
    assert "axis_session=" in logout.headers["set-cookie"]
    assert "Max-Age=0" in logout.headers["set-cookie"]


def test_revoked_oidc_session_cookie_cannot_authenticate_again() -> None:
    settings = _settings(oidc_session_cookie_secure=False)
    client, factory, _token_requests = _app_with_static_oidc(
        settings,
        token_secret="axis-test-secret",
    )
    authorize = client.get("/identity/oidc/authorize?return_to=/")
    state = parse_qs(urlparse(authorize.headers["location"]).query)["state"][0]
    callback = client.get(f"/identity/oidc/callback?code=valid-code&state={state}")
    cookie_value = SimpleCookie(callback.headers["set-cookie"])["axis_session"].value
    assert client.post("/identity/session/logout").status_code == 204
    client.cookies.set("axis_session", cookie_value)

    response = client.get("/identity/session")

    assert response.status_code == 401
    assert response.json()["detail"]["reason"] == "revoked_session_cookie"
    with factory() as session:
        persisted_session = _one_oidc_browser_session(session)
        assert persisted_session["status"] == "revoked"
