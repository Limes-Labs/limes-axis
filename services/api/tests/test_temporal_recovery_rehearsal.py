from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "services" / "api" / "scripts" / "rehearse_temporal_recovery.py"


def load_rehearsal_module():
    assert SCRIPT.exists(), "Temporal recovery rehearsal script is missing"
    spec = importlib.util.spec_from_file_location("rehearse_temporal_recovery", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_temporal_recovery_rehearsal_builds_read_only_evidence_steps() -> None:
    rehearsal = load_rehearsal_module()

    config = rehearsal.TemporalRecoveryRehearsalConfig(
        namespace="axis-prod",
        kube_context="prod-eu",
        runtime_config_map="axis-config",
        runtime_secret="axis-runtime",
        recovery_secret="axis-temporal-recovery",
        recovery_id="20260702T180000Z",
        local_evidence_dir=Path(".axis/temporal-recovery/20260702T180000Z"),
        image="registry.example.com/platform/temporal-cli:stable",
        timeout="19m",
    )

    steps = rehearsal.build_rehearsal_steps(config)
    command_lines = [rehearsal.format_command(step.command) for step in steps]
    manifest = rehearsal.build_pod_manifest(config)
    manifest_payload = json.loads(manifest)
    pod_spec = manifest_payload["spec"]
    container = pod_spec["containers"][0]
    script = container["args"][0]

    assert "axis-temporal-recovery-20260702t180000z" in manifest
    assert "registry.example.com/platform/temporal-cli:stable" in manifest
    assert pod_spec["securityContext"]["runAsNonRoot"] is True
    assert pod_spec["securityContext"]["runAsUser"] == 10001
    assert pod_spec["securityContext"]["runAsGroup"] == 10001
    assert pod_spec["securityContext"]["fsGroup"] == 10001
    assert pod_spec["volumes"] == [{"name": "temporal-recovery", "emptyDir": {}}]
    assert container["volumeMounts"] == [
        {"name": "temporal-recovery", "mountPath": "/temporal-recovery"}
    ]
    assert container["envFrom"] == [
        {"configMapRef": {"name": "axis-config"}},
        {"secretRef": {"name": "axis-runtime"}},
        {"secretRef": {"name": "axis-temporal-recovery"}},
    ]
    assert "while true" in script
    assert any(
        "kubectl --context prod-eu -n axis-prod get configmap axis-config" in line
        for line in command_lines
    )
    assert any(
        "kubectl --context prod-eu -n axis-prod get secret axis-runtime" in line
        for line in command_lines
    )
    assert any(
        "kubectl --context prod-eu -n axis-prod get secret axis-temporal-recovery"
        in line
        for line in command_lines
    )
    assert any("temporal-recovery-target" in line and "isolated" in line for line in command_lines)
    assert any("AXIS_TEMPORAL_ADDRESS" in line for line in command_lines)
    assert any("AXIS_TEMPORAL_NAMESPACE" in line for line in command_lines)
    assert any("AXIS_TEMPORAL_RECOVERY_WORKFLOW_ID" in line for line in command_lines)
    assert any("--help" in line and "temporal.cli.help" in line for line in command_lines)
    assert any("operator cluster health" in line for line in command_lines)
    assert any("operator namespace describe" in line for line in command_lines)
    assert any("workflow list" in line for line in command_lines)
    assert any("workflow show" in line for line in command_lines)
    assert any("--output json" in line for line in command_lines)
    assert any("temporal.namespace.json" in line for line in command_lines)
    assert any("temporal.workflow-list.json" in line for line in command_lines)
    assert any("temporal.workflow-history.json" in line for line in command_lines)
    assert any("temporal.sha256" in line for line in command_lines)
    assert all("temporal-api-key" not in line for line in command_lines)
    assert "temporal-api-key" not in manifest


def test_temporal_recovery_rehearsal_plan_prints_without_executing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rehearsal = load_rehearsal_module()
    executed: list[object] = []
    monkeypatch.setattr(rehearsal, "run_rehearsal", lambda steps: executed.extend(steps))

    result = rehearsal.main(
        [
            "--plan",
            "--namespace",
            "axis-prod",
            "--context",
            "prod-eu",
            "--runtime-config-map",
            "axis-config",
            "--runtime-secret",
            "axis-runtime",
            "--recovery-secret",
            "axis-temporal-recovery",
            "--recovery-id",
            "20260702T180000Z",
            "--image",
            "registry.example.com/platform/temporal-cli:stable",
        ]
    )

    output = capsys.readouterr().out
    assert result == 0
    assert executed == []
    assert "operator cluster health" in output
    assert "operator namespace describe" in output
    assert "workflow list" in output
    assert "workflow show" in output
    assert "AXIS_TEMPORAL_RECOVERY_WORKFLOW_ID" in output
    assert "temporal-api-key" not in output


def test_temporal_recovery_rehearsal_rejects_unsafe_or_runtime_recovery_inputs() -> None:
    rehearsal = load_rehearsal_module()

    with pytest.raises(ValueError, match="recovery_id"):
        rehearsal.TemporalRecoveryRehearsalConfig(recovery_id="bad;rm-rf")

    with pytest.raises(ValueError, match="namespace"):
        rehearsal.TemporalRecoveryRehearsalConfig(namespace="axis prod")

    with pytest.raises(ValueError, match="recovery_secret"):
        rehearsal.TemporalRecoveryRehearsalConfig(recovery_secret="limes-axis-runtime")

    with pytest.raises(ValueError, match="recovery_secret"):
        rehearsal.TemporalRecoveryRehearsalConfig(
            runtime_secret="axis-runtime",
            recovery_secret="axis-runtime",
        )

    with pytest.raises(ValueError, match="run_as_user"):
        rehearsal.TemporalRecoveryRehearsalConfig(run_as_user=0)

    with pytest.raises(ValueError, match="image"):
        rehearsal.TemporalRecoveryRehearsalConfig(image="")


def test_temporal_recovery_rehearsal_cli_reports_invalid_inputs_without_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rehearsal = load_rehearsal_module()

    result = rehearsal.main(["--plan", "--recovery-id", "bad;rm-rf"])

    captured = capsys.readouterr()
    assert result == 2
    assert "recovery_id" in captured.err
    assert "Traceback" not in captured.err


def test_temporal_recovery_rehearsal_execute_requires_temporal_cli_image(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rehearsal = load_rehearsal_module()

    result = rehearsal.main(["--execute"])

    captured = capsys.readouterr()
    assert result == 2
    assert "Temporal CLI" in captured.err
    assert "Traceback" not in captured.err
