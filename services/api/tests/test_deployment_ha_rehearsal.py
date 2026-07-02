from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "services" / "api" / "scripts" / "rehearse_ha_restart.py"


def load_ha_module():
    assert SCRIPT.exists(), "HA restart rehearsal script is missing"
    spec = importlib.util.spec_from_file_location("rehearse_ha_restart", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ha_rehearsal_builds_real_restart_validation_sequence() -> None:
    rehearsal = load_ha_module()

    config = rehearsal.RehearsalConfig(
        release="axis-prod",
        namespace="axis",
        kube_context="prod-eu",
        timeout="8m",
        ready_url="https://api.axis.example.com/ready",
        require_hpa=True,
        require_pdb=True,
        run_helm_tests=True,
    )

    steps = rehearsal.build_rehearsal_steps(config)
    commands = [step.command for step in steps if step.command is not None]
    readiness_steps = [step.ready_url for step in steps if step.ready_url is not None]

    assert (
        "kubectl",
        "--context",
        "prod-eu",
        "-n",
        "axis",
        "get",
        "hpa/axis-prod-api",
        "hpa/axis-prod-web",
    ) in commands
    assert (
        "kubectl",
        "--context",
        "prod-eu",
        "-n",
        "axis",
        "get",
        "pdb/axis-prod-api",
        "pdb/axis-prod-web",
    ) in commands
    assert (
        "kubectl",
        "--context",
        "prod-eu",
        "-n",
        "axis",
        "rollout",
        "restart",
        "deployment/axis-prod-api",
    ) in commands
    assert (
        "kubectl",
        "--context",
        "prod-eu",
        "-n",
        "axis",
        "wait",
        "--for=condition=available",
        "deployment/axis-prod-api",
        "--timeout=8m",
    ) in commands
    assert (
        "kubectl",
        "--context",
        "prod-eu",
        "-n",
        "axis",
        "rollout",
        "status",
        "deployment/axis-prod-web",
        "--timeout=8m",
    ) in commands
    assert (
        "helm",
        "test",
        "axis-prod",
        "--namespace",
        "axis",
        "--timeout",
        "8m",
        "--kube-context",
        "prod-eu",
    ) in commands
    assert readiness_steps == [
        "https://api.axis.example.com/ready",
        "https://api.axis.example.com/ready",
    ]


def test_ha_rehearsal_plan_prints_commands_without_executing(monkeypatch, capsys) -> None:
    rehearsal = load_ha_module()
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
            "axis-prod",
            "--namespace",
            "axis",
            "--context",
            "prod-eu",
            "--timeout",
            "8m",
            "--ready-url",
            "https://api.axis.example.com/ready",
            "--require-hpa",
            "--require-pdb",
        ]
    )

    output = capsys.readouterr().out
    assert result == 0
    assert executed == []
    assert "kubectl --context prod-eu -n axis rollout restart deployment/axis-prod-api" in output
    assert "kubectl --context prod-eu -n axis wait --for=condition=available" in output
    assert "kubectl --context prod-eu -n axis get hpa/axis-prod-api hpa/axis-prod-web" in output
    assert "kubectl --context prod-eu -n axis get pdb/axis-prod-api pdb/axis-prod-web" in output
    assert "helm test axis-prod --namespace axis --timeout 8m --kube-context prod-eu" in output
