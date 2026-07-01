from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,48}$")
_SAFE_DNS_LABEL = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")


@dataclass(frozen=True)
class CommandStep:
    name: str
    command: tuple[str, ...]
    stdin_text: str | None = None


@dataclass(frozen=True)
class BackupRehearsalConfig:
    namespace: str = "limes-axis"
    kube_context: str | None = None
    runtime_secret: str = "limes-axis-runtime"
    backup_id: str = "manual-rehearsal"
    local_backup_dir: Path | None = None
    image: str = "postgres:16-alpine"
    timeout: str = "15m"
    run_as_user: int = 70
    run_as_group: int = 70
    delete_job: bool = True

    def __post_init__(self) -> None:
        _validate_dns_label("namespace", self.namespace)
        _validate_dns_label("runtime_secret", self.runtime_secret)
        _validate_identifier("backup_id", self.backup_id)
        _validate_positive_integer("run_as_user", self.run_as_user)
        _validate_positive_integer("run_as_group", self.run_as_group)
        if self.kube_context is not None:
            _validate_context(self.kube_context)
        if self.local_backup_dir is None:
            object.__setattr__(
                self,
                "local_backup_dir",
                Path(".axis/production-backups") / self.backup_id,
            )

    @property
    def job_name(self) -> str:
        normalized = self.backup_id.lower().replace(".", "-")
        return f"axis-postgres-backup-{normalized}"[:63].rstrip("-")


def _validate_identifier(name: str, value: str) -> None:
    if _SAFE_IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{name} must be alphanumeric with optional '.', '-' separators")


def _validate_dns_label(name: str, value: str) -> None:
    if len(value) > 63 or _SAFE_DNS_LABEL.fullmatch(value) is None:
        raise ValueError(f"{name} must be a Kubernetes DNS label")


def _validate_context(value: str) -> None:
    if not value or any(character.isspace() for character in value):
        raise ValueError("kube_context must be a non-empty kubectl context name")


def _validate_positive_integer(name: str, value: int) -> None:
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")


def format_command(command: tuple[str, ...]) -> str:
    return shlex.join(command)


def _kubectl_base(config: BackupRehearsalConfig) -> list[str]:
    command = ["kubectl"]
    if config.kube_context:
        command.extend(["--context", config.kube_context])
    return command


def build_job_manifest(config: BackupRehearsalConfig) -> str:
    dump_command = (
        'pg_dump "$AXIS_POSTGRES_DSN" --format=custom --no-owner '
        "--file=/backup/postgres.dump"
    )
    restore_catalog_command = (
        "pg_restore --list /backup/postgres.dump "
        ">/backup/postgres.restore.list"
    )
    checksum_command = (
        "sha256sum /backup/postgres.dump "
        ">/backup/postgres.dump.sha256"
    )
    manifest = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": config.job_name,
            "labels": {
                "app.kubernetes.io/name": "limes-axis",
                "app.kubernetes.io/component": "postgres-backup-rehearsal",
            },
        },
        "spec": {
            "backoffLimit": 0,
            "template": {
                "metadata": {
                    "labels": {
                        "app.kubernetes.io/name": "limes-axis",
                        "app.kubernetes.io/component": "postgres-backup-rehearsal",
                    }
                },
                "spec": {
                    "restartPolicy": "Never",
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": config.run_as_user,
                        "runAsGroup": config.run_as_group,
                        "fsGroup": config.run_as_group,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "containers": [
                        {
                            "name": "postgres-backup",
                            "image": config.image,
                            "envFrom": [{"secretRef": {"name": config.runtime_secret}}],
                            "command": ["/bin/sh", "-ec"],
                            "args": [
                                "\n".join(
                                    (
                                        "mkdir -p /backup",
                                        dump_command,
                                        restore_catalog_command,
                                        checksum_command,
                                    )
                                )
                            ],
                            "securityContext": {
                                "allowPrivilegeEscalation": False,
                                "capabilities": {"drop": ["ALL"]},
                            },
                            "volumeMounts": [{"name": "backup", "mountPath": "/backup"}],
                        }
                    ],
                    "volumes": [{"name": "backup", "emptyDir": {}}],
                },
            },
        },
    }
    return json.dumps(manifest, sort_keys=True)


