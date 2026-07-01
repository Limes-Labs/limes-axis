from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "services" / "api" / "scripts" / "rehearse_production_backup.py"


def load_rehearsal_module():
    assert SCRIPT.exists(), "production backup rehearsal script is missing"
    spec = importlib.util.spec_from_file_location("rehearse_production_backup", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_production_backup_rehearsal_builds_cluster_safe_postgres_steps() -> None:
    rehearsal = load_rehearsal_module()

    config = rehearsal.BackupRehearsalConfig(
        namespace="axis-prod",
        kube_context="prod-eu",
        runtime_secret="axis-runtime",
        backup_id="20260701T180000Z",
        local_backup_dir=Path(".axis/production-backups/20260701T180000Z"),
        timeout="17m",
    )

    steps = rehearsal.build_rehearsal_steps(config)
    command_lines = [
        rehearsal.format_command(step.command)
        for step in steps
        if step.command is not None
    ]
    manifest = rehearsal.build_job_manifest(config)
    manifest_payload = json.loads(manifest)
    pod_spec = manifest_payload["spec"]["template"]["spec"]
    container = pod_spec["containers"][0]
    script = container["args"][0]

    assert "axis-postgres-backup-20260701t180000z" in manifest
    assert "postgres:16-alpine" in manifest
    assert pod_spec["securityContext"]["runAsNonRoot"] is True
    assert pod_spec["securityContext"]["runAsUser"] == 70
    assert pod_spec["securityContext"]["runAsGroup"] == 70
    assert pod_spec["securityContext"]["fsGroup"] == 70
    assert pod_spec["volumes"] == [{"name": "backup", "emptyDir": {}}]
    assert container["volumeMounts"] == [{"name": "backup", "mountPath": "/backup"}]
    assert container["envFrom"] == [{"secretRef": {"name": "axis-runtime"}}]
    assert 'pg_dump "$AXIS_POSTGRES_DSN" --format=custom --no-owner' in script
    assert "pg_restore --list /backup/postgres.dump" in script
    assert any(
        "kubectl --context prod-eu config current-context" in line
        for line in command_lines
    )
    assert any(
        "kubectl --context prod-eu -n axis-prod get secret axis-runtime" in line
        for line in command_lines
    )
    assert any(
        "kubectl --context prod-eu -n axis-prod apply -f -" in line
        for line in command_lines
    )
    assert any(
        "kubectl --context prod-eu -n axis-prod wait --for=condition=complete "
        "job/axis-postgres-backup-20260701t180000z --timeout=17m" in line
        for line in command_lines
    )
    assert any("kubectl --context prod-eu -n axis-prod cp" in line for line in command_lines)
    assert any("postgres.restore.list" in line for line in command_lines)
    assert all("postgresql://" not in line for line in command_lines)
    assert "postgresql://" not in manifest


def test_production_backup_rehearsal_plan_prints_without_executing(
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
            "--backup-id",
            "20260701T180000Z",
        ]
    )

    output = capsys.readouterr().out
    assert result == 0
    assert executed == []
    assert "apply -f -" in output
    assert "pg_restore --list" in output
    assert "postgres.dump" in output
    assert "postgresql://" not in output


def test_production_backup_rehearsal_rejects_unsafe_identifiers() -> None:
    rehearsal = load_rehearsal_module()

    with pytest.raises(ValueError, match="backup_id"):
        rehearsal.BackupRehearsalConfig(backup_id="bad;rm-rf")

    with pytest.raises(ValueError, match="namespace"):
        rehearsal.BackupRehearsalConfig(namespace="axis prod")

    with pytest.raises(ValueError, match="run_as_user"):
        rehearsal.BackupRehearsalConfig(run_as_user=0)


def test_production_backup_rehearsal_cli_reports_invalid_identifiers_without_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rehearsal = load_rehearsal_module()

    result = rehearsal.main(["--plan", "--backup-id", "bad;rm-rf"])

    captured = capsys.readouterr()
    assert result == 2
    assert "backup_id" in captured.err
    assert "Traceback" not in captured.err
