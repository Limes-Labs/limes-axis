from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = Field(default="development", alias="AXIS_ENV")
    postgres_dsn: str = Field(
        default="postgresql+psycopg://axis:axis@localhost:5432/axis",
        alias="AXIS_POSTGRES_DSN",
    )
    typedb_address: str = Field(default="localhost:1729", alias="AXIS_TYPEDB_ADDRESS")
    typedb_username: str = Field(default="admin", alias="AXIS_TYPEDB_USERNAME")
    typedb_password: str = Field(default="password", alias="AXIS_TYPEDB_PASSWORD")
    temporal_address: str = Field(default="localhost:7233", alias="AXIS_TEMPORAL_ADDRESS")
    external_model_egress_enabled: bool = Field(
        default=False,
        alias="AXIS_EXTERNAL_MODEL_EGRESS_ENABLED",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)