def _copy_artifacts_script(config: BackupRehearsalConfig) -> str:
    base = _kubectl_base(config)
    get_pod = format_command(
        tuple(
            [
                *base,
                "-n",
                config.namespace,
                "get",
                "pods",
                "-l",
                f"job-name={config.job_name}",
                "-o",
                "jsonpath={.items[0].metadata.name}",
            ]
        )
    )
    cp_base = format_command(tuple([*base, "-n", config.namespace, "cp"]))
    local_dir = shlex.quote(str(config.local_backup_dir))
    return "\n".join(
        (
            f'pod="$({get_pod})"',
            'test -n "$pod"',
            f"mkdir -p {local_dir}",
            f'{cp_base} "${{pod}}:/backup/postgres.dump" {local_dir}/postgres.dump',
            f'{cp_base} "${{pod}}:/backup/postgres.restore.list" {local_dir}/postgres.restore.list',
            f'{cp_base} "${{pod}}:/backup/postgres.dump.sha256" {local_dir}/postgres.dump.sha256',
        )
    )


def build_rehearsal_steps(config: BackupRehearsalConfig) -> list[CommandStep]:
    base = _kubectl_base(config)
    steps = [
        CommandStep(
            name="confirm Kubernetes context",
            command=tuple([*base, "config", "current-context"]),
        ),
        CommandStep(
            name="confirm Axis runtime secret exists",
            command=tuple([*base, "-n", config.namespace, "get", "secret", config.runtime_secret]),
        ),
        CommandStep(
            name="create local backup evidence directory",
            command=("mkdir", "-p", str(config.local_backup_dir)),
        ),
        CommandStep(
            name="create in-cluster Postgres backup job",
            command=tuple([*base, "-n", config.namespace, "apply", "-f", "-"]),
            stdin_text=build_job_manifest(config),
        ),
        CommandStep(
            name="wait for Postgres backup job completion",
            command=tuple(
                [
                    *base,
                    "-n",
                    config.namespace,
                    "wait",
                    "--for=condition=complete",
                    f"job/{config.job_name}",
                    f"--timeout={config.timeout}",
                ]
            ),
        ),
        CommandStep(
            name="copy backup artifacts and restore catalog locally",
            command=("sh", "-ec", _copy_artifacts_script(config)),
        ),
        CommandStep(
            name="capture backup job logs",
            command=tuple([*base, "-n", config.namespace, "logs", f"job/{config.job_name}"]),
        ),
    ]
    if config.delete_job:
        steps.append(
            CommandStep(
                name="delete backup rehearsal job",
                command=tuple(
                    [*base, "-n", config.namespace, "delete", "job", config.job_name]
                ),
            )
        )
    return steps


def print_plan(steps: list[CommandStep]) -> None:
    for index, step in enumerate(steps, start=1):
        print(f"{index}. {step.name}")
        print(f"   {format_command(step.command)}")
        if step.stdin_text is not None:
            print(f"   stdin: {step.stdin_text}")


def run_rehearsal(steps: list[CommandStep]) -> None:
    for step in steps:
        print(f"[axis-backup] {step.name}")
        subprocess.run(step.command, input=step.stdin_text, text=True, check=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or print the Limes Axis production backup rehearsal."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true", help="Print rehearsal steps only.")
    mode.add_argument("--execute", action="store_true", help="Execute rehearsal steps.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--namespace", default="limes-axis")
    parser.add_argument("--context", dest="kube_context")
    parser.add_argument("--runtime-secret", default="limes-axis-runtime")
    parser.add_argument("--backup-id", default="manual-rehearsal")
    parser.add_argument("--local-backup-dir", type=Path)
    parser.add_argument("--image", default="postgres:16-alpine")
    parser.add_argument("--timeout", default="15m")
    parser.add_argument(
        "--run-as-user",
        type=int,
        default=70,
        help="Container UID for the Postgres client image. Default matches postgres:16-alpine.",
    )
    parser.add_argument(
        "--run-as-group",
        type=int,
        default=70,
        help="Container GID and backup volume fsGroup. Default matches postgres:16-alpine.",
    )
    parser.add_argument("--keep-job", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> BackupRehearsalConfig:
    backup_dir = args.local_backup_dir
    if backup_dir is None:
        backup_dir = args.repo_root.resolve() / ".axis" / "production-backups" / args.backup_id
    return BackupRehearsalConfig(
        namespace=args.namespace,
        kube_context=args.kube_context,
        runtime_secret=args.runtime_secret,
        backup_id=args.backup_id,
        local_backup_dir=backup_dir,
        image=args.image,
        timeout=args.timeout,
        run_as_user=args.run_as_user,
        run_as_group=args.run_as_group,
        delete_job=not args.keep_job,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = config_from_args(args)
    except ValueError as error:
        print(f"[axis-backup] invalid configuration: {error}", file=sys.stderr)
        return 2
    steps = build_rehearsal_steps(config)
    if args.plan:
        print_plan(steps)
        return 0

    try:
        run_rehearsal(steps)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"[axis-backup] failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
