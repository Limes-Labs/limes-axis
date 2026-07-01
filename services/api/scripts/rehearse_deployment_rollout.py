from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple
from urllib.error import URLError
from urllib.request import Request, urlopen


class RehearsalStep(NamedTuple):
    name: str
    command: tuple[str, ...] | None = None
    ready_url: str | None = None
    timeout_seconds: float = 60.0


class RehearsalConfig(NamedTuple):
    release: str = "limes-axis"
    namespace: str = "limes-axis"
    chart: Path = Path("infra/helm/limes-axis")
    repo_root: Path = Path(__file__).resolve().parents[3]
    kube_context: str | None = None
    values: tuple[Path, ...] = ()
    set_values: tuple[str, ...] = ()
    timeout: str = "10m"
    readiness_timeout_seconds: float = 60.0
    ready_url: str | None = None
    rollback: bool = False
    rollback_revision: int | None = None
    create_namespace: bool = True


def format_command(command: tuple[str, ...]) -> str:
    return shlex.join(command)


def _kubectl_base(config: RehearsalConfig) -> list[str]:
    command = ["kubectl"]
    if config.kube_context:
        command.extend(["--context", config.kube_context])
    return command


def _helm_context_args(config: RehearsalConfig) -> list[str]:
    if not config.kube_context:
        return []
    return ["--kube-context", config.kube_context]


def _helm_upgrade_command(config: RehearsalConfig) -> tuple[str, ...]:
    command = [
        "helm",
        "upgrade",
        "--install",
        config.release,
        str(config.chart),
        "--namespace",
        config.namespace,
    ]
    if config.create_namespace:
        command.append("--create-namespace")
    command.extend(["--wait", "--timeout", config.timeout])
    command.extend(_helm_context_args(config))
    for values_file in config.values:
        command.extend(["--values", str(values_file)])
    for value in config.set_values:
        command.extend(["--set", value])
    return tuple(command)


def _helm_status_command(config: RehearsalConfig) -> tuple[str, ...]:
    command = [
        "helm",
        "status",
        config.release,
        "--namespace",
        config.namespace,
    ]
    command.extend(_helm_context_args(config))
    return tuple(command)


def _helm_rollback_command(config: RehearsalConfig) -> tuple[str, ...]:
    command = ["helm", "rollback", config.release]
    if config.rollback_revision is not None:
        command.append(str(config.rollback_revision))
    command.extend(["--namespace", config.namespace, "--wait", "--timeout", config.timeout])
    command.extend(_helm_context_args(config))
    return tuple(command)


def _rollout_status_command(config: RehearsalConfig, component: str) -> tuple[str, ...]:
    return tuple(
        [
            *_kubectl_base(config),
            "-n",
            config.namespace,
            "rollout",
            "status",
            f"deployment/{config.release}-{component}",
            f"--timeout={config.timeout}",
        ]
    )


def _pod_inventory_command(config: RehearsalConfig) -> tuple[str, ...]:
    return tuple(
        [
            *_kubectl_base(config),
            "-n",
            config.namespace,
            "get",
            "pods",
            "-l",
            f"app.kubernetes.io/instance={config.release}",
            "-o",
            "wide",
        ]
    )


def _ready_step(config: RehearsalConfig, name: str) -> RehearsalStep | None:
    if config.ready_url is None:
        return None
    return RehearsalStep(
        name=name,
        ready_url=config.ready_url,
        timeout_seconds=config.readiness_timeout_seconds,
    )


def build_rehearsal_steps(config: RehearsalConfig) -> list[RehearsalStep]:
    steps = [
        RehearsalStep(
            name="confirm Kubernetes context",
            command=tuple([*_kubectl_base(config), "config", "current-context"]),
        ),
        RehearsalStep(name="lint Helm chart", command=("helm", "lint", str(config.chart))),
        RehearsalStep(name="upgrade or install release", command=_helm_upgrade_command(config)),
        RehearsalStep(
            name="wait for API deployment rollout",
            command=_rollout_status_command(config, "api"),
        ),
        RehearsalStep(
            name="wait for web deployment rollout",
            command=_rollout_status_command(config, "web"),
        ),
        RehearsalStep(name="capture pod inventory", command=_pod_inventory_command(config)),
        RehearsalStep(name="capture Helm release status", command=_helm_status_command(config)),
    ]

    ready_after_upgrade = _ready_step(config, "check API /ready after rollout")
    if ready_after_upgrade is not None:
        steps.append(ready_after_upgrade)

    if config.rollback:
        steps.extend(
            [
                RehearsalStep(name="rollback Helm release", command=_helm_rollback_command(config)),
                RehearsalStep(
                    name="wait for API deployment rollback",
                    command=_rollout_status_command(config, "api"),
                ),
                RehearsalStep(
                    name="wait for web deployment rollback",
                    command=_rollout_status_command(config, "web"),
                ),
                RehearsalStep(
                    name="capture pod inventory after rollback",
                    command=_pod_inventory_command(config),
                ),
                RehearsalStep(
                    name="capture Helm release status after rollback",
                    command=_helm_status_command(config),
                ),
            ]
        )
        ready_after_rollback = _ready_step(config, "check API /ready after rollback")
        if ready_after_rollback is not None:
            steps.append(ready_after_rollback)

    return steps


