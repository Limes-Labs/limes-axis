from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = Field(default="development", alias="AXIS_ENV")
    public_base_url: str = Field(default="http://localhost:3000", alias="AXIS_PUBLIC_BASE_URL")
    api_base_url: str = Field(default="http://localhost:8000", alias="AXIS_API_BASE_URL")
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3100",
            "http://127.0.0.1:3100",
        ],
        alias="AXIS_CORS_ORIGINS",
    )
    api_rate_limit_enabled: bool = Field(
        default=False,
        alias="AXIS_API_RATE_LIMIT_ENABLED",
    )
    api_rate_limit_requests: int = Field(
        default=120,
        alias="AXIS_API_RATE_LIMIT_REQUESTS",
    )
    api_rate_limit_window_seconds: int = Field(
        default=60,
        alias="AXIS_API_RATE_LIMIT_WINDOW_SECONDS",
    )
    api_rate_limit_paths: list[str] = Field(
        default_factory=lambda: [
            "/identity/oidc/authorize",
            "/identity/oidc/callback",
            "/identity/oidc/logout",
            "/identity/session/logout",
            "/deployment/readiness",
            "/support/diagnostics",
        ],
        alias="AXIS_API_RATE_LIMIT_PATHS",
    )
    postgres_dsn: str = Field(
        default="postgresql+psycopg://axis:axis@localhost:5432/axis",
        alias="AXIS_POSTGRES_DSN",
    )
    typedb_address: str = Field(default="localhost:1729", alias="AXIS_TYPEDB_ADDRESS")
    typedb_username: str = Field(default="admin", alias="AXIS_TYPEDB_USERNAME")
    typedb_password: str = Field(default="password", alias="AXIS_TYPEDB_PASSWORD")
    typedb_database: str = Field(default="axis", alias="AXIS_TYPEDB_DATABASE")
    ontology_mutations_enabled: bool = Field(
        default=False,
        alias="AXIS_ONTOLOGY_MUTATIONS_ENABLED",
    )
    ontology_queries_enabled: bool = Field(
        default=False,
        alias="AXIS_ONTOLOGY_QUERIES_ENABLED",
    )
    temporal_address: str = Field(default="localhost:7233", alias="AXIS_TEMPORAL_ADDRESS")
    temporal_namespace: str = Field(default="default", alias="AXIS_TEMPORAL_NAMESPACE")
    temporal_signal_timeout_seconds: float = Field(
        default=2.0,
        alias="AXIS_TEMPORAL_SIGNAL_TIMEOUT_SECONDS",
    )
    workflow_signals_enabled: bool = Field(
        default=True,
        alias="AXIS_WORKFLOW_SIGNALS_ENABLED",
    )
    oidc_issuer: str = Field(
        default="http://localhost:8080/realms/axis",
        alias="AXIS_OIDC_ISSUER",
    )
    oidc_audience: str = Field(default="limes-axis-api", alias="AXIS_OIDC_AUDIENCE")
    oidc_jwks_url: str | None = Field(default=None, alias="AXIS_OIDC_JWKS_URL")
    oidc_algorithms: list[str] = Field(
        default_factory=lambda: ["RS256"],
        alias="AXIS_OIDC_ALGORITHMS",
    )
    oidc_actor_claim: str = Field(default="sub", alias="AXIS_OIDC_ACTOR_CLAIM")
    oidc_tenant_claim: str = Field(default="axis_tenant", alias="AXIS_OIDC_TENANT_CLAIM")
    oidc_jwks_cache_seconds: int = Field(default=300, alias="AXIS_OIDC_JWKS_CACHE_SECONDS")
    oidc_auth_required: bool = Field(default=False, alias="AXIS_OIDC_AUTH_REQUIRED")
    oidc_client_id: str | None = Field(default=None, alias="AXIS_OIDC_CLIENT_ID")
    oidc_client_secret: str | None = Field(default=None, alias="AXIS_OIDC_CLIENT_SECRET")
    oidc_authorization_url: str | None = Field(default=None, alias="AXIS_OIDC_AUTHORIZATION_URL")
    oidc_token_url: str | None = Field(default=None, alias="AXIS_OIDC_TOKEN_URL")
    oidc_redirect_uri: str | None = Field(default=None, alias="AXIS_OIDC_REDIRECT_URI")
    oidc_end_session_url: str | None = Field(
        default=None,
        alias="AXIS_OIDC_END_SESSION_URL",
    )
    oidc_post_logout_redirect_uri: str | None = Field(
        default=None,
        alias="AXIS_OIDC_POST_LOGOUT_REDIRECT_URI",
    )
    oidc_scopes: list[str] = Field(
        default_factory=lambda: ["openid", "profile", "email"],
        alias="AXIS_OIDC_SCOPES",
    )
    oidc_login_cookie_name: str = Field(
        default="axis_oidc_login",
        alias="AXIS_OIDC_LOGIN_COOKIE_NAME",
    )
    oidc_session_cookie_name: str = Field(
        default="axis_session",
        alias="AXIS_OIDC_SESSION_COOKIE_NAME",
    )
    oidc_session_cookie_signing_secret: str | None = Field(
        default=None,
        alias="AXIS_OIDC_SESSION_COOKIE_SIGNING_SECRET",
    )
    oidc_login_state_ttl_seconds: int = Field(
        default=600,
        alias="AXIS_OIDC_LOGIN_STATE_TTL_SECONDS",
    )
    oidc_session_cookie_ttl_seconds: int = Field(
        default=3600,
        alias="AXIS_OIDC_SESSION_COOKIE_TTL_SECONDS",
    )
    oidc_session_cookie_secure: bool = Field(
        default=False,
        alias="AXIS_OIDC_SESSION_COOKIE_SECURE",
    )
    external_model_egress_enabled: bool = Field(
        default=False,
        alias="AXIS_EXTERNAL_MODEL_EGRESS_ENABLED",
    )
    credential_lease_execution_enabled: bool = Field(
        default=False,
        alias="AXIS_CREDENTIAL_LEASE_EXECUTION_ENABLED",
    )
    credential_lease_provider_adapters_enabled: bool = Field(
        default=False,
        alias="AXIS_CREDENTIAL_LEASE_PROVIDER_ADAPTERS_ENABLED",
    )
    connector_sync_execution_enabled: bool = Field(
        default=False,
        alias="AXIS_CONNECTOR_SYNC_EXECUTION_ENABLED",
    )
    external_db_sync_execution_enabled: bool = Field(
        default=False,
        alias="AXIS_EXTERNAL_DB_SYNC_EXECUTION_ENABLED",
    )
    external_db_live_query_preflight_enabled: bool = Field(
        default=False,
        alias="AXIS_EXTERNAL_DB_LIVE_QUERY_PREFLIGHT_ENABLED",
    )
    audit_ledger_signing_key_id: str = Field(
        default="axis-self-hosted-audit-ledger",
        alias="AXIS_AUDIT_LEDGER_SIGNING_KEY_ID",
    )
    audit_ledger_signing_secret: str | None = Field(
        default=None,
        alias="AXIS_AUDIT_LEDGER_SIGNING_SECRET",
    )
    connector_export_object_store_root: str = Field(
        default=".axis/object-store",
        alias="AXIS_CONNECTOR_EXPORT_OBJECT_STORE_ROOT",
    )
    connector_export_object_store_adapter: str = Field(
        default="local_filesystem",
        alias="AXIS_CONNECTOR_EXPORT_OBJECT_STORE_ADAPTER",
    )
    connector_export_s3_endpoint: str | None = Field(
        default=None,
        alias="AXIS_CONNECTOR_EXPORT_S3_ENDPOINT",
    )
    connector_export_s3_region: str | None = Field(
        default=None,
        alias="AXIS_CONNECTOR_EXPORT_S3_REGION",
    )
    connector_export_s3_bucket: str | None = Field(
        default=None,
        alias="AXIS_CONNECTOR_EXPORT_S3_BUCKET",
    )
    connector_export_s3_access_key: str | None = Field(
        default=None,
        alias="AXIS_CONNECTOR_EXPORT_S3_ACCESS_KEY",
    )
    connector_export_s3_secret_key: str | None = Field(
        default=None,
        alias="AXIS_CONNECTOR_EXPORT_S3_SECRET_KEY",
    )
    connector_export_s3_secure_transport: bool = Field(
        default=True,
        alias="AXIS_CONNECTOR_EXPORT_S3_SECURE_TRANSPORT",
    )
    connector_export_s3_object_lock_enabled: bool = Field(
        default=False,
        alias="AXIS_CONNECTOR_EXPORT_S3_OBJECT_LOCK_ENABLED",
    )
    connector_export_s3_retention_mode: str = Field(
        default="GOVERNANCE",
        alias="AXIS_CONNECTOR_EXPORT_S3_RETENTION_MODE",
    )
    connector_export_s3_retention_days: int = Field(
        default=0,
        alias="AXIS_CONNECTOR_EXPORT_S3_RETENTION_DAYS",
    )
    connector_export_s3_legal_hold_enabled: bool = Field(
        default=False,
        alias="AXIS_CONNECTOR_EXPORT_S3_LEGAL_HOLD_ENABLED",
    )
    support_model_enabled: bool = Field(
        default=False,
        alias="AXIS_SUPPORT_MODEL_ENABLED",
    )
    support_coverage: str = Field(
        default="demo_business_hours",
        alias="AXIS_SUPPORT_COVERAGE",
    )
    support_s1_response_minutes: int = Field(
        default=0,
        alias="AXIS_SUPPORT_S1_RESPONSE_MINUTES",
    )
    support_s2_response_minutes: int = Field(
        default=0,
        alias="AXIS_SUPPORT_S2_RESPONSE_MINUTES",
    )
    support_s3_response_minutes: int = Field(
        default=0,
        alias="AXIS_SUPPORT_S3_RESPONSE_MINUTES",
    )
    support_s4_response_minutes: int = Field(
        default=0,
        alias="AXIS_SUPPORT_S4_RESPONSE_MINUTES",
    )
    support_escalation_channels: list[str] = Field(
        default_factory=list,
        alias="AXIS_SUPPORT_ESCALATION_CHANNELS",
    )
    support_customer_runbook_url: str | None = Field(
        default=None,
        alias="AXIS_SUPPORT_CUSTOMER_RUNBOOK_URL",
    )
    support_status_page_url: str | None = Field(
        default=None,
        alias="AXIS_SUPPORT_STATUS_PAGE_URL",
    )
    support_incident_review_required: bool = Field(
        default=False,
        alias="AXIS_SUPPORT_INCIDENT_REVIEW_REQUIRED",
    )
    support_signed_commitment_configured: bool = Field(
        default=False,
        alias="AXIS_SUPPORT_SIGNED_COMMITMENT_CONFIGURED",
    )
    support_named_staffing_model_configured: bool = Field(
        default=False,
        alias="AXIS_SUPPORT_NAMED_STAFFING_MODEL_CONFIGURED",
    )
    support_customer_incident_operations_configured: bool = Field(
        default=False,
        alias="AXIS_SUPPORT_CUSTOMER_INCIDENT_OPERATIONS_CONFIGURED",
    )
    support_legal_sla_terms_configured: bool = Field(
        default=False,
        alias="AXIS_SUPPORT_LEGAL_SLA_TERMS_CONFIGURED",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)
