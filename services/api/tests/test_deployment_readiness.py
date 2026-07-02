from fastapi.testclient import TestClient

from axis_api.config import Settings
from axis_api.main import create_app


def _checks_by_id(body: dict) -> dict[str, dict]:
    return {check["check_id"]: check for check in body["checks"]}


def _enterprise_sso_settings(**overrides: object) -> Settings:
    values = {
        "environment": "production",
        "postgres_dsn": "sqlite+pysqlite://",
        "api_base_url": "https://api.axis.example",
        "public_base_url": "https://console.axis.example",
        "oidc_auth_required": True,
        "oidc_issuer": "https://idp.example/realms/axis",
        "oidc_jwks_url": "https://idp.example/realms/axis/protocol/openid-connect/certs",
        "oidc_algorithms": ["RS256"],
        "oidc_client_id": "axis-console",
        "oidc_redirect_uri": "https://api.axis.example/identity/oidc/callback",
        "oidc_authorization_url": (
            "https://idp.example/realms/axis/protocol/openid-connect/auth"
        ),
        "oidc_token_url": "https://idp.example/realms/axis/protocol/openid-connect/token",
        "oidc_end_session_url": (
            "https://idp.example/realms/axis/protocol/openid-connect/logout"
        ),
        "oidc_post_logout_redirect_uri": "https://console.axis.example/signed-out",
        "oidc_session_cookie_signing_secret": "axis-cookie-signing-key",
        "oidc_session_cookie_secure": True,
        "api_rate_limit_enabled": True,
        "api_rate_limit_requests": 120,
        "api_rate_limit_window_seconds": 60,
    }
    values.update(overrides)
    return Settings(**values)


