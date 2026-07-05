import pytest

from axis_sdk.exceptions import (
    ActionRequiresApprovalError,
    AuthRequiredError,
    AxisAPIError,
    ConflictError,
    ConnectorUnavailableError,
    ModelProviderBlockedError,
    NotFoundError,
    PermissionDeniedError,
    PolicyViolationError,
    RateLimitedError,
    ReplayNotAvailableError,
    ServerError,
    TenantScopeRequiredError,
    ValidationFailedError,
    WorkflowNotFoundError,
    error_from_response,
)

CODE_CASES = [
    ("AUTH_REQUIRED", 401, AuthRequiredError),
    ("PERMISSION_DENIED", 403, PermissionDeniedError),
    ("TENANT_SCOPE_REQUIRED", 403, TenantScopeRequiredError),
    ("NOT_FOUND", 404, NotFoundError),
    ("WORKFLOW_NOT_FOUND", 404, WorkflowNotFoundError),
    ("CONFLICT", 409, ConflictError),
    ("VALIDATION_FAILED", 422, ValidationFailedError),
    ("ACTION_REQUIRES_APPROVAL", 409, ActionRequiresApprovalError),
    ("POLICY_VIOLATION", 409, PolicyViolationError),
    ("CONNECTOR_UNAVAILABLE", 503, ConnectorUnavailableError),
    ("MODEL_PROVIDER_BLOCKED", 403, ModelProviderBlockedError),
    ("REPLAY_NOT_AVAILABLE", 409, ReplayNotAvailableError),
    ("RATE_LIMITED", 429, RateLimitedError),
]


@pytest.mark.parametrize(("code", "status_code", "error_cls"), CODE_CASES)
def test_error_code_maps_to_typed_exception(
    code: str, status_code: int, error_cls: type[AxisAPIError]
) -> None:
    error = error_from_response(
        status_code=status_code,
        body={"detail": {"code": code, "message": "synthetic", "reason": "test"}},
        request_id="req_client",
    )
    assert type(error) is error_cls
    assert error.code == code
    assert error.message == "synthetic"
    assert error.status_code == status_code
    assert error.request_id == "req_client"
    assert error.detail == {"detail": {"code": code, "message": "synthetic", "reason": "test"}}


def test_workflow_not_found_is_a_not_found_error() -> None:
    error = error_from_response(
        status_code=404,
        body={"detail": {"code": "WORKFLOW_NOT_FOUND", "message": "missing"}},
        request_id=None,
    )
    assert isinstance(error, NotFoundError)


def test_plain_string_detail_falls_back_to_status_mapping() -> None:
    error = error_from_response(
        status_code=404,
        body={"detail": "Approval not found"},
        request_id="req_client",
    )
    assert type(error) is NotFoundError
    assert error.code is None
    assert error.message == "Approval not found"


def test_fastapi_validation_list_detail_maps_to_validation_failed() -> None:
    body = {"detail": [{"loc": ["body", "decision"], "msg": "invalid", "type": "enum"}]}
    error = error_from_response(status_code=422, body=body, request_id=None)
    assert type(error) is ValidationFailedError
    assert error.detail == body


def test_error_envelope_shape_is_supported() -> None:
    error = error_from_response(
        status_code=403,
        body={
            "error": {
                "code": "PERMISSION_DENIED",
                "message": "The actor cannot perform this action.",
                "request_id": "req_server",
            }
        },
        request_id="req_client",
    )
    assert type(error) is PermissionDeniedError
    assert error.request_id == "req_server"


def test_body_request_id_takes_precedence_over_client_request_id() -> None:
    error = error_from_response(
        status_code=401,
        body={"detail": {"code": "AUTH_REQUIRED", "message": "m", "request_id": "req_server"}},
        request_id="req_client",
    )
    assert error.request_id == "req_server"


def test_unknown_5xx_maps_to_server_error() -> None:
    error = error_from_response(status_code=500, body={"detail": "boom"}, request_id="req_x")
    assert type(error) is ServerError
    assert error.request_id == "req_x"


def test_unknown_4xx_maps_to_generic_api_error() -> None:
    error = error_from_response(status_code=418, body={"unexpected": True}, request_id=None)
    assert type(error) is AxisAPIError
    assert error.message == "The Axis API returned HTTP 418."


def test_rate_limited_error_carries_retry_after() -> None:
    error = error_from_response(
        status_code=429,
        body={"detail": {"code": "RATE_LIMITED", "message": "Too many requests."}},
        request_id=None,
        retry_after_seconds=17,
    )
    assert isinstance(error, RateLimitedError)
    assert error.retry_after_seconds == 17
