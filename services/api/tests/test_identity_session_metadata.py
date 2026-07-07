"""Browser-session device metadata and cursor pagination through the API.

Covers the metadata captured at login and refresh rotation (user agent,
client IP under the trusted-proxy flag, derived device label), its privacy
boundary (owner/admin listing only, never audit payloads) and the keyset
cursor pagination of ``GET /identity/sessions``.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from jose import jwt
from jose.utils import base64url_encode
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.config import Settings
from axis_api.identity import StaticJwksOidcVerifier
from axis_api.main import create_app
from axis_api.models import AuditEvent, Base, OidcBrowserSession
from axis_api.session_metadata import USER_AGENT_MAX_LENGTH

TOKEN_SECRET = "axis-test-secret"
DEFAULT_ACTOR = "plant-operations-owner-role"
DEFAULT_TENANT = "tenant_demo_manufacturing"
STRONG_REFRESH_KEY = "axis-refresh-credential-encryption-key-01"

SAFARI_MACOS_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15"
)
FIREFOX_LINUX_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0"
)


def _oct_jwks(secret: str) -> dict:
    return {
        "keys": [
            {
                "kty": "oct",
                "kid": "axis-test",
                "k": base64url_encode(secret.encode()).decode(),
            }
        ]
    }


def _access_token(
    settings: Settings,
    *,
    actor_id: str = DEFAULT_ACTOR,
    scope: str = "audit:read approvals:supply:decide",
) -> str:
    payload = {
        "iss": settings.oidc_issuer,
        "aud": settings.oidc_audience,
        "sub": actor_id,
        "axis_tenant": DEFAULT_TENANT,
        "scope": scope,
        "exp": 4102444800,
    }
    return jwt.encode(payload, TOKEN_SECRET, algorithm="HS256", headers={"kid": "axis-test"})


def _id_token(settings: Settings, *, nonce: str, actor_id: str = DEFAULT_ACTOR) -> str:
    payload = {
        "iss": settings.oidc_issuer,
        "aud": settings.oidc_client_id,
        "azp": settings.oidc_client_id,
        "sub": actor_id,
        "nonce": nonce,
        "exp": 4102444800,
        "iat": 1893456000,
    }
    return jwt.encode(payload, TOKEN_SECRET, algorithm="HS256", headers={"kid": "axis-test"})


def _settings(**overrides: object) -> Settings:
    values = {
        "postgres_dsn": "sqlite+pysqlite://",
        "api_base_url": "https://api.axis.example",
        "public_base_url": "https://console.axis.example",
        "oidc_auth_required": True,
        "oidc_issuer": "https://idp.example/realms/axis",
        "oidc_audience": "limes-axis-api",
        "oidc_jwks_url": "https://idp.example/realms/axis/protocol/openid-connect/certs",
        "oidc_algorithms": ["HS256"],
        "oidc_client_id": "axis-console",
        "oidc_client_secret": "axis-client-secret",
        "oidc_authorization_url": (
            "https://idp.example/realms/axis/protocol/openid-connect/auth"
        ),
        "oidc_token_url": "https://idp.example/realms/axis/protocol/openid-connect/token",
        "oidc_session_cookie_signing_secret": "a-secure-cookie-signing-secret",
        "oidc_session_cookie_secure": False,
        "oidc_refresh_token_encryption_key": STRONG_REFRESH_KEY,
    }
    values.update(overrides)
    return Settings(**values)


def _session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class _FakeTokenEndpoint:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.nonce = ""
        self.issued_refresh_tokens = 0

    def __call__(self, form: dict[str, str], _settings: Settings) -> dict[str, Any]:
        self.issued_refresh_tokens += 1
        response: dict[str, Any] = {
            "access_token": _access_token(self.settings),
            "expires_in": 900,
            "token_type": "Bearer",
            "refresh_token": f"refresh-token-{self.issued_refresh_tokens}",
        }
        if form.get("grant_type") != "refresh_token":
            response["id_token"] = _id_token(self.settings, nonce=self.nonce)
        return response


def _build_app(
    settings: Settings,
) -> tuple[TestClient, sessionmaker[Session], _FakeTokenEndpoint]:
    app = create_app(settings)
    factory = _session_factory()
    app.state.session_factory = factory
    app.state.identity_verifier = StaticJwksOidcVerifier(
        issuer=settings.oidc_issuer,
        audience=settings.oidc_audience,
        algorithms=settings.oidc_algorithms,
        jwks=_oct_jwks(TOKEN_SECRET),
        tenant_claim=settings.oidc_tenant_claim,
    )
    token_endpoint = _FakeTokenEndpoint(settings)
    app.state.oidc_token_exchanger = token_endpoint
    client = TestClient(app, follow_redirects=False)
    return client, factory, token_endpoint


def _login(
    client: TestClient,
    token_endpoint: _FakeTokenEndpoint,
    *,
    headers: dict[str, str] | None = None,
) -> None:
    authorize = client.get("/identity/oidc/authorize?return_to=/")
    params = parse_qs(urlparse(authorize.headers["location"]).query)
    token_endpoint.nonce = params["nonce"][0]
    state = params["state"][0]
    callback = client.get(
        f"/identity/oidc/callback?code=valid-code&state={state}",
        headers=headers,
    )
    assert callback.status_code == 307


def _csrf_headers(client: TestClient) -> dict[str, str]:
    csrf_token = client.cookies.get("axis_csrf")
    assert csrf_token
    return {"X-Axis-Csrf-Token": csrf_token}


def _sessions(session: Session) -> list[OidcBrowserSession]:
    return list(
        session.scalars(
            select(OidcBrowserSession).order_by(OidcBrowserSession.created_at.asc())
        )
    )


# --- Metadata capture -------------------------------------------------------


def test_login_captures_user_agent_ip_and_device_label() -> None:
    client, factory, token_endpoint = _build_app(_settings())

    _login(client, token_endpoint, headers={"User-Agent": SAFARI_MACOS_AGENT})

    with factory() as session:
        stored = _sessions(session)
        assert len(stored) == 1
        assert stored[0].user_agent == SAFARI_MACOS_AGENT
        assert stored[0].client_ip == "testclient"
        assert stored[0].device_label == "Safari on macOS"


def test_login_user_agent_is_truncated_to_the_bound() -> None:
    client, factory, token_endpoint = _build_app(_settings())
    oversized_agent = "Mozilla/5.0 " + "x" * 600

    _login(client, token_endpoint, headers={"User-Agent": oversized_agent})

    with factory() as session:
        stored = _sessions(session)
        assert stored[0].user_agent == oversized_agent[:USER_AGENT_MAX_LENGTH]
        assert len(stored[0].user_agent) == USER_AGENT_MAX_LENGTH


def test_forwarded_for_is_ignored_without_the_trusted_proxy_flag() -> None:
    client, factory, token_endpoint = _build_app(_settings())

    _login(
        client,
        token_endpoint,
        headers={"X-Forwarded-For": "198.51.100.9"},
    )

    with factory() as session:
        assert _sessions(session)[0].client_ip == "testclient"


def test_forwarded_for_last_hop_is_honored_with_the_trusted_proxy_flag() -> None:
    client, factory, token_endpoint = _build_app(
        _settings(identity_session_trusted_proxy_enabled=True)
    )

    # The single trusted proxy appends the peer it observed as the final hop;
    # the forged leftmost value must not be recorded.
    _login(
        client,
        token_endpoint,
        headers={"X-Forwarded-For": "1.2.3.4, 198.51.100.9"},
    )

    with factory() as session:
        recorded_ip = _sessions(session)[0].client_ip
        assert recorded_ip == "198.51.100.9"
        assert recorded_ip != "1.2.3.4"


def test_garbage_forwarded_for_falls_back_to_the_socket_peer() -> None:
    client, factory, token_endpoint = _build_app(
        _settings(identity_session_trusted_proxy_enabled=True)
    )

    _login(
        client,
        token_endpoint,
        headers={"X-Forwarded-For": "198.51.100.9, <not-an-ip>"},
    )

    with factory() as session:
        assert _sessions(session)[0].client_ip == "testclient"


def test_refresh_rotation_recaptures_metadata_from_the_refreshing_request() -> None:
    client, factory, token_endpoint = _build_app(_settings())
    _login(client, token_endpoint, headers={"User-Agent": SAFARI_MACOS_AGENT})

    refresh = client.post(
        "/identity/session/refresh",
        headers={**_csrf_headers(client), "User-Agent": FIREFOX_LINUX_AGENT},
    )

    assert refresh.status_code == 204
    with factory() as session:
        rotated, active = _sessions(session)
        assert rotated.status == "rotated"
        assert rotated.user_agent == SAFARI_MACOS_AGENT
        assert rotated.device_label == "Safari on macOS"
        assert active.status == "active"
        assert active.user_agent == FIREFOX_LINUX_AGENT
        assert active.device_label == "Firefox on Linux"
        assert active.client_ip == "testclient"


# --- Metadata visibility boundary -------------------------------------------


def test_session_listing_returns_metadata_to_the_owner() -> None:
    client, _factory, token_endpoint = _build_app(_settings())
    _login(client, token_endpoint, headers={"User-Agent": SAFARI_MACOS_AGENT})

    body = client.get("/identity/sessions").json()

    assert len(body["sessions"]) == 1
    record = body["sessions"][0]
    assert record["user_agent"] == SAFARI_MACOS_AGENT
    assert record["client_ip"] == "testclient"
    assert record["device_label"] == "Safari on macOS"


def test_tenant_wide_listing_returns_metadata_to_admins() -> None:
    settings = _settings()
    client, _factory, token_endpoint = _build_app(settings)
    _login(client, token_endpoint, headers={"User-Agent": SAFARI_MACOS_AGENT})
    admin_token = _access_token(
        settings,
        actor_id="identity-admin-role",
        scope="identity:sessions:admin",
    )

    body = client.get(
        "/identity/sessions?tenant_wide=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()

    assert body["tenant_wide"] is True
    assert body["sessions"][0]["device_label"] == "Safari on macOS"
    assert body["sessions"][0]["client_ip"] == "testclient"


def test_device_metadata_never_enters_audit_payloads() -> None:
    client, factory, token_endpoint = _build_app(
        _settings(identity_session_trusted_proxy_enabled=True)
    )
    _login(
        client,
        token_endpoint,
        headers={
            "User-Agent": SAFARI_MACOS_AGENT,
            "X-Forwarded-For": "198.51.100.9",
        },
    )
    assert (
        client.post(
            "/identity/session/refresh",
            headers={**_csrf_headers(client), "User-Agent": FIREFOX_LINUX_AGENT},
        ).status_code
        == 204
    )

    with factory() as session:
        stored = _sessions(session)
        assert stored[0].client_ip == "198.51.100.9"
        rendered_payloads = str(
            [event.payload for event in session.scalars(select(AuditEvent))]
        )
        assert "198.51.100.9" not in rendered_payloads
        assert "testclient" not in rendered_payloads
        assert "Safari" not in rendered_payloads
        assert "Firefox" not in rendered_payloads
        assert "Mozilla" not in rendered_payloads


# --- Cursor pagination -------------------------------------------------------


def test_session_listing_without_cursor_keeps_the_response_shape() -> None:
    client, _factory, token_endpoint = _build_app(_settings())
    _login(client, token_endpoint)

    body = client.get("/identity/sessions").json()

    assert body["tenant_id"] == DEFAULT_TENANT
    assert body["actor_id"] == DEFAULT_ACTOR
    assert body["tenant_wide"] is False
    assert body["has_more"] is False
    assert body["next_cursor"] is None
    assert len(body["sessions"]) == 1
    assert body["sessions"][0]["current"] is True


def test_pagination_is_stable_across_pages_with_cursor_round_trip() -> None:
    client, _factory, token_endpoint = _build_app(_settings())
    for _ in range(5):
        _login(client, token_endpoint)

    pages: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        path = "/identity/sessions?page_size=2"
        if cursor is not None:
            path = f"{path}&cursor={cursor}"
        body = client.get(path).json()
        pages.append(body)
        cursor = body["next_cursor"]
        if not body["has_more"]:
            break

    assert [len(page["sessions"]) for page in pages] == [2, 2, 1]
    assert [page["has_more"] for page in pages] == [True, True, False]
    assert pages[-1]["next_cursor"] is None
    refs = [
        record["session_ref"] for page in pages for record in page["sessions"]
    ]
    assert len(refs) == len(set(refs)) == 5
    created_instants = [
        record["created_at"] for page in pages for record in page["sessions"]
    ]
    assert created_instants == sorted(created_instants, reverse=True)
    # The newest session is the one currently bound to the cookie.
    assert pages[0]["sessions"][0]["current"] is True


def test_rotated_sessions_paginate_newest_first() -> None:
    client, _factory, token_endpoint = _build_app(_settings())
    _login(client, token_endpoint)
    assert (
        client.post("/identity/session/refresh", headers=_csrf_headers(client)).status_code
        == 204
    )

    first_page = client.get("/identity/sessions?page_size=1").json()
    assert first_page["has_more"] is True
    assert first_page["sessions"][0]["status"] == "active"
    assert first_page["sessions"][0]["current"] is True

    second_page = client.get(
        f"/identity/sessions?page_size=1&cursor={first_page['next_cursor']}"
    ).json()
    assert second_page["has_more"] is False
    assert second_page["next_cursor"] is None
    assert second_page["sessions"][0]["status"] == "rotated"
    assert second_page["sessions"][0]["current"] is False


def test_invalid_cursor_is_rejected_as_422() -> None:
    client, _factory, token_endpoint = _build_app(_settings())
    _login(client, token_endpoint)

    for garbage in ("not-base64!!", "e30", "AAAA"):
        response = client.get(f"/identity/sessions?cursor={garbage}")
        assert response.status_code == 422, garbage
        detail = response.json()["detail"]
        assert detail["reason"] == "invalid_session_cursor"


def test_page_size_bounds_are_enforced() -> None:
    client, _factory, token_endpoint = _build_app(_settings())
    _login(client, token_endpoint)

    assert client.get("/identity/sessions?page_size=0").status_code == 422
    assert client.get("/identity/sessions?page_size=101").status_code == 422
    assert client.get("/identity/sessions?page_size=1").status_code == 200
    assert client.get("/identity/sessions?page_size=100").status_code == 200
