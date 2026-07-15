from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import time
from dataclasses import dataclass
from typing import Protocol

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from axis_api.config import Settings
from axis_api.errors import AxisErrorCode
from axis_api.identity import OidcAuthenticationError, OidcPrincipal
from axis_api.oidc_code_flow import (
    OidcCodeFlowConfigurationError,
    OidcCookieValidationError,
    read_session_cookie,
    session_cookie_name,
)
from axis_api.platform_tenants import TenantQuotaKey, TenantStateCache
from axis_api.usage_metering import (
    TenantUsageMetric,
    UsageAccumulator,
    UsageRecordResult,
)

_LOGGER = logging.getLogger(__name__)

_METERING_EXCLUDED_PATHS = {
    "/health",
    "/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/identity/oidc/authorize",
    "/identity/oidc/callback",
}


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


class RateLimitBackendError(RuntimeError):
    pass


class RateLimitBackend(Protocol):
    async def check(self, key: str, *, limit: int) -> RateLimitDecision: ...

    async def close(self) -> None: ...


class InMemoryRateLimiter:
    def __init__(self, *, limit: int, window_seconds: int) -> None:
        self.limit = max(1, limit)
        self.window_seconds = max(1, window_seconds)
        self._buckets: dict[str, _RateLimitBucket] = {}
        self._lock = asyncio.Lock()
        self._checks = 0

    async def check(
        self,
        key: str,
        *,
        limit: int,
        now: float | None = None,
    ) -> RateLimitDecision:
        async with self._lock:
            return self._check_locked(key, limit=limit, now=now)

    def _check_locked(
        self,
        key: str,
        *,
        limit: int,
        now: float | None,
    ) -> RateLimitDecision:
        observed_at = now if now is not None else time.monotonic()
        effective_limit = max(1, limit)
        self._checks += 1
        if self._checks % 256 == 0:
            self._buckets = {
                bucket_key: candidate
                for bucket_key, candidate in self._buckets.items()
                if observed_at - candidate.window_started_at < self.window_seconds
            }
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

    async def close(self) -> None:
        return None


