from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECK_SCRIPT = REPO_ROOT / "services" / "api" / "scripts" / "check_demo_environment.py"


def load_check_module():
    spec = importlib.util.spec_from_file_location("check_demo_environment", CHECK_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_demo_environment_static_contract_passes() -> None:
    checker = load_check_module()

    results = checker.run_static_checks(REPO_ROOT)

    failures = [f"{result.name}: {result.detail}" for result in results if not result.ok]
    assert failures == []


def test_demo_environment_declares_critical_demo_routes() -> None:
    checker = load_check_module()

    required_paths = checker.required_openapi_paths()

    assert "/health" in required_paths
    assert "/ready" in required_paths
    assert "/identity/oidc/readiness" in required_paths
    assert "/identity/oidc/onboarding" in required_paths
    assert "/identity/oidc/logout" in required_paths
    assert "/demo/manufacturing/operations/snapshot" in required_paths
    assert "/demo/manufacturing/connectors/evidence-invariants/snapshots/export-requests" in (
        required_paths
    )


def test_demo_static_checks_include_backup_restore_contract() -> None:
    checker = load_check_module()

    results = checker.run_static_checks(REPO_ROOT)
    names = {result.name for result in results}

    assert "makefile.backup_restore_targets" in names
    assert "docs.backup_restore_runbook" in names


def test_demo_static_checks_include_guided_local_keycloak_sso_contract() -> None:
    checker = load_check_module()

    results = checker.run_static_checks(REPO_ROOT)
    names = {result.name for result in results}

    assert "docker.keycloak_realm_import" in names
    assert "docker.keycloak_local_realm_contract" in names
    assert "makefile.local_sso_targets" in names
    assert "docs.local_sso_runbook" in names


def test_demo_verify_runs_profile_render_gate() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "demo-verify: openapi-check demo-check deployment-profile-render-check" in makefile


def test_demo_makefile_declares_local_sso_api_target() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "demo-api-sso:" in makefile
    assert "AXIS_OIDC_CLIENT_ID=limes-axis-web" in makefile
    assert "AXIS_OIDC_REDIRECT_URI=http://127.0.0.1:8000/identity/oidc/callback" in makefile
    assert "AXIS_OIDC_SESSION_COOKIE_SIGNING_SECRET=axis-local-demo-session-signing-key" in makefile


def test_local_keycloak_realm_maps_axis_demo_claims_and_scopes() -> None:
    realm_path = REPO_ROOT / "infra" / "docker" / "keycloak" / "axis-realm.json"
    realm = json.loads(realm_path.read_text(encoding="utf-8"))

    assert realm["realm"] == "axis"
    client = next(client for client in realm["clients"] if client["clientId"] == "limes-axis-web")
    assert "http://127.0.0.1:8000/identity/oidc/callback" in client["redirectUris"]
    assert "http://127.0.0.1:3000/*" in client["webOrigins"]
    mapper_names = {mapper["name"] for mapper in client["protocolMappers"]}
    assert {"axis_tenant", "limes-axis-api-audience"} <= mapper_names

    role_names = {role["name"] for role in realm["roles"]["realm"]}
    assert {
        "audit:read",
        "briefs:generate",
        "maintenance:read",
        "notifications:acknowledge",
        "quality:read",
        "supply:read",
        "workflows:read",
    } <= role_names
    user = next(user for user in realm["users"] if user["username"] == "axis-operator")
    assert user["attributes"]["axis_tenant"] == ["tenant_demo_manufacturing"]
    assert "axis-local-demo-operator" in user["realmRoles"]


def test_demo_readiness_checklist_mentions_profile_render_gate() -> None:
    docs = (REPO_ROOT / "docs" / "demo-readiness.md").read_text(encoding="utf-8")

    assert "`make deployment-profile-render-check`" in docs
    assert "profile render gate" in docs


def test_demo_live_checks_include_browser_no_store_cors_preflight(monkeypatch) -> None:
    checker = load_check_module()
    cors_origins: list[str] = []

    monkeypatch.setattr(checker, "_fetch_json", lambda _url: (True, "HTTP 200"))
    monkeypatch.setattr(
        checker,
        "_fetch_operations_snapshot",
        lambda _api_url: (True, "snapshot includes persisted operations"),
        raising=False,
    )
    monkeypatch.setattr(checker, "_fetch_text", lambda _url: (True, "HTTP 200"))

    def fake_cors_check(_api_url: str, web_url: str) -> tuple[bool, str]:
        cors_origins.append(web_url)
        return True, "HTTP 200"

    monkeypatch.setattr(
        checker,
        "_fetch_cors_no_store_preflight",
        fake_cors_check,
        raising=False,
    )

    results = checker.run_live_checks("http://127.0.0.1:8000", "http://127.0.0.1:3000")

    assert any(result.name == "live.api_cors_no_store_preflight" for result in results)
    assert any(result.name == "live.api_oidc_onboarding" for result in results)
    assert "http://localhost:3100" in cors_origins
    assert "http://127.0.0.1:3100" in cors_origins


def test_demo_live_checks_include_operations_snapshot_contract(monkeypatch) -> None:
    checker = load_check_module()

    monkeypatch.setattr(checker, "_fetch_json", lambda _url: (True, "HTTP 200"))
    monkeypatch.setattr(
        checker,
        "_fetch_operations_snapshot",
        lambda _api_url: (True, "snapshot includes persisted operations"),
        raising=False,
    )

    results = checker.run_live_checks("http://127.0.0.1:8000", None)

    assert any(result.name == "live.api_operations_snapshot" for result in results)


def test_demo_live_checks_include_demo_readiness_contract(monkeypatch) -> None:
    checker = load_check_module()

    monkeypatch.setattr(checker, "_fetch_json", lambda _url: (True, "HTTP 200"))
    monkeypatch.setattr(
        checker,
        "_fetch_operations_snapshot",
        lambda _api_url: (True, "snapshot includes persisted operations"),
        raising=False,
    )
    monkeypatch.setattr(
        checker,
        "_fetch_demo_readiness_report",
        lambda _api_url: (True, "readiness derived from persisted evidence"),
        raising=False,
    )

    results = checker.run_live_checks("http://127.0.0.1:8000", None)

    assert any(result.name == "live.api_demo_readiness" for result in results)


def test_demo_live_checks_include_oidc_readiness_contract(monkeypatch) -> None:
    checker = load_check_module()

    monkeypatch.setattr(checker, "_fetch_json", lambda _url: (True, "HTTP 200"))
    monkeypatch.setattr(
        checker,
        "_fetch_operations_snapshot",
        lambda _api_url: (True, "snapshot includes persisted operations"),
        raising=False,
    )
    monkeypatch.setattr(
        checker,
        "_fetch_demo_readiness_report",
        lambda _api_url: (True, "readiness derived from persisted evidence"),
        raising=False,
    )
    monkeypatch.setattr(
        checker,
        "_fetch_oidc_readiness_report",
        lambda _api_url: (True, "OIDC readiness is explicit"),
        raising=False,
    )

    results = checker.run_live_checks("http://127.0.0.1:8000", None)

    assert any(result.name == "live.api_oidc_readiness" for result in results)


def test_demo_environment_declares_deployment_readiness_route() -> None:
    checker = load_check_module()

    required_paths = checker.required_openapi_paths()

    assert "/deployment/readiness" in required_paths


def test_demo_live_checks_include_deployment_readiness_contract(monkeypatch) -> None:
    checker = load_check_module()

    monkeypatch.setattr(checker, "_fetch_json", lambda _url: (True, "HTTP 200"))
    monkeypatch.setattr(
        checker,
        "_fetch_operations_snapshot",
        lambda _api_url: (True, "snapshot includes persisted operations"),
        raising=False,
    )
    monkeypatch.setattr(
        checker,
        "_fetch_demo_readiness_report",
        lambda _api_url: (True, "readiness derived from persisted evidence"),
        raising=False,
    )
    monkeypatch.setattr(
        checker,
        "_fetch_oidc_readiness_report",
        lambda _api_url: (True, "OIDC readiness is explicit"),
        raising=False,
    )
    monkeypatch.setattr(
        checker,
        "_fetch_deployment_readiness_report",
        lambda _api_url: (True, "deployment readiness is explicit"),
        raising=False,
    )

    results = checker.run_live_checks("http://127.0.0.1:8000", None)

    assert any(result.name == "live.api_deployment_readiness" for result in results)


def test_deployment_readiness_live_check_allows_public_safe_secret_capability_names(
    monkeypatch,
) -> None:
    checker = load_check_module()

    payload = {
        "status": "action_required",
        "production_ready": False,
        "demo_safe": True,
        "profile": "local_demo",
        "production_blockers": ["oidc_secure_cookie_session"],
        "capabilities": {
            "object_store_adapter": "local_filesystem",
            "object_store_worm_retention_enabled": False,
            "object_store_retention_days": 0,
            "object_store_retention_mode": "GOVERNANCE",
            "oidc_session_cookie_signing_secret_configured": False,
            "object_store_credentials_configured": False,
        },
        "checks": [
            {
                "check_id": "oidc_secure_cookie_session",
                "status": "action_required",
                "production_required": True,
                "detail": "OIDC browser sessions need an operator-provided signing secret.",
            },
            {
                "check_id": "production_object_store_adapter",
                "status": "action_required",
                "production_required": True,
                "detail": "S3/MinIO WORM retention is not production-ready; missing credentials.",
            },
            {
                "check_id": "api_rate_limiting",
                "status": "action_required",
                "production_required": True,
                "detail": "API rate limiting is not enabled.",
            },
            {
                "check_id": "network_egress_restricted",
                "status": "action_required",
                "production_required": True,
                "detail": "Network egress is not production-restricted.",
            },
            {
                "check_id": "deployment_tenancy_profile",
                "status": "action_required",
                "production_required": True,
                "detail": "Deployment tenancy profile is incomplete.",
            },
        ],
    }

    class FakeResponse:
        status = 200

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr(checker, "urlopen", lambda *_args, **_kwargs: FakeResponse())

    ok, detail = checker._fetch_deployment_readiness_report("http://127.0.0.1:8000")

    assert ok is True
    assert detail == "HTTP 200, local_demo production_ready=False"


def test_deployment_readiness_live_check_rejects_token_material_values(
    monkeypatch,
) -> None:
    checker = load_check_module()

    payload = {
        "status": "action_required",
        "production_ready": False,
        "demo_safe": True,
        "profile": "local_demo",
        "production_blockers": ["oidc_secure_cookie_session"],
        "capabilities": {
            "object_store_adapter": "local_filesystem",
            "object_store_worm_retention_enabled": False,
            "object_store_retention_days": 0,
            "object_store_retention_mode": "GOVERNANCE",
        },
        "checks": [
            {
                "check_id": str(index),
                "status": "action_required",
                "production_required": True,
                "detail": "Leaked access_token value should fail the public-safe check.",
            }
            for index in range(5)
        ],
    }

    class FakeResponse:
        status = 200

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr(checker, "urlopen", lambda *_args, **_kwargs: FakeResponse())

    ok, detail = checker._fetch_deployment_readiness_report("http://127.0.0.1:8000")

    assert ok is False
    assert detail == "HTTP 200, invalid deployment readiness contract"


def test_demo_environment_declares_support_diagnostics_route() -> None:
    checker = load_check_module()

    required_paths = checker.required_openapi_paths()

    assert "/support/diagnostics" in required_paths


def test_demo_live_checks_include_support_diagnostics_contract(monkeypatch) -> None:
    checker = load_check_module()

    monkeypatch.setattr(checker, "_fetch_json", lambda _url: (True, "HTTP 200"))
    monkeypatch.setattr(
        checker,
        "_fetch_operations_snapshot",
        lambda _api_url: (True, "snapshot includes persisted operations"),
        raising=False,
    )
    monkeypatch.setattr(
        checker,
        "_fetch_demo_readiness_report",
        lambda _api_url: (True, "readiness derived from persisted evidence"),
        raising=False,
    )
    monkeypatch.setattr(
        checker,
        "_fetch_oidc_readiness_report",
        lambda _api_url: (True, "OIDC readiness is explicit"),
        raising=False,
    )
    monkeypatch.setattr(
        checker,
        "_fetch_deployment_readiness_report",
        lambda _api_url: (True, "deployment readiness is explicit"),
        raising=False,
    )
    monkeypatch.setattr(
        checker,
        "_fetch_support_diagnostics_report",
        lambda _api_url: (True, "support diagnostics are explicit"),
        raising=False,
    )

    results = checker.run_live_checks("http://127.0.0.1:8000", None)

    assert any(result.name == "live.api_support_diagnostics" for result in results)
