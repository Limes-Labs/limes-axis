from fastapi.testclient import TestClient

from axis_api.config import Settings
from axis_api.main import create_app


def _checks_by_id(body: dict) -> dict[str, dict]:
    return {check["check_id"]: check for check in body["checks"]}


def _enterprise_sso_settings(**overrides: object) -> Settings:
    values = {
        "environment": "production",
        "postgres_dsn": "sqlite+pysqlite://",
        "oidc_auth_required": True,
        "oidc_issuer": "https://idp.example/realms/axis",
        "oidc_jwks_url": "https://idp.example/realms/axis/protocol/openid-connect/certs",
        "oidc_algorithms": ["RS256"],
        "oidc_client_id": "axis-console",
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
    }
    values.update(overrides)
    return Settings(**values)


def test_support_diagnostics_reports_public_safe_demo_support_bundle() -> None:
    client = TestClient(create_app(Settings(postgres_dsn="sqlite+pysqlite://")))

    response = client.get("/support/diagnostics")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "axis-api"
    assert body["status"] == "action_required"
    assert body["safe_to_share"] is True
    assert body["demo_support_ready"] is True
    assert body["production_support_ready"] is False
    assert body["diagnostics"]["deployment"]["profile"] == "local_demo"
    assert body["diagnostics"]["deployment"]["demo_safe"] is True
    assert body["diagnostics"]["deployment"]["production_ready"] is False
    assert body["diagnostics"]["identity"]["readiness_status"] == "action_required"
    assert body["support_blockers"] == [
        "oidc_enterprise_sso",
        "audit_ledger_signing_configured",
        "production_object_store_adapter",
        "production_support_model",
    ]
    assert body["support_artifacts"] == [
        {"label": "Demo readiness runbook", "path": "docs/demo-readiness.md"},
        {"label": "Deployment threat model", "path": "docs/threat-model.md"},
        {"label": "Support operations runbook", "path": "docs/support-operations.md"},
    ]
    assert body["redaction_policy"] == [
        "bearer_tokens",
        "raw_jwks",
        "credential_material",
        "signing_material",
        "database_dsn",
    ]

    checks = _checks_by_id(body)
    assert checks["support_diagnostics_public_safe"]["status"] == "ready"
    assert checks["support_runbook_baseline"]["status"] == "ready"
    assert checks["production_support_model"]["status"] == "action_required"
    assert "password" not in str(body).lower()


def test_support_diagnostics_never_returns_sensitive_signing_material() -> None:
    client = TestClient(
        create_app(
            _enterprise_sso_settings(
                audit_ledger_signing_secret="do-not-return-this-signing-material",
                external_model_egress_enabled=False,
                connector_sync_execution_enabled=False,
                external_db_sync_execution_enabled=False,
                external_db_live_query_preflight_enabled=False,
                credential_lease_execution_enabled=False,
                credential_lease_provider_adapters_enabled=False,
            )
        )
    )

    response = client.get("/support/diagnostics")

    assert response.status_code == 200
    body = response.json()
    assert body["diagnostics"]["deployment"]["profile"] == "production"
    assert body["diagnostics"]["identity"]["readiness_status"] == "ready"
    assert body["diagnostics"]["audit_ledger_signing_configured"] is True
    assert body["production_support_ready"] is False
    assert body["support_blockers"] == [
        "production_object_store_adapter",
        "production_support_model",
    ]
    assert "do-not-return-this-signing-material" not in str(body)
    assert "password" not in str(body).lower()


def test_support_diagnostics_reports_s3_object_store_without_secret_material() -> None:
    client = TestClient(
        create_app(
            _enterprise_sso_settings(
                audit_ledger_signing_secret="do-not-return-this-signing-material",
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
                connector_export_s3_object_lock_enabled=True,
                connector_export_s3_retention_mode="COMPLIANCE",
                connector_export_s3_retention_days=365,
                connector_export_s3_legal_hold_enabled=True,
            )
        )
    )

    response = client.get("/support/diagnostics")

    assert response.status_code == 200
    body = response.json()
    assert body["diagnostics"]["object_store_adapter"] == "s3_compatible"
    assert body["diagnostics"]["object_store_worm_retention_enabled"] is True
    assert body["diagnostics"]["object_store_retention_mode"] == "COMPLIANCE"
    assert body["diagnostics"]["object_store_retention_days"] == 365
    assert body["support_blockers"] == ["production_support_model"]
    assert "axis-secret-key" not in str(body)
    assert "axis-service-account" not in str(body)
    assert "do-not-return-this-signing-material" not in str(body)
