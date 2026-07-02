from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


class TlsTarget(NamedTuple):
    host: str
    url: str


class RehearsalStep(NamedTuple):
    name: str
    command: tuple[str, ...]


class RehearsalConfig(NamedTuple):
    release: str = "limes-axis"
    namespace: str = "limes-axis"
    repo_root: Path = Path(__file__).resolve().parents[3]
    kube_context: str | None = None
    ingress_name: str | None = None
    tls_secret: str | None = None
    certificate_name: str | None = None
    issuer_name: str | None = None
    issuer_kind: str = "ClusterIssuer"
    timeout: str = "10m"
    curl_timeout_seconds: int = 10
    dns_server: str | None = None
    targets: tuple[TlsTarget, ...] = ()


def format_command(command: tuple[str, ...]) -> str:
    return shlex.join(command)


def _kubectl_base(config: RehearsalConfig) -> list[str]:
    command = ["kubectl"]
    if config.kube_context:
        command.extend(["--context", config.kube_context])
    return command


def _ingress_name(config: RehearsalConfig) -> str:
    if config.ingress_name:
        return config.ingress_name
    return config.release


def _certificate_name(config: RehearsalConfig) -> str | None:
    if config.certificate_name:
        return config.certificate_name
    return config.tls_secret


def _default_targets() -> tuple[TlsTarget, ...]:
    return (
        TlsTarget(host="axis.example.com", url="https://axis.example.com/"),
        TlsTarget(host="api.axis.example.com", url="https://api.axis.example.com/ready"),
    )


def _targets(config: RehearsalConfig) -> tuple[TlsTarget, ...]:
    if config.targets:
        return config.targets
    return _default_targets()


def _validate_config(config: RehearsalConfig) -> None:
    if not config.release.strip():
        raise ValueError("release cannot be empty")
    if not config.namespace.strip():
        raise ValueError("namespace cannot be empty")
    if not config.timeout.strip():
        raise ValueError("timeout cannot be empty")
    if config.curl_timeout_seconds <= 0:
        raise ValueError("curl timeout must be greater than zero")
    for target in _targets(config):
        if not target.host.strip():
            raise ValueError("TLS readiness target host cannot be empty")
        if not target.url.startswith("https://"):
            raise ValueError("TLS readiness targets must use https://")


def _ingress_get_command(config: RehearsalConfig) -> tuple[str, ...]:
    return tuple(
        [
            *_kubectl_base(config),
            "-n",
            config.namespace,
            "get",
            "ingress",
            _ingress_name(config),
            "-o",
            "wide",
        ]
    )


def _ingress_describe_command(config: RehearsalConfig) -> tuple[str, ...]:
    return tuple(
        [
            *_kubectl_base(config),
            "-n",
            config.namespace,
            "describe",
            "ingress",
            _ingress_name(config),
        ]
    )


def _tls_secret_command(config: RehearsalConfig) -> tuple[str, ...] | None:
    if not config.tls_secret:
        return None
    return tuple(
        [
            *_kubectl_base(config),
            "-n",
            config.namespace,
            "get",
            "secret",
            config.tls_secret,
            "-o",
            "jsonpath={.type}",
        ]
    )


def _issuer_command(config: RehearsalConfig) -> tuple[str, ...] | None:
    if not config.issuer_name:
        return None
    if config.issuer_kind.casefold() == "clusterissuer":
        return tuple(
            [
                *_kubectl_base(config),
                "get",
                "clusterissuer",
                config.issuer_name,
                "-o",
                "wide",
            ]
        )
    return tuple(
        [
            *_kubectl_base(config),
            "-n",
            config.namespace,
            "get",
            "issuer",
            config.issuer_name,
            "-o",
            "wide",
        ]
    )


def _certificate_get_command(config: RehearsalConfig, certificate_name: str) -> tuple[str, ...]:
    return tuple(
        [
            *_kubectl_base(config),
            "-n",
            config.namespace,
            "get",
            "certificate",
            certificate_name,
            "-o",
            "wide",
        ]
    )


def _certificate_describe_command(
    config: RehearsalConfig,
    certificate_name: str,
) -> tuple[str, ...]:
    return tuple(
        [
            *_kubectl_base(config),
            "-n",
            config.namespace,
            "describe",
            "certificate",
            certificate_name,
        ]
    )


def _certificate_wait_command(config: RehearsalConfig, certificate_name: str) -> tuple[str, ...]:
    return tuple(
        [
            *_kubectl_base(config),
            "-n",
            config.namespace,
            "wait",
            "--for=condition=Ready",
            f"certificate/{certificate_name}",
            f"--timeout={config.timeout}",
        ]
    )


def _dns_command(config: RehearsalConfig, target: TlsTarget) -> tuple[str, ...]:
    command = ["dig"]
    if config.dns_server:
        command.append(f"@{config.dns_server}")
    command.extend(["+short", target.host])
    return tuple(command)


