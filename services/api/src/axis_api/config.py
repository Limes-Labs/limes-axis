from pydantic_settings import BaseSettings, SettingsConfigDict

from axis_api.settings.connectors import ConnectorsSettings
from axis_api.settings.identity import IdentitySettings
from axis_api.settings.models import ModelsSettings
from axis_api.settings.observability import ObservabilitySettings
from axis_api.settings.persistence import PersistenceSettings
from axis_api.settings.policy import PolicySettings
from axis_api.settings.runtime import RuntimeSettings
from axis_api.tenant_admission import TENANT_ADMISSION_REGISTERED_ONLY


class Settings(
    IdentitySettings,
    PersistenceSettings,
    ModelsSettings,
    ConnectorsSettings,
    PolicySettings,
    ObservabilitySettings,
    RuntimeSettings,
    BaseSettings,
):
    """Stable flat environment facade over capability-owned field definitions."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)


class RuntimeConfigurationError(ValueError):
    """Raised before startup side effects when a runtime profile is unsafe."""


#: Minimum length of the operator-provided session-cookie signing secret in
#: production; matches the refresh-credential encryption key minimum.
SESSION_COOKIE_SIGNING_SECRET_MIN_LENGTH = 32
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "[::1]", "::1", "0.0.0.0"})


def _is_plain_http_loopback_origin(origin: str) -> bool:
    value = origin.strip().casefold()
    if not value.startswith("http://"):
        return False
    authority = value[len("http://") :].split("/", 1)[0]
    if authority.startswith("["):
        host = authority.split("]", 1)[0] + "]"
    else:
        host = authority.rsplit(":", 1)[0] if ":" in authority else authority
    return host in _LOOPBACK_HOSTS or host.endswith(".localhost")


def _validate_production_browser_boundary(settings: "Settings") -> None:
    """Session cookie and CORS posture that production must never relax."""

    if not settings.oidc_session_cookie_secure:
        raise RuntimeConfigurationError(
            "AXIS_OIDC_SESSION_COOKIE_SECURE must be true when AXIS_ENV is production."
        )
    signing_secret = settings.oidc_session_cookie_signing_secret or ""
    if len(signing_secret) < SESSION_COOKIE_SIGNING_SECRET_MIN_LENGTH:
        raise RuntimeConfigurationError(
            "AXIS_OIDC_SESSION_COOKIE_SIGNING_SECRET must be set to at least "
            f"{SESSION_COOKIE_SIGNING_SECRET_MIN_LENGTH} characters when AXIS_ENV is "
            "production."
        )
    for origin in settings.cors_origins:
        if "*" in origin:
            raise RuntimeConfigurationError(
                "AXIS_CORS_ORIGINS must not contain wildcard origins when AXIS_ENV is "
                "production."
            )
        if _is_plain_http_loopback_origin(origin):
            raise RuntimeConfigurationError(
                "AXIS_CORS_ORIGINS must not contain plain-http localhost origins when "
                "AXIS_ENV is production."
            )


def validate_runtime_configuration(settings: Settings) -> None:
    """Reject unsafe production combinations before startup side effects."""

    environment = settings.environment.strip().casefold()
    if environment in {"prod", "production"} and not settings.oidc_auth_required:
        raise RuntimeConfigurationError(
            "AXIS_OIDC_AUTH_REQUIRED must be true when AXIS_ENV is production."
        )
    if environment in {"prod", "production"} and not settings.api_rate_limit_enabled:
        raise RuntimeConfigurationError(
            "AXIS_API_RATE_LIMIT_ENABLED must be true when AXIS_ENV is production."
        )
    if environment in {"prod", "production"}:
        if "*" not in settings.api_rate_limit_paths:
            raise RuntimeConfigurationError(
                "AXIS_API_RATE_LIMIT_PATHS must include '*' in production."
            )
        if settings.api_rate_limit_backend != "redis":
            raise RuntimeConfigurationError(
                "AXIS_API_RATE_LIMIT_BACKEND must be redis in production."
            )
        if settings.api_rate_limit_failure_mode != "closed":
            raise RuntimeConfigurationError(
                "AXIS_API_RATE_LIMIT_FAILURE_MODE must be closed in production."
            )
        if not settings.redis_url:
            raise RuntimeConfigurationError(
                "AXIS_REDIS_URL is required for production rate limiting."
            )
        if (
            settings.usage_metering_enabled
            and settings.usage_metering_failure_mode != "closed"
        ):
            raise RuntimeConfigurationError(
                "AXIS_USAGE_METERING_FAILURE_MODE must be closed in production "
                "when usage metering is enabled."
            )
        if settings.tenant_admission_mode != TENANT_ADMISSION_REGISTERED_ONLY:
            raise RuntimeConfigurationError(
                "AXIS_TENANT_ADMISSION_MODE must be registered_only when "
                "AXIS_ENV is production."
            )
        if settings.api_rate_limit_requests <= 0 or settings.api_rate_limit_window_seconds <= 0:
            raise RuntimeConfigurationError(
                "AXIS_API_RATE_LIMIT_REQUESTS and AXIS_API_RATE_LIMIT_WINDOW_SECONDS "
                "must be positive in production."
            )
        if settings.source_ingestion_dispatch_enabled:
            if (
                settings.source_ingestion_retry_max_seconds
                < settings.source_ingestion_retry_base_seconds
            ):
                raise RuntimeConfigurationError(
                    "AXIS_SOURCE_INGESTION_RETRY_MAX_SECONDS must be greater than or "
                    "equal to AXIS_SOURCE_INGESTION_RETRY_BASE_SECONDS when dispatch "
                    "is enabled in production."
                )
            if (
                settings.source_ingestion_extraction_enabled
                and settings.source_ingestion_claim_timeout_seconds
                <= settings.source_ingestion_extraction_time_budget_seconds
            ):
                raise RuntimeConfigurationError(
                    "AXIS_SOURCE_INGESTION_CLAIM_TIMEOUT_SECONDS must be greater than "
                    "AXIS_SOURCE_INGESTION_EXTRACTION_TIME_BUDGET_SECONDS when dispatch "
                    "and extraction are enabled in production."
                )
        _validate_production_browser_boundary(settings)
