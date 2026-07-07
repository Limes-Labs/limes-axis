import pytest

from axis_sdk import USER_AGENT, AxisClientConfig, RetryConfig
from axis_sdk._version import SDK_VERSION


def test_config_requires_base_url() -> None:
    with pytest.raises(ValueError, match="base_url"):
        AxisClientConfig(base_url="")


def test_config_rejects_token_and_token_provider_together() -> None:
    with pytest.raises(ValueError, match="token_provider"):
        AxisClientConfig(
            base_url="http://axis.local",
            token="static",
            token_provider=lambda: "dynamic",
        )


def test_config_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        AxisClientConfig(base_url="http://axis.local", timeout_seconds=0)


def test_config_resolves_static_token() -> None:
    config = AxisClientConfig(base_url="http://axis.local", token="static-token")
    assert config.resolve_token() == "static-token"


def test_config_resolves_token_provider_per_call() -> None:
    tokens = iter(["first", "second"])
    config = AxisClientConfig(base_url="http://axis.local", token_provider=lambda: next(tokens))
    assert config.resolve_token() == "first"
    assert config.resolve_token() == "second"


def test_config_defaults_to_no_token_and_sdk_user_agent() -> None:
    config = AxisClientConfig(base_url="http://axis.local")
    assert config.resolve_token() is None
    assert config.user_agent == USER_AGENT
    assert SDK_VERSION in config.user_agent


def test_retry_config_rejects_negative_retries() -> None:
    with pytest.raises(ValueError, match="max_retries"):
        RetryConfig(max_retries=-1)


def test_retry_config_disabled_means_zero_retries() -> None:
    retry = RetryConfig(enabled=False, max_retries=5)
    assert retry.effective_max_retries == 0


def test_retry_backoff_is_capped_and_jittered() -> None:
    retry = RetryConfig(backoff_initial_seconds=1.0, backoff_max_seconds=2.0)
    assert retry.backoff_seconds(0, jitter=1.0) == 1.0
    assert retry.backoff_seconds(5, jitter=1.0) == 2.0
    assert retry.backoff_seconds(5, jitter=0.5) == 1.0
    assert retry.backoff_seconds(0, jitter=0.0) == 0.0
