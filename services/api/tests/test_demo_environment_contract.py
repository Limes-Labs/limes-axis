from __future__ import annotations

import importlib.util
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
