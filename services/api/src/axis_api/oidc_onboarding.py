from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel

from axis_api.config import Settings
from axis_api.oidc_code_flow import (
    authorization_endpoint,
    end_session_endpoint,
    post_logout_redirect_uri,
    redirect_uri,
    token_endpoint,
)


class OidcProviderOnboarding(BaseModel):
    issuer: str
    discovery_url: str
    jwks_url: str
    authorization_url: str
    token_url: str
    end_session_url: str
    jwks_source: str
    end_session_source: str


class OidcClientOnboarding(BaseModel):
    client_id: str | None
    auth_flow: str
    redirect_uri: str
    post_logout_redirect_uri: str
    public_base_url: str
    api_base_url: str
    scopes: list[str]
    session_cookie_secure: bool
    confidential_client_configured: bool


class OidcClaimOnboarding(BaseModel):
    actor_claim: str
    tenant_claim: str
    scope_sources: list[str]


class OidcOnboardingReport(BaseModel):
    status: str
    enterprise_sso_ready: bool
    provider: OidcProviderOnboarding
    client: OidcClientOnboarding
    claims: OidcClaimOnboarding
    required_redirect_uris: list[str]
    required_post_logout_redirect_uris: list[str]
    recommended_idp_controls: list[str]
    open_action_items: list[str]
    security_notes: list[str]


def build_oidc_onboarding_report(
    settings: Settings,
    *,
    oidc_readiness_report: Mapping[str, Any],
) -> OidcOnboardingReport:
    resolved_redirect_uri = redirect_uri(settings)
    resolved_post_logout_redirect_uri = post_logout_redirect_uri(settings, "/")
    federated_logout = oidc_readiness_report.get("federated_logout")
    token_binding = oidc_readiness_report.get("token_binding")

    return OidcOnboardingReport(
        status=str(oidc_readiness_report.get("status", "action_required")),
        enterprise_sso_ready=bool(oidc_readiness_report.get("enterprise_sso_ready")),
        provider=OidcProviderOnboarding(
            issuer=settings.oidc_issuer,
            discovery_url=_discovery_url(settings),
            jwks_url=_jwks_url(settings),
            authorization_url=authorization_endpoint(settings),
            token_url=token_endpoint(settings),
            end_session_url=end_session_endpoint(settings),
            jwks_source=str(
                oidc_readiness_report.get(
                    "jwks_source",
                    "configured" if settings.oidc_jwks_url else "derived_from_issuer",
                )
            ),
            end_session_source=_nested_text(
                federated_logout,
                "end_session_source",
                "configured" if settings.oidc_end_session_url else "derived_from_issuer",
            ),
        ),
        client=OidcClientOnboarding(
            client_id=settings.oidc_client_id,
            auth_flow="authorization_code_pkce",
            redirect_uri=resolved_redirect_uri,
            post_logout_redirect_uri=resolved_post_logout_redirect_uri,
            public_base_url=settings.public_base_url,
            api_base_url=settings.api_base_url,
            scopes=[str(scope) for scope in settings.oidc_scopes],
            session_cookie_secure=settings.oidc_session_cookie_secure,
            confidential_client_configured=bool(settings.oidc_client_secret),
        ),
        claims=OidcClaimOnboarding(
            actor_claim=_nested_text(token_binding, "actor_claim", settings.oidc_actor_claim),
            tenant_claim=_nested_text(token_binding, "tenant_claim", settings.oidc_tenant_claim),
            scope_sources=_scope_sources(settings, token_binding),
        ),
        required_redirect_uris=[resolved_redirect_uri],
        required_post_logout_redirect_uris=[resolved_post_logout_redirect_uri],
        recommended_idp_controls=[
            "Use authorization-code with PKCE S256 for browser sign-in.",
            "Allow only the exact Axis redirect URI values listed in this report.",
            "Allow only the exact Axis post-logout redirect URI values listed in this report.",
            "Issue stable actor and tenant claims that match the Axis claim mapping.",
            "Expose group, role or scope claims through standard OIDC claim locations.",
            "Keep confidential OIDC client material outside the repository.",
            "Rotate confidential OIDC client material operationally.",
            "Use HTTPS for issuer, authorization, token, JWKS and end-session endpoints.",
        ],
        open_action_items=_open_action_items(oidc_readiness_report),
        security_notes=[
            "This report is safe to share with identity administrators.",
            "Axis does not expose provider token material in this report.",
            "Axis browser sessions are represented by HTTP-only API cookies.",
            "For enterprise use, require secure cookies and TLS-only redirect endpoints.",
        ],
    )


def _discovery_url(settings: Settings) -> str:
    return f"{settings.oidc_issuer.rstrip('/')}/.well-known/openid-configuration"


def _jwks_url(settings: Settings) -> str:
    if settings.oidc_jwks_url:
        return settings.oidc_jwks_url
    return f"{settings.oidc_issuer.rstrip('/')}/protocol/openid-connect/certs"


def _nested_text(value: object, key: str, default: str) -> str:
    if isinstance(value, Mapping):
        nested = value.get(key)
        if nested is not None:
            return str(nested)
    return default


def _scope_sources(settings: Settings, token_binding: object) -> list[str]:
    if isinstance(token_binding, Mapping):
        scope_sources = token_binding.get("scope_sources")
        if isinstance(scope_sources, list):
            return [str(source) for source in scope_sources]
    return [
        "scope",
        "scp",
        "realm_access.roles",
        f"resource_access[{settings.oidc_audience}].roles",
    ]


def _open_action_items(oidc_readiness_report: Mapping[str, Any]) -> list[str]:
    checks = oidc_readiness_report.get("checks")
    if not isinstance(checks, list):
        return []

    action_items: list[str] = []
    for check in checks:
        if not isinstance(check, Mapping):
            continue
        if check.get("status") == "ready":
            continue
        check_id = check.get("check_id")
        if check_id is not None:
            action_items.append(str(check_id))
    return action_items
