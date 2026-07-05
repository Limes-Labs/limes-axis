"""Shared request core for the sync and async clients.

Both client variants share this module for request construction, retry
decisions and response handling so their behavior cannot diverge. Only the
I/O execution differs and lives in ``client.py``.
"""

from __future__ import annotations

import math
import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from axis_sdk.config import AxisClientConfig, RetryConfig
from axis_sdk.exceptions import MalformedResponseError, error_from_response

REQUEST_ID_HEADER = "X-Request-Id"


@dataclass(frozen=True)
class RequestSpec:
    """A fully described API request, independent of the httpx client."""

    method: str
    path: str
    params: dict[str, Any] = field(default_factory=dict)
    json_body: dict[str, Any] | None = None
    #: Whether the request is tenant-scoped and accepts a ``tenant_id``
    #: query parameter that the client may default from its configuration.
    tenant_scoped: bool = False
    #: Whether the request is safe to retry. GETs are idempotent; POSTs are
    #: only marked idempotent when they carry an idempotency key.
    idempotent: bool = False


def new_request_id() -> str:
    return f"req_{uuid.uuid4().hex}"


def build_headers(config: AxisClientConfig, request_id: str) -> dict[str, str]:
    headers = {
        "User-Agent": config.user_agent,
        REQUEST_ID_HEADER: request_id,
    }
    token = config.resolve_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def resolve_params(spec: RequestSpec, config: AxisClientConfig) -> dict[str, Any]:
    params = {key: value for key, value in spec.params.items() if value is not None}
    if spec.tenant_scoped and "tenant_id" not in params and config.tenant_id is not None:
        params["tenant_id"] = config.tenant_id
    return params


def should_retry_response(
    spec: RequestSpec,
    response: httpx.Response,
    retry: RetryConfig,
    attempt: int,
) -> bool:
    return (
        spec.idempotent
        and attempt < retry.effective_max_retries
        and response.status_code in retry.retry_statuses
    )


def should_retry_error(spec: RequestSpec, retry: RetryConfig, attempt: int) -> bool:
    return spec.idempotent and attempt < retry.effective_max_retries


def backoff_delay(retry: RetryConfig, attempt: int) -> float:
    return retry.backoff_seconds(attempt, jitter=random.random())  # noqa: S311


def retry_after_seconds(response: httpx.Response) -> int | None:
    """Parse a Retry-After header: integer seconds or an HTTP-date."""
    value = response.headers.get("Retry-After")
    if value is None or not value.strip():
        return None
    value = value.strip()
    try:
        return max(0, int(value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0, math.ceil((when - datetime.now(UTC)).total_seconds()))


def response_retry_delay(retry: RetryConfig, attempt: int, response: httpx.Response) -> float:
    """Delay before retrying a retryable response.

    Honours a Retry-After header when present: the SDK waits at least that
    long (never less than the computed backoff), capped by the configured
    maximum backoff. Without a parseable header it falls back to backoff.
    """
    delay = backoff_delay(retry, attempt)
    retry_after = retry_after_seconds(response)
    if retry_after is not None:
        delay = min(max(float(retry_after), delay), retry.backoff_max_seconds)
    return delay


def handle_response(response: httpx.Response, request_id: str) -> Any:
    """Return the decoded JSON body or raise the mapped typed error."""
    if response.is_success:
        if not response.content:
            raise MalformedResponseError(
                "The Axis API returned an empty success response body.",
                status_code=response.status_code,
                request_id=request_id,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise MalformedResponseError(
                f"The Axis API returned a success response that is not JSON: {exc}",
                status_code=response.status_code,
                request_id=request_id,
            ) from exc

    try:
        body = response.json()
    except ValueError:
        body = {"detail": response.text}
    raise error_from_response(
        status_code=response.status_code,
        body=body,
        request_id=request_id,
        retry_after_seconds=retry_after_seconds(response),
    )


def parse_model[ModelT: BaseModel](data: Any, model_type: type[ModelT]) -> ModelT:
    try:
        return model_type.model_validate(data)
    except ValidationError as exc:
        raise MalformedResponseError(
            f"The Axis API response does not match the {model_type.__name__} schema: {exc}"
        ) from exc
