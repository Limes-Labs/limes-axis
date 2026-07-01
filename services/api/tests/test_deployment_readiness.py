from fastapi.testclient import TestClient

from axis_api.config import Settings
from axis_api.main import create_app


def _checks_by_id(body: dict) -> dict[str, dict]:
    return {check["check_id"]: check for check in body["checks"]}


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
    assert body["capabilities"]["object_store_adapter"] == "local_filesystem"

    checks = _checks_by_id(body)
    assert checks["oidc_enterprise_sso"]["status"] == "action_required"
    assert checks["external_model_egress_disabled"]["status"] == "ready"
    assert checks["live_connector_execution_disabled"]["status"] == "ready"
    assert checks["audit_ledger_signing_configured"]["status"] == "action_required"
    assert checks["production_object_store_adapter"]["status"] == "action_required"
    assert body["production_blockers"] == [
        "oidc_enterprise_sso",
        "audit_ledger_signing_configured",
        "production_object_store_adapter",
    ]
    assert "secret key" not in str(body).lower()
    assert "access key" not in str(body).lower()


def test_deployment_readiness_flags_unsafe_production_egress_and_live_execution() -> None:
    client = TestClient(
        create_app(
            Settings(
                environment="production",
                postgres_dsn="sqlite+pysqlite://",
                oidc_auth_required=True,
                oidc_issuer="https://idp.example/realms/axis",
                oidc_jwks_url="https://idp.example/realms/axis/protocol/openid-connect/certs",
                oidc_algorithms=["RS256"],
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
    assert checks["audit_ledger_signing_configured"]["status"] == "ready"
    assert checks["external_model_egress_disabled"]["status"] == "action_required"
    assert checks["live_connector_execution_disabled"]["status"] == "action_required"
    assert "external_model_egress_disabled" in body["production_blockers"]
    assert "live_connector_execution_disabled" in body["production_blockers"]
    assert "super-secret-signing-key" not in str(body)


def test_deployment_readiness_keeps_object_store_as_production_blocker() -> None:
    client = TestClient(
        create_app(
            Settings(
                environment="production",
                postgres_dsn="sqlite+pysqlite://",
                oidc_auth_required=True,
                oidc_issuer="https://idp.example/realms/axis",
                oidc_jwks_url="https://idp.example/realms/axis/protocol/openid-connect/certs",
                oidc_algorithms=["RS256"],
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
    assert checks["external_model_egress_disabled"]["status"] == "ready"
    assert checks["live_connector_execution_disabled"]["status"] == "ready"
    assert checks["audit_ledger_signing_configured"]["status"] == "ready"
    assert checks["production_object_store_adapter"]["status"] == "action_required"
    assert body["production_blockers"] == ["production_object_store_adapter"]
    assert "production-signing-key" not in str(body)


def test_deployment_readiness_accepts_s3_compatible_worm_object_store_profile() -> None:
    client = TestClient(
        create_app(
            Settings(
                environment="production",
                postgres_dsn="sqlite+pysqlite://",
                oidc_auth_required=True,
                oidc_issuer="https://idp.example/realms/axis",
                oidc_jwks_url="https://idp.example/realms/axis/protocol/openid-connect/certs",
                oidc_algorithms=["RS256"],
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
    assert checks["production_object_store_adapter"]["status"] == "ready"
    assert "production_object_store_adapter" not in body["production_blockers"]
    assert body["capabilities"]["object_store_adapter"] == "s3_compatible"
    assert body["capabilities"]["object_store_bucket_configured"] is True
    assert body["capabilities"]["object_store_endpoint_configured"] is True
    assert body["capabilities"]["object_store_credentials_configured"] is True
    assert body["capabilities"]["object_store_worm_retention_enabled"] is True
    assert body["capabilities"]["object_store_retention_mode"] == "GOVERNANCE"
    assert body["capabilities"]["object_store_retention_days"] == 90
    assert "axis-secret-key" not in str(body)
    assert "axis-service-account" not in str(body)
