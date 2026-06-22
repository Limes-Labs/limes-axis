from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, inspect, pool, text
from sqlalchemy.engine import Connection

from axis_api.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def ensure_alembic_version_table_capacity(connection: Connection) -> None:
    inspector = inspect(connection)
    if not inspector.has_table("alembic_version"):
        connection.execute(
            text(
                "CREATE TABLE alembic_version "
                "(version_num VARCHAR(128) NOT NULL PRIMARY KEY)"
            )
        )
        return

    if connection.dialect.name == "postgresql":
        connection.execute(
            text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)")
        )


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        with connection.begin():
            ensure_alembic_version_table_capacity(connection)

        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
