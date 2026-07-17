"""Runtime configuration helpers for Alembic migrations."""

from collections.abc import Mapping
from typing import Protocol


class AlembicConfig(Protocol):
    """The small Alembic ``Config`` surface used by this module."""

    def set_main_option(self, name: str, value: str) -> None: ...


def apply_runtime_database_url(
    config: AlembicConfig,
    environ: Mapping[str, str],
) -> bool:
    """Apply the runtime database URL when the deployment provides one.

    Alembic reads ``sqlalchemy.url`` from ``alembic.ini`` by default, while the
    API and deployment profiles use ``AXIS_POSTGRES_DSN``. Keeping those two
    sources disconnected can migrate a different database from the one the API
    serves. An explicitly supplied runtime value therefore takes precedence.

    ``ConfigParser`` treats percent signs as interpolation markers, so literal
    percent-encoded credentials must be escaped before passing the URL to
    Alembic's ``Config`` object.
    """

    runtime_database_url = environ.get("AXIS_POSTGRES_DSN")
    if runtime_database_url is None:
        return False

    config.set_main_option(
        "sqlalchemy.url",
        runtime_database_url.replace("%", "%%"),
    )
    return True
