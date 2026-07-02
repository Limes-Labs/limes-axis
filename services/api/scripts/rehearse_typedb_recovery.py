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
_PLACEHOLDER_TYPEDB_IMAGE = "REPLACE_WITH_TYPEDB_CONSOLE_IMAGE"
_RUNTIME_SECRET_KEYS = (
    "AXIS_TYPEDB_ADDRESS",
    "AXIS_TYPEDB_USERNAME",
    "AXIS_TYPEDB_PASSWORD",
    "AXIS_TYPEDB_DATABASE",
)
_RESTORE_SECRET_KEYS = (
    "AXIS_TYPEDB_RESTORE_ADDRESS",
    "AXIS_TYPEDB_RESTORE_USERNAME",
    "AXIS_TYPEDB_RESTORE_PASSWORD",
    "AXIS_TYPEDB_RESTORE_DATABASE",
)


@dataclass(frozen=True)
class CommandStep:
    name: str
    command: tuple[str, ...]
    stdin_text: str | None = None


@dataclass(frozen=True)
class TypeDBRecoveryRehearsalConfig:
    namespace: str = "limes-axis"
    kube_context: str | None = None
    runtime_secret: str = "limes-axis-runtime"
    restore_target_secret: str = "limes-axis-typedb-restore-target"
    recovery_id: str = "manual-rehearsal"
    local_evidence_dir: Path | None = None
    image: str = _PLACEHOLDER_TYPEDB_IMAGE
    timeout: str = "20m"
    run_as_user: int = 10001
    run_as_group: int = 10001
    delete_pod: bool = True

    def __post_init__(self) -> None:
        _validate_dns_label("namespace", self.namespace)
        _validate_dns_label("runtime_secret", self.runtime_secret)
        _validate_dns_label("restore_target_secret", self.restore_target_secret)
        _validate_restore_secret_name(self.runtime_secret, self.restore_target_secret)
        _validate_identifier("recovery_id", self.recovery_id)
        _validate_image(self.image)
        _validate_positive_integer("run_as_user", self.run_as_user)
        _validate_positive_integer("run_as_group", self.run_as_group)
        if self.kube_context is not None:
            _validate_context(self.kube_context)
        if self.local_evidence_dir is None:
            object.__setattr__(
                self,
                "local_evidence_dir",
                Path(".axis/typedb-recovery") / self.recovery_id,
            )

    @property
    def pod_name(self) -> str:
        normalized = self.recovery_id.lower().replace(".", "-")
        return f"axis-typedb-recovery-{normalized}"[:63].rstrip("-")


def _validate_identifier(name: str, value: str) -> None:
    if _SAFE_IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{name} must be alphanumeric with optional '.', '-' separators")


def _validate_dns_label(name: str, value: str) -> None:
    if len(value) > 63 or _SAFE_DNS_LABEL.fullmatch(value) is None:
        raise ValueError(f"{name} must be a Kubernetes DNS label")


def _validate_restore_secret_name(runtime_secret: str, restore_target_secret: str) -> None:
    if restore_target_secret in _FORBIDDEN_RESTORE_SECRETS:
        raise ValueError("restore_target_secret must not be the Axis runtime secret")
    if restore_target_secret == runtime_secret:
        raise ValueError("restore_target_secret must be separate from runtime_secret")


def _validate_context(value: str) -> None:
    if not value or any(character.isspace() for character in value):
        raise ValueError("kube_context must be a non-empty kubectl context name")


def _validate_image(value: str) -> None:
    if not value or any(character.isspace() for character in value):
        raise ValueError("image must be a non-empty container image reference")


def _requires_operator_image(value: str) -> bool:
    return value == _PLACEHOLDER_TYPEDB_IMAGE


def _validate_positive_integer(name: str, value: int) -> None:
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")


def format_command(command: tuple[str, ...]) -> str:
    return shlex.join(command)


def _kubectl_base(config: TypeDBRecoveryRehearsalConfig) -> list[str]:
    command = ["kubectl"]
    if config.kube_context:
        command.extend(["--context", config.kube_context])
    return command


