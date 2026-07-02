from pydantic import BaseModel, Field

from axis_api.config import Settings
from axis_api.identity import OidcPrincipal


class IdentitySessionReadModel(BaseModel):
    authenticated: bool
    mode: str = Field(min_length=1)
    actor_id: str | None = None
    tenant_id: str | None = None
    scopes: list[str] = Field(default_factory=list)
    expires_at: int | None = Field(default=None, ge=0)
    api_auth_required: bool
    enterprise_sso_ready: bool
    readiness_status: str = Field(min_length=1)
    issuer: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    jwks_source: str = Field(min_length=1)
    session_boundary: str = Field(min_length=1)
    capabilities: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def build_identity_session_read_model(
    *,
    settings: Settings,
    oidc_readiness_report: dict[str, object],
    principal: OidcPrincipal | None,
) -> IdentitySessionReadModel:
    authenticated = principal is not None
    capabilities = _session_capabilities(principal)
    limitations = _session_limitations(
        authenticated=authenticated,
        principal=principal,
        oidc_readiness_report=oidc_readiness_report,
    )

    return IdentitySessionReadModel(
        authenticated=authenticated,
        mode=_session_mode(principal) if authenticated else "public_evaluation",
        actor_id=principal.actor_id if principal else None,
        tenant_id=principal.tenant_id if principal else None,
        scopes=principal.scopes if principal else [],
        expires_at=principal.expires_at if principal else None,
        api_auth_required=settings.oidc_auth_required,
        enterprise_sso_ready=bool(oidc_readiness_report.get("enterprise_sso_ready")),
        readiness_status=str(oidc_readiness_report.get("status", "action_required")),
        issuer=str(oidc_readiness_report.get("issuer") or settings.oidc_issuer),
        audience=str(oidc_readiness_report.get("audience") or settings.oidc_audience),
        jwks_source=str(oidc_readiness_report.get("jwks_source", "unknown")),
        session_boundary=(
            _session_boundary(principal)
            if authenticated
            else "no_authenticated_api_actor"
        ),
        capabilities=capabilities,
        limitations=limitations,
        notes=[
            "The API never returns bearer token material.",
            "The browser may attach a bearer token, but API validation owns the session truth.",
        ],
    )


def _session_mode(principal: OidcPrincipal | None) -> str:
    if principal is not None and principal.session_source == "secure_cookie":
        return "secure_oidc_cookie"
    return "validated_oidc_bearer"


def _session_boundary(principal: OidcPrincipal | None) -> str:
    if principal is not None and principal.session_source == "secure_cookie":
        return "http_only_cookie_verified_by_axis_api"
    return "bearer_token_verified_by_axis_api"


def _session_capabilities(principal: OidcPrincipal | None) -> list[str]:
    if principal is None:
        return [
            "Public evaluation endpoints can be read when OIDC auth is optional.",
            "No tenant-scoped mutation is authorized without a validated bearer token.",
        ]

    capabilities = [
        (
            "HTTP-only Axis session cookie validated by the API session verifier."
            if principal.session_source == "secure_cookie"
            else "Bearer token validated by the Axis OIDC verifier."
        ),
        "Tenant and actor binding is available for protected API paths.",
    ]
    if principal.scopes:
        capabilities.append("Token scopes are available for RBAC and policy checks.")
    return capabilities


def _session_limitations(
    *,
    authenticated: bool,
    principal: OidcPrincipal | None,
    oidc_readiness_report: dict[str, object],
) -> list[str]:
    limitations: list[str] = []
    if not authenticated:
        limitations.append("No authenticated API actor is attached.")
    if principal is not None and not principal.scopes:
        limitations.append("The validated token does not expose scopes or roles.")
    if not bool(oidc_readiness_report.get("auth_required")):
        limitations.append("OIDC is optional in this environment; require it outside demos.")
    if not bool(oidc_readiness_report.get("enterprise_sso_ready")):
        limitations.append(
            "Enterprise SSO is not fully ready; complete issuer, JWKS and algorithm hardening."
        )
    return limitations
