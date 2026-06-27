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
    assert "/demo/manufacturing/operations/snapshot" in required_paths
    assert "/demo/manufacturing/connectors/evidence-invariants/snapshots/export-requests" in (
        required_paths
    )
