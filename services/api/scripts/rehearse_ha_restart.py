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
    repo_root: Path = Path(__file__).resolve().parents[3]
    kube_context: str | None = None
    timeout: str = "10m"
    readiness_timeout_seconds: float = 60.0
    ready_url: str | None = None
    require_hpa: bool = False
    require_pdb: bool = False
    run_helm_tests: bool = True


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


def _workload_resource(config: RehearsalConfig, component: str) -> str:
    return f"deployment/{config.release}-{component}"


def _availability_resource(config: RehearsalConfig, component: str) -> str:
    return f"deployment/{config.release}-{component}"


def _rollout_restart_command(config: RehearsalConfig, component: str) -> tuple[str, ...]:
    return tuple(
        [
            *_kubectl_base(config),
            "-n",
            config.namespace,
            "rollout",
            "restart",
            _workload_resource(config, component),
        ]
    )


def _rollout_status_command(config: RehearsalConfig, component: str) -> tuple[str, ...]:
    return tuple(
        [
            *_kubectl_base(config),
            "-n",
            config.namespace,
            "rollout",
            "status",
            _workload_resource(config, component),
            f"--timeout={config.timeout}",
        ]
    )


def _wait_available_command(config: RehearsalConfig, component: str) -> tuple[str, ...]:
    return tuple(
        [
            *_kubectl_base(config),
            "-n",
            config.namespace,
            "wait",
            "--for=condition=available",
            _availability_resource(config, component),
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


def _deployment_inventory_command(config: RehearsalConfig) -> tuple[str, ...]:
    return tuple(
        [
            *_kubectl_base(config),
            "-n",
            config.namespace,
            "get",
            _workload_resource(config, "api"),
            _workload_resource(config, "web"),
            "-o",
            "wide",
        ]
    )


def _hpa_command(config: RehearsalConfig) -> tuple[str, ...]:
    return tuple(
        [
            *_kubectl_base(config),
            "-n",
            config.namespace,
            "get",
            f"hpa/{config.release}-api",
            f"hpa/{config.release}-web",
        ]
    )


def _pdb_command(config: RehearsalConfig) -> tuple[str, ...]:
    return tuple(
        [
            *_kubectl_base(config),
            "-n",
            config.namespace,
            "get",
            f"pdb/{config.release}-api",
            f"pdb/{config.release}-web",
        ]
    )


def _helm_test_command(config: RehearsalConfig) -> tuple[str, ...]:
    command = [
        "helm",
        "test",
        config.release,
        "--namespace",
        config.namespace,
        "--timeout",
        config.timeout,
    ]
    command.extend(_helm_context_args(config))
    return tuple(command)


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
        RehearsalStep(
            name="capture deployment inventory before restart",
            command=_deployment_inventory_command(config),
        ),
        RehearsalStep(
            name="capture pod inventory before restart",
            command=_pod_inventory_command(config),
        ),
    ]
    if config.require_hpa:
        steps.append(RehearsalStep(name="verify API and web HPAs", command=_hpa_command(config)))
    if config.require_pdb:
        steps.append(RehearsalStep(name="verify API and web PDBs", command=_pdb_command(config)))

    for component in ("api", "web"):
        steps.extend(
            [
                RehearsalStep(
                    name=f"restart {component} deployment",
                    command=_rollout_restart_command(config, component),
                ),
                RehearsalStep(
                    name=f"wait for {component} rollout status",
                    command=_rollout_status_command(config, component),
                ),
                RehearsalStep(
                    name=f"wait for {component} deployment availability",
                    command=_wait_available_command(config, component),
                ),
            ]
        )
        ready_after_restart = _ready_step(config, f"check API /ready after {component} restart")
        if ready_after_restart is not None:
            steps.append(ready_after_restart)

    steps.extend(
        [
            RehearsalStep(
                name="capture deployment inventory after restart",
                command=_deployment_inventory_command(config),
            ),
            RehearsalStep(
                name="capture pod inventory after restart",
                command=_pod_inventory_command(config),
            ),
        ]
    )
    if config.run_helm_tests:
        steps.append(RehearsalStep(name="run Helm smoke tests", command=_helm_test_command(config)))
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
        print(f"[axis-ha-rehearsal] {step.name}")
        if step.command is not None:
            run_command_step(step)
        if step.ready_url is not None:
            wait_for_readiness_url(step.ready_url, step.timeout_seconds)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or print the Limes Axis Kubernetes HA restart rehearsal."
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
    parser.add_argument("--context", dest="kube_context", help="Kubernetes context to use.")
    parser.add_argument("--timeout", default="10m", help="kubectl and helm timeout.")
    parser.add_argument("--ready-url", help="Optional externally reachable API /ready URL.")
    parser.add_argument(
        "--readiness-timeout-seconds",
        type=float,
        default=60.0,
        help="Timeout for --ready-url polling.",
    )
    parser.add_argument(
        "--require-hpa",
        action="store_true",
        help="Require API and web HorizontalPodAutoscaler resources to exist.",
    )
    parser.add_argument(
        "--require-pdb",
        action="store_true",
        help="Require API and web PodDisruptionBudget resources to exist.",
    )
    parser.add_argument(
        "--skip-helm-test",
        action="store_true",
        help="Skip helm test after restart validation.",
    )
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> RehearsalConfig:
    return RehearsalConfig(
        release=args.release,
        namespace=args.namespace,
        repo_root=args.repo_root.resolve(),
        kube_context=args.kube_context,
        timeout=args.timeout,
        readiness_timeout_seconds=args.readiness_timeout_seconds,
        ready_url=args.ready_url,
        require_hpa=args.require_hpa,
        require_pdb=args.require_pdb,
        run_helm_tests=not args.skip_helm_test,
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
        print(f"[axis-ha-rehearsal] failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
