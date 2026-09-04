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
    else "sqlite+pysqlite:///./insight_dev.db"
)
_connect_args = (
    {"check_same_thread": False} if db_url.startswith("sqlite") else {}
)
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
