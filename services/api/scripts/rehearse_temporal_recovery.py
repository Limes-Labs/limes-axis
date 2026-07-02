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
_FORBIDDEN_RECOVERY_SECRETS = frozenset({"axis-runtime", "limes-axis-runtime"})
_PLACEHOLDER_TEMPORAL_IMAGE = "REPLACE_WITH_TEMPORAL_CLI_IMAGE"
_RUNTIME_CONFIG_KEYS = ("AXIS_TEMPORAL_ADDRESS", "AXIS_TEMPORAL_NAMESPACE")
_RECOVERY_SECRET_KEYS = ("AXIS_TEMPORAL_RECOVERY_WORKFLOW_ID",)


@dataclass(frozen=True)
class CommandStep:
    name: str
    command: tuple[str, ...]
    stdin_text: str | None = None


@dataclass(frozen=True)
class TemporalRecoveryRehearsalConfig:
    namespace: str = "limes-axis"
    kube_context: str | None = None
    runtime_config_map: str = "limes-axis-config"
    runtime_secret: str = "limes-axis-runtime"
    recovery_secret: str = "limes-axis-temporal-recovery"
    recovery_id: str = "manual-rehearsal"
    local_evidence_dir: Path | None = None
    image: str = _PLACEHOLDER_TEMPORAL_IMAGE
    timeout: str = "15m"
    run_as_user: int = 10001
    run_as_group: int = 10001
    delete_pod: bool = True

    def __post_init__(self) -> None:
        _validate_dns_label("namespace", self.namespace)
        _validate_dns_label("runtime_config_map", self.runtime_config_map)
        _validate_dns_label("runtime_secret", self.runtime_secret)
        _validate_dns_label("recovery_secret", self.recovery_secret)
        _validate_recovery_secret_name(self.runtime_secret, self.recovery_secret)
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
                Path(".axis/temporal-recovery") / self.recovery_id,
            )

    @property
    def pod_name(self) -> str:
        normalized = self.recovery_id.lower().replace(".", "-")
        return f"axis-temporal-recovery-{normalized}"[:63].rstrip("-")


def _validate_identifier(name: str, value: str) -> None:
    if _SAFE_IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{name} must be alphanumeric with optional '.', '-' separators")


def _validate_dns_label(name: str, value: str) -> None:
    if len(value) > 63 or _SAFE_DNS_LABEL.fullmatch(value) is None:
        raise ValueError(f"{name} must be a Kubernetes DNS label")


def _validate_recovery_secret_name(runtime_secret: str, recovery_secret: str) -> None:
    if recovery_secret in _FORBIDDEN_RECOVERY_SECRETS:
        raise ValueError("recovery_secret must not be the Axis runtime secret")
    if recovery_secret == runtime_secret:
        raise ValueError("recovery_secret must be separate from runtime_secret")


def _validate_context(value: str) -> None:
    if not value or any(character.isspace() for character in value):
        raise ValueError("kube_context must be a non-empty kubectl context name")


def _validate_image(value: str) -> None:
    if not value or any(character.isspace() for character in value):
        raise ValueError("image must be a non-empty container image reference")


def _requires_operator_image(value: str) -> bool:
    return value == _PLACEHOLDER_TEMPORAL_IMAGE


def _validate_positive_integer(name: str, value: int) -> None:
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")


def format_command(command: tuple[str, ...]) -> str:
    return shlex.join(command)


def _kubectl_base(config: TemporalRecoveryRehearsalConfig) -> list[str]:
    command = ["kubectl"]
    if config.kube_context:
        command.extend(["--context", config.kube_context])
    return command


def build_pod_manifest(config: TemporalRecoveryRehearsalConfig) -> str:
    manifest = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": config.pod_name,
            "labels": {
                "app.kubernetes.io/name": "limes-axis",
                "app.kubernetes.io/component": "temporal-recovery-rehearsal",
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
                    "name": "temporal-recovery",
                    "image": config.image,
                    "env": [
                        {"name": "HOME", "value": "/temporal-recovery"},
                        {
                            "name": "TEMPORAL_CLI_HOME",
                            "value": "/temporal-recovery/.temporal",
                        },
                    ],
                    "envFrom": [
                        {"configMapRef": {"name": config.runtime_config_map}},
                        {"secretRef": {"name": config.runtime_secret}},
                        {"secretRef": {"name": config.recovery_secret}},
                    ],
                    "command": ["/bin/sh", "-ec"],
                    "args": [
                        "trap 'exit 0' TERM INT\n"
                        "mkdir -p /temporal-recovery/.temporal\n"
                        "while true; do sleep 30; done"
                    ],
                    "securityContext": {
                        "allowPrivilegeEscalation": False,
                        "capabilities": {"drop": ["ALL"]},
                    },
                    "volumeMounts": [
                        {
                            "name": "temporal-recovery",
                            "mountPath": "/temporal-recovery",
                        }
                    ],
                }
            ],
            "volumes": [{"name": "temporal-recovery", "emptyDir": {}}],
        },
    }
    return json.dumps(manifest, sort_keys=True)


