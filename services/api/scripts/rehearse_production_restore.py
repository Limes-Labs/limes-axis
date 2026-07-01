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
_FORBIDDEN_RESTORE_SECRETS = frozenset({"axis-runtime", "limes-axis-runtime"})


@dataclass(frozen=True)
class CommandStep:
    name: str
    command: tuple[str, ...]
    stdin_text: str | None = None


@dataclass(frozen=True)
class RestoreRehearsalConfig:
    namespace: str = "limes-axis"
    kube_context: str | None = None
    restore_target_secret: str = "limes-axis-restore-target"
    restore_id: str = "manual-rehearsal"
    dump_path: Path = Path(".axis/production-backups/manual-rehearsal/postgres.dump")
    checksum_path: Path | None = None
    local_evidence_dir: Path | None = None
    image: str = "postgres:16-alpine"
    timeout: str = "15m"
    run_as_user: int = 70
    run_as_group: int = 70
    delete_pod: bool = True

    def __post_init__(self) -> None:
        _validate_dns_label("namespace", self.namespace)
        _validate_dns_label("restore_target_secret", self.restore_target_secret)
        _validate_restore_secret_name(self.restore_target_secret)
        _validate_identifier("restore_id", self.restore_id)
        _validate_positive_integer("run_as_user", self.run_as_user)
        _validate_positive_integer("run_as_group", self.run_as_group)
        if self.kube_context is not None:
            _validate_context(self.kube_context)
        if self.checksum_path is None:
            object.__setattr__(
                self,
                "checksum_path",
                self.dump_path.with_name(f"{self.dump_path.name}.sha256"),
            )
        if self.local_evidence_dir is None:
            object.__setattr__(
                self,
                "local_evidence_dir",
                Path(".axis/production-restores") / self.restore_id,
            )

    @property
    def pod_name(self) -> str:
        normalized = self.restore_id.lower().replace(".", "-")
        return f"axis-postgres-restore-{normalized}"[:63].rstrip("-")


def _validate_identifier(name: str, value: str) -> None:
    if _SAFE_IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{name} must be alphanumeric with optional '.', '-' separators")


def _validate_dns_label(name: str, value: str) -> None:
    if len(value) > 63 or _SAFE_DNS_LABEL.fullmatch(value) is None:
        raise ValueError(f"{name} must be a Kubernetes DNS label")


def _validate_restore_secret_name(value: str) -> None:
    if value in _FORBIDDEN_RESTORE_SECRETS:
        raise ValueError("restore_target_secret must not be the Axis runtime secret")


def _validate_context(value: str) -> None:
    if not value or any(character.isspace() for character in value):
        raise ValueError("kube_context must be a non-empty kubectl context name")


def _validate_positive_integer(name: str, value: int) -> None:
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")


def format_command(command: tuple[str, ...]) -> str:
    return shlex.join(command)


def _kubectl_base(config: RestoreRehearsalConfig) -> list[str]:
    command = ["kubectl"]
    if config.kube_context:
        command.extend(["--context", config.kube_context])
    return command


def build_pod_manifest(config: RestoreRehearsalConfig) -> str:
    manifest = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": config.pod_name,
            "labels": {
                "app.kubernetes.io/name": "limes-axis",
                "app.kubernetes.io/component": "postgres-restore-rehearsal",
            },
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
                    "name": "postgres-restore",
                    "image": config.image,
                    "envFrom": [{"secretRef": {"name": config.restore_target_secret}}],
                    "command": ["/bin/sh", "-ec"],
                    "args": [
                        "trap 'exit 0' TERM INT\n"
                        "mkdir -p /restore\n"
                        "while true; do sleep 30; done"
                    ],
                    "securityContext": {
                        "allowPrivilegeEscalation": False,
                        "capabilities": {"drop": ["ALL"]},
                    },
                    "volumeMounts": [{"name": "restore", "mountPath": "/restore"}],
                }
            ],
            "volumes": [{"name": "restore", "emptyDir": {}}],
        },
    }
    return json.dumps(manifest, sort_keys=True)


def _jsonpath_secret_annotation(config: RestoreRehearsalConfig) -> str:
    base = _kubectl_base(config)
    command = tuple(
        [
            *base,
            "-n",
            config.namespace,
            "get",
            "secret",
            config.restore_target_secret,
            "-o",
            r"jsonpath={.metadata.annotations.limes-axis\.io/restore-target}",
        ]
    )
    return format_command(command)


