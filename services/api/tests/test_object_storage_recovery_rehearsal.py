from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "services" / "api" / "scripts" / "rehearse_object_storage_recovery.py"


def load_rehearsal_module():
    assert SCRIPT.exists(), "object storage recovery rehearsal script is missing"
    spec = importlib.util.spec_from_file_location("rehearse_object_storage_recovery", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_object_storage_recovery_rehearsal_builds_isolated_copy_probe_steps() -> None:
    rehearsal = load_rehearsal_module()

    config = rehearsal.ObjectStorageRecoveryRehearsalConfig(
        namespace="axis-prod",
        kube_context="prod-eu",
        runtime_config_map="axis-config",
        runtime_secret="axis-runtime",
        restore_target_secret="axis-object-store-restore",
        recovery_id="20260702T140000Z",
        local_evidence_dir=Path(".axis/object-storage-recovery/20260702T140000Z"),
        image="registry.example.com/platform/minio-mc:stable",
        timeout="17m",
    )

    steps = rehearsal.build_rehearsal_steps(config)
    command_lines = [rehearsal.format_command(step.command) for step in steps]
    manifest = rehearsal.build_pod_manifest(config)
    manifest_payload = json.loads(manifest)
    pod_spec = manifest_payload["spec"]
    container = pod_spec["containers"][0]
    script = container["args"][0]

    assert "axis-object-store-recovery-20260702t140000z" in manifest
    assert "registry.example.com/platform/minio-mc:stable" in manifest
    assert pod_spec["securityContext"]["runAsNonRoot"] is True
    assert pod_spec["securityContext"]["runAsUser"] == 10001
    assert pod_spec["securityContext"]["runAsGroup"] == 10001
    assert pod_spec["securityContext"]["fsGroup"] == 10001
    assert pod_spec["volumes"] == [
        {"name": "object-store-recovery", "emptyDir": {}}
    ]
    assert container["volumeMounts"] == [
        {"name": "object-store-recovery", "mountPath": "/object-store-recovery"}
    ]
    assert container["envFrom"] == [
        {"configMapRef": {"name": "axis-config"}},
        {"secretRef": {"name": "axis-runtime"}},
        {"secretRef": {"name": "axis-object-store-restore"}},
    ]
    assert "while true" in script
    assert any(
        "kubectl --context prod-eu -n axis-prod get secret axis-runtime" in line
        for line in command_lines
    )
    assert any(
        "kubectl --context prod-eu -n axis-prod get configmap axis-config" in line
        for line in command_lines
    )
    assert any(
        "kubectl --context prod-eu -n axis-prod get secret axis-object-store-restore" in line
        for line in command_lines
    )
    assert any(
        "object-store-restore-target" in line and "isolated" in line
        for line in command_lines
    )
    assert any("AXIS_CONNECTOR_EXPORT_S3_ENDPOINT" in line for line in command_lines)
    assert any(
        "AXIS_CONNECTOR_EXPORT_S3_RESTORE_BUCKET" in line
        for line in command_lines
    )
    assert any("mc --help" in line or "mcli --help" in line for line in command_lines)
    assert any("mc alias set" in line or "mcli alias set" in line for line in command_lines)
    assert any("mc cp" in line or "mcli cp" in line for line in command_lines)
    assert any("mc cat" in line or "mcli cat" in line for line in command_lines)
    assert any("sha256sum" in line for line in command_lines)
    assert any("object-store.sha256" in line for line in command_lines)
    assert any("source.object.stat" in line for line in command_lines)
    assert any("restore.object.stat" in line for line in command_lines)
    assert all("axis-secret-key" not in line for line in command_lines)
    assert all("minioadmin" not in line for line in command_lines)
    assert "axis-secret-key" not in manifest
    assert "minioadmin" not in manifest


def test_object_storage_recovery_rehearsal_plan_prints_without_executing(
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
            "--runtime-secret",
            "axis-runtime",
            "--runtime-config-map",
            "axis-config",
            "--restore-target-secret",
            "axis-object-store-restore",
            "--recovery-id",
            "20260702T140000Z",
            "--image",
            "registry.example.com/platform/minio-mc:stable",
        ]
    )

    output = capsys.readouterr().out
    assert result == 0
    assert executed == []
    assert "AXIS_CONNECTOR_EXPORT_S3_RESTORE_BUCKET" in output
    assert "object-store-restore-target" in output
    assert "alias set" in output
    assert "mc cp" in output or "mcli cp" in output
    assert "mc cat" in output or "mcli cat" in output
    assert "axis-secret-key" not in output
    assert "minioadmin" not in output


def test_object_storage_recovery_rehearsal_rejects_unsafe_or_runtime_restore_inputs() -> None:
    rehearsal = load_rehearsal_module()

    with pytest.raises(ValueError, match="recovery_id"):
        rehearsal.ObjectStorageRecoveryRehearsalConfig(recovery_id="bad;rm-rf")

    with pytest.raises(ValueError, match="namespace"):
        rehearsal.ObjectStorageRecoveryRehearsalConfig(namespace="axis prod")

    with pytest.raises(ValueError, match="restore_target_secret"):
        rehearsal.ObjectStorageRecoveryRehearsalConfig(
            restore_target_secret="limes-axis-runtime"
        )

    with pytest.raises(ValueError, match="restore_target_secret"):
        rehearsal.ObjectStorageRecoveryRehearsalConfig(
            runtime_secret="axis-runtime",
            restore_target_secret="axis-runtime",
        )

    with pytest.raises(ValueError, match="probe_prefix"):
        rehearsal.ObjectStorageRecoveryRehearsalConfig(probe_prefix="../escape")

    with pytest.raises(ValueError, match="run_as_user"):
        rehearsal.ObjectStorageRecoveryRehearsalConfig(run_as_user=0)


def test_object_storage_recovery_rehearsal_cli_reports_invalid_inputs_without_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rehearsal = load_rehearsal_module()

    result = rehearsal.main(["--plan", "--recovery-id", "bad;rm-rf"])

    captured = capsys.readouterr()
    assert result == 2
    assert "recovery_id" in captured.err
    assert "Traceback" not in captured.err


def test_object_storage_recovery_rehearsal_execute_requires_mc_image(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rehearsal = load_rehearsal_module()

    result = rehearsal.main(["--execute"])

    captured = capsys.readouterr()
    assert result == 2
    assert "MinIO Client" in captured.err
    assert "Traceback" not in captured.err
