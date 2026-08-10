"""SQLAlchemy engine and session factory (card C2.3).

``DATABASE_URL`` is supplied by docker-compose as a Postgres DSN
(``postgresql+psycopg://…/svc_research``). It falls back to a local SQLite file so
``scripts/run_trait_fit.py`` and the test suite run standalone with no server.

Both :data:`engine` and :data:`SessionLocal` are module-level globals on purpose:
``scripts.run_trait_fit`` imports them by name, and the e2e tests monkeypatch that
module's references to swap in an in-memory SQLite database.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DATABASE_URL = "sqlite:///./research_evaluation.db"

DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

# SQLite rejects cross-thread connection reuse by default; FastAPI and the CLI
# both hand connections between threads, so the check is disabled for SQLite only.
_connect_args: dict[str, object] = (
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    # Postgres connections can be culled by the pooler between experiment runs;
    # pre-ping trades a round trip for not raising on a dead connection.
    pool_pre_ping=not DATABASE_URL.startswith("sqlite"),
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a session that is always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
