from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings
from .observability import instrument_db

settings = get_settings()

db_url = (
    settings.database_url
    if (settings.database_url and settings.database_url.strip())
    else "sqlite+pysqlite:///./progress_dev.db"
)
_connect_args = (
    {"check_same_thread": False} if db_url.startswith("sqlite") else {}
)
# Card O4.3: default pool_size=5/max_overflow=10 (15 total) queued/failed requests
# at 2x pilot concurrency (60 simulated users) — see docs/deployment/o4-3-pilot-load-test-report.md.
# Sized against Postgres's shared max_connections=100 across all services, not
# maxed out for one service alone.
_pool_kwargs = (
    {} if db_url.startswith("sqlite") else {"pool_size": 10, "max_overflow": 10}
)
engine = create_engine(
    db_url, connect_args=_connect_args, future=True, **_pool_kwargs
)
instrument_db(engine)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()