def print_plan(steps: list[RehearsalStep]) -> None:
    for index, step in enumerate(steps, start=1):
        print(f"{index}. {step.name}")
        if step.command is not None:
            print(f"   {format_command(step.command)}")
        if step.ready_url is not None:
            print(f"   GET {step.ready_url}")


def run_command_step(step: RehearsalStep) -> None:
    if step.command is None:
        raise ValueError(f"step {step.name!r} has no command")
    subprocess.run(step.command, check=True)


def wait_for_readiness_url(url: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    request = Request(url, headers={"Cache-Control": "no-cache"})

    while time.monotonic() < deadline:
        try:
            with urlopen(request, timeout=5) as response:
                if 200 <= response.status < 400:
                    return
                last_error = RuntimeError(f"unexpected HTTP status {response.status}")
        except (OSError, URLError) as error:
            last_error = error
        time.sleep(2)

    detail = f": {last_error}" if last_error is not None else ""
    raise TimeoutError(f"{url} did not become ready within {timeout_seconds:.0f}s{detail}")


def run_rehearsal(steps: list[RehearsalStep]) -> None:
    for step in steps:
        print(f"[axis-rollout] {step.name}")
        if step.command is not None:
            run_command_step(step)
        if step.ready_url is not None:
            wait_for_readiness_url(step.ready_url, step.timeout_seconds)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or print the Limes Axis Kubernetes rollout rehearsal."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true", help="Print the rehearsal steps only.")
    mode.add_argument("--execute", action="store_true", help="Execute the rehearsal steps.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="Repository root.",
    )
    parser.add_argument("--release", default="limes-axis", help="Helm release name.")
    parser.add_argument("--namespace", default="limes-axis", help="Kubernetes namespace.")
    parser.add_argument(
        "--chart",
        type=Path,
        default=None,
        help="Helm chart path. Defaults to infra/helm/limes-axis under repo root.",
    )
    parser.add_argument("--context", dest="kube_context", help="Kubernetes context to use.")
    parser.add_argument(
        "--values",
        type=Path,
        action="append",
        default=[],
        help="Additional Helm values file. Can be supplied more than once.",
    )
    parser.add_argument(
        "--set",
        dest="set_values",
        action="append",
        default=[],
        help="Additional Helm --set value. Can be supplied more than once.",
    )
    parser.add_argument("--timeout", default="10m", help="Helm and kubectl rollout timeout.")
    parser.add_argument("--ready-url", help="Optional externally reachable API /ready URL.")
    parser.add_argument(
        "--readiness-timeout-seconds",
        type=float,
        default=60.0,
        help="Timeout for --ready-url polling.",
    )
    parser.add_argument("--rollback", action="store_true", help="Run helm rollback after upgrade.")
    parser.add_argument(
        "--rollback-revision",
        type=int,
        help="Optional Helm revision number to rollback to.",
    )
    parser.add_argument(
        "--no-create-namespace",
        action="store_true",
        help="Do not pass --create-namespace to helm upgrade.",
    )
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> RehearsalConfig:
    repo_root = args.repo_root.resolve()
    chart = args.chart if args.chart is not None else repo_root / "infra" / "helm" / "limes-axis"
    return RehearsalConfig(
        release=args.release,
        namespace=args.namespace,
        chart=chart,
        repo_root=repo_root,
        kube_context=args.kube_context,
        values=tuple(args.values),
        set_values=tuple(args.set_values),
        timeout=args.timeout,
        readiness_timeout_seconds=args.readiness_timeout_seconds,
        ready_url=args.ready_url,
        rollback=args.rollback,
        rollback_revision=args.rollback_revision,
        create_namespace=not args.no_create_namespace,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = config_from_args(args)
    steps = build_rehearsal_steps(config)

    if args.plan:
        print_plan(steps)
        return 0

    try:
        run_rehearsal(steps)
    except (subprocess.CalledProcessError, OSError, TimeoutError, ValueError) as error:
        print(f"[axis-rollout] failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
