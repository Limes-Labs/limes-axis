"""Client device metadata capture for OIDC browser sessions.

The login callback and the refresh rotation capture a small, deterministic
snapshot of the requesting client: the raw ``User-Agent`` header (bounded),
the client IP and a compact human-readable device label parsed from the
user agent. The snapshot is stored on the session row so operators can tell
their own sessions apart in the session inventory; it is never emitted into
audit payloads.

Trust model for the client IP: by default the API records the direct socket
peer (``request.client.host``). Deployments that sit behind exactly one
trusted reverse proxy or ingress must set
``AXIS_IDENTITY_SESSION_TRUSTED_PROXY_ENABLED=true`` so the LAST (rightmost)
hop of ``X-Forwarded-For`` is recorded instead. Standard proxies append the
peer they observed (nginx ``$proxy_add_x_forwarded_for``), so with a single
trusted proxy the rightmost entry is the address that proxy actually saw the
connection from; every entry to its left is client-attested and forgeable.
The flag must stay off when clients can reach the API directly, because
``X-Forwarded-For`` is entirely client-controlled input in that topology.

Limitation: this assumes exactly one trusted proxy. Multi-proxy chains would
need a configurable trusted-hop count to skip the additional proxy-added
hops; that is a documented follow-up, not implemented here.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass

from starlette.requests import Request

from axis_api.config import Settings

USER_AGENT_MAX_LENGTH = 256
CLIENT_IP_MAX_LENGTH = 64
DEVICE_LABEL_MAX_LENGTH = 80
UNKNOWN_DEVICE_LABEL = "Unknown device"

_FORWARDED_FOR_HEADER = "x-forwarded-for"

# Ordered by specificity: tokens earlier in the table also appear in less
# specific user agents (Edge and Opera both embed "Chrome/", Chrome embeds
# "Safari/"), so the first match wins.
_BROWSER_FAMILIES: tuple[tuple[str, str], ...] = (
    ("Edg", "Edge"),
    ("OPR", "Opera"),
    ("Opera", "Opera"),
    ("Firefox", "Firefox"),
    ("FxiOS", "Firefox"),
    ("CriOS", "Chrome"),
    ("Chrome", "Chrome"),
    ("Safari", "Safari"),
)

_OS_FAMILIES: tuple[tuple[str, str], ...] = (
    ("Windows", "Windows"),
    ("iPhone", "iOS"),
    ("iPad", "iOS"),
    ("iPod", "iOS"),
    ("Mac OS X", "macOS"),
    ("Macintosh", "macOS"),
    ("Android", "Android"),
    ("CrOS", "ChromeOS"),
    ("Linux", "Linux"),
    ("X11", "Linux"),
)


@dataclass(frozen=True)
class SessionClientMetadata:
    user_agent: str | None
    client_ip: str | None
    device_label: str | None


def extract_session_client_metadata(
    request: Request,
    settings: Settings,
) -> SessionClientMetadata:
    user_agent = _bounded_user_agent(request.headers.get("user-agent"))
    return SessionClientMetadata(
        user_agent=user_agent,
        client_ip=resolve_client_ip(request, settings),
        device_label=derive_device_label(user_agent),
    )


def resolve_client_ip(request: Request, settings: Settings) -> str | None:
    """Resolve the client IP under the configured proxy trust model.

    Behind a single trusted proxy the LAST ``X-Forwarded-For`` hop is the
    address that proxy observed the connection from - it appended it after any
    client-supplied entries, which are all forgeable. Without the trust flag
    the header is ignored entirely because any client can forge it.
    """
    if settings.identity_session_trusted_proxy_enabled:
        forwarded_ip = _last_forwarded_hop(request.headers.get(_FORWARDED_FOR_HEADER))
        if forwarded_ip is not None:
            return forwarded_ip
    if request.client is None or not request.client.host:
        return None
    return request.client.host[:CLIENT_IP_MAX_LENGTH]


def derive_device_label(user_agent: str | None) -> str:
    """Derive a compact "<Browser> on <OS>" label from a user agent.

    Deterministic substring matching over the major browser and OS families
    only; anything unrecognized collapses to ``Unknown device`` instead of
    echoing attacker-controlled header content back to the console.
    """
    if not user_agent:
        return UNKNOWN_DEVICE_LABEL
    browser = _match_family(user_agent, _BROWSER_FAMILIES)
    if browser is None:
        return UNKNOWN_DEVICE_LABEL
    operating_system = _match_family(user_agent, _OS_FAMILIES)
    if operating_system is None:
        return browser
    return f"{browser} on {operating_system}"


def _bounded_user_agent(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    stripped = raw_value.strip()
    if not stripped:
        return None
    return stripped[:USER_AGENT_MAX_LENGTH]


def _last_forwarded_hop(header_value: str | None) -> str | None:
    if not header_value:
        return None
    # A single trusted proxy appends the peer it observed as the final entry,
    # so the rightmost hop is the only non-forgeable one in this topology.
    last_hop = header_value.rsplit(",", 1)[-1].strip()
    if not last_hop or len(last_hop) > CLIENT_IP_MAX_LENGTH:
        return None
    candidate = last_hop
    # RFC 7239-style bracketed IPv6 (with optional port) and bare
    # "ip:port" IPv4 values both appear in the wild; strip to the address.
    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1 : candidate.index("]")]
    elif candidate.count(":") == 1:
        candidate = candidate.split(":", 1)[0]
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return None
    return candidate


def _match_family(user_agent: str, families: tuple[tuple[str, str], ...]) -> str | None:
    for token, family in families:
        if token in user_agent:
            return family
    return None
