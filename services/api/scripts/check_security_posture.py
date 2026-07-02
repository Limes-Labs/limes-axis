from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import NamedTuple


class CheckResult(NamedTuple):
    name: str
    ok: bool
    detail: str


def required_threat_model_sections() -> tuple[str, ...]:
    return (
        "## Executive Summary",
        "## Scope And Assumptions",
        "## System Model",
        "## Assets",
        "## Trust Boundaries",
        "## Entry Points",
        "## Attacker Model",
        "## Threats And Abuse Paths",
        "## Existing Controls",
        "## Open Risks And Next Hardening Work",
        "## Focus Paths For Security Review",
        "## Review Cadence",
    )


def required_boundary_terms() -> tuple[str, ...]:
    return (
        "/identity/oidc/readiness",
        "/identity/oidc/authorize",
        "/identity/oidc/callback",
        "/demo/manufacturing/operations/snapshot",
        "/demo/manufacturing/connectors",
        "Postgres",
        "TypeDB",
        "Temporal",
        "MinIO",
        "Keycloak",
        "connector credential leases",
        "external model egress",
        "append-only audit",
        "OpenAPI",
    )


def required_threat_ids() -> tuple[str, ...]:
    return tuple(f"TM-{index:03d}" for index in range(1, 7))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _make_targets(makefile_text: str) -> set[str]:
    return {
        match.group(1)
        for match in re.finditer(r"^([A-Za-z0-9_.-]+):(?:\s|$)", makefile_text, re.MULTILINE)
    }


def _missing_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    normalized = text.casefold()
    return [term for term in terms if term.casefold() not in normalized]


def check_make_target(repo_root: Path) -> list[CheckResult]:
    makefile = repo_root / "Makefile"
    if not makefile.exists():
        return [CheckResult("security.make_target", False, "Makefile is missing.")]

    targets = _make_targets(_read_text(makefile))
    return [
        CheckResult(
            "security.make_target",
            "security-check" in targets,
            "security-check target is present"
            if "security-check" in targets
            else "Makefile is missing security-check target",
        )
    ]


def check_threat_model_document(repo_root: Path) -> list[CheckResult]:
    threat_model = repo_root / "docs" / "threat-model.md"
    if not threat_model.exists():
        return [CheckResult("security.threat_model", False, "docs/threat-model.md is missing.")]

    text = _read_text(threat_model)
    missing_sections = _missing_terms(text, required_threat_model_sections())
    missing_boundaries = _missing_terms(text, required_boundary_terms())
    missing_threat_ids = _missing_terms(text, required_threat_ids())
    mermaid_present = "```mermaid" in text and "flowchart" in text
    explicit_non_claim = "not a production certification" in text.casefold()

    results = [
        CheckResult(
            "security.threat_model.sections",
            not missing_sections,
            "threat model has required sections"
            if not missing_sections
            else f"missing sections: {', '.join(missing_sections)}",
        ),
        CheckResult(
            "security.threat_model.boundaries",
            not missing_boundaries,
            "threat model covers core Axis boundaries"
            if not missing_boundaries
            else f"missing boundary terms: {', '.join(missing_boundaries)}",
        ),
        CheckResult(
            "security.threat_model.threat_ids",
            not missing_threat_ids,
            "threat model includes stable threat IDs"
            if not missing_threat_ids
            else f"missing threat IDs: {', '.join(missing_threat_ids)}",
        ),
        CheckResult(
            "security.threat_model.diagram",
            mermaid_present,
            "threat model includes a Mermaid system diagram"
            if mermaid_present
            else "threat model is missing Mermaid diagram",
        ),
        CheckResult(
            "security.threat_model.non_claim",
            explicit_non_claim,
            "threat model avoids production certification claims"
            if explicit_non_claim
            else "threat model must say it is not a production certification",
        ),
    ]
    return results


def check_public_docs_links(repo_root: Path) -> list[CheckResult]:
    checks: list[CheckResult] = []
    readme = repo_root / "README.md"
    plan = repo_root / "plan.md"
    demo_readiness = repo_root / "docs" / "demo-readiness.md"

    for name, path, expected in (
        ("security.readme_link", readme, "docs/threat-model.md"),
        ("security.plan_tracking", plan, "Add initial security review and threat model"),
        ("security.demo_readiness_link", demo_readiness, "threat model"),
    ):
        if not path.exists():
            checks.append(CheckResult(name, False, f"{path.name} is missing."))
            continue
        text = _read_text(path)
        checks.append(
            CheckResult(
                name,
                expected.casefold() in text.casefold(),
                f"{path.name} references {expected}"
                if expected.casefold() in text.casefold()
                else f"{path.name} does not reference {expected}",
            )
        )
    return checks


def run_static_checks(repo_root: Path) -> list[CheckResult]:
    repo_root = repo_root.resolve()
    checks: list[CheckResult] = []
    checks.extend(check_make_target(repo_root))
    checks.extend(check_threat_model_document(repo_root))
    checks.extend(check_public_docs_links(repo_root))
    return checks


def _print_results(results: list[CheckResult], *, json_output: bool) -> None:
    if json_output:
        print(
            json.dumps(
                [
                    {"name": result.name, "ok": result.ok, "detail": result.detail}
                    for result in results
                ],
                indent=2,
                sort_keys=True,
            )
        )
        return

    for result in results:
        status = "OK" if result.ok else "FAIL"
        print(f"[{status}] {result.name}: {result.detail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Limes Axis security posture docs.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="Repository root to inspect.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)

    results = run_static_checks(args.repo_root)
    _print_results(results, json_output=args.json)
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
