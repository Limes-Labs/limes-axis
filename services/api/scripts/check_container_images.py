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


def required_container_files() -> tuple[str, ...]:
    return (
        ".dockerignore",
        "services/api/Dockerfile",
        "apps/web/Dockerfile",
    )


def required_api_dockerfile_terms() -> tuple[str, ...]:
    return (
        "ghcr.io/astral-sh/uv:python3.12-bookworm-slim",
        "uv sync --frozen --no-dev --no-editable",
        "AXIS_ENV=production",
        "uvicorn axis_api.main:create_app --factory",
        "EXPOSE 8000",
        "USER 10001",
        "HEALTHCHECK",
    )


def required_web_dockerfile_terms() -> tuple[str, ...]:
    return (
        "node:24-bookworm-slim",
        "corepack prepare pnpm@10.28.0 --activate",
        "pnpm install --frozen-lockfile",
        "pnpm install --prod --frozen-lockfile",
        "NEXT_TELEMETRY_DISABLED=1",
        "next start",
        "EXPOSE 3000",
        "USER 10001",
        "HEALTHCHECK",
    )


def required_dockerignore_terms() -> tuple[str, ...]:
    return (
        ".git",
        ".axis/",
        "**/.venv/",
        "**/__pycache__/",
        "**/.pytest_cache/",
        "**/.ruff_cache/",
        "**/node_modules/",
        "**/.next/",
        "**/test-results/",
        ".env",
    )


def required_docs_terms() -> tuple[str, ...]:
    return (
        "make container-check",
        "make container-build-api",
        "make container-build-web",
        "not image provenance",
    )


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


def check_required_files(repo_root: Path) -> list[CheckResult]:
    missing = [
        relative for relative in required_container_files() if not (repo_root / relative).exists()
    ]
    return [
        CheckResult(
            "container.required_files",
            not missing,
            "required container files are present"
            if not missing
            else f"missing: {', '.join(missing)}",
        )
    ]


def check_api_dockerfile(repo_root: Path) -> list[CheckResult]:
    dockerfile = repo_root / "services" / "api" / "Dockerfile"
    if not dockerfile.exists():
        return [
            CheckResult(
                "container.api_dockerfile",
                False,
                "services/api/Dockerfile is missing.",
            )
        ]

    text = _read_text(dockerfile)
    single_line = " ".join(line.strip() for line in text.splitlines())
    missing = _missing_terms(single_line, required_api_dockerfile_terms())
    return [
        CheckResult(
            "container.api_dockerfile",
            not missing,
            "API image contract is explicit"
            if not missing
            else f"missing terms: {', '.join(missing)}",
        )
    ]


def check_web_dockerfile(repo_root: Path) -> list[CheckResult]:
    dockerfile = repo_root / "apps" / "web" / "Dockerfile"
    if not dockerfile.exists():
        return [CheckResult("container.web_dockerfile", False, "apps/web/Dockerfile is missing.")]

    text = _read_text(dockerfile)
    single_line = " ".join(line.strip() for line in text.splitlines())
    missing = _missing_terms(single_line, required_web_dockerfile_terms())
    return [
        CheckResult(
            "container.web_dockerfile",
            not missing,
            "web image contract is explicit"
            if not missing
            else f"missing terms: {', '.join(missing)}",
        )
    ]


def check_dockerignore(repo_root: Path) -> list[CheckResult]:
    dockerignore = repo_root / ".dockerignore"
    if not dockerignore.exists():
        return [CheckResult("container.dockerignore", False, ".dockerignore is missing.")]

    text = _read_text(dockerignore)
    missing = _missing_terms(text, required_dockerignore_terms())
    return [
        CheckResult(
            "container.dockerignore",
            not missing,
            "Docker build context excludes local state and generated artifacts"
            if not missing
            else f"missing terms: {', '.join(missing)}",
        )
    ]


def check_make_targets(repo_root: Path) -> list[CheckResult]:
    makefile = repo_root / "Makefile"
    if not makefile.exists():
        return [CheckResult("container.make_targets", False, "Makefile is missing.")]

    required_targets = {"container-check", "container-build-api", "container-build-web"}
    targets = _make_targets(_read_text(makefile))
    missing = sorted(required_targets - targets)
    return [
        CheckResult(
            "container.make_targets",
            not missing,
            "container Makefile targets are present"
            if not missing
            else f"missing targets: {', '.join(missing)}",
        )
    ]


def check_docs(repo_root: Path) -> list[CheckResult]:
    docs = repo_root / "docs" / "deployment.md"
    readme = repo_root / "README.md"
    plan = repo_root / "plan.md"
    results: list[CheckResult] = []

    if not docs.exists():
        results.append(CheckResult("container.docs", False, "docs/deployment.md is missing."))
    else:
        text = _read_text(docs)
        missing = _missing_terms(text, required_docs_terms())
        results.append(
            CheckResult(
                "container.docs",
                not missing,
                "deployment docs include container build boundaries"
                if not missing
                else f"missing terms: {', '.join(missing)}",
            )
        )

    for name, path, term in (
        ("container.readme_link", readme, "container-check"),
        ("container.plan_tracking", plan, "Add buildable API and web container image baseline"),
    ):
        if not path.exists():
            results.append(CheckResult(name, False, f"{path.name} is missing."))
            continue
        text = _read_text(path)
        results.append(
            CheckResult(
                name,
                term.casefold() in text.casefold(),
                f"{path.name} references {term}"
                if term.casefold() in text.casefold()
                else f"{path.name} does not reference {term}",
            )
        )
    return results


def run_static_checks(repo_root: Path) -> list[CheckResult]:
    repo_root = repo_root.resolve()
    checks: list[CheckResult] = []
    checks.extend(check_required_files(repo_root))
    checks.extend(check_api_dockerfile(repo_root))
    checks.extend(check_web_dockerfile(repo_root))
    checks.extend(check_dockerignore(repo_root))
    checks.extend(check_make_targets(repo_root))
    checks.extend(check_docs(repo_root))
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
    parser = argparse.ArgumentParser(description="Check Limes Axis container image package.")
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
