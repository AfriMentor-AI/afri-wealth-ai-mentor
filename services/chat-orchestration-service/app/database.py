"""SQLAlchemy engine/session for chat-orchestration-service (svc_chat)."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings
from .observability import instrument_db

settings = get_settings()

_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
# Card O4.3: default pool_size=5/max_overflow=10 (15 total) queued/failed requests
# at 2x pilot concurrency (60 simulated users) — see docs/deployment/o4-3-pilot-load-test-report.md.
# Chat holds its DB session open for the whole request, including the slow
# persona/RAG calls and SSE streaming — unlike goals/progress/insight's quick
# round trips, a chat request can hold a connection for several seconds, so it
# needs a pool sized close to full concurrency, not just headroom over the
# default. Postgres's max_connections was raised to 300 in the staging overlay
# to make room for this (see docker-compose.staging.yml).
_pool_kwargs = (
    {} if settings.database_url.startswith("sqlite") else {"pool_size": 30, "max_overflow": 30}
)
engine = create_engine(
    settings.database_url, connect_args=_connect_args, future=True, **_pool_kwargs
)
instrument_db(engine)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create tables. Real migrations use Alembic; this is for dev/test bootstrap."""
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
