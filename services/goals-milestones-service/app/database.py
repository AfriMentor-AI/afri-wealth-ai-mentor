from __future__ import annotations

import logging
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings
from .observability import instrument_db

logger = logging.getLogger(__name__)
settings = get_settings()

db_url = (
    settings.database_url
    if (settings.database_url and settings.database_url.strip())
    else "sqlite+pysqlite:///./goals_dev.db"
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


# Columns added to `goals` after its original table creation, in the order
# introduced. This service has no Alembic (see docs/bug-triage-backlog.md
# BUG-03 for the sibling case in research-evaluation-service); startup relies
# entirely on `Base.metadata.create_all`, which creates a brand-new table with
# every column but never ALTERs one that already exists. On a long-lived dev/
# staging Postgres volume whose `goals` table predates these fields, POST
# /api/v1/goals 500s on `UndefinedColumn` — confirmed via O5.1's regression
# pass. Each SQL type string must equal what `create_all` emits for the ORM
# column, so an ALTERed table ends up identical to a fresh one.
_GOALS_ADDED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("description", "TEXT"),
    ("status", "VARCHAR(20)"),
)


def _ensure_goals_columns() -> None:
    """Additively add post-launch columns to an existing `goals` table.
    Postgres only — SQLite (tests, local CLI) gets them from `create_all` on a
    fresh table. Idempotent (`ADD COLUMN IF NOT EXISTS`); wrapped so a locked
    or absent table logs rather than crashing startup.
    """
    if engine.dialect.name != "postgresql":
        return
    try:
        with engine.begin() as conn:
            for name, sql_type in _GOALS_ADDED_COLUMNS:
                conn.exec_driver_sql(
                    f"ALTER TABLE goals ADD COLUMN IF NOT EXISTS {name} {sql_type}"
                )
            # Rows inserted before this column existed have NULL status —
            # backfill to the model's own default so pre-existing goals
            # don't silently disappear from any status-filtered query.
            conn.exec_driver_sql("UPDATE goals SET status = 'active' WHERE status IS NULL")
    except Exception as exc:  # pragma: no cover - defensive: never block startup
        logger.warning("Could not ensure goals columns: %s", exc)


def init_db() -> None:
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _ensure_goals_columns()


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()