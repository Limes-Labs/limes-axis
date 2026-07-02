from fastapi.testclient import TestClient
from jose import jwt
from jose.utils import base64url_encode

from axis_api.config import Settings
from axis_api.identity import StaticJwksOidcVerifier
from axis_api.main import create_app


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


def _token(secret: str, claims: dict) -> str:
    return jwt.encode(claims, secret, algorithm="HS256", headers={"kid": "axis-test"})


def test_health_returns_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "axis-api"}


def test_ready_returns_dependency_configuration_without_secrets() -> None:
    client = TestClient(create_app())
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["dependencies"] == {
        "postgres": True,
        "typedb": True,
        "typedb_queries": False,
        "temporal": True,
    }
    assert "password" not in str(body).lower()


def test_local_console_origin_is_allowed_for_cors_preflight() -> None:
    client = TestClient(create_app())
    response = client.options(
        "/ready",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_console_no_store_fetch_header_is_allowed_for_cors_preflight() -> None:
    client = TestClient(create_app())
    response = client.options(
        "/demo/manufacturing/overview",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "cache-control",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
    assert "cache-control" in response.headers["access-control-allow-headers"].lower()


def test_playwright_console_origin_is_allowed_for_cors_preflight() -> None:
    client = TestClient(create_app())
    response = client.options(
        "/demo/manufacturing/overview",
        headers={
            "Origin": "http://127.0.0.1:3100",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "cache-control",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3100"
    assert "cache-control" in response.headers["access-control-allow-headers"].lower()


def test_openapi_metadata_names_axis() -> None:
    client = TestClient(create_app())
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Limes Axis API"
    assert "/ready" in response.json()["paths"]


def test_oidc_readiness_reports_enterprise_profile_without_secrets() -> None:
    client = TestClient(
        create_app(
            Settings(
                postgres_dsn="sqlite+pysqlite://",
                oidc_auth_required=True,
                oidc_issuer="https://idp.example/realms/axis",
                oidc_audience="limes-axis-api",
                oidc_jwks_url="https://idp.example/realms/axis/protocol/openid-connect/certs",
                oidc_algorithms=["RS256"],
                oidc_actor_claim="preferred_username",
                oidc_tenant_claim="axis_tenant",
                oidc_jwks_cache_seconds=900,
                oidc_client_id="axis-console",
                oidc_authorization_url=(
                    "https://idp.example/realms/axis/protocol/openid-connect/auth"
                ),
                oidc_token_url="https://idp.example/realms/axis/protocol/openid-connect/token",
                oidc_end_session_url=(
                    "https://idp.example/realms/axis/protocol/openid-connect/logout"
                ),
                oidc_post_logout_redirect_uri="https://console.axis.example/signed-out",
                oidc_session_cookie_signing_secret="axis-cookie-signing-secret",
                oidc_session_cookie_secure=True,
            )
        )
    )

    response = client.get("/identity/oidc/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["enterprise_sso_ready"] is True
    assert body["auth_required"] is True
    assert body["issuer"] == "https://idp.example/realms/axis"
    assert body["audience"] == "limes-axis-api"
    assert body["jwks_source"] == "configured"
    assert body["jwks_url_configured"] is True
    assert body["jwks_cache_seconds"] == 900
    assert body["federated_logout"] == {
        "end_session_source": "configured",
        "end_session_url_configured": True,
        "post_logout_redirect_uri": "https://console.axis.example/signed-out",
        "stores_provider_logout_tokens": False,
    }
    assert body["token_binding"] == {
        "actor_claim": "preferred_username",
        "tenant_claim": "axis_tenant",
        "scope_sources": [
            "scope",
            "scp",
            "realm_access.roles",
            "resource_access[limes-axis-api].roles",
        ],
    }
    assert {check["check_id"]: check["status"] for check in body["checks"]} == {
        "auth_required": "ready",
        "https_issuer": "ready",
        "explicit_jwks_url": "ready",
        "asymmetric_algorithms": "ready",
        "tenant_claim": "ready",
        "actor_claim": "ready",
        "authorization_code_client": "ready",
        "authorization_endpoint": "ready",
        "token_endpoint": "ready",
        "end_session_endpoint": "ready",
        "post_logout_redirect": "ready",
        "session_cookie_signing": "ready",
        "secure_session_cookie": "ready",
    }
    assert "secret" not in str(body).lower()
    assert "password" not in str(body).lower()


def test_oidc_readiness_marks_default_local_profile_as_not_enterprise_ready() -> None:
    client = TestClient(create_app(Settings(postgres_dsn="sqlite+pysqlite://")))

    response = client.get("/identity/oidc/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "action_required"
    assert body["enterprise_sso_ready"] is False
    assert body["auth_required"] is False
    assert body["jwks_source"] == "derived_from_issuer"
    checks = {check["check_id"]: check for check in body["checks"]}
    assert checks["auth_required"]["status"] == "action_required"
    assert checks["https_issuer"]["status"] == "action_required"
    assert checks["explicit_jwks_url"]["status"] == "action_required"
    assert checks["authorization_code_client"]["status"] == "action_required"
    assert checks["end_session_endpoint"]["status"] == "action_required"
    assert checks["post_logout_redirect"]["status"] == "action_required"
    assert checks["session_cookie_signing"]["status"] == "action_required"
    assert checks["secure_session_cookie"]["status"] == "action_required"


def test_identity_session_reports_public_evaluation_without_local_claims() -> None:
    client = TestClient(create_app(Settings(postgres_dsn="sqlite+pysqlite://")))

    response = client.get("/identity/session")

    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is False
    assert body["mode"] == "public_evaluation"
    assert body["actor_id"] is None
    assert body["tenant_id"] is None
    assert body["scopes"] == []
    assert body["session_boundary"] == "no_authenticated_api_actor"
    assert body["api_auth_required"] is False
    assert body["enterprise_sso_ready"] is False
    assert "No authenticated API actor is attached." in body["limitations"]
    rendered = str(body).lower()
    assert "access_token" not in rendered
    assert "refresh_token" not in rendered
    assert "id_token" not in rendered
    assert "secret" not in str(body).lower()
    assert "password" not in str(body).lower()


def test_identity_session_returns_validated_oidc_context_without_token_material() -> None:
    secret = "axis-test-secret"
    settings = Settings(
        postgres_dsn="sqlite+pysqlite://",
        oidc_auth_required=True,
        oidc_issuer="https://issuer.example/realms/axis",
        oidc_audience="limes-axis-api",
        oidc_jwks_url="https://issuer.example/realms/axis/protocol/openid-connect/certs",
        oidc_algorithms=["HS256"],
    )
    app = create_app(settings)
    app.state.identity_verifier = StaticJwksOidcVerifier(
        issuer=settings.oidc_issuer,
        audience=settings.oidc_audience,
        algorithms=settings.oidc_algorithms,
        jwks=_oct_jwks(secret),
        tenant_claim=settings.oidc_tenant_claim,
    )
    token = _token(
        secret,
        {
            "iss": settings.oidc_issuer,
            "aud": settings.oidc_audience,
            "sub": "plant-operations-owner-role",
            "axis_tenant": "tenant_demo_manufacturing",
            "scope": "approvals:supply:decide audit:read",
            "exp": 4102444800,
        },
    )
    client = TestClient(app)

    response = client.get("/identity/session", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is True
    assert body["mode"] == "validated_oidc_bearer"
    assert body["actor_id"] == "plant-operations-owner-role"
    assert body["tenant_id"] == "tenant_demo_manufacturing"
    assert body["scopes"] == ["approvals:supply:decide", "audit:read"]
    assert body["expires_at"] == 4102444800
    assert body["api_auth_required"] is True
    assert body["session_boundary"] == "bearer_token_verified_by_axis_api"
    assert "Bearer token validated by the Axis OIDC verifier." in body["capabilities"]
    assert token not in str(body)
    assert "secret" not in str(body).lower()
    assert "password" not in str(body).lower()


def test_identity_session_requires_token_when_oidc_auth_is_required() -> None:
    client = TestClient(
        create_app(
            Settings(
                postgres_dsn="sqlite+pysqlite://",
                oidc_auth_required=True,
            )
        )
    )

    response = client.get("/identity/session")

    assert response.status_code == 401
    assert response.json()["detail"]["reason"] == "missing_authorization"


def test_ready_includes_oidc_readiness_summary() -> None:
    client = TestClient(
        create_app(
            Settings(
                postgres_dsn="sqlite+pysqlite://",
                oidc_auth_required=True,
                oidc_issuer="https://idp.example/realms/axis",
                oidc_jwks_url="https://idp.example/realms/axis/protocol/openid-connect/certs",
                oidc_client_id="axis-console",
                oidc_authorization_url=(
                    "https://idp.example/realms/axis/protocol/openid-connect/auth"
                ),
                oidc_token_url="https://idp.example/realms/axis/protocol/openid-connect/token",
                oidc_end_session_url=(
                    "https://idp.example/realms/axis/protocol/openid-connect/logout"
                ),
                oidc_post_logout_redirect_uri="https://console.axis.example/signed-out",
                oidc_session_cookie_signing_secret="axis-cookie-signing-secret",
                oidc_session_cookie_secure=True,
            )
        )
    )

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["identity"] == {
        "oidc_auth_required": True,
        "enterprise_sso_ready": True,
        "readiness_status": "ready",
    }
