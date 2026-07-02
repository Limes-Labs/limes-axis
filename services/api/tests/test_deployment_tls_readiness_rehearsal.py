from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "services" / "api" / "scripts" / "rehearse_tls_readiness.py"


def load_tls_module():
    assert SCRIPT.exists(), "TLS readiness rehearsal script is missing"
    spec = importlib.util.spec_from_file_location("rehearse_tls_readiness", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tls_readiness_builds_real_ingress_cert_and_host_checks() -> None:
    rehearsal = load_tls_module()

    config = rehearsal.RehearsalConfig(
        release="axis-prod",
        namespace="axis",
        kube_context="prod-eu",
        ingress_name="axis-prod",
        tls_secret="axis-tls",
        certificate_name="axis-tls",
        issuer_name="letsencrypt-prod",
        issuer_kind="ClusterIssuer",
        timeout="8m",
        targets=(
            rehearsal.TlsTarget(host="axis.example.com", url="https://axis.example.com/"),
            rehearsal.TlsTarget(
                host="api.axis.example.com",
                url="https://api.axis.example.com/ready",
            ),
        ),
    )

    steps = rehearsal.build_rehearsal_steps(config)
    commands = [step.command for step in steps]

    assert (
        "kubectl",
        "--context",
        "prod-eu",
        "-n",
        "axis",
        "get",
        "ingress",
        "axis-prod",
        "-o",
        "wide",
    ) in commands
    assert (
        "kubectl",
        "--context",
        "prod-eu",
        "get",
        "clusterissuer",
        "letsencrypt-prod",
        "-o",
        "wide",
    ) in commands
    assert (
        "kubectl",
        "--context",
        "prod-eu",
        "-n",
        "axis",
        "wait",
        "--for=condition=Ready",
        "certificate/axis-tls",
        "--timeout=8m",
    ) in commands
    assert ("dig", "+short", "axis.example.com") in commands
    assert (
        "openssl",
        "s_client",
        "-servername",
        "axis.example.com",
        "-connect",
        "axis.example.com:443",
        "-brief",
    ) in commands
    assert (
        "curl",
        "--fail",
        "--silent",
        "--show-error",
        "--location",
        "--max-time",
        "10",
        "https://api.axis.example.com/ready",
    ) in commands


def test_tls_readiness_plan_prints_commands_without_executing(monkeypatch, capsys) -> None:
    rehearsal = load_tls_module()
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
            "--tls-secret",
            "axis-tls",
            "--issuer-name",
            "letsencrypt-prod",
            "--host",
            "axis.example.com=https://axis.example.com/",
            "--host",
            "api.axis.example.com=https://api.axis.example.com/ready",
        ]
    )

    output = capsys.readouterr().out
    assert result == 0
    assert executed == []
    assert "kubectl --context prod-eu -n axis get ingress axis-prod -o wide" in output
    assert "kubectl --context prod-eu -n axis get certificate axis-tls -o wide" in output
    assert "dig +short axis.example.com" in output
    assert "openssl s_client -servername axis.example.com" in output
    assert "curl --fail --silent --show-error --location" in output


def test_tls_readiness_rejects_non_https_targets(capsys) -> None:
    rehearsal = load_tls_module()

    result = rehearsal.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--plan",
            "--host",
            "axis.example.com=http://axis.example.com/",
        ]
    )

    error_output = capsys.readouterr().err
    assert result == 1
    assert "TLS readiness targets must use https://" in error_output
