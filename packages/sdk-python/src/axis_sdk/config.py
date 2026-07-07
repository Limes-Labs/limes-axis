"""Client configuration for the Limes Axis SDK.

The SDK only talks to the configured ``base_url``. It performs no other
network egress and sends no telemetry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from axis_sdk._version import USER_AGENT

TokenProvider = Callable[[], str]

#: HTTP status codes that are considered transient and safe to retry for
#: idempotent requests. 4xx responses are never retried.
DEFAULT_RETRY_STATUSES = frozenset({502, 503, 504})


@dataclass(frozen=True)
class RetryConfig:
    """Conservative retry policy for idempotent requests.

    Retries apply only to GET requests and to POST requests that carry an
    idempotency key. Transport errors and the configured 5xx statuses are
    retried with exponential backoff and full jitter. 4xx responses are
    never retried. Set ``max_retries=0`` (or ``enabled=False``) to disable.
    """

    enabled: bool = True
    max_retries: int = 2
    backoff_initial_seconds: float = 0.25
    backoff_max_seconds: float = 4.0
    retry_statuses: frozenset[int] = DEFAULT_RETRY_STATUSES

    def __post_init__(self) -> None:
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if self.backoff_initial_seconds < 0 or self.backoff_max_seconds < 0:
            raise ValueError("backoff durations must be >= 0")

    @property
    def effective_max_retries(self) -> int:
        return self.max_retries if self.enabled else 0

    def backoff_seconds(self, attempt: int, *, jitter: float) -> float:
        """Full-jitter exponential backoff delay for a retry ``attempt`` (0-based)."""
        ceiling = min(self.backoff_max_seconds, self.backoff_initial_seconds * (2**attempt))
        return ceiling * jitter


@dataclass(frozen=True)
class AxisClientConfig:
    """Configuration shared by the sync and async clients.

    - ``base_url``: root URL of the Axis API, e.g. ``http://127.0.0.1:8000``.
    - ``token``: static bearer token, or ``token_provider`` for a callable
      that returns a fresh token per request. At most one may be set.
    - ``tenant_id``: default tenant context injected as the ``tenant_id``
      query parameter on tenant-scoped endpoints; per-call overrides win.
    - ``timeout_seconds``: request timeout applied to the httpx client.
    - ``user_agent``: sent on every request; defaults to the SDK identity.
    """

    base_url: str
    token: str | None = None
    token_provider: TokenProvider | None = None
    tenant_id: str | None = None
    timeout_seconds: float = 30.0
    user_agent: str = USER_AGENT
    retry: RetryConfig = field(default_factory=RetryConfig)

    def __post_init__(self) -> None:
        if not self.base_url:
            raise ValueError("base_url is required")
        if self.token is not None and self.token_provider is not None:
            raise ValueError("Set either token or token_provider, not both")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")

    def resolve_token(self) -> str | None:
        if self.token_provider is not None:
            return self.token_provider()
        return self.token
