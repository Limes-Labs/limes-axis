from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECK_SCRIPT = REPO_ROOT / "services" / "api" / "scripts" / "check_deployment_package.py"


def load_check_module():
    assert CHECK_SCRIPT.exists(), "deployment package checker is missing"
    spec = importlib.util.spec_from_file_location("check_deployment_package", CHECK_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_deployment_package_static_contract_passes() -> None:
    checker = load_check_module()

    results = checker.run_static_checks(REPO_ROOT)

    failures = [f"{result.name}: {result.detail}" for result in results if not result.ok]
    assert failures == []


def test_deployment_package_declares_critical_chart_files() -> None:
    checker = load_check_module()

    required_files = checker.required_chart_files()

    assert "infra/helm/limes-axis/Chart.yaml" in required_files
    assert "infra/helm/limes-axis/values.yaml" in required_files
    assert "infra/helm/limes-axis/templates/api-deployment.yaml" in required_files
    assert "infra/helm/limes-axis/templates/api-service.yaml" in required_files
    assert "infra/helm/limes-axis/templates/web-deployment.yaml" in required_files
    assert "infra/helm/limes-axis/templates/web-service.yaml" in required_files
    assert "infra/helm/limes-axis/templates/configmap.yaml" in required_files
    assert "infra/helm/limes-axis/templates/secret-example.yaml" in required_files
    assert "infra/helm/limes-axis/templates/networkpolicy.yaml" in required_files
    assert "infra/helm/limes-axis/templates/NOTES.txt" in required_files


def test_deployment_package_externalizes_state_and_secrets() -> None:
    checker = load_check_module()

    required_terms = checker.required_chart_terms()

    assert "AXIS_POSTGRES_DSN" in required_terms
    assert "AXIS_TYPEDB_ADDRESS" in required_terms
    assert "AXIS_TEMPORAL_ADDRESS" in required_terms
    assert "AXIS_CONNECTOR_EXPORT_OBJECT_STORE_ROOT" in required_terms
    assert "AXIS_OIDC_ISSUER" in required_terms
    assert "existingSecret" in required_terms
    assert "REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE" in required_terms


def test_deployment_docs_are_public_safe_and_do_not_claim_certification() -> None:
    checker = load_check_module()

    required_terms = checker.required_docs_terms()

    assert "helm upgrade --install" in required_terms
    assert "external Postgres" in required_terms
    assert "OIDC" in required_terms
    assert "S3/MinIO WORM" in required_terms
    assert "not a production certification" in required_terms
