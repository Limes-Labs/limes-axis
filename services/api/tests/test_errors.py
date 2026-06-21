from axis_api.errors import AxisErrorCode, error_response


def test_error_response_shape() -> None:
    payload = error_response(
        code=AxisErrorCode.PERMISSION_DENIED,
        message="The actor cannot perform this action.",
        request_id="req_123",
    )
    assert payload == {
        "error": {
            "code": "PERMISSION_DENIED",
            "message": "The actor cannot perform this action.",
            "request_id": "req_123",
        }
    }