def build_pod_manifest(config: TypeDBRecoveryRehearsalConfig) -> str:
    manifest = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": config.pod_name,
            "labels": {
                "app.kubernetes.io/name": "limes-axis",
                "app.kubernetes.io/component": "typedb-recovery-rehearsal",
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
                    "name": "typedb-recovery",
                    "image": config.image,
                    "env": [
                        {"name": "HOME", "value": "/typedb-recovery"},
                        {"name": "XDG_CACHE_HOME", "value": "/typedb-recovery/.cache"},
                    ],
                    "envFrom": [
                        {"secretRef": {"name": config.runtime_secret}},
                        {"secretRef": {"name": config.restore_target_secret}},
                    ],
                    "command": ["/bin/sh", "-ec"],
                    "args": [
                        "trap 'exit 0' TERM INT\n"
                        "mkdir -p /typedb-recovery/.cache\n"
                        "while true; do sleep 30; done"
                    ],
                    "securityContext": {
                        "allowPrivilegeEscalation": False,
                        "capabilities": {"drop": ["ALL"]},
                    },
                    "volumeMounts": [
                        {"name": "typedb-recovery", "mountPath": "/typedb-recovery"}
                    ],
                }
            ],
            "volumes": [{"name": "typedb-recovery", "emptyDir": {}}],
        },
    }
    return json.dumps(manifest, sort_keys=True)


def _jsonpath_secret_annotation(config: TypeDBRecoveryRehearsalConfig) -> str:
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
            r"jsonpath={.metadata.annotations.limes-axis\.io/typedb-restore-target}",
        ]
    )
    return format_command(command)


def _jsonpath_secret_key(
    config: TypeDBRecoveryRehearsalConfig, secret_name: str, key: str
) -> str:
    base = _kubectl_base(config)
    command = tuple(
        [
            *base,
            "-n",
            config.namespace,
            "get",
            "secret",
            secret_name,
            "-o",
            f"jsonpath={{.data.{key}}}",
        ]
    )
    return format_command(command)


def _kubectl_exec(config: TypeDBRecoveryRehearsalConfig, script: str) -> tuple[str, ...]:
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


def _kubectl_cp(config: TypeDBRecoveryRehearsalConfig, source: str, target: str) -> tuple[str, ...]:
    base = _kubectl_base(config)
    return tuple([*base, "-n", config.namespace, "cp", source, target])


def _required_secret_key_steps(
    config: TypeDBRecoveryRehearsalConfig, secret_name: str, keys: tuple[str, ...]
) -> list[CommandStep]:
    steps: list[CommandStep] = []
    for key in keys:
        steps.append(
            CommandStep(
                name=f"confirm {secret_name} exposes {key}",
                command=(
                    "sh",
                    "-ec",
                    "encoded=\"$(" + _jsonpath_secret_key(config, secret_name, key) + ")\"\n"
                    'test -n "$encoded"',
                ),
            )
        )
    return steps


def _copy_evidence_script(config: TypeDBRecoveryRehearsalConfig) -> str:
    assert config.local_evidence_dir is not None
    local_dir = shlex.quote(str(config.local_evidence_dir))
    copies = (
        _kubectl_cp(
            config,
            f"{config.pod_name}:/typedb-recovery/typedb.schema.typeql",
            f"{config.local_evidence_dir}/typedb.schema.typeql",
        ),
        _kubectl_cp(
            config,
            f"{config.pod_name}:/typedb-recovery/typedb.data",
            f"{config.local_evidence_dir}/typedb.data",
        ),
        _kubectl_cp(
            config,
            f"{config.pod_name}:/typedb-recovery/typedb.sha256",
            f"{config.local_evidence_dir}/typedb.sha256",
        ),
        _kubectl_cp(
            config,
            f"{config.pod_name}:/typedb-recovery/typedb.console.help",
            f"{config.local_evidence_dir}/typedb.console.help",
        ),
        _kubectl_cp(
            config,
            f"{config.pod_name}:/typedb-recovery/typedb.export.log",
            f"{config.local_evidence_dir}/typedb.export.log",
        ),
        _kubectl_cp(
            config,
            f"{config.pod_name}:/typedb-recovery/typedb.import.log",
            f"{config.local_evidence_dir}/typedb.import.log",
        ),
        _kubectl_cp(
            config,
            f"{config.pod_name}:/typedb-recovery/typedb.restore.probe",
            f"{config.local_evidence_dir}/typedb.restore.probe",
        ),
    )
    return "\n".join((f"mkdir -p {local_dir}", *(format_command(command) for command in copies)))


