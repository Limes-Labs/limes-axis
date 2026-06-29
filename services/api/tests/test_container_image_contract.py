from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECK_SCRIPT = REPO_ROOT / "services" / "api" / "scripts" / "check_container_images.py"


def load_check_module():
    assert CHECK_SCRIPT.exists(), "container image checker is missing"
    spec = importlib.util.spec_from_file_location("check_container_images", CHECK_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_container_image_static_contract_passes() -> None:
    checker = load_check_module()

    results = checker.run_static_checks(REPO_ROOT)

    failures = [f"{result.name}: {result.detail}" for result in results if not result.ok]
    assert failures == []


def test_container_image_package_declares_required_files() -> None:
    checker = load_check_module()

    required_files = checker.required_container_files()

    assert ".dockerignore" in required_files
    assert "services/api/Dockerfile" in required_files
    assert "apps/web/Dockerfile" in required_files


def test_container_image_package_declares_runtime_boundaries() -> None:
    checker = load_check_module()

    api_terms = checker.required_api_dockerfile_terms()
    web_terms = checker.required_web_dockerfile_terms()

    assert "uv sync --frozen --no-dev --no-editable" in api_terms
    assert "uvicorn axis_api.main:create_app --factory" in api_terms
    assert "EXPOSE 8000" in api_terms
    assert "USER 10001" in api_terms
    assert "HEALTHCHECK" in api_terms
    assert "pnpm install --frozen-lockfile" in web_terms
    assert "NEXT_TELEMETRY_DISABLED=1" in web_terms
    assert "next start" in web_terms
    assert "EXPOSE 3000" in web_terms
    assert "USER 10001" in web_terms
    assert "HEALTHCHECK" in web_terms
    assert "rm -rf /usr/local/lib/node_modules/npm" in web_terms
    assert "/usr/local/bin/npm" in web_terms
    assert "/usr/local/bin/npx" in web_terms


def test_container_docs_and_targets_are_tracked() -> None:
    checker = load_check_module()

    required_terms = checker.required_docs_terms()

    assert "make container-check" in required_terms
    assert "make container-build-api" in required_terms
    assert "make container-build-web" in required_terms
    assert "not image provenance" in required_terms