def _openssl_command(target: TlsTarget) -> tuple[str, ...]:
    return (
        "openssl",
        "s_client",
        "-servername",
        target.host,
        "-connect",
        f"{target.host}:443",
        "-brief",
    )


def _curl_command(config: RehearsalConfig, target: TlsTarget) -> tuple[str, ...]:
    return (
        "curl",
        "--fail",
        "--silent",
        "--show-error",
        "--location",
        "--max-time",
        str(config.curl_timeout_seconds),
        target.url,
    )


def build_rehearsal_steps(config: RehearsalConfig) -> list[RehearsalStep]:
    _validate_config(config)
    steps = [
        RehearsalStep(
            name="confirm Kubernetes context",
            command=tuple([*_kubectl_base(config), "config", "current-context"]),
        ),
        RehearsalStep(name="inspect Ingress", command=_ingress_get_command(config)),
        RehearsalStep(name="describe Ingress", command=_ingress_describe_command(config)),
    ]

    secret_command = _tls_secret_command(config)
    if secret_command is not None:
        steps.append(RehearsalStep(name="verify TLS Secret type", command=secret_command))

    issuer_command = _issuer_command(config)
    if issuer_command is not None:
        steps.append(RehearsalStep(name="inspect cert-manager issuer", command=issuer_command))

    certificate_name = _certificate_name(config)
    if certificate_name is not None:
        steps.extend(
            [
                RehearsalStep(
                    name="inspect cert-manager Certificate",
                    command=_certificate_get_command(config, certificate_name),
                ),
                RehearsalStep(
                    name="describe cert-manager Certificate",
                    command=_certificate_describe_command(config, certificate_name),
                ),
                RehearsalStep(
                    name="wait for cert-manager Certificate readiness",
                    command=_certificate_wait_command(config, certificate_name),
                ),
            ]
        )

    for target in _targets(config):
        steps.extend(
            [
                RehearsalStep(
                    name=f"resolve DNS for {target.host}",
                    command=_dns_command(config, target),
                ),
                RehearsalStep(
                    name=f"verify TLS handshake for {target.host}",
                    command=_openssl_command(target),
                ),
                RehearsalStep(
                    name=f"verify HTTPS reachability for {target.host}",
                    command=_curl_command(config, target),
                ),
            ]
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
        print(f"[axis-tls-readiness] {step.name}")
        run_command_step(step)


def _parse_target(value: str) -> TlsTarget:
    if "=" not in value:
        raise argparse.ArgumentTypeError("--host must use host=https://url format")
    host, url = value.split("=", 1)
    return TlsTarget(host=host.strip(), url=url.strip())


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or print the Limes Axis Kubernetes TLS readiness rehearsal."
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
    parser.add_argument("--ingress-name", help="Ingress name. Defaults to --release.")
    parser.add_argument("--tls-secret", help="Kubernetes TLS Secret name to verify.")
    parser.add_argument("--certificate-name", help="cert-manager Certificate name.")
    parser.add_argument("--issuer-name", help="cert-manager Issuer or ClusterIssuer name.")
    parser.add_argument(
        "--issuer-kind",
        default="ClusterIssuer",
        help="cert-manager issuer kind: ClusterIssuer or Issuer.",
    )
    parser.add_argument("--timeout", default="10m", help="kubectl wait timeout.")
    parser.add_argument(
        "--curl-timeout-seconds",
        type=int,
        default=10,
        help="curl --max-time value for each HTTPS target.",
    )
    parser.add_argument("--dns-server", help="Optional DNS server for dig, for example 1.1.1.1.")
    parser.add_argument(
        "--host",
        action="append",
        type=_parse_target,
        default=[],
        help="Host and HTTPS URL in host=https://url format. May be repeated.",
    )
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> RehearsalConfig:
    return RehearsalConfig(
        release=args.release,
        namespace=args.namespace,
        repo_root=args.repo_root.resolve(),
        kube_context=args.kube_context,
        ingress_name=args.ingress_name,
        tls_secret=args.tls_secret,
        certificate_name=args.certificate_name,
        issuer_name=args.issuer_name,
        issuer_kind=args.issuer_kind,
        timeout=args.timeout,
        curl_timeout_seconds=args.curl_timeout_seconds,
        dns_server=args.dns_server,
        targets=tuple(args.host),
    )


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        config = config_from_args(args)
        steps = build_rehearsal_steps(config)
    except (argparse.ArgumentTypeError, ValueError) as error:
        print(f"[axis-tls-readiness] failed: {error}", file=sys.stderr)
        return 1

    if args.plan:
        print_plan(steps)
        return 0

    try:
        run_rehearsal(steps)
    except (subprocess.CalledProcessError, OSError) as error:
        print(f"[axis-tls-readiness] failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
