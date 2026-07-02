from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,48}$")
_SAFE_DNS_LABEL = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
_FORBIDDEN_RESTORE_SECRETS = frozenset({"axis-runtime", "limes-axis-runtime"})
_PLACEHOLDER_MC_IMAGE = "REPLACE_WITH_MINIO_CLIENT_IMAGE"
_SOURCE_CONFIG_KEYS = (
    "AXIS_CONNECTOR_EXPORT_S3_ENDPOINT",
    "AXIS_CONNECTOR_EXPORT_S3_BUCKET",
    "AXIS_CONNECTOR_EXPORT_S3_SECURE_TRANSPORT",
    "AXIS_CONNECTOR_EXPORT_S3_OBJECT_LOCK_ENABLED",
    "AXIS_CONNECTOR_EXPORT_S3_RETENTION_DAYS",
)
_SOURCE_SECRET_KEYS = (
    "AXIS_CONNECTOR_EXPORT_S3_ACCESS_KEY",
    "AXIS_CONNECTOR_EXPORT_S3_SECRET_KEY",
)
_RESTORE_SECRET_KEYS = (
    "AXIS_CONNECTOR_EXPORT_S3_RESTORE_ENDPOINT",
    "AXIS_CONNECTOR_EXPORT_S3_RESTORE_BUCKET",
    "AXIS_CONNECTOR_EXPORT_S3_RESTORE_ACCESS_KEY",
    "AXIS_CONNECTOR_EXPORT_S3_RESTORE_SECRET_KEY",
)


@dataclass(frozen=True)
class CommandStep:
    name: str
    command: tuple[str, ...]
    stdin_text: str | None = None


@dataclass(frozen=True)
class ObjectStorageRecoveryRehearsalConfig:
    namespace: str = "limes-axis"
    kube_context: str | None = None
    runtime_config_map: str = "limes-axis-config"
    runtime_secret: str = "limes-axis-runtime"
    restore_target_secret: str = "limes-axis-object-store-restore-target"
    recovery_id: str = "manual-rehearsal"
    probe_prefix: str = "axis-recovery-probes"
    local_evidence_dir: Path | None = None
    image: str = _PLACEHOLDER_MC_IMAGE
    timeout: str = "15m"
    run_as_user: int = 10001
    run_as_group: int = 10001
    delete_pod: bool = True

    def __post_init__(self) -> None:
        _validate_dns_label("namespace", self.namespace)
        _validate_dns_label("runtime_config_map", self.runtime_config_map)
        _validate_dns_label("runtime_secret", self.runtime_secret)
        _validate_dns_label("restore_target_secret", self.restore_target_secret)
        _validate_restore_secret_name(self.runtime_secret, self.restore_target_secret)
        _validate_identifier("recovery_id", self.recovery_id)
        _validate_probe_prefix(self.probe_prefix)
        _validate_image(self.image)
        _validate_positive_integer("run_as_user", self.run_as_user)
        _validate_positive_integer("run_as_group", self.run_as_group)
        if self.kube_context is not None:
            _validate_context(self.kube_context)
        if self.local_evidence_dir is None:
            object.__setattr__(
                self,
                "local_evidence_dir",
                Path(".axis/object-storage-recovery") / self.recovery_id,
            )

    @property
    def pod_name(self) -> str:
        normalized = self.recovery_id.lower().replace(".", "-")
        return f"axis-object-store-recovery-{normalized}"[:63].rstrip("-")

    @property
    def probe_key(self) -> str:
        prefix = self.probe_prefix.strip("/")
        return f"{prefix}/{self.recovery_id}/probe.json"


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


def _validate_probe_prefix(value: str) -> None:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError("probe_prefix must be a relative clean object-store prefix")


def _requires_operator_image(value: str) -> bool:
    return value == _PLACEHOLDER_MC_IMAGE


def _validate_positive_integer(name: str, value: int) -> None:
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")


def format_command(command: tuple[str, ...]) -> str:
    return shlex.join(command)


def _kubectl_base(config: ObjectStorageRecoveryRehearsalConfig) -> list[str]:
    command = ["kubectl"]
    if config.kube_context:
        command.extend(["--context", config.kube_context])
    return command


