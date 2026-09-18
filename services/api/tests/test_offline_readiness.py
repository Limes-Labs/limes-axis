"""Contract tests for the #871 offline readiness section.

Covers the six acceptance criteria: configured-but-unverified without a
rehearsal, required external dependencies blocking the profile, evidence
invalidation on a material change, malformed/tampered/stale evidence, backward
compatibility plus schema fixtures, and the documentation contract.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from axis_api.config import Settings
from axis_api.main import create_app as create_axis_app
from axis_api.offline_readiness import (
    MANIFEST_REVISION_LENGTH,
    OFFLINE_PROFILE_SCHEMA,
    OFFLINE_REHEARSAL_MAX_AGE_SECONDS,
    OPTIONAL_OFFLINE_DEPENDENCIES,
    REHEARSAL_EVIDENCE_FIELDS,
    REQUIRED_OFFLINE_DEPENDENCIES,
    evaluate_offline_readiness,
    offline_profile_digest,
    rehearsal_result_digest,
)
from axis_api.rate_limit import InMemoryRateLimiter

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_FIXTURE = Path(__file__).parent / "fixtures" / "offline_readiness_contract.json"
DOCUMENTATION = REPO_ROOT / "docs" / "offline-readiness.md"

NOW = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
MANIFEST_REVISION = "a" * MANIFEST_REVISION_LENGTH

LOCAL_BINDINGS = [
    "artifact-object-store=private-endpoint://local/evidence-store",
    "distributed-rate-limit=private-endpoint://local/valkey",
    "identity-validation=private-endpoint://local/keycloak",
    "operational-database=private-endpoint://local/ops-postgres",
    "workflow-engine=private-endpoint://local/temporal",
]


def create_app(settings: Settings) -> FastAPI:
    """Build a production-shaped app without requiring Redis in unit tests."""

    return create_axis_app(
        settings,
        rate_limit_backend=InMemoryRateLimiter(
            limit=settings.api_rate_limit_requests,
            window_seconds=settings.api_rate_limit_window_seconds,
        ),
    )


def offline_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "postgres_dsn": "sqlite+pysqlite://",
        "api_base_url": "https://api.axis.example",
        "public_base_url": "https://console.axis.example",
        "oidc_auth_required": True,
        "oidc_issuer": "https://idp.example/realms/axis",
        "oidc_jwks_url": "https://idp.example/realms/axis/protocol/openid-connect/certs",
        "oidc_algorithms": ["RS256"],
        "oidc_client_id": "axis-console",
        "oidc_redirect_uri": "https://api.axis.example/identity/oidc/callback",
        "oidc_authorization_url": "https://idp.example/realms/axis/protocol/openid-connect/auth",
        "oidc_token_url": "https://idp.example/realms/axis/protocol/openid-connect/token",
        "oidc_end_session_url": "https://idp.example/realms/axis/protocol/openid-connect/logout",
        "oidc_post_logout_redirect_uri": "https://console.axis.example/signed-out",
        "oidc_session_cookie_signing_secret": "axis-cookie-signing-key",
        "oidc_session_cookie_secure": True,
        "oidc_refresh_token_encryption_key": "axis-refresh-credential-encryption-key-01",
        "api_rate_limit_enabled": True,
        "api_rate_limit_paths": ["*"],
        "api_rate_limit_backend": "redis",
        "api_rate_limit_failure_mode": "closed",
        "redis_url": "redis://redis.example:6379/0",
        "api_rate_limit_requests": 120,
        "api_rate_limit_window_seconds": 60,
        "tenant_admission_mode": "registered_only",
        "deployment_tenancy_mode": "on_prem",
        "deployment_network_policy_enabled": True,
        "deployment_network_egress_mode": "local_only",
        "deployment_dependency_manifest_revision": MANIFEST_REVISION,
        "deployment_offline_local_bindings": list(LOCAL_BINDINGS),
    }
    return Settings(_env_file=None, **(values | overrides))


def section_for(settings: Settings, *, egress_mode: str = "local_only"):
    return evaluate_offline_readiness(settings, egress_mode=egress_mode, now=NOW)


def declared_evidence(section, **overrides: object) -> str:
    declared: dict[str, str] = {
        "ref": "rehearsal-artifact://local/2026-09-17-isolated-run",
        "release": section.release_identity,
        "profile_digest": section.profile_digest,
        "captured_at": (NOW - timedelta(days=2)).isoformat(),
        "scope": "isolated-cluster/calico-ipv4",
    }
    declared.update({key: str(value) for key, value in overrides.items()})
    declared["result_digest"] = rehearsal_result_digest(declared)
    return json.dumps(declared)


def tampered_evidence(section) -> str:
    declared = json.loads(declared_evidence(section))
    # Refresh the capture time without touching the declared result digest, so
    # the header and its consistency binding no longer agree.
    declared["captured_at"] = (NOW - timedelta(hours=1)).isoformat()
    return json.dumps(declared)


def readiness_body(settings: Settings) -> dict:
    response = TestClient(create_app(settings)).get("/deployment/readiness")
    assert response.status_code == 200
    return response.json()


# --- Acceptance criterion 1: configured but unverified -----------------------


def test_local_profile_without_a_rehearsal_is_configured_but_unverified() -> None:
    section = section_for(offline_settings())

    assert section.state == "configured_unverified"
    assert section.configuration.state == "valid"
    assert section.observed_evidence.state == "not_run"
    assert section.observed_evidence.matched is False
    assert section.dependency_manifest_revision == MANIFEST_REVISION


def test_non_offline_deployment_does_not_claim_offline_readiness() -> None:
    section = section_for(offline_settings(), egress_mode="port_allowlist")

    assert section.state == "not_declared"
    assert section.declared is False
    assert section.configuration.state == "not_evaluated"
    assert section.configuration.dependencies == []
    assert section.observed_evidence.state == "not_run"


def test_readiness_endpoint_separates_the_offline_section_from_production_blockers() -> None:
    base = offline_settings()
    configured = readiness_body(base)
    unbound = readiness_body(
        offline_settings(
            deployment_offline_local_bindings=[],
            offline_rehearsal_evidence=declared_evidence(section_for(base)),
        )
    )
    control = readiness_body(offline_settings(deployment_network_egress_mode="port_allowlist"))

    assert configured["offline_readiness"]["state"] == "configured_unverified"
    assert control["offline_readiness"]["state"] == "not_declared"
    # The section reports its own blockers without touching production blockers.
    assert configured["offline_readiness"]["configuration"]["blockers"] == []
    assert unbound["offline_readiness"]["configuration"]["blockers"]
    assert unbound["production_blockers"] == configured["production_blockers"]


# --- Acceptance criterion 2: required external dependencies block ------------


def test_required_dependency_without_a_local_binding_blocks_the_profile() -> None:
    section = section_for(offline_settings(deployment_offline_local_bindings=[]))

    assert section.state == "action_required"
    assert section.configuration.state == "invalid"
    for dependency_id in (
        "identity-validation",
        "operational-database",
        "workflow-engine",
    ):
        assert f"required_dependency_not_locally_bound:{dependency_id}" in (
            section.configuration.blockers
        )
    # The local filesystem export adapter is a local replacement, not an
    # external object-store dependency, and is reported as a reasoned omission.
    omitted = {
        capability.dependency_id: capability.reason
        for capability in section.configuration.omitted_capabilities
    }
    assert "local_filesystem" in omitted["artifact-object-store"]
    assert "artifact-object-store" in REQUIRED_OFFLINE_DEPENDENCIES


def test_active_optional_dependency_without_a_local_binding_blocks_the_profile() -> None:
    settings = offline_settings(
        otel_enabled=True,
        deployment_offline_local_bindings=[
            entry for entry in LOCAL_BINDINGS if not entry.startswith("distributed-rate-limit")
        ],
    )

    section = section_for(settings)

    assert section.state == "action_required"
    assert "optional_dependency_not_locally_bound:distributed-rate-limit" in (
        section.configuration.blockers
    )
    assert "optional_dependency_not_locally_bound:telemetry-export" in (
        section.configuration.blockers
    )


def test_disabled_optional_dependencies_are_reported_with_reasons() -> None:
    settings = offline_settings(
        deployment_offline_local_bindings=[
            entry
            for entry in LOCAL_BINDINGS
            if not entry.startswith("distributed-rate-limit")
        ],
        api_rate_limit_backend="memory",
    )

    section = section_for(settings)

    assert section.configuration.state == "valid"
    omitted = {
        capability.dependency_id: capability.reason
        for capability in section.configuration.omitted_capabilities
    }
    assert "distributed-rate-limit" in omitted
    assert "AXIS_API_RATE_LIMIT_BACKEND" in omitted["distributed-rate-limit"]
    assert "telemetry-export" in omitted
    assert "AXIS_OTEL_ENABLED" in omitted["telemetry-export"]
    assert section.state == "configured_unverified"


def test_missing_or_invalid_manifest_revision_is_a_configuration_blocker() -> None:
    missing = section_for(offline_settings(deployment_dependency_manifest_revision=""))
    invalid = section_for(
        offline_settings(deployment_dependency_manifest_revision="not-a-revision")
    )

    assert missing.configuration.state == "invalid"
    assert "dependency_manifest_revision_not_declared" in missing.configuration.blockers
    assert invalid.configuration.state == "invalid"
    assert "dependency_manifest_revision_not_a_git_revision" in invalid.configuration.blockers


def test_binding_references_must_be_opaque_and_bounded() -> None:
    section = section_for(
        offline_settings(
            deployment_offline_local_bindings=[
                "operational-database=https://axis:secret@db.internal/axis",
                "workflow-engine=private-endpoint://local/temporal?token=secret",
                "identity-validation=not-a-reference",
                "unknown-dependency=private-endpoint://local/x",
                "no-separator",
            ]
        )
    )

    assert "invalid_binding_reference:operational-database" in section.configuration.blockers
    assert "invalid_binding_reference:workflow-engine" in section.configuration.blockers
    assert "invalid_binding_reference:identity-validation" in section.configuration.blockers
    assert "unknown_binding_dependency:unknown-dependency" in section.configuration.blockers
    assert "malformed_local_binding:4" in section.configuration.blockers
    rendered = section.model_dump_json()
    assert "axis:secret@" not in rendered
    assert "token=secret" not in rendered
    assert "db.internal" not in rendered


# --- Acceptance criterion 3: material change invalidates evidence ------------


def test_matching_rehearsal_evidence_is_observed_but_not_accredited() -> None:
    settings = offline_settings()
    base = section_for(settings)
    matched = section_for(
        offline_settings(offline_rehearsal_evidence=declared_evidence(base))
    )

    assert matched.state == "verified_in_rehearsal"
    assert matched.observed_evidence.state == "matched"
    assert matched.observed_evidence.age_seconds == 2 * 86400
    assert "no accreditation" in matched.model_dump_json()


@pytest.mark.parametrize(
    ("overrides", "expected_detail"),
    [
        (
            {
                "deployment_offline_local_bindings": [
                    entry
                    for entry in LOCAL_BINDINGS
                    if not entry.startswith("operational-database")
                ]
                + ["operational-database=private-endpoint://local/moved-postgres"],
            },
            "profile",
        ),
        ({"deployment_dependency_manifest_revision": "b" * 40}, "profile"),
        ({"deployment_release_identity": "release-2026-10"}, "release"),
    ],
)
def test_material_change_invalidates_prior_evidence(
    overrides: dict[str, object], expected_detail: str
) -> None:
    base = section_for(offline_settings())
    evidence = declared_evidence(base)
    changed = section_for(offline_settings(offline_rehearsal_evidence=evidence, **overrides))

    assert changed.state == "configured_unverified"
    assert changed.observed_evidence.state == "mismatched"
    assert expected_detail in changed.observed_evidence.detail


def test_egress_mode_change_changes_the_profile_digest() -> None:
    first = offline_profile_digest(
        egress_mode="local_only",
        release_identity="0.0.0",
        dependency_manifest_revision=MANIFEST_REVISION,
        bindings={"operational-database": "private-endpoint://local/ops-postgres"},
    )
    second = offline_profile_digest(
        egress_mode="offline",
        release_identity="0.0.0",
        dependency_manifest_revision=MANIFEST_REVISION,
        bindings={"operational-database": "private-endpoint://local/ops-postgres"},
    )

    assert first != second


# --- Acceptance criterion 4: malformed, tampered and stale evidence ----------


@pytest.mark.parametrize(
    ("raw", "expected_state"),
    [
        ("{not json", "malformed"),
        ('["not-an-object"]', "malformed"),
        ('{"ref": "rehearsal-artifact://x"}', "incomplete"),
        (
            json.dumps(
                {
                    "ref": "rehearsal-artifact://x",
                    "release": "0.0.0",
                    "profile_digest": "a" * 64,
                    "captured_at": "2026-09-15 10:00",
                    "scope": "isolated",
                    "result_digest": "b" * 64,
                }
            ),
            "malformed",
        ),
        (
            json.dumps(
                {
                    "ref": "rehearsal-artifact://x",
                    "release": "0.0.0",
                    "profile_digest": "not-a-digest",
                    "captured_at": "2026-09-15T10:00:00+00:00",
                    "scope": "isolated",
                    "result_digest": "b" * 64,
                }
            ),
            "malformed",
        ),
        (
            json.dumps(
                {
                    "ref": "rehearsal-artifact://x",
                    "release": "0.0.0",
                    "profile_digest": "a" * 64,
                    "captured_at": "2027-09-15T10:00:00+00:00",
                    "scope": "isolated",
                    "result_digest": "b" * 64,
                }
            ),
            "malformed",
        ),
    ],
)
def test_unusable_evidence_is_never_verified(raw: str, expected_state: str) -> None:
    section = section_for(offline_settings(offline_rehearsal_evidence=raw))

    assert section.observed_evidence.state == expected_state
    assert section.state == "configured_unverified"
    assert section.observed_evidence.matched is False


def test_tampered_evidence_is_unverified() -> None:
    base = section_for(offline_settings())
    section = section_for(
        offline_settings(offline_rehearsal_evidence=tampered_evidence(base))
    )

    assert section.observed_evidence.state == "tampered"
    assert section.state == "configured_unverified"


def test_stale_evidence_is_unverified() -> None:
    base = section_for(offline_settings())
    stale = declared_evidence(
        base,
        captured_at=(NOW - timedelta(seconds=OFFLINE_REHEARSAL_MAX_AGE_SECONDS + 60)).isoformat(),
    )
    section = section_for(offline_settings(offline_rehearsal_evidence=stale))

    assert section.observed_evidence.state == "stale"
    assert section.state == "configured_unverified"


def test_readiness_response_never_exposes_configured_endpoints_or_secrets() -> None:
    settings = offline_settings(
        postgres_dsn="postgresql+psycopg://axis:leak-marker-password@db.internal:5432/axis",
        oidc_jwks_url="https://idp.internal/leak-marker-jwks",
        otel_enabled=False,
        otel_exporter_otlp_endpoint="http://collector.internal:4318/leak-marker-otel",
        connector_export_s3_endpoint="minio.internal:9000/leak-marker-s3",
        connector_export_object_store_adapter="s3_compatible",
        connector_export_s3_bucket="axis-evidence",
        connector_export_s3_access_key="leak-marker-key",
        connector_export_s3_secret_key="leak-marker-secret",
    )

    rendered = TestClient(create_app(settings)).get("/deployment/readiness").text

    for marker in (
        "leak-marker-password",
        "leak-marker-jwks",
        "leak-marker-otel",
        "leak-marker-s3",
        "leak-marker-key",
        "leak-marker-secret",
        "db.internal",
        "idp.internal",
        "collector.internal",
        "minio.internal",
    ):
        assert marker not in rendered
    assert json.loads(rendered)["offline_readiness"]["profile_digest"]


# --- Acceptance criterion 5: compatibility and schema fixtures ---------------


def test_section_shape_matches_the_committed_contract_fixture() -> None:
    contract = json.loads(CONTRACT_FIXTURE.read_text(encoding="utf-8"))
    section = section_for(offline_settings())

    assert contract["profile_schema"] == OFFLINE_PROFILE_SCHEMA
    assert contract["rehearsal_max_age_seconds"] == OFFLINE_REHEARSAL_MAX_AGE_SECONDS
    assert sorted(contract["required_dependencies"]) == sorted(REQUIRED_OFFLINE_DEPENDENCIES)
    assert sorted(contract["optional_dependencies"]) == sorted(OPTIONAL_OFFLINE_DEPENDENCIES)
    assert sorted(contract["evidence_fields"]) == sorted(REHEARSAL_EVIDENCE_FIELDS)
    assert sorted(contract["section_states"]) == sorted(
        {
            "not_declared",
            "action_required",
            "configured_unverified",
            "verified_in_rehearsal",
        }
    )
    assert sorted(contract["observed_evidence_states"]) == sorted(
        {
            "not_run",
            "incomplete",
            "malformed",
            "tampered",
            "mismatched",
            "stale",
            "matched",
        }
    )
    assert sorted(section.model_dump()) == sorted(contract["section_fields"])


def test_existing_readiness_fields_remain_available() -> None:
    body = readiness_body(offline_settings())

    for key in (
        "status",
        "environment",
        "profile",
        "production_ready",
        "demo_safe",
        "capabilities",
        "production_blockers",
        "checks",
        "notes",
        "offline_readiness",
    ):
        assert key in body
    assert body["capabilities"]["network_egress_mode"] == "local_only"


def test_openapi_documents_the_offline_readiness_contract() -> None:
    schema = json.loads((REPO_ROOT / "docs" / "openapi.json").read_text(encoding="utf-8"))
    schemas = schema["components"]["schemas"]

    for name in (
        "OfflineReadinessSection",
        "OfflineConfigurationValidation",
        "OfflineObservedEvidence",
        "OfflineDependencyBinding",
        "OfflineOmittedCapability",
    ):
        assert name in schemas, f"{name} is missing from the OpenAPI contract"
    report = schemas["DeploymentReadinessReport"]["properties"]
    assert "offline_readiness" in report


# --- Acceptance criterion 6: documentation contract --------------------------


def test_documentation_states_which_checks_are_static_configuration_or_runtime() -> None:
    assert DOCUMENTATION.exists(), "docs/offline-readiness.md is missing"
    text = DOCUMENTATION.read_text(encoding="utf-8")

    for term in (
        "static",
        "configuration",
        "runtime",
        "NOT RUN",
        "configured_unverified",
        "verified_in_rehearsal",
        "accredit",
    ):
        assert term in text, f"documentation must explain {term!r}"
