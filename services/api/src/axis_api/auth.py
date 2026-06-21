from pydantic import BaseModel, Field


class OIDCSettings(BaseModel):
    issuer: str
    audience: str


class ActorClaims(BaseModel):
    subject: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    scopes: list[str] = Field(default_factory=list)


def parse_development_actor_claims(claims: dict) -> ActorClaims:
    """Parse already-decoded claims for local development tests only.

    Production OIDC handling must validate issuer, audience, signature, expiry,
    nonce where relevant, and token binding before constructing ActorClaims.
    """

    scope_value = claims.get("scope", "")
    scopes = scope_value.split() if isinstance(scope_value, str) else list(scope_value)
    return ActorClaims(
        subject=str(claims["sub"]),
        tenant_id=str(claims["tenant_id"]),
        scopes=scopes,
    )
