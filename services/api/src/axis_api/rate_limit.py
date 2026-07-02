from __future__ import annotations

import math
import time
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from axis_api.config import Settings
from axis_api.errors import AxisErrorCode


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

    def check(self, key: str, *, now: float | None = None) -> RateLimitDecision:
        observed_at = now if now is not None else time.monotonic()
        bucket = self._buckets.get(key)
        if bucket is None or observed_at - bucket.window_started_at >= self.window_seconds:
            bucket = _RateLimitBucket(window_started_at=observed_at, request_count=0)
            self._buckets[key] = bucket

        elapsed_seconds = max(0.0, observed_at - bucket.window_started_at)
        reset_seconds = max(1, math.ceil(self.window_seconds - elapsed_seconds))
        if bucket.request_count >= self.limit:
            return RateLimitDecision(
                allowed=False,
                limit=self.limit,
                remaining=0,
                retry_after_seconds=reset_seconds,
                reset_seconds=reset_seconds,
            )

        bucket.request_count += 1
        remaining = max(0, self.limit - bucket.request_count)
        return RateLimitDecision(
            allowed=True,
            limit=self.limit,
            remaining=remaining,
            retry_after_seconds=0,
            reset_seconds=reset_seconds,
        )


class ApiRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        super().__init__(app)
        self.enabled = settings.api_rate_limit_enabled
        self.protected_paths = set(settings.api_rate_limit_paths)
        self.window_seconds = max(1, settings.api_rate_limit_window_seconds)
        self.limiter = InMemoryRateLimiter(
            limit=settings.api_rate_limit_requests,
            window_seconds=settings.api_rate_limit_window_seconds,
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self._should_limit(request):
            return await call_next(request)

        decision = self.limiter.check(_rate_limit_key(request))
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
                        "scope": "client_endpoint",
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