def _jsonpath_recovery_annotation(config: TemporalRecoveryRehearsalConfig) -> str:
    base = _kubectl_base(config)
    command = tuple(
        [
            *base,
            "-n",
            config.namespace,
            "get",
            "secret",
            config.recovery_secret,
            "-o",
            r"jsonpath={.metadata.annotations.limes-axis\.io/temporal-recovery-target}",
        ]
    )
    return format_command(command)


def _jsonpath_config_key(
    config: TemporalRecoveryRehearsalConfig, config_map_name: str, key: str
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
    config: TemporalRecoveryRehearsalConfig, secret_name: str, key: str
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


def _kubectl_exec(config: TemporalRecoveryRehearsalConfig, script: str) -> tuple[str, ...]:
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
    config: TemporalRecoveryRehearsalConfig, source: str, target: str
) -> tuple[str, ...]:
    base = _kubectl_base(config)
    return tuple([*base, "-n", config.namespace, "cp", source, target])


def _required_config_key_steps(
    config: TemporalRecoveryRehearsalConfig,
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
    config: TemporalRecoveryRehearsalConfig,
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


def _temporal_prelude() -> str:
    return "\n".join(
        (
            "resolve_temporal_bin() {",
            '  if [ -n "${AXIS_TEMPORAL_CLI_BIN:-}" ]; then',
            '    printf "%s\\n" "$AXIS_TEMPORAL_CLI_BIN"',
            "    return",
            "  fi",
            "  for candidate in /usr/local/bin/temporal /usr/bin/temporal "
            "/bin/temporal; do",
            '    if [ -x "$candidate" ]; then',
            '      printf "%s\\n" "$candidate"',
            "      return",
            "    fi",
            "  done",
            "  command -v temporal",
            "}",
            'temporal_bin="$(resolve_temporal_bin)"',
            "run_temporal() {",
            '  if [ "${AXIS_TEMPORAL_TLS_ENABLED:-false}" = "true" ] '
            '&& [ -n "${AXIS_TEMPORAL_API_KEY:-}" ]; then',
            '    "$temporal_bin" --address "$AXIS_TEMPORAL_ADDRESS" '
            '--namespace "$AXIS_TEMPORAL_NAMESPACE" --tls '
            '--api-key "$AXIS_TEMPORAL_API_KEY" "$@"',
            '  elif [ "${AXIS_TEMPORAL_TLS_ENABLED:-false}" = "true" ]; then',
            '    "$temporal_bin" --address "$AXIS_TEMPORAL_ADDRESS" '
            '--namespace "$AXIS_TEMPORAL_NAMESPACE" --tls "$@"',
            '  elif [ -n "${AXIS_TEMPORAL_API_KEY:-}" ]; then',
            '    "$temporal_bin" --address "$AXIS_TEMPORAL_ADDRESS" '
            '--namespace "$AXIS_TEMPORAL_NAMESPACE" '
            '--api-key "$AXIS_TEMPORAL_API_KEY" "$@"',
            "  else",
            '    "$temporal_bin" --address "$AXIS_TEMPORAL_ADDRESS" '
            '--namespace "$AXIS_TEMPORAL_NAMESPACE" "$@"',
            "  fi",
            "}",
        )
    )


def _cli_probe_script() -> str:
    return "\n".join(
        (
            "set -eu",
            "mkdir -p /temporal-recovery",
            _temporal_prelude(),
            '"$temporal_bin" --help >/temporal-recovery/temporal.cli.help',
        )
    )


def _history_export_command() -> str:
    return "\n".join(
        (
            'if [ -n "${AXIS_TEMPORAL_RECOVERY_RUN_ID:-}" ]; then',
            '  run_temporal workflow show --workflow-id '
            '"$AXIS_TEMPORAL_RECOVERY_WORKFLOW_ID" --run-id '
            '"$AXIS_TEMPORAL_RECOVERY_RUN_ID" --output json '
            ">/temporal-recovery/temporal.workflow-history.json",
            "else",
            '  run_temporal workflow show --workflow-id '
            '"$AXIS_TEMPORAL_RECOVERY_WORKFLOW_ID" --output json '
            ">/temporal-recovery/temporal.workflow-history.json",
            "fi",
        )
    )


def _recovery_probe_script() -> str:
    return "\n".join(
        (
            "set -eu",
            "mkdir -p /temporal-recovery",
            _temporal_prelude(),
            'run_temporal operator cluster health --output json '
            ">/temporal-recovery/temporal.cluster-health.json",
            'run_temporal operator namespace describe --output json '
            ">/temporal-recovery/temporal.namespace.json",
            'run_temporal operator namespace list --output json '
            ">/temporal-recovery/temporal.namespace-list.json",
            'run_temporal workflow list --limit '
            '"${AXIS_TEMPORAL_RECOVERY_WORKFLOW_LIMIT:-20}" --output json '
            ">/temporal-recovery/temporal.workflow-list.json",
            _history_export_command(),
            "sha256sum /temporal-recovery/temporal.cluster-health.json "
            "/temporal-recovery/temporal.namespace.json "
            "/temporal-recovery/temporal.namespace-list.json "
            "/temporal-recovery/temporal.workflow-list.json "
            "/temporal-recovery/temporal.workflow-history.json "
            ">/temporal-recovery/temporal.sha256",
        )
    )


def _copy_evidence_script(config: TemporalRecoveryRehearsalConfig) -> str:
    assert config.local_evidence_dir is not None
    local_dir = shlex.quote(str(config.local_evidence_dir))
    names = (
        "temporal.cli.help",
        "temporal.cluster-health.json",
        "temporal.namespace.json",
        "temporal.namespace-list.json",
        "temporal.workflow-list.json",
        "temporal.workflow-history.json",
        "temporal.sha256",
    )
    copies = [
        _kubectl_cp(
            config,
            f"{config.pod_name}:/temporal-recovery/{name}",
            f"{config.local_evidence_dir}/{name}",
        )
        for name in names
    ]
    return "\n".join((f"mkdir -p {local_dir}", *(format_command(command) for command in copies)))


def build_rehearsal_steps(config: TemporalRecoveryRehearsalConfig) -> list[CommandStep]:
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
            name="confirm Temporal recovery Secret exists",
            command=tuple([*base, "-n", config.namespace, "get", "secret", config.recovery_secret]),
        ),
        CommandStep(
            name="confirm Temporal recovery target is marked isolated",
            command=(
                "sh",
                "-ec",
                "annotation=\"$("
                + _jsonpath_recovery_annotation(config)
                + ")\"\n"
                'test "$annotation" = "isolated"',
            ),
        ),
    ]
    steps.extend(
        _required_config_key_steps(config, config.runtime_config_map, _RUNTIME_CONFIG_KEYS)
    )
    steps.extend(_required_secret_key_steps(config, config.recovery_secret, _RECOVERY_SECRET_KEYS))
    steps.extend(
        [
            CommandStep(
                name="create local Temporal recovery evidence directory",
                command=("mkdir", "-p", str(config.local_evidence_dir)),
            ),
            CommandStep(
                name="create isolated in-cluster Temporal recovery pod",
                command=tuple([*base, "-n", config.namespace, "apply", "-f", "-"]),
                stdin_text=build_pod_manifest(config),
            ),
            CommandStep(
                name="wait for Temporal recovery pod readiness",
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
                name="verify Temporal CLI is available in recovery image",
                command=_kubectl_exec(config, _cli_probe_script()),
            ),
            CommandStep(
                name="capture Temporal namespace and workflow-history evidence",
                command=_kubectl_exec(config, _recovery_probe_script()),
            ),
            CommandStep(
                name="copy Temporal recovery evidence locally",
                command=("sh", "-ec", _copy_evidence_script(config)),
            ),
            CommandStep(
                name="capture Temporal recovery pod logs",
                command=tuple([*base, "-n", config.namespace, "logs", config.pod_name]),
            ),
        ]
    )
    if config.delete_pod:
        steps.append(
            CommandStep(
                name="delete Temporal recovery pod",
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
        print(f"[axis-temporal-recovery] {step.name}")
        subprocess.run(step.command, input=step.stdin_text, text=True, check=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or print the Limes Axis Temporal recovery rehearsal."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true", help="Print rehearsal steps only.")
    mode.add_argument("--execute", action="store_true", help="Execute rehearsal steps.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--namespace", default="limes-axis")
    parser.add_argument("--context", dest="kube_context")
    parser.add_argument("--runtime-config-map", default="limes-axis-config")
    parser.add_argument("--runtime-secret", default="limes-axis-runtime")
    parser.add_argument("--recovery-secret", default="limes-axis-temporal-recovery")
    parser.add_argument("--recovery-id", default="manual-rehearsal")
    parser.add_argument("--local-evidence-dir", type=Path)
    parser.add_argument("--image", default=_PLACEHOLDER_TEMPORAL_IMAGE)
    parser.add_argument("--timeout", default="15m")
    parser.add_argument("--run-as-user", type=int, default=10001)
    parser.add_argument("--run-as-group", type=int, default=10001)
    parser.add_argument("--keep-pod", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> TemporalRecoveryRehearsalConfig:
    recovery_id = args.recovery_id
    evidence_dir = args.local_evidence_dir
    if evidence_dir is None:
        evidence_dir = args.repo_root.resolve() / ".axis" / "temporal-recovery" / recovery_id
    return TemporalRecoveryRehearsalConfig(
        namespace=args.namespace,
        kube_context=args.kube_context,
        runtime_config_map=args.runtime_config_map,
        runtime_secret=args.runtime_secret,
        recovery_secret=args.recovery_secret,
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
            "[axis-temporal-recovery] invalid configuration: set --image or "
            "AXIS_TEMPORAL_RECOVERY_IMAGE to a Temporal CLI image",
            file=sys.stderr,
        )
        return 2
    try:
        config = config_from_args(args)
    except ValueError as error:
        print(f"[axis-temporal-recovery] invalid configuration: {error}", file=sys.stderr)
        return 2
    steps = build_rehearsal_steps(config)
    if args.plan:
        print_plan(steps)
        return 0

    try:
        run_rehearsal(steps)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"[axis-temporal-recovery] failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