def _typedb_bin_prelude() -> str:
    return "\n".join(
        (
            "resolve_typedb_bin() {",
            '  if [ -n "${AXIS_TYPEDB_BIN:-}" ]; then',
            '    printf "%s\\n" "$AXIS_TYPEDB_BIN"',
            "    return",
            "  fi",
            "  for candidate in "
            "/opt/typedb-server-*/typedb /usr/local/bin/typedb /usr/bin/typedb; do",
            '    if [ -x "$candidate" ]; then',
            '      printf "%s\\n" "$candidate"',
            "      return",
            "    fi",
            "  done",
            "  command -v typedb",
            "}",
            'typedb_bin="$(resolve_typedb_bin)"',
        )
    )


def _console_probe_script() -> str:
    return "\n".join(
        (
            "set -eu",
            "mkdir -p /typedb-recovery",
            _typedb_bin_prelude(),
            '"$typedb_bin" console --help >/typedb-recovery/typedb.console.help',
        )
    )


def _export_script() -> str:
    return "\n".join(
        (
            "set -eu",
            "mkdir -p /typedb-recovery",
            _typedb_bin_prelude(),
            'source_database="$AXIS_TYPEDB_DATABASE"',
            "if [ \"${AXIS_TYPEDB_TLS_DISABLED:-false}\" = \"true\" ]; then",
            '  tls_flag="--tls-disabled"',
            "else",
            '  tls_flag=""',
            "fi",
            '"$typedb_bin" console $tls_flag '
            '--address "$AXIS_TYPEDB_ADDRESS" '
            '--username "$AXIS_TYPEDB_USERNAME" '
            '--password "$AXIS_TYPEDB_PASSWORD" '
            '--command "database export ${source_database} '
            '/typedb-recovery/typedb.schema.typeql /typedb-recovery/typedb.data" '
            ">/typedb-recovery/typedb.export.log",
            "sha256sum /typedb-recovery/typedb.schema.typeql /typedb-recovery/typedb.data "
            ">/typedb-recovery/typedb.sha256",
        )
    )


def _import_script() -> str:
    return "\n".join(
        (
            "set -eu",
            _typedb_bin_prelude(),
            'restore_database="$AXIS_TYPEDB_RESTORE_DATABASE"',
            "if [ \"${AXIS_TYPEDB_RESTORE_TLS_DISABLED:-false}\" = \"true\" ]; then",
            '  tls_flag="--tls-disabled"',
            "else",
            '  tls_flag=""',
            "fi",
            '"$typedb_bin" console $tls_flag '
            '--address "$AXIS_TYPEDB_RESTORE_ADDRESS" '
            '--username "$AXIS_TYPEDB_RESTORE_USERNAME" '
            '--password "$AXIS_TYPEDB_RESTORE_PASSWORD" '
            '--command "database import ${restore_database} '
            '/typedb-recovery/typedb.schema.typeql /typedb-recovery/typedb.data" '
            ">/typedb-recovery/typedb.import.log",
            '"$typedb_bin" console $tls_flag '
            '--address "$AXIS_TYPEDB_RESTORE_ADDRESS" '
            '--username "$AXIS_TYPEDB_RESTORE_USERNAME" '
            '--password "$AXIS_TYPEDB_RESTORE_PASSWORD" '
            '--command "database list" >/typedb-recovery/typedb.restore.probe',
            'grep -F "$restore_database" /typedb-recovery/typedb.restore.probe >/dev/null',
        )
    )


