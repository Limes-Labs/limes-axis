from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "services" / "api" / "scripts" / "rehearse_typedb_recovery.py"


def load_rehearsal_module():
    assert SCRIPT.exists(), "TypeDB recovery rehearsal script is missing"
    spec = importlib.util.spec_from_file_location("rehearse_typedb_recovery", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_typedb_recovery_rehearsal_builds_isolated_export_import_steps() -> None:
    rehearsal = load_rehearsal_module()

    config = rehearsal.TypeDBRecoveryRehearsalConfig(
        namespace="axis-prod",
        kube_context="prod-eu",
        runtime_secret="axis-runtime",
        restore_target_secret="axis-typedb-restore",
        recovery_id="20260702T100000Z",
        local_evidence_dir=Path(".axis/typedb-recovery/20260702T100000Z"),
        image="registry.example.com/platform/typedb-console:3.11.5",
        timeout="21m",
    )

    steps = rehearsal.build_rehearsal_steps(config)
    command_lines = [rehearsal.format_command(step.command) for step in steps]
    manifest = rehearsal.build_pod_manifest(config)
    manifest_payload = json.loads(manifest)
    pod_spec = manifest_payload["spec"]
    container = pod_spec["containers"][0]
    script = container["args"][0]

    assert "axis-typedb-recovery-20260702t100000z" in manifest
    assert "registry.example.com/platform/typedb-console:3.11.5" in manifest
    assert pod_spec["securityContext"]["runAsNonRoot"] is True
    assert pod_spec["securityContext"]["runAsUser"] == 10001
    assert pod_spec["securityContext"]["runAsGroup"] == 10001
    assert pod_spec["securityContext"]["fsGroup"] == 10001
    assert pod_spec["volumes"] == [{"name": "typedb-recovery", "emptyDir": {}}]
    assert container["volumeMounts"] == [
        {"name": "typedb-recovery", "mountPath": "/typedb-recovery"}
    ]
    assert container["envFrom"] == [
        {"secretRef": {"name": "axis-runtime"}},
        {"secretRef": {"name": "axis-typedb-restore"}},
    ]
    assert "while true" in script
    assert any(
        "kubectl --context prod-eu -n axis-prod get secret axis-runtime" in line
        for line in command_lines
    )
    assert any(
        "kubectl --context prod-eu -n axis-prod get secret axis-typedb-restore" in line
        for line in command_lines
    )
    assert any("typedb-restore-target" in line and "isolated" in line for line in command_lines)
    assert any("AXIS_TYPEDB_ADDRESS" in line for line in command_lines)
    assert any("AXIS_TYPEDB_RESTORE_ADDRESS" in line for line in command_lines)
    assert any(
        "kubectl --context prod-eu -n axis-prod apply -f -" in line
        for line in command_lines
    )
    assert any(
        "kubectl --context prod-eu -n axis-prod wait --for=condition=Ready "
        "pod/axis-typedb-recovery-20260702t100000z --timeout=21m" in line
        for line in command_lines
    )
    assert any("console --help" in line for line in command_lines)
    assert any("database export" in line for line in command_lines)
    assert any('"$AXIS_TYPEDB_DATABASE"' in line for line in command_lines)
    assert any("database import" in line for line in command_lines)
    assert any('"$AXIS_TYPEDB_RESTORE_DATABASE"' in line for line in command_lines)
    assert any("typedb.schema.typeql" in line for line in command_lines)
    assert any("typedb.data" in line for line in command_lines)
    assert any("typedb.console.help" in line for line in command_lines)
    assert any("typedb.sha256" in line for line in command_lines)
    assert any("typedb.restore.probe" in line for line in command_lines)
    assert all("typedb://" not in line for line in command_lines)
    assert "typedb://" not in manifest


def test_typedb_recovery_rehearsal_plan_prints_without_executing(
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
            "--restore-target-secret",
            "axis-typedb-restore",
            "--recovery-id",
            "20260702T100000Z",
            "--image",
            "registry.example.com/platform/typedb-console:3.11.5",
        ]
    )

    output = capsys.readouterr().out
    assert result == 0
    assert executed == []
    assert "database export" in output
    assert "database import" in output
    assert "console --help" in output
    assert "AXIS_TYPEDB_RESTORE_DATABASE" in output
    assert "typedb.restore.probe" in output
    assert "typedb://" not in output


def test_typedb_recovery_rehearsal_rejects_unsafe_or_runtime_restore_inputs() -> None:
    rehearsal = load_rehearsal_module()

    with pytest.raises(ValueError, match="recovery_id"):
        rehearsal.TypeDBRecoveryRehearsalConfig(recovery_id="bad;rm-rf")

    with pytest.raises(ValueError, match="namespace"):
        rehearsal.TypeDBRecoveryRehearsalConfig(namespace="axis prod")

    with pytest.raises(ValueError, match="restore_target_secret"):
        rehearsal.TypeDBRecoveryRehearsalConfig(restore_target_secret="limes-axis-runtime")

    with pytest.raises(ValueError, match="restore_target_secret"):
        rehearsal.TypeDBRecoveryRehearsalConfig(
            runtime_secret="axis-runtime",
            restore_target_secret="axis-runtime",
        )

    with pytest.raises(ValueError, match="run_as_user"):
        rehearsal.TypeDBRecoveryRehearsalConfig(run_as_user=0)

    with pytest.raises(ValueError, match="image"):
        rehearsal.TypeDBRecoveryRehearsalConfig(image="")


def test_typedb_recovery_rehearsal_cli_reports_invalid_inputs_without_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rehearsal = load_rehearsal_module()

    result = rehearsal.main(["--plan", "--recovery-id", "bad;rm-rf"])

    captured = capsys.readouterr()
    assert result == 2
    assert "recovery_id" in captured.err
    assert "Traceback" not in captured.err


def test_typedb_recovery_rehearsal_execute_requires_console_image(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rehearsal = load_rehearsal_module()

    result = rehearsal.main(["--execute"])

    captured = capsys.readouterr()
    assert result == 2
    assert "typedb-console-capable image" in captured.err
    assert "Traceback" not in captured.err