def _jsonpath_restore_dsn_key(config: RestoreRehearsalConfig) -> str:
    base = _kubectl_base(config)
    command = tuple(
        [
            *base,
            "-n",
            config.namespace,
            "get",
            "secret",
            config.restore_target_secret,
            "-o",
            "jsonpath={.data.AXIS_POSTGRES_RESTORE_DSN}",
        ]
    )
    return format_command(command)


def _kubectl_exec(config: RestoreRehearsalConfig, script: str) -> tuple[str, ...]:
    base = _kubectl_base(config)
    return tuple(
        [
            *base,
            "-n",
            config.namespace,
            "exec",
            config.pod_name,
            "--",
            "sh",
            "-ec",
            script,
        ]
    )


def _kubectl_cp(config: RestoreRehearsalConfig, source: str, target: str) -> tuple[str, ...]:
    base = _kubectl_base(config)
    return tuple([*base, "-n", config.namespace, "cp", source, target])


def _copy_evidence_script(config: RestoreRehearsalConfig) -> str:
    local_dir = shlex.quote(str(config.local_evidence_dir))
    restore_list = format_command(
        _kubectl_cp(
            config,
            f"{config.pod_name}:/restore/postgres.restore.list",
            f"{config.local_evidence_dir}/postgres.restore.list",
        )
    )
    restore_probe = format_command(
        _kubectl_cp(
            config,
            f"{config.pod_name}:/restore/postgres.restore.probe",
            f"{config.local_evidence_dir}/postgres.restore.probe",
        )
    )
    checksum = format_command(
        _kubectl_cp(
            config,
            f"{config.pod_name}:/restore/postgres.dump.sha256.calculated",
            f"{config.local_evidence_dir}/postgres.dump.sha256.calculated",
        )
    )
    return "\n".join((f"mkdir -p {local_dir}", restore_list, restore_probe, checksum))


