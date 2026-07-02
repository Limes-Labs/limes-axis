from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


class LoadTarget(NamedTuple):
    name: str
    url: str


class RehearsalStep(NamedTuple):
    name: str
    command: tuple[str, ...]


class RehearsalConfig(NamedTuple):
    release: str = "limes-axis"
    namespace: str = "limes-axis"
    repo_root: Path = Path(__file__).resolve().parents[3]
    kube_context: str | None = None
    image: str = "fortio/fortio:1.69.3"
    duration: str = "60s"
    qps: int = 10
    connections: int = 2
    timeout: str = "10m"
    targets: tuple[LoadTarget, ...] = ()
    cleanup: bool = True


def format_command(command: tuple[str, ...]) -> str:
    return shlex.join(command)


def _kubectl_base(config: RehearsalConfig) -> list[str]:
    command = ["kubectl"]
    if config.kube_context:
        command.extend(["--context", config.kube_context])
    return command


def _safe_dns_label(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    if not normalized:
        raise ValueError("Kubernetes Job name parts must contain at least one DNS-label character")
    return normalized[:63].rstrip("-")


def _truncate_dns_label(value: str, max_length: int) -> str:
    if max_length < 1:
        raise ValueError("Kubernetes DNS label budget must be positive")
    truncated = value[:max_length].rstrip("-")
    if not truncated:
        return value[:1]
    return truncated


def _job_name(config: RehearsalConfig, target: LoadTarget) -> str:
    release = _safe_dns_label(config.release)
    target_name = _safe_dns_label(target.name)
    name = f"{release}-load-{target_name}"
    if len(name) <= 63:
        return name

    infix = "-load-"
    target_part = _truncate_dns_label(target_name, min(len(target_name), 32))
    release_budget = 63 - len(infix) - len(target_part)
    if release_budget < 1:
        target_part = _truncate_dns_label(target_name, 63 - len(infix) - 1)
        release_budget = 1
    release_part = _truncate_dns_label(release, min(len(release), release_budget))
    return f"{release_part}{infix}{target_part}"


def _validate_config(config: RehearsalConfig) -> None:
    if config.qps <= 0:
        raise ValueError("qps must be greater than zero")
    if config.connections <= 0:
        raise ValueError("connections must be greater than zero")
    if not config.duration.strip():
        raise ValueError("duration cannot be empty")
    if not config.timeout.strip():
        raise ValueError("timeout cannot be empty")
    if not config.image.strip():
        raise ValueError("image cannot be empty")


def _default_targets(config: RehearsalConfig) -> tuple[LoadTarget, ...]:
    return (
        LoadTarget(name="api-ready", url=f"http://{config.release}-api:8000/ready"),
        LoadTarget(name="web-home", url=f"http://{config.release}-web:3000/"),
    )


def _targets(config: RehearsalConfig) -> tuple[LoadTarget, ...]:
    if config.targets:
        return config.targets
    return _default_targets(config)


def _delete_job_command(
    config: RehearsalConfig,
    job_name: str,
    *,
    ignore_missing: bool,
) -> tuple[str, ...]:
    command = [
        *_kubectl_base(config),
        "-n",
        config.namespace,
        "delete",
        "job",
        job_name,
    ]
    if ignore_missing:
        command.append("--ignore-not-found=true")
    return tuple(command)


def _create_job_command(
    config: RehearsalConfig,
    job_name: str,
    target: LoadTarget,
) -> tuple[str, ...]:
    return tuple(
        [
            *_kubectl_base(config),
            "-n",
            config.namespace,
            "create",
            "job",
            job_name,
            f"--image={config.image}",
            "--",
            "load",
            "-quiet",
            "-qps",
            str(config.qps),
            "-c",
            str(config.connections),
            "-t",
            config.duration,
            target.url,
        ]
    )


def _wait_job_command(config: RehearsalConfig, job_name: str) -> tuple[str, ...]:
    return tuple(
        [
            *_kubectl_base(config),
            "-n",
            config.namespace,
            "wait",
            "--for=condition=complete",
            f"job/{job_name}",
            f"--timeout={config.timeout}",
        ]
    )


def _logs_command(config: RehearsalConfig, job_name: str) -> tuple[str, ...]:
    return tuple([*_kubectl_base(config), "-n", config.namespace, "logs", f"job/{job_name}"])


def build_rehearsal_steps(config: RehearsalConfig) -> list[RehearsalStep]:
    _validate_config(config)
    steps = [
        RehearsalStep(
            name="confirm Kubernetes context",
            command=tuple([*_kubectl_base(config), "config", "current-context"]),
        )
    ]

    for target in _targets(config):
        job_name = _job_name(config, target)
        steps.extend(
            [
                RehearsalStep(
                    name=f"remove stale load job for {target.name}",
                    command=_delete_job_command(config, job_name, ignore_missing=True),
                ),
                RehearsalStep(
                    name=f"start Fortio load job for {target.name}",
                    command=_create_job_command(config, job_name, target),
                ),
                RehearsalStep(
                    name=f"wait for Fortio load job for {target.name}",
                    command=_wait_job_command(config, job_name),
                ),
                RehearsalStep(
                    name=f"collect Fortio load job logs for {target.name}",
                    command=_logs_command(config, job_name),
                ),
            ]
        )
        if config.cleanup:
            steps.append(
                RehearsalStep(
                    name=f"delete Fortio load job for {target.name}",
                    command=_delete_job_command(config, job_name, ignore_missing=False),
                )
            )
    return steps


def print_plan(steps: list[RehearsalStep]) -> None:
    for index, step in enumerate(steps, start=1):
        print(f"{index}. {step.name}")
        print(f"   {format_command(step.command)}")


def run_command_step(step: RehearsalStep) -> None:
    subprocess.run(step.command, check=True)


def run_rehearsal(steps: list[RehearsalStep]) -> None:
    for step in steps:
        print(f"[axis-load-rehearsal] {step.name}")
        run_command_step(step)


def _parse_target(value: str) -> LoadTarget:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--target must use name=url format")
    name, url = value.split("=", 1)
    name = name.strip()
    url = url.strip()
    if not name:
        raise argparse.ArgumentTypeError("--target name cannot be empty")
    if not url.startswith(("http://", "https://")):
        raise argparse.ArgumentTypeError("--target URL must start with http:// or https://")
    return LoadTarget(name=name, url=url)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or print the Limes Axis Kubernetes bounded load rehearsal."
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
    parser.add_argument("--image", default="fortio/fortio:1.69.3", help="Fortio container image.")
    parser.add_argument("--duration", default="60s", help="Fortio load duration.")
    parser.add_argument("--qps", type=int, default=10, help="Fortio QPS target per job.")
    parser.add_argument("--connections", type=int, default=2, help="Fortio connection count.")
    parser.add_argument("--timeout", default="10m", help="kubectl wait timeout.")
    parser.add_argument(
        "--target",
        action="append",
        type=_parse_target,
        default=[],
        help="Load target in name=url format. May be repeated.",
    )
    parser.add_argument(
        "--keep-jobs",
        action="store_true",
        help="Leave Fortio Jobs in the namespace after logs are collected.",
    )
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> RehearsalConfig:
    return RehearsalConfig(
        release=args.release,
        namespace=args.namespace,
        repo_root=args.repo_root.resolve(),
        kube_context=args.kube_context,
        image=args.image,
        duration=args.duration,
        qps=args.qps,
        connections=args.connections,
        timeout=args.timeout,
        targets=tuple(args.target),
        cleanup=not args.keep_jobs,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = config_from_args(args)
    try:
        steps = build_rehearsal_steps(config)
    except ValueError as error:
        print(f"[axis-load-rehearsal] failed: {error}", file=sys.stderr)
        return 1

    if args.plan:
        print_plan(steps)
        return 0

    try:
        run_rehearsal(steps)
    except (subprocess.CalledProcessError, OSError) as error:
        print(f"[axis-load-rehearsal] failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
