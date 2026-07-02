from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "services" / "api" / "scripts" / "rehearse_secret_rotation.py"


def load_rehearsal_module():
    assert SCRIPT.exists(), "secret rotation rehearsal script is missing"
    spec = importlib.util.spec_from_file_location("rehearse_secret_rotation", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_secret_rotation_rehearsal_builds_staged_secret_comparison_steps() -> None:
    rehearsal = load_rehearsal_module()

    config = rehearsal.SecretRotationRehearsalConfig(
        namespace="axis-prod",
        kube_context="prod-eu",
        active_secret="axis-runtime",
        staged_secret="axis-runtime-next",
        rotation_id="20260702T210000Z",
        local_evidence_dir=Path(".axis/secret-rotation/20260702T210000Z"),
        image="registry.example.com/platform/busybox-coreutils:stable",
        timeout="11m",
    )

    steps = rehearsal.build_rehearsal_steps(config)
    command_lines = [rehearsal.format_command(step.command) for step in steps]
    manifest = rehearsal.build_pod_manifest(config)
    manifest_payload = json.loads(manifest)
    pod_spec = manifest_payload["spec"]
    container = pod_spec["containers"][0]

    assert "axis-secret-rotation-20260702t210000z" in manifest
    assert "registry.example.com/platform/busybox-coreutils:stable" in manifest
    assert pod_spec["securityContext"]["runAsNonRoot"] is True
    assert pod_spec["securityContext"]["runAsUser"] == 10001
    assert pod_spec["securityContext"]["runAsGroup"] == 10001
    assert pod_spec["securityContext"]["fsGroup"] == 10001
    assert pod_spec["volumes"] == [
        {"name": "active-secret", "secret": {"defaultMode": 288, "secretName": "axis-runtime"}},
        {
            "name": "staged-secret",
            "secret": {"defaultMode": 288, "secretName": "axis-runtime-next"},
        },
        {"name": "secret-rotation-evidence", "emptyDir": {}},
    ]
    assert container["volumeMounts"] == [
        {"name": "active-secret", "mountPath": "/rotation/active", "readOnly": True},
        {"name": "staged-secret", "mountPath": "/rotation/staged", "readOnly": True},
        {"name": "secret-rotation-evidence", "mountPath": "/rotation/evidence"},
    ]
    assert "while true" in container["args"][0]
    assert any(
        "kubectl --context prod-eu -n axis-prod get secret axis-runtime" in line
        for line in command_lines
    )
    assert any(
        "kubectl --context prod-eu -n axis-prod get secret axis-runtime-next" in line
        for line in command_lines
    )
    assert any("secret-rotation-target" in line and "staged" in line for line in command_lines)
    assert any("AXIS_POSTGRES_DSN" in line for line in command_lines)
    assert any("AXIS_AUDIT_LEDGER_SIGNING_SECRET" in line for line in command_lines)
    assert any("AXIS_CONNECTOR_EXPORT_S3_SECRET_KEY" in line for line in command_lines)
    assert any("sha256sum" in line for line in command_lines)
    assert any("cmp -s" in line for line in command_lines)
    assert any("secret-rotation.summary.json" in line for line in command_lines)
    assert any("secret-rotation.keys" in line for line in command_lines)
    assert any("secret-rotation.sha256" in line for line in command_lines)
    assert all("postgres://user:pass" not in line for line in command_lines)
    assert all("axis-secret-value" not in line for line in command_lines)
    assert "postgres://user:pass" not in manifest
    assert "axis-secret-value" not in manifest


def test_secret_rotation_rehearsal_plan_prints_without_executing(
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
            "--active-secret",
            "axis-runtime",
            "--staged-secret",
            "axis-runtime-next",
            "--rotation-id",
            "20260702T210000Z",
            "--image",
            "registry.example.com/platform/busybox-coreutils:stable",
        ]
    )

    output = capsys.readouterr().out
    assert result == 0
    assert executed == []
    assert "secret-rotation-target" in output
    assert "AXIS_POSTGRES_DSN" in output
    assert "AXIS_CONNECTOR_EXPORT_S3_SECRET_KEY" in output
    assert "secret-rotation.summary.json" in output
    assert "secret-rotation.sha256" in output
    assert "axis-secret-value" not in output


def test_secret_rotation_rehearsal_rejects_unsafe_or_runtime_inputs() -> None:
    rehearsal = load_rehearsal_module()

    with pytest.raises(ValueError, match="rotation_id"):
        rehearsal.SecretRotationRehearsalConfig(rotation_id="bad;rm-rf")

    with pytest.raises(ValueError, match="namespace"):
        rehearsal.SecretRotationRehearsalConfig(namespace="axis prod")

    with pytest.raises(ValueError, match="staged_secret"):
        rehearsal.SecretRotationRehearsalConfig(staged_secret="limes-axis-runtime")

    with pytest.raises(ValueError, match="staged_secret"):
        rehearsal.SecretRotationRehearsalConfig(
            active_secret="axis-runtime",
            staged_secret="axis-runtime",
        )

    with pytest.raises(ValueError, match="run_as_user"):
        rehearsal.SecretRotationRehearsalConfig(run_as_user=0)

    with pytest.raises(ValueError, match="image"):
        rehearsal.SecretRotationRehearsalConfig(image="")


def test_secret_rotation_rehearsal_cli_reports_invalid_inputs_without_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rehearsal = load_rehearsal_module()

    result = rehearsal.main(["--plan", "--rotation-id", "bad;rm-rf"])

    captured = capsys.readouterr()
    assert result == 2
    assert "rotation_id" in captured.err
    assert "Traceback" not in captured.err


def test_secret_rotation_rehearsal_execute_requires_coreutils_image(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rehearsal = load_rehearsal_module()

    result = rehearsal.main(["--execute"])

    captured = capsys.readouterr()
    assert result == 2
    assert "sha256sum" in captured.err
    assert "Traceback" not in captured.err
