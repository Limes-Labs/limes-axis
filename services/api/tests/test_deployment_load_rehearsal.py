from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "services" / "api" / "scripts" / "rehearse_load.py"


def load_load_module():
    assert SCRIPT.exists(), "load rehearsal script is missing"
    spec = importlib.util.spec_from_file_location("rehearse_load", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_rehearsal_builds_real_fortio_job_sequence() -> None:
    rehearsal = load_load_module()

    config = rehearsal.RehearsalConfig(
        release="axis-prod",
        namespace="axis",
        kube_context="prod-eu",
        duration="90s",
        qps=25,
        connections=5,
        timeout="8m",
        image="fortio/fortio:1.69.3",
        targets=(
            rehearsal.LoadTarget(name="api-ready", url="http://axis-prod-api:8000/ready"),
            rehearsal.LoadTarget(name="web-home", url="http://axis-prod-web:3000/"),
        ),
    )

    steps = rehearsal.build_rehearsal_steps(config)
    commands = [step.command for step in steps if step.command is not None]

    assert (
        "kubectl",
        "--context",
        "prod-eu",
        "-n",
        "axis",
        "delete",
        "job",
        "axis-prod-load-api-ready",
        "--ignore-not-found=true",
    ) in commands
    assert (
        "kubectl",
        "--context",
        "prod-eu",
        "-n",
        "axis",
        "create",
        "job",
        "axis-prod-load-api-ready",
        "--image=fortio/fortio:1.69.3",
        "--",
        "load",
        "-quiet",
        "-qps",
        "25",
        "-c",
        "5",
        "-t",
        "90s",
        "http://axis-prod-api:8000/ready",
    ) in commands
    assert (
        "kubectl",
        "--context",
        "prod-eu",
        "-n",
        "axis",
        "wait",
        "--for=condition=complete",
        "job/axis-prod-load-web-home",
        "--timeout=8m",
    ) in commands
    assert (
        "kubectl",
        "--context",
        "prod-eu",
        "-n",
        "axis",
        "logs",
        "job/axis-prod-load-web-home",
    ) in commands
    assert (
        "kubectl",
        "--context",
        "prod-eu",
        "-n",
        "axis",
        "delete",
        "job",
        "axis-prod-load-web-home",
    ) in commands


def test_load_rehearsal_plan_prints_commands_without_executing(monkeypatch, capsys) -> None:
    rehearsal = load_load_module()
    executed: list[object] = []

    monkeypatch.setattr(rehearsal, "run_command_step", lambda step: executed.append(step))

    result = rehearsal.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--plan",
            "--release",
            "axis-prod",
            "--namespace",
            "axis",
            "--context",
            "prod-eu",
            "--duration",
            "90s",
            "--qps",
            "25",
            "--connections",
            "5",
            "--target",
            "api-ready=http://axis-prod-api:8000/ready",
            "--target",
            "web-home=http://axis-prod-web:3000/",
        ]
    )

    output = capsys.readouterr().out
    assert result == 0
    assert executed == []
    assert "kubectl --context prod-eu -n axis create job axis-prod-load-api-ready" in output
    assert "fortio/fortio" in output
    assert "http://axis-prod-api:8000/ready" in output
    assert "kubectl --context prod-eu -n axis logs job/axis-prod-load-web-home" in output


def test_load_rehearsal_truncates_job_names_to_kubernetes_dns_limit() -> None:
    rehearsal = load_load_module()

    config = rehearsal.RehearsalConfig(
        release="axis-production-europe-west-manufacturing-reference-environment",
        namespace="axis",
        targets=(
            rehearsal.LoadTarget(
                name="very-long-customer-facing-ingress-readiness-target",
                url="http://axis-api:8000/ready",
            ),
        ),
    )

    steps = rehearsal.build_rehearsal_steps(config)
    create_commands = [step.command for step in steps if "create" in step.command]

    assert len(create_commands) == 1
    job_name = create_commands[0][create_commands[0].index("job") + 1]
    assert len(job_name) <= 63
    assert job_name == job_name.lower()
    assert job_name.strip("-") == job_name
    assert "-load-" in job_name


def test_load_rehearsal_rejects_invalid_load_parameters(capsys) -> None:
    rehearsal = load_load_module()

    result = rehearsal.main(["--repo-root", str(REPO_ROOT), "--plan", "--qps", "0"])

    error_output = capsys.readouterr().err
    assert result == 1
    assert "qps must be greater than zero" in error_output