def test_deployment_readiness_marks_default_profile_demo_safe_not_production_ready() -> None:
    client = TestClient(create_app(Settings(postgres_dsn="sqlite+pysqlite://")))

    response = client.get("/deployment/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "action_required"
    assert body["environment"] == "development"
    assert body["profile"] == "local_demo"
    assert body["production_ready"] is False
    assert body["demo_safe"] is True
    assert body["capabilities"]["external_model_egress_enabled"] is False
    assert body["capabilities"]["api_rate_limit_enabled"] is False
    assert body["capabilities"]["object_store_adapter"] == "local_filesystem"

    checks = _checks_by_id(body)
    assert checks["oidc_enterprise_sso"]["status"] == "action_required"
    assert checks["oidc_secure_cookie_session"]["status"] == "action_required"
    assert checks["api_rate_limiting"]["status"] == "action_required"
    assert checks["external_model_egress_disabled"]["status"] == "ready"
    assert checks["live_connector_execution_disabled"]["status"] == "ready"
    assert checks["audit_ledger_signing_configured"]["status"] == "action_required"
    assert checks["production_object_store_adapter"]["status"] == "action_required"
    assert body["production_blockers"] == [
        "oidc_enterprise_sso",
        "oidc_secure_cookie_session",
        "api_rate_limiting",
        "audit_ledger_signing_configured",
        "production_object_store_adapter",
    ]
    assert "secret key" not in str(body).lower()
    assert "access key" not in str(body).lower()


def test_deployment_readiness_flags_unsafe_production_egress_and_live_execution() -> None:
    client = TestClient(
        create_app(
            _enterprise_sso_settings(
                audit_ledger_signing_secret="super-secret-signing-key",
                external_model_egress_enabled=True,
                connector_sync_execution_enabled=True,
            )
        )
    )

    response = client.get("/deployment/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["profile"] == "production"
    assert body["production_ready"] is False
    checks = _checks_by_id(body)
    assert checks["oidc_enterprise_sso"]["status"] == "ready"
    assert checks["oidc_secure_cookie_session"]["status"] == "ready"
    assert checks["api_rate_limiting"]["status"] == "ready"
    assert checks["audit_ledger_signing_configured"]["status"] == "ready"
    assert checks["external_model_egress_disabled"]["status"] == "action_required"
    assert checks["live_connector_execution_disabled"]["status"] == "action_required"
    assert "external_model_egress_disabled" in body["production_blockers"]
    assert "live_connector_execution_disabled" in body["production_blockers"]
    assert "super-secret-signing-key" not in str(body)


def test_deployment_readiness_keeps_object_store_as_production_blocker() -> None:
    client = TestClient(
        create_app(
            _enterprise_sso_settings(
                audit_ledger_signing_secret="production-signing-key",
                external_model_egress_enabled=False,
                connector_sync_execution_enabled=False,
                external_db_sync_execution_enabled=False,
                external_db_live_query_preflight_enabled=False,
                credential_lease_execution_enabled=False,
                credential_lease_provider_adapters_enabled=False,
            )
        )
    )

    response = client.get("/deployment/readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "action_required"
    assert body["production_ready"] is False
    checks = _checks_by_id(body)
    assert checks["oidc_enterprise_sso"]["status"] == "ready"
    assert checks["oidc_secure_cookie_session"]["status"] == "ready"
    assert checks["api_rate_limiting"]["status"] == "ready"
    assert checks["external_model_egress_disabled"]["status"] == "ready"
    assert checks["live_connector_execution_disabled"]["status"] == "ready"
    assert checks["audit_ledger_signing_configured"]["status"] == "ready"
    assert checks["production_object_store_adapter"]["status"] == "action_required"
    assert body["production_blockers"] == ["production_object_store_adapter"]
    assert "production-signing-key" not in str(body)


def test_deployment_readiness_accepts_s3_compatible_worm_object_store_profile() -> None:
    client = TestClient(
        create_app(
            _enterprise_sso_settings(
                audit_ledger_signing_secret="production-signing-key",
                external_model_egress_enabled=False,
                connector_sync_execution_enabled=False,
                external_db_sync_execution_enabled=False,
                external_db_live_query_preflight_enabled=False,
                credential_lease_execution_enabled=False,
                credential_lease_provider_adapters_enabled=False,
                connector_export_object_store_adapter="s3_compatible",
                connector_export_s3_endpoint="minio.internal:9000",
                connector_export_s3_bucket="axis-evidence",
                connector_export_s3_access_key="axis-service-account",
                connector_export_s3_secret_key="axis-secret-key",
                connector_export_s3_secure_transport=True,
                connector_export_s3_object_lock_enabled=True,
                connector_export_s3_retention_mode="GOVERNANCE",
                connector_export_s3_retention_days=90,
                connector_export_s3_legal_hold_enabled=False,
            )
        )
    )

    response = client.get("/deployment/readiness")

    assert response.status_code == 200
    body = response.json()
    checks = _checks_by_id(body)
    assert checks["oidc_secure_cookie_session"]["status"] == "ready"
    assert checks["production_object_store_adapter"]["status"] == "ready"
    assert checks["api_rate_limiting"]["status"] == "ready"
    assert "production_object_store_adapter" not in body["production_blockers"]
    assert body["capabilities"]["oidc_session_cookie_secure"] is True
    assert body["capabilities"][
        "oidc_session_cookie_signing_secret_configured"
    ] is True
    assert body["capabilities"]["oidc_session_cookie_ttl_seconds"] == 3600
    assert body["capabilities"]["api_base_url_https"] is True
    assert body["capabilities"]["public_base_url_https"] is True
    assert body["capabilities"]["oidc_redirect_uri_https"] is True
    assert body["capabilities"]["oidc_post_logout_redirect_uri_https"] is True
    assert body["capabilities"]["api_rate_limit_enabled"] is True
    assert body["capabilities"]["api_rate_limit_requests"] == 120
    assert body["capabilities"]["api_rate_limit_window_seconds"] == 60
    assert body["capabilities"]["object_store_adapter"] == "s3_compatible"
    assert body["capabilities"]["object_store_bucket_configured"] is True
    assert body["capabilities"]["object_store_endpoint_configured"] is True
    assert body["capabilities"]["object_store_credentials_configured"] is True
    assert body["capabilities"]["object_store_worm_retention_enabled"] is True
    assert body["capabilities"]["object_store_retention_mode"] == "GOVERNANCE"
    assert body["capabilities"]["object_store_retention_days"] == 90
    assert "axis-secret-key" not in str(body)
    assert "axis-service-account" not in str(body)


def test_deployment_readiness_flags_insecure_cookie_session_profile() -> None:
    client = TestClient(
        create_app(
            _enterprise_sso_settings(
                api_base_url="http://api.axis.example",
                public_base_url="http://console.axis.example",
                oidc_redirect_uri="http://api.axis.example/identity/oidc/callback",
                oidc_post_logout_redirect_uri="https://console.axis.example/signed-out",
                oidc_session_cookie_secure=True,
                oidc_session_cookie_signing_secret="super-secret-cookie-key",
                audit_ledger_signing_secret="production-signing-key",
            )
        )
    )

    response = client.get("/deployment/readiness")

    assert response.status_code == 200
    body = response.json()
    checks = _checks_by_id(body)
    assert checks["oidc_enterprise_sso"]["status"] == "ready"
    assert checks["oidc_secure_cookie_session"]["status"] == "action_required"
    assert "oidc_secure_cookie_session" in body["production_blockers"]
    assert body["capabilities"]["oidc_session_cookie_secure"] is True
    assert body["capabilities"][
        "oidc_session_cookie_signing_secret_configured"
    ] is True
    assert body["capabilities"]["oidc_session_cookie_ttl_seconds"] == 3600
    assert body["capabilities"]["api_base_url_https"] is False
    assert body["capabilities"]["public_base_url_https"] is False
    assert body["capabilities"]["oidc_redirect_uri_https"] is False
    assert body["capabilities"]["oidc_post_logout_redirect_uri_https"] is True
    assert "super-secret-cookie-key" not in str(body)