def build_rehearsal_steps(config: RestoreRehearsalConfig) -> list[CommandStep]:
    base = _kubectl_base(config)
    assert config.checksum_path is not None
    steps = [
        CommandStep(
            name="confirm Kubernetes context",
            command=tuple([*base, "config", "current-context"]),
        ),
        CommandStep(
            name="confirm isolated restore target secret exists",
            command=tuple(
                [
                    *base,
                    "-n",
                    config.namespace,
                    "get",
                    "secret",
                    config.restore_target_secret,
                ]
            ),
        ),
        CommandStep(
            name="confirm restore target is marked isolated",
            command=(
                "sh",
                "-ec",
                "annotation=\"$("
                + _jsonpath_secret_annotation(config)
                + ")\"\n"
                'test "$annotation" = "isolated"',
            ),
        ),
        CommandStep(
            name="confirm restore target secret exposes AXIS_POSTGRES_RESTORE_DSN",
            command=(
                "sh",
                "-ec",
                "encoded=\"$("
                + _jsonpath_restore_dsn_key(config)
                + ")\"\n"
                'test -n "$encoded"',
            ),
        ),
        CommandStep(
            name="confirm local Postgres dump artifact exists",
            command=("test", "-f", str(config.dump_path)),
        ),
        CommandStep(
            name="confirm local Postgres dump checksum exists",
            command=("test", "-f", str(config.checksum_path)),
        ),
        CommandStep(
            name="create local restore evidence directory",
            command=("mkdir", "-p", str(config.local_evidence_dir)),
        ),
        CommandStep(
            name="create isolated in-cluster Postgres restore pod",
            command=tuple([*base, "-n", config.namespace, "apply", "-f", "-"]),
            stdin_text=build_pod_manifest(config),
        ),
        CommandStep(
            name="wait for Postgres restore pod readiness",
            command=tuple(
                [
                    *base,
                    "-n",
                    config.namespace,
                    "wait",
                    "--for=condition=Ready",
                    f"pod/{config.pod_name}",
                    f"--timeout={config.timeout}",
                ]
            ),
        ),
        CommandStep(
            name="copy Postgres dump into isolated restore pod",
            command=_kubectl_cp(
                config,
                str(config.dump_path),
                f"{config.pod_name}:/restore/postgres.dump",
            ),
        ),
        CommandStep(
            name="copy Postgres dump checksum into isolated restore pod",
            command=_kubectl_cp(
                config,
                str(config.checksum_path),
                f"{config.pod_name}:/restore/postgres.dump.sha256",
            ),
        ),
        CommandStep(
            name="verify Postgres dump checksum inside restore pod",
            command=_kubectl_exec(
                config,
                "cd /restore\n"
                "expected=\"$(awk '{print $1}' postgres.dump.sha256)\"\n"
                "actual=\"$(sha256sum postgres.dump | awk '{print $1}')\"\n"
                'test "$expected" = "$actual"\n'
                "printf '%s  postgres.dump\\n' \"$actual\" "
                ">postgres.dump.sha256.calculated",
            ),
        ),
        CommandStep(
            name="validate Postgres dump restore catalog",
            command=_kubectl_exec(
                config,
                "pg_restore --list /restore/postgres.dump "
                ">/restore/postgres.restore.list",
            ),
        ),
        CommandStep(
            name="restore Postgres dump into isolated target",
            command=_kubectl_exec(
                config,
                'pg_restore --clean --if-exists --no-owner '
                '--dbname "$AXIS_POSTGRES_RESTORE_DSN" '
                "/restore/postgres.dump",
            ),
        ),
        CommandStep(
            name="probe isolated restore target",
            command=_kubectl_exec(
                config,
                'psql "$AXIS_POSTGRES_RESTORE_DSN" '
                "-v ON_ERROR_STOP=1 -Atc 'select 1' "
                ">/restore/postgres.restore.probe",
            ),
        ),
        CommandStep(
            name="copy restore rehearsal evidence locally",
            command=("sh", "-ec", _copy_evidence_script(config)),
        ),
        CommandStep(
            name="capture restore rehearsal pod logs",
            command=tuple([*base, "-n", config.namespace, "logs", config.pod_name]),
        ),
    ]
    if config.delete_pod:
        steps.append(
            CommandStep(
                name="delete isolated restore pod",
                command=tuple([*base, "-n", config.namespace, "delete", "pod", config.pod_name]),
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
        print(f"[axis-restore] {step.name}")
        subprocess.run(step.command, input=step.stdin_text, text=True, check=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or print the Limes Axis production restore rehearsal."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true", help="Print rehearsal steps only.")
    mode.add_argument("--execute", action="store_true", help="Execute rehearsal steps.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--namespace", default="limes-axis")
    parser.add_argument("--context", dest="kube_context")
    parser.add_argument("--restore-target-secret", default="limes-axis-restore-target")
    parser.add_argument("--restore-id", default="manual-rehearsal")
    parser.add_argument("--dump-path", type=Path)
    parser.add_argument("--checksum-path", type=Path)
    parser.add_argument("--local-evidence-dir", type=Path)
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
        help="Container GID and restore volume fsGroup. Default matches postgres:16-alpine.",
    )
    parser.add_argument("--keep-pod", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> RestoreRehearsalConfig:
    restore_id = args.restore_id
    dump_path = args.dump_path
    if dump_path is None:
        dump_path = (
            args.repo_root.resolve()
            / ".axis"
            / "production-backups"
            / restore_id
            / "postgres.dump"
        )
    evidence_dir = args.local_evidence_dir
    if evidence_dir is None:
        evidence_dir = (
            args.repo_root.resolve() / ".axis" / "production-restores" / restore_id
        )
    return RestoreRehearsalConfig(
        namespace=args.namespace,
        kube_context=args.kube_context,
        restore_target_secret=args.restore_target_secret,
        restore_id=restore_id,
        dump_path=dump_path,
        checksum_path=args.checksum_path,
        local_evidence_dir=evidence_dir,
        image=args.image,
        timeout=args.timeout,
        run_as_user=args.run_as_user,
        run_as_group=args.run_as_group,
        delete_pod=not args.keep_pod,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = config_from_args(args)
    except ValueError as error:
        print(f"[axis-restore] invalid configuration: {error}", file=sys.stderr)
        return 2
    steps = build_rehearsal_steps(config)
    if args.plan:
        print_plan(steps)
        return 0

    try:
        run_rehearsal(steps)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"[axis-restore] failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
