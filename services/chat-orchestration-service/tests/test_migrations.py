"""Alembic migrations are the deployed schema — these tests hold them to the models.

`create_all` is a dev/test bootstrap (app/database.py), so nothing in the rest of
the suite would notice a migration that drifted from the ORM. Card C2.4 shipped
two columns with no migration at all and had to carry raw DDL in its PR
description; these tests exist so that cannot recur silently.

Every test runs against its own throwaway SQLite file, so they are hermetic and
leave no artifact behind.
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC = Path(sys.executable).parent / "alembic"

#: The revision that predates card C2.4 — the point an already-deployed database
#: is stamped at before upgrading. Pinned deliberately: if someone renumbers the
#: initial revision, the documented deployment procedure in docs/deployment/
#: silently stops working, and this constant is what fails first.
INITIAL_REVISION = "a08ba172d89e"

pytestmark = pytest.mark.skipif(
    not ALEMBIC.exists(), reason="alembic console script not present in this environment"
)


def run_alembic(db_path: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [str(ALEMBIC), *args],
        cwd=SERVICE_ROOT,
        env={"DATABASE_URL": f"sqlite+pysqlite:///{db_path}", "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"alembic {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}"
    )
    return result


def table_columns(db_path: Path, table: str) -> dict[str, tuple[str, int]]:
    """Map column name -> (declared type, notnull flag)."""
    conn = sqlite3.connect(db_path)
    try:
        return {r[1]: (r[2], r[3]) for r in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def test_upgrade_head_leaves_no_drift_from_the_models(tmp_path):
    """The acceptance check: `alembic check` is Alembic's own drift detector.

    If a model gains a column and no migration follows, this fails.
    """
    db = tmp_path / "head.db"
    run_alembic(db, "upgrade", "head")
    result = run_alembic(db, "check")
    assert "No new upgrade operations detected" in (result.stdout + result.stderr)


def test_migrated_schema_matches_create_all(tmp_path):
    """Migrations and the dev/test bootstrap must not describe different databases."""
    from sqlalchemy import create_engine

    from app import models  # noqa: F401  (registers models on Base.metadata)
    from app.database import Base

    migrated = tmp_path / "migrated.db"
    run_alembic(migrated, "upgrade", "head")

    reference = tmp_path / "reference.db"
    Base.metadata.create_all(bind=create_engine(f"sqlite+pysqlite:///{reference}"))

    for table in ("conversations", "messages"):
        assert table_columns(migrated, table) == table_columns(reference, table), (
            f"{table} differs between the migration chain and create_all"
        )


def test_existing_database_upgrades_without_losing_rows(tmp_path):
    """The deployed path: stamp the pre-C2.4 revision, then upgrade.

    Reproduces what an operator runs against a database that already holds
    conversations, which is the case the C2.4 columns could not be applied to by
    `create_all` — it creates missing tables but never adds columns.
    """
    db = tmp_path / "deployed.db"
    run_alembic(db, "upgrade", INITIAL_REVISION)

    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO conversations VALUES "
        "('c1','u1',NULL,NULL,'active',0,0,'2026-08-01','2026-08-01')"
    )
    for i in range(3):
        conn.execute(
            "INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?,?)",
            (f"m{i}", "c1", "user", f"turn {i}", i, 0, 0, 0, "[]", "2026-08-01"),
        )
    conn.commit()
    conn.close()

    run_alembic(db, "upgrade", "head")

    columns = table_columns(db, "messages")
    assert "guardrail_action" in columns
    assert "guardrail_categories" in columns
    # An unscreened turn and an allowed one are different facts (see the C2.4
    # revision docstring), so this column must stay nullable.
    assert columns["guardrail_action"][1] == 0
    # Adding this NOT NULL to a populated table is the step that fails if the
    # backfill is dropped from the revision.
    assert columns["guardrail_categories"][1] == 1

    conn = sqlite3.connect(db)
    try:
        assert conn.execute("select count(*) from messages").fetchone()[0] == 3
        assert (
            conn.execute(
                "select count(*) from messages where guardrail_categories = '[]'"
            ).fetchone()[0]
            == 3
        ), "pre-existing rows were not backfilled"
        assert (
            conn.execute(
                "select count(*) from messages where guardrail_action is null"
            ).fetchone()[0]
            == 3
        ), "turns written before C2.4 must read as unscreened, not as allowed"
    finally:
        conn.close()


def test_downgrade_restores_the_previous_schema(tmp_path):
    """A migration that cannot be undone is a migration nobody dares deploy."""
    db = tmp_path / "roundtrip.db"
    run_alembic(db, "upgrade", "head")
    run_alembic(db, "downgrade", INITIAL_REVISION)

    columns = table_columns(db, "messages")
    assert "guardrail_action" not in columns
    assert "guardrail_categories" not in columns
    # The rest of the table must survive the SQLite batch-mode table rebuild.
    assert "citations" in columns
    assert "content" in columns

    run_alembic(db, "upgrade", "head")
    assert "guardrail_action" in table_columns(db, "messages")


def test_single_migration_head(tmp_path):
    """Two heads mean a silent merge conflict that only shows up at deploy time."""
    result = run_alembic(tmp_path / "unused.db", "heads")
    heads = [line for line in result.stdout.splitlines() if "(head)" in line]
    assert len(heads) == 1, f"expected exactly one head, got: {heads}"
