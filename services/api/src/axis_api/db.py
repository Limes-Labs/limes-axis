from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from axis_api.config import Settings


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    engine_options: dict[str, object] = {"pool_pre_ping": True}
    if make_url(settings.postgres_dsn).get_backend_name() == "postgresql":
        engine_options.update(
            pool_timeout=settings.postgres_pool_timeout_seconds,
            connect_args={
                "connect_timeout": settings.postgres_connect_timeout_seconds,
            },
        )
    engine = create_engine(settings.postgres_dsn, **engine_options)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Generator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