def build_pod_manifest(config: ObjectStorageRecoveryRehearsalConfig) -> str:
    manifest = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": config.pod_name,
            "labels": {
                "app.kubernetes.io/name": "limes-axis",
                "app.kubernetes.io/component": "object-storage-recovery-rehearsal",
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
                    "name": "object-storage-recovery",
                    "image": config.image,
                    "env": [
                        {"name": "HOME", "value": "/object-store-recovery"},
                        {
                            "name": "MC_CONFIG_DIR",
                            "value": "/object-store-recovery/.mc",
                        },
                    ],
                    "envFrom": [
                        {"configMapRef": {"name": config.runtime_config_map}},
                        {"secretRef": {"name": config.runtime_secret}},
                        {"secretRef": {"name": config.restore_target_secret}},
                    ],
                    "command": ["/bin/sh", "-ec"],
                    "args": [
                        "trap 'exit 0' TERM INT\n"
                        "mkdir -p /object-store-recovery/.mc\n"
                        "while true; do sleep 30; done"
                    ],
                    "securityContext": {
                        "allowPrivilegeEscalation": False,
                        "capabilities": {"drop": ["ALL"]},
                    },
                    "volumeMounts": [
                        {
                            "name": "object-store-recovery",
                            "mountPath": "/object-store-recovery",
                        }
                    ],
                }
            ],
            "volumes": [{"name": "object-store-recovery", "emptyDir": {}}],
        },
    }
    return json.dumps(manifest, sort_keys=True)


def _jsonpath_secret_annotation(config: ObjectStorageRecoveryRehearsalConfig) -> str:
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
            r"jsonpath={.metadata.annotations.limes-axis\.io/object-store-restore-target}",
        ]
    )
    return format_command(command)


def _jsonpath_config_key(
    config: ObjectStorageRecoveryRehearsalConfig, config_map_name: str, key: str
) -> str:
    base = _kubectl_base(config)
    command = tuple(
        [
            *base,
            "-n",
            config.namespace,
            "get",
            "configmap",
            config_map_name,
            "-o",
            f"jsonpath={{.data.{key}}}",
        ]
    )
    return format_command(command)


