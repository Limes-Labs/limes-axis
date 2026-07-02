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
_FORBIDDEN_STAGED_SECRETS = frozenset({"axis-runtime", "limes-axis-runtime"})
_PLACEHOLDER_ROTATION_IMAGE = "REPLACE_WITH_SECRET_ROTATION_IMAGE"
_SECRET_VOLUME_MODE = 0o440
_REQUIRED_SECRET_KEYS = (
    "AXIS_POSTGRES_DSN",
    "AXIS_TYPEDB_USERNAME",
    "AXIS_TYPEDB_PASSWORD",
    "AXIS_AUDIT_LEDGER_SIGNING_SECRET",
    "AXIS_CONNECTOR_EXPORT_S3_ACCESS_KEY",
    "AXIS_CONNECTOR_EXPORT_S3_SECRET_KEY",
)


@dataclass(frozen=True)
class CommandStep:
    name: str
    command: tuple[str, ...]
    stdin_text: str | None = None


@dataclass(frozen=True)
class SecretRotationRehearsalConfig:
    namespace: str = "limes-axis"
    kube_context: str | None = None
    active_secret: str = "limes-axis-runtime"
    staged_secret: str = "limes-axis-runtime-next"
    rotation_id: str = "manual-rehearsal"
    local_evidence_dir: Path | None = None
    image: str = _PLACEHOLDER_ROTATION_IMAGE
    timeout: str = "15m"
    run_as_user: int = 10001
    run_as_group: int = 10001
    allow_unchanged: bool = False
    delete_pod: bool = True

    def __post_init__(self) -> None:
        _validate_dns_label("namespace", self.namespace)
        _validate_dns_label("active_secret", self.active_secret)
        _validate_dns_label("staged_secret", self.staged_secret)
        _validate_staged_secret_name(self.active_secret, self.staged_secret)
        _validate_identifier("rotation_id", self.rotation_id)
        _validate_image(self.image)
        _validate_positive_integer("run_as_user", self.run_as_user)
        _validate_positive_integer("run_as_group", self.run_as_group)
        if self.kube_context is not None:
            _validate_context(self.kube_context)
        if self.local_evidence_dir is None:
            object.__setattr__(
                self,
                "local_evidence_dir",
                Path(".axis/secret-rotation") / self.rotation_id,
            )

    @property
    def pod_name(self) -> str:
        normalized = self.rotation_id.lower().replace(".", "-")
        return f"axis-secret-rotation-{normalized}"[:63].rstrip("-")


def _validate_identifier(name: str, value: str) -> None:
    if _SAFE_IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"{name} must be alphanumeric with optional '.', '-' separators")


def _validate_dns_label(name: str, value: str) -> None:
    if len(value) > 63 or _SAFE_DNS_LABEL.fullmatch(value) is None:
        raise ValueError(f"{name} must be a Kubernetes DNS label")


def _validate_staged_secret_name(active_secret: str, staged_secret: str) -> None:
    if staged_secret in _FORBIDDEN_STAGED_SECRETS:
        raise ValueError("staged_secret must not be the Axis runtime secret")
    if staged_secret == active_secret:
        raise ValueError("staged_secret must be separate from active_secret")


def _validate_context(value: str) -> None:
    if not value or any(character.isspace() for character in value):
        raise ValueError("kube_context must be a non-empty kubectl context name")


def _validate_image(value: str) -> None:
    if not value or any(character.isspace() for character in value):
        raise ValueError("image must be a non-empty container image reference")


def _requires_operator_image(value: str) -> bool:
    return value == _PLACEHOLDER_ROTATION_IMAGE


def _validate_positive_integer(name: str, value: int) -> None:
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")


def format_command(command: tuple[str, ...]) -> str:
    return shlex.join(command)


def _kubectl_base(config: SecretRotationRehearsalConfig) -> list[str]:
    command = ["kubectl"]
    if config.kube_context:
        command.extend(["--context", config.kube_context])
    return command


def build_pod_manifest(config: SecretRotationRehearsalConfig) -> str:
    manifest = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": config.pod_name,
            "labels": {
                "app.kubernetes.io/name": "limes-axis",
                "app.kubernetes.io/component": "secret-rotation-rehearsal",
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
                    "name": "secret-rotation",
                    "image": config.image,
                    "command": ["/bin/sh", "-ec"],
                    "args": [
                        "trap 'exit 0' TERM INT\n"
                        "mkdir -p /rotation/evidence\n"
                        "while true; do sleep 30; done"
                    ],
                    "securityContext": {
                        "allowPrivilegeEscalation": False,
                        "capabilities": {"drop": ["ALL"]},
                    },
                    "volumeMounts": [
                        {
                            "name": "active-secret",
                            "mountPath": "/rotation/active",
                            "readOnly": True,
                        },
                        {
                            "name": "staged-secret",
                            "mountPath": "/rotation/staged",
                            "readOnly": True,
                        },
                        {
                            "name": "secret-rotation-evidence",
                            "mountPath": "/rotation/evidence",
                        },
                    ],
                }
            ],
            "volumes": [
                {
                    "name": "active-secret",
                    "secret": {
                        "secretName": config.active_secret,
                        "defaultMode": _SECRET_VOLUME_MODE,
                    },
                },
                {
                    "name": "staged-secret",
                    "secret": {
                        "secretName": config.staged_secret,
                        "defaultMode": _SECRET_VOLUME_MODE,
                    },
                },
                {"name": "secret-rotation-evidence", "emptyDir": {}},
            ],
        },
    }
    return json.dumps(manifest, sort_keys=True)


