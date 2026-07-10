from __future__ import annotations

import math
import time
from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from axis_api.config import Settings
from axis_api.errors import AxisErrorCode
from axis_api.oidc_code_flow import (
    OidcCodeFlowConfigurationError,
    OidcCookieValidationError,
    read_session_cookie,
    session_cookie_name,
)
from axis_api.platform_tenants import TenantQuotaKey, TenantStateCache
from axis_api.usage_metering import TenantUsageMetric, UsageAccumulator


@dataclass
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int
    reset_seconds: int


@dataclass
class _RateLimitBucket:
    window_started_at: float
    request_count: int


class InMemoryRateLimiter:
    def __init__(self, *, limit: int, window_seconds: int) -> None:
        self.limit = max(1, limit)
        self.window_seconds = max(1, window_seconds)
        self._buckets: dict[str, _RateLimitBucket] = {}

    def check(
        self,
        key: str,
        *,
        now: float | None = None,
        limit: int | None = None,
    ) -> RateLimitDecision:
        observed_at = now if now is not None else time.monotonic()
        effective_limit = max(1, limit) if limit is not None else self.limit
        bucket = self._buckets.get(key)
        if bucket is None or observed_at - bucket.window_started_at >= self.window_seconds:
            bucket = _RateLimitBucket(window_started_at=observed_at, request_count=0)
            self._buckets[key] = bucket

        elapsed_seconds = max(0.0, observed_at - bucket.window_started_at)
        reset_seconds = max(1, math.ceil(self.window_seconds - elapsed_seconds))
        if bucket.request_count >= effective_limit:
            return RateLimitDecision(
                allowed=False,
                limit=effective_limit,
                remaining=0,
                retry_after_seconds=reset_seconds,
                reset_seconds=reset_seconds,
            )

        bucket.request_count += 1
        remaining = max(0, effective_limit - bucket.request_count)
        return RateLimitDecision(
            allowed=True,
            limit=effective_limit,
            remaining=remaining,
            retry_after_seconds=0,
            reset_seconds=reset_seconds,
        )


class ApiRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings
        self.enabled = settings.api_rate_limit_enabled
        self.protected_paths = set(settings.api_rate_limit_paths)
        self.window_seconds = max(1, settings.api_rate_limit_window_seconds)
        # Usage metering reuses the same verified-cookie tenant resolution and the
        # same protected-path set, but is gated by its own flag so it can run even
        # when rate limiting is disabled (metering is passive accounting).
        self.metering_enabled = settings.usage_metering_enabled
        self.metered_paths = set(settings.api_rate_limit_paths)
        self.limiter = InMemoryRateLimiter(
            limit=settings.api_rate_limit_requests,
            window_seconds=settings.api_rate_limit_window_seconds,
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        should_limit = self._should_limit(request)
        should_meter = self._should_meter(request)
        if not should_limit and not should_meter:
            return await call_next(request)

        # Resolve the tenant once from the verified cookie and share it between
        # metering and rate limiting so the hot path parses the cookie at most once.
        tenant_id = self._session_cookie_tenant(request)
        if should_meter and tenant_id is not None:
            self._record_api_request_usage(request, tenant_id)

        if not should_limit:
            return await call_next(request)

        tenant_limit = self._tenant_request_limit(request, tenant_id)
        if tenant_id is not None and tenant_limit is not None:
            # A per-tenant quota shares one bucket across the tenant's clients.
            decision = self.limiter.check(
                f"tenant:{tenant_id}:{request.method}:{request.url.path}",
                limit=tenant_limit,
            )
            scope = "tenant_quota"
        else:
            decision = self.limiter.check(_rate_limit_key(request))
            scope = "client_endpoint"
        headers = _rate_limit_headers(decision)
        if not decision.allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": {
                        "code": AxisErrorCode.RATE_LIMITED.value,
                        "message": "Too many requests for this endpoint.",
                        "limit": decision.limit,
                        "window_seconds": self.window_seconds,
                        "retry_after_seconds": decision.retry_after_seconds,
                        "scope": scope,
                    }
                },
                headers=headers,
            )

        response = await call_next(request)
        for header, value in headers.items():
            response.headers[header] = value
        return response

    def _should_limit(self, request: Request) -> bool:
        return (
            self.enabled
            and request.method != "OPTIONS"
            and request.url.path in self.protected_paths
        )

    def _should_meter(self, request: Request) -> bool:
        return (
            self.metering_enabled
            and request.method != "OPTIONS"
            and request.url.path in self.metered_paths
        )

    def _record_api_request_usage(self, request: Request, tenant_id: str) -> None:
        accumulator: UsageAccumulator | None = getattr(
            request.app.state, "usage_accumulator", None
        )
        if accumulator is None:
            return
        # In-memory increment only; the ledger write happens on the periodic flush.
        accumulator.record(tenant_id, TenantUsageMetric.API_REQUEST.value)

    def _session_cookie_tenant(self, request: Request) -> str | None:
        """Resolve the tenant from the HMAC-verified session cookie only.

        Bearer requests fall back to the global limit: verifying a JWT inside
        the middleware would duplicate the principal resolver, and an
        unverified tenant claim must never select a higher per-tenant limit.
        """
        session_cookie = request.cookies.get(session_cookie_name(self.settings))
        if not session_cookie:
            return None
        try:
            return read_session_cookie(session_cookie, self.settings).tenant_id
        except (OidcCodeFlowConfigurationError, OidcCookieValidationError):
            return None

    def _tenant_request_limit(self, request: Request, tenant_id: str | None) -> int | None:
        if tenant_id is None:
            return None
        cache: TenantStateCache | None = getattr(
            request.app.state, "tenant_state_cache", None
        )
        session_factory = getattr(request.app.state, "session_factory", None)
        if cache is None or session_factory is None:
            return None
        try:
            snapshot = cache.snapshot(session_factory, tenant_id)
        except SQLAlchemyError:
            # A failed quota lookup falls back to the global limit; the request
            # itself will surface the database failure at the route layer.
            return None
        return snapshot.quotas.get(TenantQuotaKey.API_REQUESTS_PER_WINDOW.value)


def _rate_limit_key(request: Request) -> str:
    client_host = request.client.host if request.client is not None else "unknown"
    return f"{client_host}:{request.method}:{request.url.path}"


def _rate_limit_headers(decision: RateLimitDecision) -> dict[str, str]:
    headers = {
        "X-RateLimit-Limit": str(decision.limit),
        "X-RateLimit-Remaining": str(decision.remaining),
        "X-RateLimit-Reset": str(decision.reset_seconds),
    }
    if not decision.allowed:
        headers["Retry-After"] = str(decision.retry_after_seconds)
    return headers