def build_rehearsal_steps(config: TypeDBRecoveryRehearsalConfig) -> list[CommandStep]:
    base = _kubectl_base(config)
    assert config.local_evidence_dir is not None
    steps = [
        CommandStep(
            name="confirm Kubernetes context",
            command=tuple([*base, "config", "current-context"]),
        ),
        CommandStep(
            name="confirm Axis TypeDB runtime secret exists",
            command=tuple([*base, "-n", config.namespace, "get", "secret", config.runtime_secret]),
        ),
        CommandStep(
            name="confirm isolated TypeDB restore target secret exists",
            command=tuple(
                [*base, "-n", config.namespace, "get", "secret", config.restore_target_secret]
            ),
        ),
        CommandStep(
            name="confirm TypeDB restore target is marked isolated",
            command=(
                "sh",
                "-ec",
                "annotation=\"$("
                + _jsonpath_secret_annotation(config)
                + ")\"\n"
                'test "$annotation" = "isolated"',
            ),
        ),
    ]
    steps.extend(_required_secret_key_steps(config, config.runtime_secret, _RUNTIME_SECRET_KEYS))
    steps.extend(
        _required_secret_key_steps(config, config.restore_target_secret, _RESTORE_SECRET_KEYS)
    )
    steps.extend(
        [
            CommandStep(
                name="create local TypeDB recovery evidence directory",
                command=("mkdir", "-p", str(config.local_evidence_dir)),
            ),
            CommandStep(
                name="create isolated in-cluster TypeDB recovery pod",
                command=tuple([*base, "-n", config.namespace, "apply", "-f", "-"]),
                stdin_text=build_pod_manifest(config),
            ),
            CommandStep(
                name="wait for TypeDB recovery pod readiness",
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
                name="verify TypeDB Console is available in recovery image",
                command=_kubectl_exec(config, _console_probe_script()),
            ),
            CommandStep(
                name="export TypeDB schema and data from runtime store",
                command=_kubectl_exec(config, _export_script()),
            ),
            CommandStep(
                name="import TypeDB export into isolated restore target",
                command=_kubectl_exec(config, _import_script()),
            ),
            CommandStep(
                name="copy TypeDB recovery evidence locally",
                command=("sh", "-ec", _copy_evidence_script(config)),
            ),
            CommandStep(
                name="capture TypeDB recovery pod logs",
                command=tuple([*base, "-n", config.namespace, "logs", config.pod_name]),
            ),
        ]
    )
    if config.delete_pod:
        steps.append(
            CommandStep(
                name="delete TypeDB recovery pod",
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
        print(f"[axis-typedb-recovery] {step.name}")
        subprocess.run(step.command, input=step.stdin_text, text=True, check=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or print the Limes Axis TypeDB recovery rehearsal."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true", help="Print rehearsal steps only.")
    mode.add_argument("--execute", action="store_true", help="Execute rehearsal steps.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--namespace", default="limes-axis")
    parser.add_argument("--context", dest="kube_context")
    parser.add_argument("--runtime-secret", default="limes-axis-runtime")
    parser.add_argument("--restore-target-secret", default="limes-axis-typedb-restore-target")
    parser.add_argument("--recovery-id", default="manual-rehearsal")
    parser.add_argument("--local-evidence-dir", type=Path)
    parser.add_argument("--image", default=_PLACEHOLDER_TYPEDB_IMAGE)
    parser.add_argument("--timeout", default="20m")
    parser.add_argument(
        "--run-as-user",
        type=int,
        default=10001,
        help="Container UID for the TypeDB client image.",
    )
    parser.add_argument(
        "--run-as-group",
        type=int,
        default=10001,
        help="Container GID and recovery volume fsGroup.",
    )
    parser.add_argument("--keep-pod", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> TypeDBRecoveryRehearsalConfig:
    recovery_id = args.recovery_id
    evidence_dir = args.local_evidence_dir
    if evidence_dir is None:
        evidence_dir = (
            args.repo_root.resolve() / ".axis" / "typedb-recovery" / recovery_id
        )
    return TypeDBRecoveryRehearsalConfig(
        namespace=args.namespace,
        kube_context=args.kube_context,
        runtime_secret=args.runtime_secret,
        restore_target_secret=args.restore_target_secret,
        recovery_id=recovery_id,
        local_evidence_dir=evidence_dir,
        image=args.image,
        timeout=args.timeout,
        run_as_user=args.run_as_user,
        run_as_group=args.run_as_group,
        delete_pod=not args.keep_pod,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.execute and _requires_operator_image(args.image):
        print(
            "[axis-typedb-recovery] invalid configuration: set --image or "
            "AXIS_TYPEDB_RECOVERY_IMAGE to a typedb-console-capable image",
            file=sys.stderr,
        )
        return 2
    try:
        config = config_from_args(args)
    except ValueError as error:
        print(f"[axis-typedb-recovery] invalid configuration: {error}", file=sys.stderr)
        return 2
    steps = build_rehearsal_steps(config)
    if args.plan:
        print_plan(steps)
        return 0

    try:
        run_rehearsal(steps)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"[axis-typedb-recovery] failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
