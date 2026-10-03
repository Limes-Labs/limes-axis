"""Explicitly enabled public context; no ontology ingestion or execution authority."""

from collections.abc import Callable
from dataclasses import dataclass
from time import time
from typing import Annotated
from urllib.parse import urlsplit

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from axis_api.db import session_scope
from axis_api.identity import OidcPrincipal
from axis_api.permissions import ScopeAuthorizationError, authorize_principal_scopes
from axis_api.persistence import AxisPersistenceRepository
from axis_api.tenant_admission import tenant_admission_denial_reason

READ_SCOPE = "institutional:context:read"


@dataclass(frozen=True)
class PublicContextConfig:
    """Operator-owned policy; absent configuration registers no endpoint.

    This separate capability gate is not the connector ingestion egress policy.
    Tenant and origin approval are local; neither goes to GovCore.
    """

    base_url: str
    approved_origins: frozenset[str]
    allowed_tenants: frozenset[str]
    enabled: bool = False
    transport: httpx.BaseTransport | None = None  # isolated acceptance tests only

    def __post_init__(self) -> None:
        url = urlsplit(self.base_url)
        if (
            url.scheme not in {"https", "http"}
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in {"", "/"}
            or (url.scheme == "http" and url.hostname not in {"127.0.0.1", "::1", "localhost"})
            or self.base_url.rstrip("/") not in self.approved_origins
        ):
            raise ValueError("A fixed approved GovCore origin is required")
        if (
            not isinstance(self.approved_origins, frozenset)
            or not isinstance(self.allowed_tenants, frozenset)
            or any(
                not isinstance(value, str) or not value.strip() for value in self.allowed_tenants
            )
        ):
            raise ValueError("Immutable explicit capability allowlists are required")
        if not isinstance(self.enabled, bool):
            raise ValueError("Explicit boolean capability configuration is required")


def register_public_context(
    app: FastAPI,
    config: PublicContextConfig,
    *,
    principal_dependency: Callable,
    refresh_principal: Callable[[Request], OidcPrincipal | None],
) -> None:
    # Import only upon opt-in; the default API has no SDK dependency.
    from govcore_client import (
        AxisPublicContextReader,
        GovCoreClient,
        GovCoreContractError,
        GovCoreUnavailable,
    )

    app.state.public_context_config = config

    def current_authorization(request: Request, tenant: str, entity_id: str) -> bool:
        current = request.app.state.public_context_config
        if (
            not isinstance(current, PublicContextConfig)
            or not current.enabled
            or tenant not in current.allowed_tenants
            or current.base_url.rstrip("/") not in current.approved_origins
            or current.base_url != config.base_url
        ):
            raise HTTPException(403, detail={"reason": "public_context_policy_denied"})
        principal = refresh_principal(request)
        if principal is None or (
            principal.expires_at is not None and principal.expires_at <= time()
        ):
            raise HTTPException(401, detail={"reason": "current_identity_required"})
        try:
            authorize_principal_scopes(
                tenant_id=tenant,
                principal=principal,
                required_scopes=[READ_SCOPE],
                attributes={"surface": "public_institutional", "resource": entity_id},
                message="Institutional context read denied",
            )
            # Fresh lifecycle state, bypassing the ordinary request-path TTL.
            # The short transaction is closed before and after remote I/O.
            with session_scope(request.app.state.session_factory) as session:
                row = AxisPersistenceRepository(session).get_tenant(tenant)
                reason = tenant_admission_denial_reason(
                    row.status if row is not None else None,
                    admission_mode="registered_only",
                )
        except ScopeAuthorizationError as exc:
            raise HTTPException(403, detail={"reason": exc.decision.reason}) from exc
        except SQLAlchemyError as exc:
            raise HTTPException(503, detail={"reason": "tenant_state_unavailable"}) from exc
        if reason:
            raise HTTPException(403, detail={"reason": reason})
        return True

    @app.get(
        "/institutional-context/entities/{gov_entity_id}",
        tags=["institutional-context"],
        responses={
            401: {"description": "Current authenticated principal required"},
            403: {"description": "Read permission, tenant or capability policy denied"},
            422: {"description": "Canonical public entity ID required"},
            503: {"description": "Public context or admission state unavailable"},
        },
    )
    def public_entity_context(
        request: Request,
        gov_entity_id: str,
        principal: Annotated[OidcPrincipal | None, Depends(principal_dependency)],
    ) -> JSONResponse:
        if principal is None:
            raise HTTPException(401, detail={"reason": "authenticated_identity_required"})
        # Neither browser credentials nor any tenant/actor fields enter this client.
        try:
            with GovCoreClient(config.base_url, transport=config.transport) as client:
                reader = AxisPublicContextReader(
                    client,
                    authorize=lambda tenant, entity: current_authorization(request, tenant, entity),
                )
                context = reader.get_entity_context(principal.tenant_id, gov_entity_id)
        except GovCoreUnavailable as exc:
            raise HTTPException(503, detail={"reason": "public_context_unavailable"}) from exc
        except GovCoreContractError as exc:
            raise HTTPException(503, detail={"reason": "public_context_contract_invalid"}) from exc
        except ValueError as exc:
            raise HTTPException(422, detail={"reason": "invalid_public_entity_id"}) from exc
        return JSONResponse(
            {"namespace": context.namespace, "entity": context.entity},
            headers={"Cache-Control": "no-store"},
        )
