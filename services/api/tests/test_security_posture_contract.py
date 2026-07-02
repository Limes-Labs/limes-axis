from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECK_SCRIPT = REPO_ROOT / "services" / "api" / "scripts" / "check_security_posture.py"


def load_security_checker():
    spec = importlib.util.spec_from_file_location("check_security_posture", CHECK_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_security_posture_static_contract_passes() -> None:
    checker = load_security_checker()

    results = checker.run_static_checks(REPO_ROOT)

    failures = [f"{result.name}: {result.detail}" for result in results if not result.ok]
    assert failures == []


def test_security_posture_declares_required_threat_model_sections() -> None:
    checker = load_security_checker()

    sections = checker.required_threat_model_sections()

    assert "## Scope And Assumptions" in sections
    assert "## Assets" in sections
    assert "## Trust Boundaries" in sections
    assert "## Entry Points" in sections
    assert "## Threats And Abuse Paths" in sections
    assert "## Existing Controls" in sections
    assert "## Open Risks And Next Hardening Work" in sections


def test_security_posture_tracks_core_axis_boundaries() -> None:
    checker = load_security_checker()

    boundaries = checker.required_boundary_terms()

    assert "/identity/oidc/readiness" in boundaries
    assert "/identity/oidc/onboarding" in boundaries
    assert "/identity/oidc/logout" in boundaries
    assert "Postgres" in boundaries
    assert "TypeDB" in boundaries
    assert "Temporal" in boundaries
    assert "MinIO" in boundaries
    assert "connector credential leases" in boundaries
    assert "external model egress" in boundaries
