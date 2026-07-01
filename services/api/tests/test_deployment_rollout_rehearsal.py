from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "services" / "api" / "scripts" / "rehearse_deployment_rollout.py"


def load_rollout_module():
    assert SCRIPT.exists(), "deployment rollout rehearsal script is missing"
    spec = importlib.util.spec_from_file_location("rehearse_deployment_rollout", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rollout_rehearsal_builds_real_cluster_command_sequence() -> None:
    rehearsal = load_rollout_module()

    config = rehearsal.RehearsalConfig(
        release="axis-canary",
        namespace="axis-prod",
        chart=Path("infra/helm/limes-axis"),
        kube_context="prod-eu",
        values=(Path("prod-values.yaml"),),
        set_values=("api.image.tag=canary",),
        timeout="7m",
        ready_url="https://api.axis.example.com/ready",
        rollback=True,
        rollback_revision=3,
    )

    steps = rehearsal.build_rehearsal_steps(config)
    commands = [step.command for step in steps if step.command is not None]
    readiness_steps = [step.ready_url for step in steps if step.ready_url is not None]

    assert (
        "helm",
        "upgrade",
        "--install",
        "axis-canary",
        "infra/helm/limes-axis",
        "--namespace",
        "axis-prod",
        "--create-namespace",
        "--wait",
        "--timeout",
        "7m",
        "--kube-context",
        "prod-eu",
        "--values",
        "prod-values.yaml",
        "--set",
        "api.image.tag=canary",
    ) in commands
    assert (
        "kubectl",
        "--context",
        "prod-eu",
        "-n",
        "axis-prod",
        "rollout",
        "status",
        "deployment/axis-canary-api",
        "--timeout=7m",
    ) in commands
    assert (
        "kubectl",
        "--context",
        "prod-eu",
        "-n",
        "axis-prod",
        "rollout",
        "status",
        "deployment/axis-canary-web",
        "--timeout=7m",
    ) in commands
    assert (
        "helm",
        "test",
        "axis-canary",
        "--namespace",
        "axis-prod",
        "--timeout",
        "7m",
        "--kube-context",
        "prod-eu",
    ) in commands
    assert (
        "helm",
        "rollback",
        "axis-canary",
        "3",
        "--namespace",
        "axis-prod",
        "--wait",
        "--timeout",
        "7m",
        "--kube-context",
        "prod-eu",
    ) in commands
    assert readiness_steps == [
        "https://api.axis.example.com/ready",
        "https://api.axis.example.com/ready",
    ]


def test_rollout_rehearsal_plan_prints_commands_without_executing(
    monkeypatch, capsys
) -> None:
    rehearsal = load_rollout_module()
    executed: list[object] = []

    monkeypatch.setattr(rehearsal, "run_command_step", lambda step: executed.append(step))
    monkeypatch.setattr(
        rehearsal, "wait_for_readiness_url", lambda url, timeout_seconds: executed.append(url)
    )

    result = rehearsal.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--plan",
            "--release",
            "axis-canary",
            "--namespace",
            "axis-prod",
            "--ready-url",
            "https://api.axis.example.com/ready",
            "--rollback",
            "--rollback-revision",
            "3",
        ]
    )

    output = capsys.readouterr().out
    assert result == 0
    assert executed == []
    assert "helm upgrade --install axis-canary" in output
    assert "kubectl -n axis-prod rollout status deployment/axis-canary-api" in output
    assert "helm test axis-canary" in output
    assert "helm rollback axis-canary 3" in output
    assert "https://api.axis.example.com/ready" in output