_REDIS_FIXED_WINDOW_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('PEXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('PTTL', KEYS[1])
return {current, ttl}
"""


class RedisRateLimiter:
    """Atomic fixed-window limiter shared by every API replica."""

    def __init__(self, client: Redis, *, window_seconds: int) -> None:
        self._client = client
        self.window_seconds = max(1, window_seconds)

    async def check(self, key: str, *, limit: int) -> RateLimitDecision:
        effective_limit = max(1, limit)
        redis_key = f"axis:rate-limit:v1:{hashlib.sha256(key.encode()).hexdigest()}"
        try:
            result = await self._client.eval(
                _REDIS_FIXED_WINDOW_SCRIPT,
                1,
                redis_key,
                self.window_seconds * 1000,
            )
            request_count, ttl_ms = int(result[0]), max(1, int(result[1]))
        except (RedisError, OSError, TypeError, ValueError) as exc:
            raise RateLimitBackendError("redis_rate_limit_unavailable") from exc

        reset_seconds = max(1, math.ceil(ttl_ms / 1000))
        allowed = request_count <= effective_limit
        return RateLimitDecision(
            allowed=allowed,
            limit=effective_limit,
            remaining=max(0, effective_limit - request_count),
            retry_after_seconds=0 if allowed else reset_seconds,
            reset_seconds=reset_seconds,
        )

    async def close(self) -> None:
        await self._client.aclose()


def build_rate_limit_backend(settings: Settings) -> RateLimitBackend:
    if settings.api_rate_limit_backend == "redis":
        if not settings.redis_url:
            raise RateLimitBackendError("redis_url_missing")
        client = Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=settings.redis_timeout_seconds,
            socket_timeout=settings.redis_timeout_seconds,
            retry_on_timeout=False,
            decode_responses=False,
        )
        return RedisRateLimiter(
            client,
            window_seconds=settings.api_rate_limit_window_seconds,
        )
    return InMemoryRateLimiter(
        limit=settings.api_rate_limit_requests,
        window_seconds=settings.api_rate_limit_window_seconds,
    )


class ApiRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        *,
        settings: Settings,
        backend: RateLimitBackend,
    ) -> None:
        super().__init__(app)
        self.settings = settings
        self.enabled = settings.api_rate_limit_enabled
        self.protected_paths = set(settings.api_rate_limit_paths)
        self.window_seconds = max(1, settings.api_rate_limit_window_seconds)
        # Metering is independent from the limiter path allowlist. It observes
        # authenticated application traffic after the shared principal dependency
        # has verified cookie or bearer credentials.
        self.metering_enabled = settings.usage_metering_enabled
        self.failure_mode = settings.api_rate_limit_failure_mode
        self.limiter = backend

    async def dispatch(self, request: Request, call_next) -> Response:
        should_limit = self._should_limit(request)
        should_meter = self._should_meter(request)
        if not should_limit and not should_meter:
            return await call_next(request)

        if not should_limit:
            response = await call_next(request)
            self._record_verified_request_usage(request)
            return response

        tenant_id = self._verified_tenant(request)

        tenant_limit = self._tenant_request_limit(request, tenant_id)
        if tenant_id is not None and tenant_limit is not None:
            # A per-tenant quota shares one bucket across the tenant's clients.
            key = f"tenant:{tenant_id}:{request.method}:{request.url.path}"
            effective_limit = tenant_limit
            scope = "tenant_quota"
        else:
            key = _rate_limit_key(request)
            effective_limit = self.settings.api_rate_limit_requests
            scope = "client_endpoint"
        try:
            decision = await self.limiter.check(key, limit=effective_limit)
        except RateLimitBackendError:
            _LOGGER.error("Rate limit backend unavailable", exc_info=True)
            if self.failure_mode == "open":
                response = await call_next(request)
                if should_meter:
                    self._record_verified_request_usage(request)
                return response
            return JSONResponse(
                status_code=503,
                content={
                    "detail": {
                        "code": AxisErrorCode.CONTROL_PLANE_UNAVAILABLE.value,
                        "message": "Request admission control is temporarily unavailable.",
                        "reason": "rate_limit_backend_unavailable",
                    }
                },
            )
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
        if should_meter:
            self._record_verified_request_usage(request)
        for header, value in headers.items():
            response.headers[header] = value
        return response

    def _should_limit(self, request: Request) -> bool:
        return (
            self.enabled
            and request.method != "OPTIONS"
            and (
                "*" in self.protected_paths
                or request.url.path in self.protected_paths
            )
        )

    def _should_meter(self, request: Request) -> bool:
        return (
            self.metering_enabled
            and request.method != "OPTIONS"
            and request.url.path not in _METERING_EXCLUDED_PATHS
        )

    def _record_verified_request_usage(self, request: Request) -> None:
        principal = getattr(request.state, "axis_principal", None)
        if not isinstance(principal, OidcPrincipal):
            return
        accumulator: UsageAccumulator | None = getattr(
            request.app.state, "usage_accumulator", None
        )
        if accumulator is None:
            return
        result = accumulator.record(
            principal.tenant_id,
            TenantUsageMetric.API_REQUEST.value,
        )
        if result is UsageRecordResult.OVERFLOW:
            _LOGGER.error(
                "Usage metering accumulator overflowed",
                extra={"metric": TenantUsageMetric.API_REQUEST.value},
            )

    def _verified_tenant(self, request: Request) -> str | None:
        """Resolve a tenant only from a verified browser session or bearer token."""

        authorization = request.headers.get("Authorization")
        if authorization:
            verifier = getattr(request.app.state, "identity_verifier", None)
            if verifier is None:
                return None
            try:
                principal = verifier.verify_authorization_header(authorization)
            except OidcAuthenticationError:
                # The route dependency returns the canonical structured 401.
                return None
            request.state.axis_principal = principal
            return principal.tenant_id

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