def _jsonpath_secret_key(
    config: ObjectStorageRecoveryRehearsalConfig, secret_name: str, key: str
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


def _kubectl_exec(
    config: ObjectStorageRecoveryRehearsalConfig, script: str
) -> tuple[str, ...]:
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


def _kubectl_cp(
    config: ObjectStorageRecoveryRehearsalConfig, source: str, target: str
) -> tuple[str, ...]:
    base = _kubectl_base(config)
    return tuple([*base, "-n", config.namespace, "cp", source, target])


def _required_config_key_steps(
    config: ObjectStorageRecoveryRehearsalConfig,
    config_map_name: str,
    keys: tuple[str, ...],
) -> list[CommandStep]:
    steps: list[CommandStep] = []
    for key in keys:
        steps.append(
            CommandStep(
                name=f"confirm {config_map_name} exposes {key}",
                command=(
                    "sh",
                    "-ec",
                    "value=\"$("
                    + _jsonpath_config_key(config, config_map_name, key)
                    + ")\"\n"
                    'test -n "$value"',
                ),
            )
        )
    return steps


def _required_secret_key_steps(
    config: ObjectStorageRecoveryRehearsalConfig,
    secret_name: str,
    keys: tuple[str, ...],
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


def _mc_prelude() -> str:
    return "\n".join(
        (
            "resolve_mc_bin() {",
            '  if [ -n "${AXIS_OBJECT_STORAGE_MC_BIN:-}" ]; then',
            '    printf "%s\\n" "$AXIS_OBJECT_STORAGE_MC_BIN"',
            "    return",
            "  fi",
            "  for candidate in /usr/bin/mc /usr/local/bin/mc /bin/mc /usr/bin/mcli "
            "/usr/local/bin/mcli /bin/mcli; do",
            '    if [ -x "$candidate" ]; then',
            '      printf "%s\\n" "$candidate"',
            "      return",
            "    fi",
            "  done",
            "  command -v mc || command -v mcli",
            "}",
            'mc_bin="$(resolve_mc_bin)"',
            "mc() { \"$mc_bin\" \"$@\"; }",
        )
    )


def _endpoint_url_function() -> str:
    return "\n".join(
        (
            "endpoint_url() {",
            '  raw="$1"',
            '  secure="${2:-true}"',
            "  case \"$raw\" in",
            "    http://*|https://*) printf '%s\\n' \"$raw\" ;;",
            "    *)",
            '      if [ "$secure" = "false" ]; then',
            '        printf "http://%s\\n" "$raw"',
            "      else",
            '        printf "https://%s\\n" "$raw"',
            "      fi",
            "      ;;",
            "  esac",
            "}",
        )
    )


def _console_probe_script() -> str:
    return "\n".join(
        (
            "set -eu",
            "mkdir -p /object-store-recovery",
            _mc_prelude(),
            "mc --help >/object-store-recovery/object-store-client.help",
        )
    )


def _recovery_probe_script(config: ObjectStorageRecoveryRehearsalConfig) -> str:
    payload = json.dumps(
        {
            "purpose": "Limes Axis object storage recovery rehearsal probe",
            "probe_key": config.probe_key,
            "recovery_id": config.recovery_id,
            "schema_version": "axis.object_storage_recovery.v1",
        },
        sort_keys=True,
    )
    return "\n".join(
        (
            "set -eu",
            "mkdir -p /object-store-recovery",
            _mc_prelude(),
            _endpoint_url_function(),
            'source_bucket="$AXIS_CONNECTOR_EXPORT_S3_BUCKET"',
            'restore_bucket="$AXIS_CONNECTOR_EXPORT_S3_RESTORE_BUCKET"',
            f"probe_key={shlex.quote(config.probe_key)}",
            "source_url=\"$(endpoint_url "
            '"$AXIS_CONNECTOR_EXPORT_S3_ENDPOINT" '
            '"${AXIS_CONNECTOR_EXPORT_S3_SECURE_TRANSPORT:-true}")"',
            "restore_url=\"$(endpoint_url "
            '"$AXIS_CONNECTOR_EXPORT_S3_RESTORE_ENDPOINT" '
            '"${AXIS_CONNECTOR_EXPORT_S3_RESTORE_SECURE_TRANSPORT:-true}")"',
            "mc alias set axis-source \"$source_url\" "
            '"$AXIS_CONNECTOR_EXPORT_S3_ACCESS_KEY" '
            '"$AXIS_CONNECTOR_EXPORT_S3_SECRET_KEY" '
            "--api S3v4 >/object-store-recovery/source.alias.log",
            "mc alias set axis-restore \"$restore_url\" "
            '"$AXIS_CONNECTOR_EXPORT_S3_RESTORE_ACCESS_KEY" '
            '"$AXIS_CONNECTOR_EXPORT_S3_RESTORE_SECRET_KEY" '
            "--api S3v4 >/object-store-recovery/restore.alias.log",
            f"printf '%s\\n' {shlex.quote(payload)} "
            ">/object-store-recovery/probe.json",
            "sha256sum /object-store-recovery/probe.json "
            ">/object-store-recovery/object-store.sha256",
            'mc stat "axis-source/${source_bucket}" '
            ">/object-store-recovery/source.bucket.stat",
            'mc cp /object-store-recovery/probe.json '
            '"axis-source/${source_bucket}/${probe_key}" '
            ">/object-store-recovery/source.upload.log",
            'mc stat "axis-source/${source_bucket}/${probe_key}" '
            ">/object-store-recovery/source.object.stat",
            'if [ "${AXIS_CONNECTOR_EXPORT_S3_OBJECT_LOCK_ENABLED:-false}" = "true" ]; then',
            '  mc retention info "axis-source/${source_bucket}/${probe_key}" '
            ">/object-store-recovery/source.retention.info",
            "else",
            "  printf 'object lock not declared enabled\\n' "
            ">/object-store-recovery/source.retention.info",
            "fi",
            'mc cp "axis-source/${source_bucket}/${probe_key}" '
            '"axis-restore/${restore_bucket}/${probe_key}" '
            ">/object-store-recovery/restore.copy.log",
            'mc stat "axis-restore/${restore_bucket}/${probe_key}" '
            ">/object-store-recovery/restore.object.stat",
            'mc cat "axis-restore/${restore_bucket}/${probe_key}" '
            ">/object-store-recovery/restored-probe.json",
            "expected=\"$(awk '{print $1}' /object-store-recovery/object-store.sha256)\"",
            "actual=\"$(sha256sum /object-store-recovery/restored-probe.json "
            "| awk '{print $1}')\"",
            'test "$expected" = "$actual"',
            "printf '%s  restored-probe.json\\n' \"$actual\" "
            ">/object-store-recovery/restored-probe.sha256",
        )
    )


def _copy_evidence_script(config: ObjectStorageRecoveryRehearsalConfig) -> str:
    assert config.local_evidence_dir is not None
    local_dir = shlex.quote(str(config.local_evidence_dir))
    names = (
        "object-store-client.help",
        "probe.json",
        "object-store.sha256",
        "source.alias.log",
        "restore.alias.log",
        "source.bucket.stat",
        "source.upload.log",
        "source.object.stat",
        "source.retention.info",
        "restore.copy.log",
        "restore.object.stat",
        "restored-probe.json",
        "restored-probe.sha256",
    )
    copies = [
        _kubectl_cp(
            config,
            f"{config.pod_name}:/object-store-recovery/{name}",
            f"{config.local_evidence_dir}/{name}",
        )
        for name in names
    ]
    return "\n".join((f"mkdir -p {local_dir}", *(format_command(command) for command in copies)))


def build_rehearsal_steps(config: ObjectStorageRecoveryRehearsalConfig) -> list[CommandStep]:
    base = _kubectl_base(config)
    assert config.local_evidence_dir is not None
    steps = [
        CommandStep(
            name="confirm Kubernetes context",
            command=tuple([*base, "config", "current-context"]),
        ),
        CommandStep(
            name="confirm Axis runtime ConfigMap exists",
            command=tuple(
                [*base, "-n", config.namespace, "get", "configmap", config.runtime_config_map]
            ),
        ),
        CommandStep(
            name="confirm Axis runtime Secret exists",
            command=tuple([*base, "-n", config.namespace, "get", "secret", config.runtime_secret]),
        ),
        CommandStep(
            name="confirm isolated object-store restore target secret exists",
            command=tuple(
                [*base, "-n", config.namespace, "get", "secret", config.restore_target_secret]
            ),
        ),
        CommandStep(
            name="confirm object-store restore target is marked isolated",
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
    steps.extend(_required_config_key_steps(config, config.runtime_config_map, _SOURCE_CONFIG_KEYS))
    steps.extend(_required_secret_key_steps(config, config.runtime_secret, _SOURCE_SECRET_KEYS))
    steps.extend(
        _required_secret_key_steps(config, config.restore_target_secret, _RESTORE_SECRET_KEYS)
    )
    steps.extend(
        [
            CommandStep(
                name="create local object-store recovery evidence directory",
                command=("mkdir", "-p", str(config.local_evidence_dir)),
            ),
            CommandStep(
                name="create isolated in-cluster object-store recovery pod",
                command=tuple([*base, "-n", config.namespace, "apply", "-f", "-"]),
                stdin_text=build_pod_manifest(config),
            ),
            CommandStep(
                name="wait for object-store recovery pod readiness",
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
                name="verify MinIO Client is available in recovery image",
                command=_kubectl_exec(config, _console_probe_script()),
            ),
            CommandStep(
                name="copy object-store recovery probe into isolated restore target",
                command=_kubectl_exec(config, _recovery_probe_script(config)),
            ),
            CommandStep(
                name="copy object-store recovery evidence locally",
                command=("sh", "-ec", _copy_evidence_script(config)),
            ),
            CommandStep(
                name="capture object-store recovery pod logs",
                command=tuple([*base, "-n", config.namespace, "logs", config.pod_name]),
            ),
        ]
    )
    if config.delete_pod:
        steps.append(
            CommandStep(
                name="delete object-store recovery pod",
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
        print(f"[axis-object-store-recovery] {step.name}")
        subprocess.run(step.command, input=step.stdin_text, text=True, check=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or print the Limes Axis object storage recovery rehearsal."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true", help="Print rehearsal steps only.")
    mode.add_argument("--execute", action="store_true", help="Execute rehearsal steps.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--namespace", default="limes-axis")
    parser.add_argument("--context", dest="kube_context")
    parser.add_argument("--runtime-config-map", default="limes-axis-config")
    parser.add_argument("--runtime-secret", default="limes-axis-runtime")
    parser.add_argument(
        "--restore-target-secret", default="limes-axis-object-store-restore-target"
    )
    parser.add_argument("--recovery-id", default="manual-rehearsal")
    parser.add_argument("--probe-prefix", default="axis-recovery-probes")
    parser.add_argument("--local-evidence-dir", type=Path)
    parser.add_argument("--image", default=_PLACEHOLDER_MC_IMAGE)
    parser.add_argument("--timeout", default="15m")
    parser.add_argument("--run-as-user", type=int, default=10001)
    parser.add_argument("--run-as-group", type=int, default=10001)
    parser.add_argument("--keep-pod", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> ObjectStorageRecoveryRehearsalConfig:
    recovery_id = args.recovery_id
    evidence_dir = args.local_evidence_dir
    if evidence_dir is None:
        evidence_dir = (
            args.repo_root.resolve() / ".axis" / "object-storage-recovery" / recovery_id
        )
    return ObjectStorageRecoveryRehearsalConfig(
        namespace=args.namespace,
        kube_context=args.kube_context,
        runtime_config_map=args.runtime_config_map,
        runtime_secret=args.runtime_secret,
        restore_target_secret=args.restore_target_secret,
        recovery_id=recovery_id,
        probe_prefix=args.probe_prefix,
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
            "[axis-object-store-recovery] invalid configuration: set --image or "
            "AXIS_OBJECT_STORAGE_RECOVERY_IMAGE to a MinIO Client image",
            file=sys.stderr,
        )
        return 2
    try:
        config = config_from_args(args)
    except ValueError as error:
        print(f"[axis-object-store-recovery] invalid configuration: {error}", file=sys.stderr)
        return 2
    steps = build_rehearsal_steps(config)
    if args.plan:
        print_plan(steps)
        return 0

    try:
        run_rehearsal(steps)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"[axis-object-store-recovery] failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