def _jsonpath_staged_annotation(config: SecretRotationRehearsalConfig) -> str:
    base = _kubectl_base(config)
    command = tuple(
        [
            *base,
            "-n",
            config.namespace,
            "get",
            "secret",
            config.staged_secret,
            "-o",
            r"jsonpath={.metadata.annotations.limes-axis\.io/secret-rotation-target}",
        ]
    )
    return format_command(command)


def _jsonpath_secret_key(config: SecretRotationRehearsalConfig, secret_name: str, key: str) -> str:
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


def _kubectl_exec(config: SecretRotationRehearsalConfig, script: str) -> tuple[str, ...]:
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


def _kubectl_cp(config: SecretRotationRehearsalConfig, source: str, target: str) -> tuple[str, ...]:
    base = _kubectl_base(config)
    return tuple([*base, "-n", config.namespace, "cp", source, target])


def _required_secret_key_steps(
    config: SecretRotationRehearsalConfig,
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


def _tooling_probe_script() -> str:
    return "\n".join(
        (
            "set -eu",
            "mkdir -p /rotation/evidence",
            "sha256sum /dev/null >/rotation/evidence/secret-rotation-tooling.help",
            "cmp -s /dev/null /dev/null",
        )
    )


def _rotation_probe_script(config: SecretRotationRehearsalConfig) -> str:
    keys = " ".join(shlex.quote(key) for key in _REQUIRED_SECRET_KEYS)
    allow_unchanged_json = "true" if config.allow_unchanged else "false"
    return "\n".join(
        (
            "set -eu",
            "mkdir -p /rotation/evidence",
            f"keys={shlex.quote(keys)}",
            "changed=0",
            "checked=0",
            "printf 'key,status\\n' >/rotation/evidence/secret-rotation.keys",
            ": >/rotation/evidence/secret-rotation.sha256",
            "for key in $keys; do",
            '  test -s "/rotation/active/${key}"',
            '  test -s "/rotation/staged/${key}"',
            '  sha256sum "/rotation/active/${key}" '
            ">>/rotation/evidence/secret-rotation.sha256",
            '  sha256sum "/rotation/staged/${key}" '
            ">>/rotation/evidence/secret-rotation.sha256",
            '  if cmp -s "/rotation/active/${key}" "/rotation/staged/${key}"; then',
            '    printf "%s,unchanged\\n" "$key" '
            ">>/rotation/evidence/secret-rotation.keys",
            "  else",
            '    printf "%s,changed\\n" "$key" '
            ">>/rotation/evidence/secret-rotation.keys",
            "    changed=$((changed + 1))",
            "  fi",
            "  checked=$((checked + 1))",
            "done",
            f"allow_unchanged={shlex.quote(str(config.allow_unchanged).lower())}",
            'if [ "$changed" -eq 0 ] && [ "$allow_unchanged" != "true" ]; then',
            "  echo 'staged Secret did not change any required key' >&2",
            "  exit 1",
            "fi",
            "printf "
            "'{"
            '"schema_version":"axis.secret_rotation_rehearsal.v1",'
            f'"rotation_id":"{config.rotation_id}",'
            f'"active_secret":"{config.active_secret}",'
            f'"staged_secret":"{config.staged_secret}",'
            '"required_key_count":%s,'
            '"changed_key_count":%s,'
            f'"allow_unchanged":{allow_unchanged_json}'
            "}\\n' "
            '"$checked" "$changed" '
            ">/rotation/evidence/secret-rotation.summary.json",
        )
    )


def _copy_evidence_script(config: SecretRotationRehearsalConfig) -> str:
    assert config.local_evidence_dir is not None
    local_dir = shlex.quote(str(config.local_evidence_dir))
    names = (
        "secret-rotation-tooling.help",
        "secret-rotation.keys",
        "secret-rotation.sha256",
        "secret-rotation.summary.json",
    )
    copies = [
        _kubectl_cp(
            config,
            f"{config.pod_name}:/rotation/evidence/{name}",
            f"{config.local_evidence_dir}/{name}",
        )
        for name in names
    ]
    return "\n".join((f"mkdir -p {local_dir}", *(format_command(command) for command in copies)))


def build_rehearsal_steps(config: SecretRotationRehearsalConfig) -> list[CommandStep]:
    base = _kubectl_base(config)
    assert config.local_evidence_dir is not None
    steps = [
        CommandStep(
            name="confirm Kubernetes context",
            command=tuple([*base, "config", "current-context"]),
        ),
        CommandStep(
            name="confirm active Axis runtime Secret exists",
            command=tuple([*base, "-n", config.namespace, "get", "secret", config.active_secret]),
        ),
        CommandStep(
            name="confirm staged Axis runtime Secret exists",
            command=tuple([*base, "-n", config.namespace, "get", "secret", config.staged_secret]),
        ),
        CommandStep(
            name="confirm staged Secret is marked for rotation",
            command=(
                "sh",
                "-ec",
                "annotation=\"$("
                + _jsonpath_staged_annotation(config)
                + ")\"\n"
                'test "$annotation" = "staged"',
            ),
        ),
    ]
    steps.extend(_required_secret_key_steps(config, config.active_secret, _REQUIRED_SECRET_KEYS))
    steps.extend(_required_secret_key_steps(config, config.staged_secret, _REQUIRED_SECRET_KEYS))
    steps.extend(
        [
            CommandStep(
                name="create local secret rotation evidence directory",
                command=("mkdir", "-p", str(config.local_evidence_dir)),
            ),
            CommandStep(
                name="create isolated in-cluster secret rotation comparison pod",
                command=tuple([*base, "-n", config.namespace, "apply", "-f", "-"]),
                stdin_text=build_pod_manifest(config),
            ),
            CommandStep(
                name="wait for secret rotation comparison pod readiness",
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
                name="verify secret rotation tooling is available",
                command=_kubectl_exec(config, _tooling_probe_script()),
            ),
            CommandStep(
                name="compare active and staged Secret values without printing them",
                command=_kubectl_exec(config, _rotation_probe_script(config)),
            ),
            CommandStep(
                name="copy secret rotation evidence locally",
                command=("sh", "-ec", _copy_evidence_script(config)),
            ),
            CommandStep(
                name="capture secret rotation pod logs",
                command=tuple([*base, "-n", config.namespace, "logs", config.pod_name]),
            ),
        ]
    )
    if config.delete_pod:
        steps.append(
            CommandStep(
                name="delete secret rotation comparison pod",
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
        print(f"[axis-secret-rotation] {step.name}")
        subprocess.run(step.command, input=step.stdin_text, text=True, check=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or print the Limes Axis Kubernetes Secret rotation rehearsal."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true", help="Print rehearsal steps only.")
    mode.add_argument("--execute", action="store_true", help="Execute rehearsal steps.")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--namespace", default="limes-axis")
    parser.add_argument("--context", dest="kube_context")
    parser.add_argument("--active-secret", default="limes-axis-runtime")
    parser.add_argument("--staged-secret", default="limes-axis-runtime-next")
    parser.add_argument("--rotation-id", default="manual-rehearsal")
    parser.add_argument("--local-evidence-dir", type=Path)
    parser.add_argument("--image", default=_PLACEHOLDER_ROTATION_IMAGE)
    parser.add_argument("--timeout", default="15m")
    parser.add_argument("--run-as-user", type=int, default=10001)
    parser.add_argument("--run-as-group", type=int, default=10001)
    parser.add_argument("--allow-unchanged", action="store_true")
    parser.add_argument("--keep-pod", action="store_true")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> SecretRotationRehearsalConfig:
    rotation_id = args.rotation_id
    evidence_dir = args.local_evidence_dir
    if evidence_dir is None:
        evidence_dir = args.repo_root.resolve() / ".axis" / "secret-rotation" / rotation_id
    return SecretRotationRehearsalConfig(
        namespace=args.namespace,
        kube_context=args.kube_context,
        active_secret=args.active_secret,
        staged_secret=args.staged_secret,
        rotation_id=rotation_id,
        local_evidence_dir=evidence_dir,
        image=args.image,
        timeout=args.timeout,
        run_as_user=args.run_as_user,
        run_as_group=args.run_as_group,
        allow_unchanged=args.allow_unchanged,
        delete_pod=not args.keep_pod,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.execute and _requires_operator_image(args.image):
        print(
            "[axis-secret-rotation] invalid configuration: set --image or "
            "AXIS_SECRET_ROTATION_IMAGE to an image that includes sh, cmp and sha256sum",
            file=sys.stderr,
        )
        return 2
    try:
        config = config_from_args(args)
    except ValueError as error:
        print(f"[axis-secret-rotation] invalid configuration: {error}", file=sys.stderr)
        return 2
    steps = build_rehearsal_steps(config)
    if args.plan:
        print_plan(steps)
        return 0

    try:
        run_rehearsal(steps)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"[axis-secret-rotation] failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
