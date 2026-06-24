from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = Field(default="development", alias="AXIS_ENV")
    public_base_url: str = Field(default="http://localhost:3000", alias="AXIS_PUBLIC_BASE_URL")
    api_base_url: str = Field(default="http://localhost:8000", alias="AXIS_API_BASE_URL")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        alias="AXIS_CORS_ORIGINS",
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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)
