import pytest
from sqlalchemy import event

from axis_api.config import Settings
from axis_api.db import create_session_factory


class _ConnectAttempted(Exception):
    pass


def _engine(**env: object):
    settings = Settings(
        AXIS_POSTGRES_DSN="postgresql+psycopg://axis:axis@127.0.0.1:1/axis",
        **env,
    )
    return create_session_factory(settings).kw["bind"]


def _connect_params(engine) -> dict:
    # Capture what the pool would pass to psycopg without opening a socket.
    captured: dict = {}

    @event.listens_for(engine, "do_connect")
    def capture(dialect, connection_record, cargs, cparams):
        captured.update(cparams)
        raise _ConnectAttempted

    with pytest.raises(_ConnectAttempted):
        engine.raw_connection()
    return captured


def test_postgres_engine_uses_configured_pool_bounds_without_statement_timeout() -> None:
    engine = _engine(AXIS_POSTGRES_POOL_SIZE=7, AXIS_POSTGRES_MAX_OVERFLOW=3)
    params = _connect_params(engine)

    assert engine.pool.size() == 7
    assert engine.pool._max_overflow == 3
    assert params["connect_timeout"] == 3
    assert "options" not in params


def test_postgres_engine_sets_session_statement_timeout_when_configured() -> None:
    params = _connect_params(_engine(AXIS_POSTGRES_STATEMENT_TIMEOUT_MS=45000))

    assert params["options"] == "-c statement_timeout=45000"
    assert params["connect_timeout"] == 3
