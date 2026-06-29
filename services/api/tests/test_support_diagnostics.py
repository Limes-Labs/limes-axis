from fastapi.testclient import TestClient

from axis_api.config import Settings
from axis_api.main import create_app


def _checks_by_id(body: dict) -> dict[str, dict]:
    return {check["check_id"]: check for check in body["checks"]}


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
            Settings(
                environment="production",
                postgres_dsn="sqlite+pysqlite://",
                oidc_auth_required=True,
                oidc_issuer="https://idp.example/realms/axis",
                oidc_jwks_url="https://idp.example/realms/axis/protocol/openid-connect/certs",
                oidc_algorithms=["RS256"],
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
