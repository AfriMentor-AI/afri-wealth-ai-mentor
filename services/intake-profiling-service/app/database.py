"""SQLAlchemy engine/session setup.

Uses DATABASE_URL from config. Defaults to a local SQLite file so the service and its
tests run without Postgres; in Docker it points at the service's `svc_intake` Postgres DB.
"""
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
    else "sqlite+pysqlite:///./intake_dev.db"
)
_connect_args = (
    {"check_same_thread": False} if db_url.startswith("sqlite") else {}
)
engine = create_engine(db_url, connect_args=_connect_args, future=True)
instrument_db(engine)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create tables. Real migrations use Alembic; this is for dev/test bootstrap."""
    from . import models  # noqa: F401  (register models on Base)

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()