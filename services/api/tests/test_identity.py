from jose import jwt
from jose.utils import base64url_encode

from axis_api.identity import (
    OidcAuthenticationError,
    RemoteJwksOidcVerifier,
    StaticJwksOidcVerifier,
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


def _token(secret: str, claims: dict) -> str:
    return jwt.encode(claims, secret, algorithm="HS256", headers={"kid": "axis-test"})


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
