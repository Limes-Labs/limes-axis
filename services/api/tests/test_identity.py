import json

from jose import jwt
from jose.utils import base64url_encode

from axis_api.identity import (
    OidcAuthenticationError,
    RemoteJwksOidcVerifier,
    StaticJwksOidcVerifier,
)


def _oct_jwks(secret: str, kid: str = "axis-test") -> dict:
    return {
        "keys": [
            {
                "kty": "oct",
                "kid": kid,
                "k": base64url_encode(secret.encode()).decode(),
            }
        ]
    }


def _token(secret: str, claims: dict, kid: str = "axis-test") -> str:
    return jwt.encode(claims, secret, algorithm="HS256", headers={"kid": kid})


def test_static_jwks_oidc_verifier_validates_token_and_extracts_actor_context() -> None:
    secret = "axis-test-secret"
    verifier = StaticJwksOidcVerifier(
        issuer="https://issuer.example/realms/axis",
        audience="limes-axis-api",
        algorithms=["HS256"],
        jwks=_oct_jwks(secret),
        tenant_claim="axis_tenant",
    )
    token = _token(
        secret,
        {
            "iss": "https://issuer.example/realms/axis",
            "aud": "limes-axis-api",
            "sub": "plant-operations-owner-role",
            "axis_tenant": "tenant_demo_manufacturing",
            "scope": "approvals:supply:decide audit:read",
            "scp": ["workflows:read"],
            "realm_access": {"roles": ["operations-owner"]},
            "resource_access": {
                "limes-axis-api": {"roles": ["approvals:maintenance:decide"]}
            },
            "exp": 4102444800,
        },
    )

    principal = verifier.verify_authorization_header(f"Bearer {token}")

    assert principal.actor_id == "plant-operations-owner-role"
    assert principal.subject_id == "plant-operations-owner-role"
    assert principal.tenant_id == "tenant_demo_manufacturing"
    assert principal.expires_at == 4102444800
    assert principal.scopes == [
        "approvals:maintenance:decide",
        "approvals:supply:decide",
        "audit:read",
        "operations-owner",
        "workflows:read",
    ]


def test_static_jwks_oidc_verifier_rejects_wrong_audience() -> None:
    secret = "axis-test-secret"
    verifier = StaticJwksOidcVerifier(
        issuer="https://issuer.example/realms/axis",
        audience="limes-axis-api",
        algorithms=["HS256"],
        jwks=_oct_jwks(secret),
        tenant_claim="axis_tenant",
    )
    token = _token(
        secret,
        {
            "iss": "https://issuer.example/realms/axis",
            "aud": "other-api",
            "sub": "plant-operations-owner-role",
            "axis_tenant": "tenant_demo_manufacturing",
            "scope": "approvals:supply:decide",
            "exp": 4102444800,
        },
    )

    try:
        verifier.verify_authorization_header(f"Bearer {token}")
    except OidcAuthenticationError as exc:
        assert exc.reason == "invalid_token"
    else:
        raise AssertionError("expected wrong audience to be rejected")


def test_static_jwks_oidc_verifier_validates_id_token_nonce_and_client_audience() -> None:
    secret = "axis-test-secret"
    verifier = StaticJwksOidcVerifier(
        issuer="https://issuer.example/realms/axis",
        audience="limes-axis-api",
        algorithms=["HS256"],
        jwks=_oct_jwks(secret),
        tenant_claim="axis_tenant",
    )
    id_token = _token(
        secret,
        {
            "iss": "https://issuer.example/realms/axis",
            "aud": "axis-console",
            "azp": "axis-console",
            "sub": "plant-operations-owner-role",
            "nonce": "login-nonce",
            "exp": 4102444800,
        },
    )

    claims = verifier.verify_id_token(
        id_token,
        client_id="axis-console",
        nonce="login-nonce",
    )

    assert claims["sub"] == "plant-operations-owner-role"
    assert claims["nonce"] == "login-nonce"


def test_static_jwks_oidc_verifier_rejects_id_token_authorized_party_mismatch() -> None:
    secret = "axis-test-secret"
    verifier = StaticJwksOidcVerifier(
        issuer="https://issuer.example/realms/axis",
        audience="limes-axis-api",
        algorithms=["HS256"],
        jwks=_oct_jwks(secret),
        tenant_claim="axis_tenant",
    )
    id_token = _token(
        secret,
        {
            "iss": "https://issuer.example/realms/axis",
            "aud": ["axis-console", "unexpected-client"],
            "azp": "unexpected-client",
            "sub": "plant-operations-owner-role",
            "nonce": "login-nonce",
            "exp": 4102444800,
        },
    )

    try:
        verifier.verify_id_token(
            id_token,
            client_id="axis-console",
            nonce="login-nonce",
        )
    except OidcAuthenticationError as exc:
        assert exc.reason == "invalid_id_token_authorized_party"
    else:
        raise AssertionError("expected wrong authorized party to be rejected")


