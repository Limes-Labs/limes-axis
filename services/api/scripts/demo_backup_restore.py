from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

DEFAULT_BACKUP_ROOT = Path(".axis/backups")
COMPOSE_FILE = Path("infra/docker/docker-compose.yml")
POSTGRES_ARTIFACT = "postgres.dump"
MINIO_ARTIFACT = "minio-data.tar.gz"
TYPEDB_ARTIFACT = "typedb-data.tar.gz"
REQUIRED_ARTIFACTS = (POSTGRES_ARTIFACT, MINIO_ARTIFACT, TYPEDB_ARTIFACT)


class BackupRestoreError(RuntimeError):
    """Base error for local demo backup and restore operations."""


class RestoreRefusedError(BackupRestoreError):
    """Raised when a destructive restore is requested without explicit confirmation."""


class StepExecutionError(BackupRestoreError):
    """Raised when an external backup or restore command fails."""


@dataclass(frozen=True)
class ArtifactPlan:
    name: str
    path: Path


@dataclass(frozen=True)
class CommandStep:
    name: str
    command: tuple[str, ...]
    stdout_path: Path | None = None
    stdin_path: Path | None = None
    archive_path: Path | None = None
    copy_path: Path | None = None
    pre_command: tuple[str, ...] | None = None


@dataclass(frozen=True)
class BackupPlan:
    backup_id: str
    repo_root: Path
    backup_dir: Path
    manifest_path: Path
    artifacts: tuple[ArtifactPlan, ...]
    steps: tuple[CommandStep, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class RestorePlan:
    backup_dir: Path
    manifest_path: Path
    steps: tuple[CommandStep, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ManifestArtifact:
    name: str
    path: str
    size_bytes: int
    sha256: str

    @classmethod
    def from_file(cls, name: str, path: Path) -> ManifestArtifact:
        return cls(
            name=name,
            path=path.name,
            size_bytes=path.stat().st_size,
            sha256=_sha256_file(path),
        )


def _utc_timestamp() -> str:
    return datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")


def _repo_root(path: str | Path | None) -> Path:
    if path is None:
        return Path(__file__).resolve().parents[3]
    return Path(path).expanduser().resolve()


def _resolve_user_path(path: str | Path, repo_root: Path) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.resolve()


def _compose_path(repo_root: Path) -> Path:
    compose_file = repo_root / COMPOSE_FILE
    if not compose_file.exists():
        raise BackupRestoreError(f"Docker Compose file not found: {compose_file}")
    return compose_file


def _compose_command(repo_root: Path, *args: str) -> tuple[str, ...]:
    return ("docker", "compose", "-f", str(_compose_path(repo_root)), *args)


def _backup_artifacts(backup_dir: Path) -> tuple[ArtifactPlan, ...]:
    return (
        ArtifactPlan(POSTGRES_ARTIFACT, backup_dir / POSTGRES_ARTIFACT),
        ArtifactPlan(MINIO_ARTIFACT, backup_dir / MINIO_ARTIFACT),
        ArtifactPlan(TYPEDB_ARTIFACT, backup_dir / TYPEDB_ARTIFACT),
    )


def build_backup_plan(
    *,
    repo_root: Path,
    backup_root: Path,
    backup_id: str | None = None,
) -> BackupPlan:
    backup_id = backup_id or _utc_timestamp()
    backup_dir = backup_root / backup_id
    artifacts = _backup_artifacts(backup_dir)
    artifacts_by_name = {artifact.name: artifact for artifact in artifacts}
    volume_copy_root = backup_dir / ".volume-copies"
    steps = (
        CommandStep(
            name="postgres",
            command=_compose_command(
                repo_root,
                "exec",
                "-T",
                "postgres",
                "pg_dump",
                "-U",
                "axis",
                "-d",
                "axis",
                "--format=custom",
                "--no-owner",
                "--no-privileges",
            ),
            stdout_path=artifacts_by_name[POSTGRES_ARTIFACT].path,
        ),
        CommandStep(
            name="minio",
            command=_compose_command(
                repo_root,
                "cp",
                "minio:/data",
                str(volume_copy_root / "minio-data"),
            ),
            archive_path=artifacts_by_name[MINIO_ARTIFACT].path,
            copy_path=volume_copy_root / "minio-data",
        ),
        CommandStep(
            name="typedb",
            command=_compose_command(
                repo_root,
                "cp",
                "typedb:/var/lib/typedb/data",
                str(volume_copy_root / "typedb-data"),
            ),
            archive_path=artifacts_by_name[TYPEDB_ARTIFACT].path,
            copy_path=volume_copy_root / "typedb-data",
        ),
    )
    warnings = (
        "Local demo backup only; production HA, offsite retention and DR are separate work.",
        "Quiesce API, worker and connector writes before taking a consistent demo backup.",
        "Temporal metadata is included in the local Postgres dump for this Compose topology.",
    )
    return BackupPlan(
        backup_id=backup_id,
        repo_root=repo_root,
        backup_dir=backup_dir,
        manifest_path=backup_dir / "manifest.json",
        artifacts=artifacts,
        steps=steps,
        warnings=warnings,
    )


def build_manifest(
    *,
    backup_id: str,
    repo_root: Path,
    backup_dir: Path,
    artifacts: Sequence[ManifestArtifact],
    warnings: Sequence[str],
) -> dict[str, Any]:
    return {
        "schema_version": "axis.demo_backup.v1",
        "backup_id": backup_id,
        "created_at": datetime.now(tz=UTC).isoformat(),
        "repo_root": str(repo_root),
        "compose_file": str(COMPOSE_FILE),
        "backup_dir": str(backup_dir),
        "artifacts": [asdict(artifact) for artifact in artifacts],
        "warnings": list(warnings),
        "restore_requires_confirm_restore": True,
    }


def build_restore_plan(
    *,
    repo_root: Path,
    backup_dir: Path,
    confirm_restore: bool,
) -> RestorePlan:
    if not confirm_restore:
        raise RestoreRefusedError(
            "Refusing destructive restore without --confirm-restore. "
            "The restore replaces local Postgres, MinIO and TypeDB demo state."
        )

    manifest_path = backup_dir / "manifest.json"
    manifest = _load_manifest(manifest_path)
    artifacts = _manifest_artifact_paths(backup_dir, manifest)
    restore_root = backup_dir / ".restore"
    steps = (
        CommandStep(
            name="postgres",
            command=_compose_command(
                repo_root,
                "exec",
                "-T",
                "postgres",
                "pg_restore",
                "-U",
                "axis",
                "-d",
                "axis",
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
            ),
            stdin_path=artifacts[POSTGRES_ARTIFACT],
        ),
        CommandStep(
            name="minio",
            command=_compose_command(
                repo_root,
                "cp",
                f"{restore_root / 'minio-data'}/.",
                "minio:/data",
            ),
            archive_path=artifacts[MINIO_ARTIFACT],
            copy_path=restore_root / "minio-data",
            pre_command=_compose_command(
                repo_root,
                "exec",
                "-T",
                "minio",
                "sh",
                "-lc",
                "rm -rf /data/* /data/.[!.]* /data/..?*",
            ),
        ),
        CommandStep(
            name="typedb",
            command=_compose_command(
                repo_root,
                "cp",
                f"{restore_root / 'typedb-data'}/.",
                "typedb:/var/lib/typedb/data",
            ),
            archive_path=artifacts[TYPEDB_ARTIFACT],
            copy_path=restore_root / "typedb-data",
            pre_command=_compose_command(
                repo_root,
                "exec",
                "-T",
                "typedb",
                "sh",
                "-lc",
                (
                    "rm -rf /var/lib/typedb/data/* /var/lib/typedb/data/.[!.]* "
                    "/var/lib/typedb/data/..?*"
                ),
            ),
        ),
    )
    warnings = (
        "Destructive local demo restore; stop API, worker and console writes first.",
        "Restart TypeDB and API processes after restoring local volume archives.",
        "Use this for repeatable demos, not as a production disaster-recovery procedure.",
    )
    return RestorePlan(
        backup_dir=backup_dir,
        manifest_path=manifest_path,
        steps=steps,
        warnings=warnings,
    )


def run_backup(plan: BackupPlan) -> dict[str, Any]:
    if plan.backup_dir.exists() and any(plan.backup_dir.iterdir()):
        raise BackupRestoreError(f"Backup directory is not empty: {plan.backup_dir}")
    plan.backup_dir.mkdir(parents=True, exist_ok=True)

    for step in plan.steps:
        _run_step(step)

    manifest_artifacts = [
        ManifestArtifact.from_file(artifact.name, artifact.path) for artifact in plan.artifacts
    ]
    manifest = build_manifest(
        backup_id=plan.backup_id,
        repo_root=plan.repo_root,
        backup_dir=plan.backup_dir,
        artifacts=manifest_artifacts,
        warnings=plan.warnings,
    )
    _write_json(plan.manifest_path, manifest)
    return manifest


def run_restore(plan: RestorePlan) -> None:
    for step in plan.steps:
        _run_step(step)


def plan_to_dict(plan: BackupPlan) -> dict[str, Any]:
    return {
        "backup_id": plan.backup_id,
        "backup_dir": str(plan.backup_dir),
        "manifest_path": str(plan.manifest_path),
        "artifacts": [
            {"name": artifact.name, "path": str(artifact.path)} for artifact in plan.artifacts
        ],
        "steps": [_step_to_dict(step) for step in plan.steps],
        "warnings": list(plan.warnings),
    }


def restore_plan_to_dict(plan: RestorePlan) -> dict[str, Any]:
    return {
        "backup_dir": str(plan.backup_dir),
        "manifest_path": str(plan.manifest_path),
        "steps": [_step_to_dict(step) for step in plan.steps],
        "warnings": list(plan.warnings),
    }


def _step_to_dict(step: CommandStep) -> dict[str, Any]:
    return {
        "name": step.name,
        "command": list(step.command),
        "pre_command": list(step.pre_command) if step.pre_command else None,
        "stdout_path": str(step.stdout_path) if step.stdout_path else None,
        "stdin_path": str(step.stdin_path) if step.stdin_path else None,
        "archive_path": str(step.archive_path) if step.archive_path else None,
        "copy_path": str(step.copy_path) if step.copy_path else None,
    }


def _run_step(step: CommandStep) -> None:
    if step.archive_path is not None and step.copy_path is not None:
        if step.pre_command is None:
            _run_volume_backup_step(step)
            return
        _run_volume_restore_step(step)
        return

    _run_command_step(step)


def _run_command_step(step: CommandStep) -> None:
    stdout_handle = None
    stdin_handle = None
    failed = False
    try:
        if step.stdout_path is not None:
            step.stdout_path.parent.mkdir(parents=True, exist_ok=True)
            stdout_handle = step.stdout_path.open("wb")
        if step.stdin_path is not None:
            stdin_handle = step.stdin_path.open("rb")

        _run_external_command(
            step.name,
            step.command,
            stdin=stdin_handle,
            stdout=stdout_handle,
        )
    except Exception:
        failed = True
        raise
    finally:
        if stdout_handle is not None:
            stdout_handle.close()
        if stdin_handle is not None:
            stdin_handle.close()
        if failed and step.stdout_path is not None and step.stdout_path.exists():
            step.stdout_path.unlink()


def _run_volume_backup_step(step: CommandStep) -> None:
    assert step.archive_path is not None
    assert step.copy_path is not None
    if step.copy_path.exists():
        shutil.rmtree(step.copy_path)
    step.copy_path.parent.mkdir(parents=True, exist_ok=True)
    step.archive_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _run_external_command(step.name, step.command)
        _archive_directory(step.copy_path, step.archive_path)
    except Exception:
        if step.archive_path.exists():
            step.archive_path.unlink()
        raise
    finally:
        if step.copy_path.exists():
            shutil.rmtree(step.copy_path)


def _run_volume_restore_step(step: CommandStep) -> None:
    assert step.archive_path is not None
    assert step.copy_path is not None
    assert step.pre_command is not None
    if step.copy_path.exists():
        shutil.rmtree(step.copy_path)
    step.copy_path.mkdir(parents=True, exist_ok=True)
    try:
        _extract_archive(step.archive_path, step.copy_path)
        _run_external_command(f"{step.name}.clear", step.pre_command)
        _run_external_command(step.name, step.command)
    finally:
        if step.copy_path.exists():
            shutil.rmtree(step.copy_path)


def _run_external_command(
    name: str,
    command: tuple[str, ...],
    *,
    stdin: object | None = None,
    stdout: object | None = None,
) -> None:
    completed = subprocess.run(
        command,
        check=False,
        stdin=stdin,
        stdout=stdout,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise StepExecutionError(f"{name} command failed: {stderr}")


def _archive_directory(source_dir: Path, archive_path: Path) -> None:
    with tarfile.open(archive_path, "w:gz") as archive:
        for child in sorted(source_dir.iterdir()):
            archive.add(child, arcname=child.name)


def _extract_archive(archive_path: Path, destination: Path) -> None:
    destination = destination.resolve()
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            target = (destination / member.name).resolve()
            if not target.is_relative_to(destination):
                raise BackupRestoreError(f"Archive member escapes restore directory: {member.name}")
        archive.extractall(destination, filter="data")


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise BackupRestoreError(f"Backup manifest not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BackupRestoreError(f"Backup manifest is invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise BackupRestoreError(f"Backup manifest must be a JSON object: {path}")
    return payload


def _manifest_artifact_paths(backup_dir: Path, manifest: dict[str, Any]) -> dict[str, Path]:
    raw_artifacts = manifest.get("artifacts")
    if not isinstance(raw_artifacts, list):
        raise BackupRestoreError("Backup manifest does not contain an artifacts list.")

    artifacts: dict[str, Path] = {}
    for raw_artifact in raw_artifacts:
        if not isinstance(raw_artifact, dict):
            raise BackupRestoreError("Backup manifest contains a non-object artifact.")
        name = raw_artifact.get("name")
        raw_path = raw_artifact.get("path")
        if not isinstance(name, str) or not isinstance(raw_path, str):
            raise BackupRestoreError("Backup manifest artifact must include name and path.")
        if name not in REQUIRED_ARTIFACTS:
            continue

        artifact_path = _safe_artifact_path(backup_dir, raw_path)
        if not artifact_path.exists():
            raise BackupRestoreError(f"Backup artifact is missing: {artifact_path}")
        _verify_manifest_artifact(raw_artifact, artifact_path)
        artifacts[name] = artifact_path

    missing = sorted(set(REQUIRED_ARTIFACTS) - set(artifacts))
    if missing:
        raise BackupRestoreError(f"Backup manifest is missing artifacts: {', '.join(missing)}")
    return artifacts


def _safe_artifact_path(backup_dir: Path, raw_path: str) -> Path:
    backup_dir = backup_dir.resolve()
    candidate = (backup_dir / raw_path).resolve()
    if not candidate.is_relative_to(backup_dir):
        raise BackupRestoreError(f"Backup artifact path escapes backup directory: {raw_path}")
    return candidate


def _verify_manifest_artifact(raw_artifact: dict[str, Any], path: Path) -> None:
    expected_size = raw_artifact.get("size_bytes")
    if expected_size is not None and expected_size != path.stat().st_size:
        raise BackupRestoreError(f"Backup artifact size mismatch: {path}")

    expected_sha256 = raw_artifact.get("sha256")
    if expected_sha256 is not None and expected_sha256 != _sha256_file(path):
        raise BackupRestoreError(f"Backup artifact checksum mismatch: {path}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan, run and restore local Limes Axis demo backups."
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root. Defaults to auto-detect.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="Print the local backup plan as JSON.")
    plan_parser.add_argument("--backup-root", default=str(DEFAULT_BACKUP_ROOT))
    plan_parser.add_argument("--backup-id", default=None)

    backup_parser = subparsers.add_parser("backup", help="Run a local demo backup.")
    backup_parser.add_argument("--backup-root", default=str(DEFAULT_BACKUP_ROOT))
    backup_parser.add_argument("--backup-id", default=None)

    restore_parser = subparsers.add_parser("restore", help="Restore a local demo backup.")
    restore_parser.add_argument("--backup-dir", required=True)
    restore_parser.add_argument("--confirm-restore", action="store_true")
    restore_parser.add_argument("--dry-run", action="store_true")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = _repo_root(args.repo_root)

    try:
        if args.command == "plan":
            backup_root = _resolve_user_path(args.backup_root, repo_root)
            plan = build_backup_plan(
                repo_root=repo_root,
                backup_root=backup_root,
                backup_id=args.backup_id,
            )
            print(json.dumps(plan_to_dict(plan), indent=2, sort_keys=True))
            return 0

        if args.command == "backup":
            backup_root = _resolve_user_path(args.backup_root, repo_root)
            plan = build_backup_plan(
                repo_root=repo_root,
                backup_root=backup_root,
                backup_id=args.backup_id,
            )
            manifest = run_backup(plan)
            print(json.dumps(manifest, indent=2, sort_keys=True))
            return 0

        if args.command == "restore":
            backup_dir = _resolve_user_path(args.backup_dir, repo_root)
            plan = build_restore_plan(
                repo_root=repo_root,
                backup_dir=backup_dir,
                confirm_restore=args.confirm_restore,
            )
            if args.dry_run:
                print(json.dumps(restore_plan_to_dict(plan), indent=2, sort_keys=True))
                return 0
            run_restore(plan)
            print(json.dumps({"restored_from": str(backup_dir)}, indent=2, sort_keys=True))
            return 0
    except BackupRestoreError as exc:
        _parser_error(parser, str(exc))

    _parser_error(parser, f"Unknown command: {args.command}")


def _parser_error(parser: argparse.ArgumentParser, message: str) -> NoReturn:
    parser.exit(2, f"{parser.prog}: error: {message}\n")


if __name__ == "__main__":
    raise SystemExit(main())
