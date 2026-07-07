from __future__ import annotations

import pytest
from starlette.requests import Request

from axis_api.config import Settings
from axis_api.session_metadata import (
    CLIENT_IP_MAX_LENGTH,
    UNKNOWN_DEVICE_LABEL,
    USER_AGENT_MAX_LENGTH,
    derive_device_label,
    extract_session_client_metadata,
    resolve_client_ip,
)

_CHROME_MACOS = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_SAFARI_MACOS = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15"
)


def _request(
    headers: dict[str, str] | None = None,
    *,
    client: tuple[str, int] | None = ("203.0.113.7", 40000),
) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/identity/oidc/callback",
        "query_string": b"",
        "headers": [
            (name.lower().encode("latin-1"), value.encode("latin-1"))
            for name, value in (headers or {}).items()
        ],
        "client": client,
    }
    return Request(scope)


def _settings(**overrides: object) -> Settings:
    return Settings(postgres_dsn="sqlite+pysqlite://", **overrides)


@pytest.mark.parametrize(
    ("user_agent", "expected_label"),
    [
        (_CHROME_MACOS, "Chrome on macOS"),
        (_SAFARI_MACOS, "Safari on macOS"),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Chrome on Windows",
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
            "Edge on Windows",
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 OPR/111.0.0.0",
            "Opera on macOS",
        ),
        (
            "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
            "Firefox on Linux",
        ),
        (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 "
            "Mobile/15E148 Safari/604.1",
            "Safari on iOS",
        ),
        (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/126.0.0.0 "
            "Mobile/15E148 Safari/604.1",
            "Chrome on iOS",
        ),
        (
            "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) FxiOS/127.0 Mobile/15E148 Safari/605.1.15",
            "Firefox on iOS",
        ),
        (
            "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
            "Chrome on Android",
        ),
        (
            "Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Chrome on ChromeOS",
        ),
        # Browser family recognized without an OS token: browser only.
        ("Chrome/126.0.0.0", "Chrome"),
        # Nothing recognizable collapses to the unknown label.
        ("curl/8.6.0", UNKNOWN_DEVICE_LABEL),
        ("totally-custom-agent/1.0", UNKNOWN_DEVICE_LABEL),
        ("", UNKNOWN_DEVICE_LABEL),
        (None, UNKNOWN_DEVICE_LABEL),
    ],
)
def test_device_label_parsing(user_agent: str | None, expected_label: str) -> None:
    assert derive_device_label(user_agent) == expected_label


def test_extract_bounds_user_agent_length() -> None:
    oversized = "Mozilla/5.0 " + "x" * 600
    metadata = extract_session_client_metadata(
        _request({"User-Agent": oversized}),
        _settings(),
    )
    assert metadata.user_agent is not None
    assert len(metadata.user_agent) == USER_AGENT_MAX_LENGTH
    assert metadata.user_agent == oversized[:USER_AGENT_MAX_LENGTH]


def test_extract_without_user_agent_yields_unknown_device() -> None:
    metadata = extract_session_client_metadata(_request(), _settings())
    assert metadata.user_agent is None
    assert metadata.device_label == UNKNOWN_DEVICE_LABEL
    assert metadata.client_ip == "203.0.113.7"


def test_forwarded_for_is_ignored_without_the_trusted_proxy_flag() -> None:
    request = _request({"X-Forwarded-For": "198.51.100.9"})
    assert resolve_client_ip(request, _settings()) == "203.0.113.7"


def test_forwarded_for_last_hop_wins_with_the_trusted_proxy_flag() -> None:
    # The single trusted proxy appends the peer it observed as the final hop.
    request = _request({"X-Forwarded-For": "203.0.113.7, 10.0.0.1, 198.51.100.9"})
    settings = _settings(identity_session_trusted_proxy_enabled=True)
    assert resolve_client_ip(request, settings) == "198.51.100.9"


def test_forged_leftmost_forwarded_for_is_not_recorded() -> None:
    # A client can prepend anything; only the proxy-appended rightmost hop is
    # trusted, so the forged leftmost value must never be recorded.
    request = _request(
        {"X-Forwarded-For": "1.2.3.4, 198.51.100.9"},
        client=("10.9.8.7", 40000),
    )
    settings = _settings(identity_session_trusted_proxy_enabled=True)
    resolved = resolve_client_ip(request, settings)
    assert resolved == "198.51.100.9"
    assert resolved != "1.2.3.4"


@pytest.mark.parametrize(
    ("header_value", "expected_ip"),
    [
        ("[2001:db8::1]:443", "2001:db8::1"),
        ("2001:db8::1", "2001:db8::1"),
        ("198.51.100.9:52341", "198.51.100.9"),
    ],
)
def test_forwarded_for_accepts_port_and_bracket_forms(
    header_value: str, expected_ip: str
) -> None:
    request = _request({"X-Forwarded-For": header_value})
    settings = _settings(identity_session_trusted_proxy_enabled=True)
    assert resolve_client_ip(request, settings) == expected_ip


@pytest.mark.parametrize(
    "garbage_header",
    [
        "not-an-ip",
        "<script>alert(1)</script>",
        "",
        "198.51.100.9, ",
        "999.999.999.999",
        "a" * (CLIENT_IP_MAX_LENGTH + 1),
    ],
)
def test_garbage_forwarded_for_falls_back_to_the_socket_peer(
    garbage_header: str,
) -> None:
    request = _request({"X-Forwarded-For": garbage_header})
    settings = _settings(identity_session_trusted_proxy_enabled=True)
    assert resolve_client_ip(request, settings) == "203.0.113.7"


def test_missing_socket_peer_resolves_to_none() -> None:
    request = _request(client=None)
    assert resolve_client_ip(request, _settings()) is None
    settings = _settings(identity_session_trusted_proxy_enabled=True)
    assert resolve_client_ip(request, settings) is None