def test_static_jwks_oidc_verifier_rejects_single_audience_id_token_with_wrong_azp() -> None:
    secret = "axis-test-secret"
    verifier = StaticJwksOidcVerifier(
        issuer="https://issuer.example/realms/axis",
        audience="limes-axis-api",
        algorithms=["HS256"],
        jwks=_oct_jwks(secret),
        tenant_claim="axis_tenant",
    )
    id_token = _token(
        secret,
        {
            "iss": "https://issuer.example/realms/axis",
            "aud": "axis-console",
            "azp": "unexpected-client",
            "sub": "plant-operations-owner-role",
            "nonce": "login-nonce",
            "exp": 4102444800,
        },
    )

    try:
        verifier.verify_id_token(
            id_token,
            client_id="axis-console",
            nonce="login-nonce",
        )
    except OidcAuthenticationError as exc:
        assert exc.reason == "invalid_id_token_authorized_party"
    else:
        raise AssertionError("expected wrong authorized party to be rejected")


def test_static_jwks_oidc_verifier_rejects_id_token_without_expiry() -> None:
    secret = "axis-test-secret"
    verifier = StaticJwksOidcVerifier(
        issuer="https://issuer.example/realms/axis",
        audience="limes-axis-api",
        algorithms=["HS256"],
        jwks=_oct_jwks(secret),
        tenant_claim="axis_tenant",
    )
    id_token = _token(
        secret,
        {
            "iss": "https://issuer.example/realms/axis",
            "aud": "axis-console",
            "azp": "axis-console",
            "sub": "plant-operations-owner-role",
            "nonce": "login-nonce",
        },
    )

    try:
        verifier.verify_id_token(
            id_token,
            client_id="axis-console",
            nonce="login-nonce",
        )
    except OidcAuthenticationError as exc:
        assert exc.reason == "missing_id_token_expiry"
    else:
        raise AssertionError("expected missing expiry to be rejected")


def test_remote_jwks_oidc_verifier_fetches_and_caches_jwks(monkeypatch) -> None:
    secret = "axis-test-secret"
    jwks = _oct_jwks(secret)
    fetches: list[str] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self) -> bytes:
            return b'{"keys":[{"kty":"oct","kid":"axis-test","k":"YXhpcy10ZXN0LXNlY3JldA"}]}'

    def fake_urlopen(url: str, timeout: int):
        fetches.append(f"{url}:{timeout}")
        return FakeResponse()

    monkeypatch.setattr("axis_api.identity.urlopen", fake_urlopen)
    verifier = RemoteJwksOidcVerifier(
        issuer="https://issuer.example/realms/axis",
        audience="limes-axis-api",
        algorithms=["HS256"],
        jwks_url="https://issuer.example/realms/axis/protocol/openid-connect/certs",
        cache_seconds=300,
        tenant_claim="axis_tenant",
    )
    token = _token(
        secret,
        {
            "iss": "https://issuer.example/realms/axis",
            "aud": "limes-axis-api",
            "sub": "agent_supply_risk",
            "axis_tenant": "tenant_demo_manufacturing",
            "scope": "supply:read",
            "exp": 4102444800,
        },
    )

    assert verifier.verify_authorization_header(f"Bearer {token}").actor_id == "agent_supply_risk"
    assert verifier.verify_authorization_header(f"Bearer {token}").actor_id == "agent_supply_risk"
    assert fetches == [
        "https://issuer.example/realms/axis/protocol/openid-connect/certs:2"
    ]
    assert verifier.jwks == jwks


def test_remote_jwks_oidc_verifier_refreshes_once_for_rotated_kid(monkeypatch) -> None:
    old_secret = "axis-old-secret"
    new_secret = "axis-new-secret"
    payloads = [_oct_jwks(old_secret, "old-key"), _oct_jwks(new_secret, "new-key")]
    fetches = 0

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self) -> bytes:
            return json.dumps(self.payload).encode()

    def fake_urlopen(_url: str, timeout: int):
        nonlocal fetches
        assert timeout == 2
        payload = payloads[min(fetches, len(payloads) - 1)]
        fetches += 1
        return FakeResponse(payload)

    monkeypatch.setattr("axis_api.identity.urlopen", fake_urlopen)
    verifier = RemoteJwksOidcVerifier(
        issuer="https://issuer.example/realms/axis",
        audience="limes-axis-api",
        algorithms=["HS256"],
        jwks_url="https://issuer.example/jwks",
        cache_seconds=300,
        tenant_claim="axis_tenant",
    )
    claims = {
        "iss": "https://issuer.example/realms/axis",
        "aud": "limes-axis-api",
        "sub": "operator",
        "axis_tenant": "tenant_demo_manufacturing",
        "exp": 4102444800,
    }

    verifier.verify_authorization_header(
        f"Bearer {_token(old_secret, claims, kid='old-key')}"
    )
    principal = verifier.verify_authorization_header(
        f"Bearer {_token(new_secret, claims, kid='new-key')}"
    )

    assert principal.actor_id == "operator"
    assert fetches == 2
    assert verifier.jwks == payloads[1]
