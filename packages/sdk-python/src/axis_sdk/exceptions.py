"""Typed exception hierarchy for the Limes Axis API error envelope.

The API reports errors as ``{"detail": {"code": ..., "message": ..., ...}}``
(or a plain-string / validation-list ``detail``), where ``code`` is one of
the ``AxisErrorCode`` values defined by the API service. The SDK maps each
code to a dedicated exception class and preserves ``code``, ``message``,
``request_id`` and the raw payload.
"""

from __future__ import annotations

from typing import Any


class AxisError(Exception):
    """Base class for all SDK errors."""


class AxisConnectionError(AxisError):
    """The API could not be reached (network or transport failure)."""

    def __init__(self, message: str, *, request_id: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.request_id = request_id


class AxisAPIError(AxisError):
    """An HTTP error response from the Axis API."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: str | None = None,
        request_id: str | None = None,
        detail: Any = None,
    ) -> None:
        super().__init__(f"[{status_code}{f' {code}' if code else ''}] {message}")
        self.message = message
        self.status_code = status_code
        self.code = code
        self.request_id = request_id
        self.detail = detail


class AuthRequiredError(AxisAPIError):
    """AUTH_REQUIRED: a valid OIDC bearer token is required."""


class PermissionDeniedError(AxisAPIError):
    """PERMISSION_DENIED: the actor lacks the required scope or tenant access."""


class TenantScopeRequiredError(AxisAPIError):
    """TENANT_SCOPE_REQUIRED: the request must carry an explicit tenant scope."""


class NotFoundError(AxisAPIError):
    """NOT_FOUND: the requested resource does not exist."""


class WorkflowNotFoundError(NotFoundError):
    """WORKFLOW_NOT_FOUND: the referenced workflow run does not exist."""


class ConflictError(AxisAPIError):
    """CONFLICT: the request conflicts with existing state."""


class ValidationFailedError(AxisAPIError):
    """VALIDATION_FAILED: the request payload failed typed validation."""


class ActionRequiresApprovalError(AxisAPIError):
    """ACTION_REQUIRES_APPROVAL: the action run needs an approval decision first."""


class PolicyViolationError(AxisAPIError):
    """POLICY_VIOLATION: the request violates a governance policy (e.g. idempotency)."""


class ConnectorUnavailableError(AxisAPIError):
    """CONNECTOR_UNAVAILABLE: the connector runtime cannot serve the request."""


class ModelProviderBlockedError(AxisAPIError):
    """MODEL_PROVIDER_BLOCKED: the model provider is blocked by egress policy."""


class ReplayNotAvailableError(AxisAPIError):
    """REPLAY_NOT_AVAILABLE: deterministic replay is not available for this run."""


class RateLimitedError(AxisAPIError):
    """RATE_LIMITED: too many requests; honour Retry-After before retrying."""

    def __init__(self, *args: Any, retry_after_seconds: int | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.retry_after_seconds = retry_after_seconds


class ServerError(AxisAPIError):
    """An unexpected 5xx response from the API."""


_CODE_TO_ERROR: dict[str, type[AxisAPIError]] = {
    "AUTH_REQUIRED": AuthRequiredError,
    "PERMISSION_DENIED": PermissionDeniedError,
    "TENANT_SCOPE_REQUIRED": TenantScopeRequiredError,
    "NOT_FOUND": NotFoundError,
    "WORKFLOW_NOT_FOUND": WorkflowNotFoundError,
    "CONFLICT": ConflictError,
    "VALIDATION_FAILED": ValidationFailedError,
    "ACTION_REQUIRES_APPROVAL": ActionRequiresApprovalError,
    "POLICY_VIOLATION": PolicyViolationError,
    "CONNECTOR_UNAVAILABLE": ConnectorUnavailableError,
    "MODEL_PROVIDER_BLOCKED": ModelProviderBlockedError,
    "REPLAY_NOT_AVAILABLE": ReplayNotAvailableError,
    "RATE_LIMITED": RateLimitedError,
}

_STATUS_TO_ERROR: dict[int, type[AxisAPIError]] = {
    401: AuthRequiredError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    422: ValidationFailedError,
    429: RateLimitedError,
}


def _parse_error_body(body: Any) -> tuple[str | None, str | None, str | None]:
    """Extract (code, message, request_id) from a JSON error body."""
    if not isinstance(body, dict):
        return None, None, None

    envelope = body.get("error")
    if isinstance(envelope, dict):
        return (
            envelope.get("code"),
            envelope.get("message"),
            envelope.get("request_id"),
        )

    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("code"), detail.get("message"), detail.get("request_id")
    if isinstance(detail, str):
        return None, detail, None
    if isinstance(detail, list):
        # FastAPI request validation errors.
        return "VALIDATION_FAILED", "The request failed validation.", None
    return None, None, None


def error_from_response(
    *,
    status_code: int,
    body: Any,
    request_id: str | None,
    retry_after_seconds: int | None = None,
) -> AxisAPIError:
    """Build the typed exception for an HTTP error response.

    ``request_id`` is the client-generated request id sent with the request;
    a ``request_id`` reported by the API error envelope takes precedence.
    """
    code, message, body_request_id = _parse_error_body(body)
    if message is None:
        message = f"The Axis API returned HTTP {status_code}."

    error_cls: type[AxisAPIError] | None = None
    if code is not None:
        error_cls = _CODE_TO_ERROR.get(code)
    if error_cls is None:
        error_cls = _STATUS_TO_ERROR.get(status_code)
    if error_cls is None:
        error_cls = ServerError if status_code >= 500 else AxisAPIError

    kwargs: dict[str, Any] = {
        "status_code": status_code,
        "code": code,
        "request_id": body_request_id or request_id,
        "detail": body,
    }
    if error_cls is RateLimitedError:
        kwargs["retry_after_seconds"] = retry_after_seconds
    return error_cls(message, **kwargs)
