from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "services" / "api" / "scripts" / "rehearse_production_restore.py"


def load_rehearsal_module():
    assert SCRIPT.exists(), "production restore rehearsal script is missing"
    spec = importlib.util.spec_from_file_location("rehearse_production_restore", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_production_restore_rehearsal_builds_isolated_target_steps() -> None:
    rehearsal = load_rehearsal_module()

    config = rehearsal.RestoreRehearsalConfig(
        namespace="axis-prod",
        kube_context="prod-eu",
        restore_target_secret="axis-restore-target",
        restore_id="20260701T183000Z",
        dump_path=Path(".axis/production-backups/20260701T180000Z/postgres.dump"),
        checksum_path=Path(".axis/production-backups/20260701T180000Z/postgres.dump.sha256"),
        local_evidence_dir=Path(".axis/production-restores/20260701T183000Z"),
        timeout="19m",
    )

    steps = rehearsal.build_rehearsal_steps(config)
    command_lines = [rehearsal.format_command(step.command) for step in steps]
    manifest = rehearsal.build_pod_manifest(config)
    manifest_payload = json.loads(manifest)
    pod_spec = manifest_payload["spec"]
    container = pod_spec["containers"][0]
    script = container["args"][0]

    assert "axis-postgres-restore-20260701t183000z" in manifest
    assert "postgres:16-alpine" in manifest
    assert pod_spec["securityContext"]["runAsNonRoot"] is True
    assert pod_spec["securityContext"]["runAsUser"] == 70
    assert pod_spec["securityContext"]["runAsGroup"] == 70
    assert pod_spec["securityContext"]["fsGroup"] == 70
    assert pod_spec["volumes"] == [{"name": "restore", "emptyDir": {}}]
    assert container["volumeMounts"] == [{"name": "restore", "mountPath": "/restore"}]
    assert container["envFrom"] == [{"secretRef": {"name": "axis-restore-target"}}]
    assert "while true" in script
    assert any(
        "kubectl --context prod-eu -n axis-prod get secret axis-restore-target"
        in line
        for line in command_lines
    )
    assert any("restore-target" in line and "isolated" in line for line in command_lines)
    assert any(
        "kubectl --context prod-eu -n axis-prod apply -f -" in line
        for line in command_lines
    )
    assert any(
        "kubectl --context prod-eu -n axis-prod wait --for=condition=Ready "
        "pod/axis-postgres-restore-20260701t183000z --timeout=19m" in line
        for line in command_lines
    )
    assert any("postgres.dump.sha256" in line and "kubectl" in line for line in command_lines)
    assert not any("sha256sum -c postgres.dump.sha256" in line for line in command_lines)
    assert any(
        "expected=" in line and "postgres.dump.sha256" in line
        for line in command_lines
    )
    assert any("actual=" in line and "sha256sum postgres.dump" in line for line in command_lines)
    assert any('test "$expected" = "$actual"' in line for line in command_lines)
    assert any("pg_restore --list /restore/postgres.dump" in line for line in command_lines)
    assert any(
        'pg_restore --clean --if-exists --no-owner --dbname "$AXIS_POSTGRES_RESTORE_DSN"'
        in line
        for line in command_lines
    )
    assert any("postgres.restore.probe" in line for line in command_lines)
    assert all("postgresql://" not in line for line in command_lines)
    assert "postgresql://" not in manifest


def test_production_restore_rehearsal_plan_prints_without_executing(
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
            "--restore-target-secret",
            "axis-restore-target",
            "--restore-id",
            "20260701T183000Z",
            "--dump-path",
            ".axis/production-backups/20260701T180000Z/postgres.dump",
        ]
    )

    output = capsys.readouterr().out
    assert result == 0
    assert executed == []
    assert "AXIS_POSTGRES_RESTORE_DSN" in output
    assert "pg_restore --list" in output
    assert "postgres.restore.probe" in output
    assert "postgresql://" not in output


def test_production_restore_rehearsal_rejects_unsafe_or_production_like_inputs() -> None:
    rehearsal = load_rehearsal_module()

    with pytest.raises(ValueError, match="restore_id"):
        rehearsal.RestoreRehearsalConfig(restore_id="bad;rm-rf")

    with pytest.raises(ValueError, match="namespace"):
        rehearsal.RestoreRehearsalConfig(namespace="axis prod")

    with pytest.raises(ValueError, match="restore_target_secret"):
        rehearsal.RestoreRehearsalConfig(restore_target_secret="limes-axis-runtime")

    with pytest.raises(ValueError, match="run_as_user"):
        rehearsal.RestoreRehearsalConfig(run_as_user=0)


def test_production_restore_rehearsal_cli_reports_invalid_inputs_without_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rehearsal = load_rehearsal_module()

    result = rehearsal.main(["--plan", "--restore-id", "bad;rm-rf"])

    captured = capsys.readouterr()
    assert result == 2
    assert "restore_id" in captured.err
    assert "Traceback" not in captured.err
