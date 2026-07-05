"""Unit tests for the shared transport core: Retry-After parsing, pacing
and malformed success-response wrapping."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from axis_sdk import AxisError, MalformedResponseError, RetryConfig
from axis_sdk._transport import (
    handle_response,
    parse_model,
    response_retry_delay,
    retry_after_seconds,
)
from axis_sdk.models import HealthStatus

ZERO_BACKOFF = RetryConfig(backoff_initial_seconds=0.0, backoff_max_seconds=4.0)


def response_with_retry_after(value: str | None) -> httpx.Response:
    headers = {} if value is None else {"Retry-After": value}
    return httpx.Response(503, headers=headers)


def test_retry_after_parses_integer_seconds() -> None:
    assert retry_after_seconds(response_with_retry_after("7")) == 7


def test_retry_after_clamps_negative_seconds_to_zero() -> None:
    assert retry_after_seconds(response_with_retry_after("-5")) == 0


def test_retry_after_parses_http_date() -> None:
    when = datetime.now(UTC) + timedelta(seconds=30)
    parsed = retry_after_seconds(response_with_retry_after(format_datetime(when)))
    assert parsed is not None
    assert 28 <= parsed <= 31


def test_retry_after_http_date_in_the_past_is_zero() -> None:
    when = datetime.now(UTC) - timedelta(seconds=60)
    assert retry_after_seconds(response_with_retry_after(format_datetime(when))) == 0


@pytest.mark.parametrize("value", [None, "", "   ", "not-a-date"])
def test_retry_after_missing_or_unparseable_is_none(value: str | None) -> None:
    assert retry_after_seconds(response_with_retry_after(value)) is None


def test_response_retry_delay_honours_retry_after_over_backoff() -> None:
    delay = response_retry_delay(ZERO_BACKOFF, 0, response_with_retry_after("2"))
    assert delay == 2.0


def test_response_retry_delay_is_capped_by_max_backoff() -> None:
    delay = response_retry_delay(ZERO_BACKOFF, 0, response_with_retry_after("100"))
    assert delay == ZERO_BACKOFF.backoff_max_seconds


def test_response_retry_delay_falls_back_to_backoff_without_header() -> None:
    delay = response_retry_delay(ZERO_BACKOFF, 0, response_with_retry_after(None))
    assert delay == 0.0


def test_response_retry_delay_falls_back_to_backoff_on_unparseable_header() -> None:
    delay = response_retry_delay(ZERO_BACKOFF, 0, response_with_retry_after("garbage"))
    assert delay == 0.0


def test_empty_success_body_raises_malformed_response_error() -> None:
    response = httpx.Response(200, content=b"")
    with pytest.raises(MalformedResponseError) as excinfo:
        handle_response(response, "req_test")

    assert isinstance(excinfo.value, AxisError)
    assert excinfo.value.status_code == 200
    assert excinfo.value.request_id == "req_test"


def test_non_json_success_body_raises_malformed_response_error() -> None:
    response = httpx.Response(200, text="<html>upstream proxy page</html>")
    with pytest.raises(MalformedResponseError) as excinfo:
        handle_response(response, "req_test")

    assert excinfo.value.status_code == 200
    assert excinfo.value.request_id == "req_test"


class GarbageTransport(httpx.BaseTransport):
    """Always returns a 200 response that is not JSON."""

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json", request=request)


def test_client_wraps_malformed_success_response() -> None:
    from axis_sdk import AxisClient

    with (
        AxisClient("http://axis-api.test", transport=GarbageTransport()) as client,
        pytest.raises(MalformedResponseError),
    ):
        client.system.health()


def test_schema_mismatch_raises_malformed_response_error() -> None:
    with pytest.raises(MalformedResponseError) as excinfo:
        parse_model({"unexpected": "shape"}, HealthStatus)

    assert isinstance(excinfo.value, AxisError)
    assert "HealthStatus" in excinfo.value.message
