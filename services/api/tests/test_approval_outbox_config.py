import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from axis_api.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_approval_outbox_is_fail_closed_by_default() -> None:
    settings = Settings(_env_file=None)

    assert settings.approval_decision_outbox_enabled is False
    assert settings.approval_decision_outbox_dispatch_enabled is False
    assert settings.approval_decision_outbox_dispatch_interval_seconds == 5
    assert settings.approval_decision_outbox_batch_size == 10
    assert settings.approval_decision_outbox_claim_timeout_seconds == 60
    assert settings.approval_decision_outbox_max_attempts == 10
    assert settings.approval_decision_outbox_retry_base_seconds == 1
    assert settings.approval_decision_outbox_retry_max_seconds == 300


def test_approval_outbox_settings_parse_environment_aliases() -> None:
    settings = Settings(
        _env_file=None,
        AXIS_APPROVAL_DECISION_OUTBOX_ENABLED="true",
        AXIS_APPROVAL_DECISION_OUTBOX_DISPATCH_ENABLED="true",
        AXIS_APPROVAL_DECISION_OUTBOX_DISPATCH_INTERVAL_SECONDS="12",
        AXIS_APPROVAL_DECISION_OUTBOX_BATCH_SIZE="40",
        AXIS_APPROVAL_DECISION_OUTBOX_CLAIM_TIMEOUT_SECONDS="120",
        AXIS_APPROVAL_DECISION_OUTBOX_MAX_ATTEMPTS="8",
        AXIS_APPROVAL_DECISION_OUTBOX_RETRY_BASE_SECONDS="3",
        AXIS_APPROVAL_DECISION_OUTBOX_RETRY_MAX_SECONDS="90",
    )

    assert settings.approval_decision_outbox_enabled is True
    assert settings.approval_decision_outbox_dispatch_enabled is True
    assert settings.approval_decision_outbox_dispatch_interval_seconds == 12
    assert settings.approval_decision_outbox_batch_size == 40
    assert settings.approval_decision_outbox_claim_timeout_seconds == 120
    assert settings.approval_decision_outbox_max_attempts == 8
    assert settings.approval_decision_outbox_retry_base_seconds == 3
    assert settings.approval_decision_outbox_retry_max_seconds == 90


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("AXIS_APPROVAL_DECISION_OUTBOX_DISPATCH_INTERVAL_SECONDS", 0),
        ("AXIS_APPROVAL_DECISION_OUTBOX_BATCH_SIZE", 0),
        ("AXIS_APPROVAL_DECISION_OUTBOX_CLAIM_TIMEOUT_SECONDS", 4),
        ("AXIS_APPROVAL_DECISION_OUTBOX_MAX_ATTEMPTS", 0),
        ("AXIS_APPROVAL_DECISION_OUTBOX_RETRY_BASE_SECONDS", 0),
        ("AXIS_APPROVAL_DECISION_OUTBOX_RETRY_MAX_SECONDS", 86_401),
    ],
)
def test_approval_outbox_rejects_unsafe_operational_limits(setting: str, value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{setting: value})


def test_approval_outbox_retry_cap_cannot_be_below_base_delay() -> None:
    with pytest.raises(ValidationError, match="RETRY_MAX_SECONDS"):
        Settings(
            _env_file=None,
            AXIS_APPROVAL_DECISION_OUTBOX_RETRY_BASE_SECONDS=30,
            AXIS_APPROVAL_DECISION_OUTBOX_RETRY_MAX_SECONDS=10,
        )


def test_approval_outbox_lease_must_exceed_temporal_signal_timeout() -> None:
    with pytest.raises(ValidationError, match="CLAIM_TIMEOUT_SECONDS"):
        Settings(
            _env_file=None,
            AXIS_APPROVAL_DECISION_OUTBOX_DISPATCH_ENABLED=True,
            AXIS_TEMPORAL_SIGNAL_TIMEOUT_SECONDS=30,
            AXIS_APPROVAL_DECISION_OUTBOX_CLAIM_TIMEOUT_SECONDS=30,
        )


def test_disabled_dispatch_preserves_existing_temporal_timeout_configuration() -> None:
    settings = Settings(
        _env_file=None,
        AXIS_APPROVAL_DECISION_OUTBOX_DISPATCH_ENABLED=False,
        AXIS_TEMPORAL_SIGNAL_TIMEOUT_SECONDS=120,
        AXIS_APPROVAL_DECISION_OUTBOX_CLAIM_TIMEOUT_SECONDS=60,
    )

    assert settings.approval_decision_outbox_dispatch_enabled is False


def test_approval_outbox_is_wired_to_examples_and_helm() -> None:
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    values = (REPO_ROOT / "infra" / "helm" / "limes-axis" / "values.yaml").read_text(
        encoding="utf-8"
    )
    configmap = (
        REPO_ROOT / "infra" / "helm" / "limes-axis" / "templates" / "configmap.yaml"
    ).read_text(encoding="utf-8")
    values_schema = json.loads(
        (REPO_ROOT / "infra" / "helm" / "limes-axis" / "values.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert "AXIS_APPROVAL_DECISION_OUTBOX_ENABLED=false" in env_example
    assert "AXIS_APPROVAL_DECISION_OUTBOX_DISPATCH_ENABLED=false" in env_example
    assert 'AXIS_APPROVAL_DECISION_OUTBOX_ENABLED: "false"' in values
    assert "approvalDecisionOutbox:" in values
    assert "dispatchEnabled: false" in values
    assert values_schema["properties"]["api"]["properties"]["env"]["properties"][
        "AXIS_APPROVAL_DECISION_OUTBOX_ENABLED"
    ]["enum"] == ["true", "false"]
    outbox_schema = values_schema["properties"]["worker"]["properties"]["approvalDecisionOutbox"][
        "properties"
    ]
    assert outbox_schema["dispatchEnabled"]["type"] == "boolean"
    assert outbox_schema["batchSize"]["maximum"] == 100
    assert outbox_schema["claimTimeoutSeconds"]["minimum"] == 5
    for setting in (
        "AXIS_APPROVAL_DECISION_OUTBOX_ENABLED",
        "AXIS_APPROVAL_DECISION_OUTBOX_DISPATCH_ENABLED",
        "AXIS_APPROVAL_DECISION_OUTBOX_DISPATCH_INTERVAL_SECONDS",
        "AXIS_APPROVAL_DECISION_OUTBOX_BATCH_SIZE",
        "AXIS_APPROVAL_DECISION_OUTBOX_CLAIM_TIMEOUT_SECONDS",
        "AXIS_APPROVAL_DECISION_OUTBOX_MAX_ATTEMPTS",
        "AXIS_APPROVAL_DECISION_OUTBOX_RETRY_BASE_SECONDS",
        "AXIS_APPROVAL_DECISION_OUTBOX_RETRY_MAX_SECONDS",
    ):
        assert setting in configmap
