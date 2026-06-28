from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "services" / "api" / "scripts" / "demo_backup_restore.py"


def load_backup_module():
    spec = importlib.util.spec_from_file_location("demo_backup_restore", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_backup_plan_declares_real_compose_artifacts(tmp_path: Path) -> None:
    backup = load_backup_module()

    plan = backup.build_backup_plan(
        repo_root=REPO_ROOT,
        backup_root=tmp_path,
        backup_id="20260628T120000Z",
    )

    artifact_names = {artifact.name for artifact in plan.artifacts}
    command_lines = [" ".join(step.command) for step in plan.steps]

    assert plan.backup_dir == tmp_path / "20260628T120000Z"
    assert {
        "postgres.dump",
        "minio-data.tar.gz",
        "typedb-data.tar.gz",
    }.issubset(artifact_names)
    assert any("exec -T postgres pg_dump" in command for command in command_lines)
    assert any("cp minio:/data" in command for command in command_lines)
    assert any("cp typedb:/var/lib/typedb/data" in command for command in command_lines)
    assert plan.manifest_path == tmp_path / "20260628T120000Z" / "manifest.json"


def test_backup_manifest_records_real_artifact_checksums(tmp_path: Path) -> None:
    backup = load_backup_module()
    backup_dir = tmp_path / "20260628T120000Z"
    backup_dir.mkdir()
    artifact_path = backup_dir / "postgres.dump"
    artifact_path.write_bytes(b"axis-postgres-backup")

    manifest = backup.build_manifest(
        backup_id="20260628T120000Z",
        repo_root=REPO_ROOT,
        backup_dir=backup_dir,
        artifacts=[backup.ManifestArtifact.from_file("postgres.dump", artifact_path)],
        warnings=("demo-only backup window",),
    )

    serialized = json.loads(json.dumps(manifest))
    [artifact] = serialized["artifacts"]

    assert artifact["name"] == "postgres.dump"
    assert artifact["size_bytes"] == len(b"axis-postgres-backup")
    assert artifact["sha256"]
    assert serialized["warnings"] == ["demo-only backup window"]


def test_restore_plan_refuses_without_explicit_confirmation(tmp_path: Path) -> None:
    backup = load_backup_module()
    backup_dir = tmp_path / "20260628T120000Z"
    backup_dir.mkdir()
    (backup_dir / "manifest.json").write_text(
        json.dumps(
            {
                "backup_id": "20260628T120000Z",
                "artifacts": [
                    {"name": "postgres.dump", "path": "postgres.dump"},
                    {"name": "minio-data.tar.gz", "path": "minio-data.tar.gz"},
                    {"name": "typedb-data.tar.gz", "path": "typedb-data.tar.gz"},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(backup.RestoreRefusedError):
        backup.build_restore_plan(
            repo_root=REPO_ROOT,
            backup_dir=backup_dir,
            confirm_restore=False,
        )


def test_restore_plan_uses_manifest_artifacts_when_confirmed(tmp_path: Path) -> None:
    backup = load_backup_module()
    backup_dir = tmp_path / "20260628T120000Z"
    backup_dir.mkdir()
    (backup_dir / "postgres.dump").write_bytes(b"postgres")
    (backup_dir / "minio-data.tar.gz").write_bytes(b"minio")
    (backup_dir / "typedb-data.tar.gz").write_bytes(b"typedb")
    (backup_dir / "manifest.json").write_text(
        json.dumps(
            {
                "backup_id": "20260628T120000Z",
                "artifacts": [
                    {"name": "postgres.dump", "path": "postgres.dump"},
                    {"name": "minio-data.tar.gz", "path": "minio-data.tar.gz"},
                    {"name": "typedb-data.tar.gz", "path": "typedb-data.tar.gz"},
                ],
            }
        ),
        encoding="utf-8",
    )

    plan = backup.build_restore_plan(
        repo_root=REPO_ROOT,
        backup_dir=backup_dir,
        confirm_restore=True,
    )

    command_lines = [" ".join(step.command) for step in plan.steps]

    assert any("exec -T postgres pg_restore" in command for command in command_lines)
    assert any("cp" in command and "minio:/data" in command for command in command_lines)
    assert any(
        "cp" in command and "typedb:/var/lib/typedb/data" in command
        for command in command_lines
    )
    assert plan.steps[0].stdin_path == backup_dir / "postgres.dump"
    assert all(step.archive_path is not None for step in plan.steps[1:])


def test_streamed_command_failure_removes_partial_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    backup = load_backup_module()
    artifact_path = tmp_path / "postgres.dump"
    step = backup.CommandStep(
        name="postgres",
        command=("docker", "compose", "exec", "-T", "postgres", "pg_dump"),
        stdout_path=artifact_path,
    )

    def fail_after_partial_write(*_args: object, stdout: object | None = None, **_kwargs: object):
        assert stdout is not None
        stdout.write(b"partial")
        raise backup.StepExecutionError("postgres command failed")

    monkeypatch.setattr(backup, "_run_external_command", fail_after_partial_write)

    with pytest.raises(backup.StepExecutionError):
        backup._run_step(step)

    assert not artifact_path.exists()


def test_restore_plan_rejects_artifact_paths_that_escape_backup_dir(tmp_path: Path) -> None:
    backup = load_backup_module()
    backup_dir = tmp_path / "20260628T120000Z"
    backup_dir.mkdir()
    (backup_dir / "manifest.json").write_text(
        json.dumps(
            {
                "backup_id": "20260628T120000Z",
                "artifacts": [
                    {"name": "postgres.dump", "path": "../postgres.dump"},
                    {"name": "minio-data.tar.gz", "path": "minio-data.tar.gz"},
                    {"name": "typedb-data.tar.gz", "path": "typedb-data.tar.gz"},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(backup.BackupRestoreError, match="escapes backup directory"):
        backup.build_restore_plan(
            repo_root=REPO_ROOT,
            backup_dir=backup_dir,
            confirm_restore=True,
        )


def test_restore_plan_rejects_checksum_mismatch(tmp_path: Path) -> None:
    backup = load_backup_module()
    backup_dir = tmp_path / "20260628T120000Z"
    backup_dir.mkdir()
    (backup_dir / "postgres.dump").write_bytes(b"postgres")
    (backup_dir / "minio-data.tar.gz").write_bytes(b"minio")
    (backup_dir / "typedb-data.tar.gz").write_bytes(b"typedb")
    (backup_dir / "manifest.json").write_text(
        json.dumps(
            {
                "backup_id": "20260628T120000Z",
                "artifacts": [
                    {
                        "name": "postgres.dump",
                        "path": "postgres.dump",
                        "sha256": "0" * 64,
                    },
                    {"name": "minio-data.tar.gz", "path": "minio-data.tar.gz"},
                    {"name": "typedb-data.tar.gz", "path": "typedb-data.tar.gz"},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(backup.BackupRestoreError, match="checksum mismatch"):
        backup.build_restore_plan(
            repo_root=REPO_ROOT,
            backup_dir=backup_dir,
            confirm_restore=True,
        )
