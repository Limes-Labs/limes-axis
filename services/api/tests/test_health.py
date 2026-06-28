from fastapi.testclient import TestClient

from axis_api.config import Settings
from axis_api.main import create_app


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


def test_ready_includes_oidc_readiness_summary() -> None:
    client = TestClient(
        create_app(
            Settings(
                postgres_dsn="sqlite+pysqlite://",
                oidc_auth_required=True,
                oidc_issuer="https://idp.example/realms/axis",
                oidc_jwks_url="https://idp.example/realms/axis/protocol/openid-connect/certs",
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
