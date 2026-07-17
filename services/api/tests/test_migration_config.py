from alembic.config import Config

from axis_api.migration_config import apply_runtime_database_url


def test_runtime_database_url_overrides_alembic_ini_value() -> None:
    config = Config()
    config.set_main_option("sqlalchemy.url", "postgresql://localhost/default")

    applied = apply_runtime_database_url(
        config,
        {"AXIS_POSTGRES_DSN": "postgresql://axis:secret@db.internal/axis"},
    )

    assert applied is True
    assert (
        config.get_main_option("sqlalchemy.url")
        == "postgresql://axis:secret@db.internal/axis"
    )


def test_runtime_database_url_preserves_percent_encoded_credentials() -> None:
    config = Config()

    apply_runtime_database_url(
        config,
        {"AXIS_POSTGRES_DSN": "postgresql://axis:p%40ss@db.internal/axis"},
    )

    assert (
        config.get_main_option("sqlalchemy.url")
        == "postgresql://axis:p%40ss@db.internal/axis"
    )


def test_alembic_ini_value_remains_when_runtime_url_is_absent() -> None:
    config = Config()
    config.set_main_option("sqlalchemy.url", "postgresql://localhost/default")

    applied = apply_runtime_database_url(config, {})

    assert applied is False
    assert config.get_main_option("sqlalchemy.url") == "postgresql://localhost/default"
