"""Tests for the Tier-2 ingestion refresh (card C3.4).

Covers the schema/API surface added for Tier-2 reference reports:
  - the ``tier`` column (default 1) and its exposure on responses/CSV/stats,
  - ``tier`` validation + filtering,
  - the ``external_id`` idempotent upsert that makes the refresh cadence safe to
    re-run (same row reused, prior vectors dropped) instead of orphaning chunks.

Like test_admin_endpoints.py these run against in-memory SQLite; ChromaDB and the
chunk-writing ``ingest_document`` are stubbed, so the route logic is exercised for
real without ``docker compose up``.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.db.session import Base
from app.main import app
from app.models.document import Document, DocumentOrigin, DocumentStatus

client = TestClient(app)
AUTH = {"X-User-Id": "user-test-123", "X-User-Roles": "admin"}


class _FakeCollection:
    """Stand-in Chroma collection that records delete()s so we can assert the
    upsert drops prior vectors."""

    name = "afrimentor_corpus"

    def __init__(self) -> None:
        self.deleted_where: list[dict] = []

    def delete(self, where=None, **_kw) -> None:
        self.deleted_where.append(where)

    def count(self) -> int:
        return 0


@pytest.fixture
def ingest_env(monkeypatch):
    """Empty SQLite DB + stubbed Chroma/ingest so POST /documents runs for real.

    Yields ``(session, collection, ingest_calls)`` where ingest_calls captures the
    kwargs each ``ingest_document`` call received (to assert tier is threaded).
    """
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()

    collection = _FakeCollection()
    ingest_calls: list[dict] = []

    def _fake_ingest(**kwargs):
        ingest_calls.append(kwargs)
        return 7  # pretend it wrote 7 chunks

    monkeypatch.setattr(routes, "get_chroma_collection", lambda: collection)
    monkeypatch.setattr(routes, "ingest_document", _fake_ingest)

    def _override():
        yield session

    app.dependency_overrides[routes.get_db] = _override
    try:
        yield session, collection, ingest_calls
    finally:
        app.dependency_overrides.pop(routes.get_db, None)
        session.close()
        Base.metadata.drop_all(bind=engine)


def _post(body: dict):
    return client.post("/api/v1/rag/documents", json=body, headers=AUTH)


# ── tier column + defaults ─────────────────────────────────────────────────────

def test_model_default_tier_is_1():
    """A Document built without tier lands on Tier-1 (no backfill needed)."""
    doc = Document(
        filename="x.txt", source_origin=DocumentOrigin.general, status=DocumentStatus.ready
    )
    # SQLAlchemy applies the column default on flush; assert against a session.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    s.add(doc)
    s.commit()
    s.refresh(doc)
    assert doc.tier == 1


def test_ingest_defaults_to_tier_1(ingest_env):
    session, _collection, ingest_calls = ingest_env
    r = _post({"filename": "adhoc.txt", "text": "some content"})
    assert r.status_code == 201
    assert r.json()["tier"] == 1
    assert ingest_calls[-1]["tier"] == 1
    assert session.query(Document).one().tier == 1


def test_ingest_accepts_tier_2(ingest_env):
    session, _collection, ingest_calls = ingest_env
    r = _post({"filename": "report.txt", "text": "reference report", "tier": 2})
    assert r.status_code == 201
    assert r.json()["tier"] == 2
    # tier must reach the chunk-metadata writer, not just the SQL row.
    assert ingest_calls[-1]["tier"] == 2
    assert session.query(Document).one().tier == 2


@pytest.mark.parametrize("bad_tier", [0, 4, -1])
def test_ingest_rejects_out_of_range_tier(ingest_env, bad_tier):
    assert _post({"filename": "x.txt", "text": "t", "tier": bad_tier}).status_code == 422


# ── external_id upsert (the refresh-safety property) ───────────────────────────

def test_ingest_without_external_id_mints_uuid(ingest_env):
    _session, collection, _calls = ingest_env
    doc_id = _post({"filename": "x.txt", "text": "t"}).json()["id"]
    # A minted uuid4, not a caller-supplied id.
    assert "-" in doc_id and len(doc_id) == 36
    # No stable id ⇒ no vector purge attempted.
    assert collection.deleted_where == []


def test_external_id_becomes_primary_key(ingest_env):
    r = _post({"filename": "x.txt", "text": "t", "external_id": "tier2_foo"})
    assert r.status_code == 201
    assert r.json()["id"] == "tier2_foo"


def test_reingest_same_external_id_upserts_single_row(ingest_env):
    session, _collection, _calls = ingest_env
    first = _post(
        {"filename": "r.txt", "text": "v1", "external_id": "tier2_foo", "title": "Draft"}
    )
    second = _post(
        {"filename": "r.txt", "text": "v2", "external_id": "tier2_foo", "title": "Final"}
    )
    assert first.json()["id"] == second.json()["id"] == "tier2_foo"
    # Re-ingest replaced the row rather than adding a second.
    rows = session.query(Document).all()
    assert len(rows) == 1
    assert rows[0].title == "Final"
    assert rows[0].status == DocumentStatus.ready


def test_reingest_drops_prior_vectors(ingest_env):
    _session, collection, _calls = ingest_env
    _post({"filename": "r.txt", "text": "v1", "external_id": "tier2_foo"})
    _post({"filename": "r.txt", "text": "v2", "external_id": "tier2_foo"})
    # Both external_id ingests purge by doc_id (the first matches nothing); the
    # point is a stable-id re-ingest never leaves orphaned vectors behind.
    assert {"doc_id": "tier2_foo"} in collection.deleted_where
    assert collection.deleted_where.count({"doc_id": "tier2_foo"}) == 2


# ── filtering / catalogue / stats ──────────────────────────────────────────────

TIERED = [
    ("t1a", 1), ("t1b", 1), ("t2a", 2), ("t2b", 2), ("t2c", 2),
]


@pytest.fixture
def seeded_db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    for i, (doc_id, tier) in enumerate(TIERED):
        session.add(Document(
            id=doc_id,
            filename=f"{doc_id}.txt",
            source_origin=DocumentOrigin.general,
            market="AFR" if tier == 2 else "NG",
            language="en",
            tier=tier,
            title=f"Doc {doc_id}",
            byte_size=100,
            status=DocumentStatus.ready,
            chunk_count=3,
            created_at=datetime(2026, 1, i + 1, tzinfo=UTC),
            updated_at=datetime(2026, 1, i + 1, tzinfo=UTC),
        ))
    session.commit()

    class _Coll:
        name = "afrimentor_corpus"

        def count(self):
            return 15

    monkeypatch.setattr(routes, "get_chroma_collection", lambda: _Coll())

    def _override():
        yield session

    app.dependency_overrides[routes.get_db] = _override
    try:
        yield session
    finally:
        app.dependency_overrides.pop(routes.get_db, None)
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_list_filter_by_tier(seeded_db):
    r = client.get("/api/v1/rag/documents?tier=2", headers=AUTH)
    assert r.status_code == 200
    assert {d["id"] for d in r.json()} == {"t2a", "t2b", "t2c"}
    assert all(d["tier"] == 2 for d in r.json())

    r1 = client.get("/api/v1/rag/documents?tier=1", headers=AUTH)
    assert {d["id"] for d in r1.json()} == {"t1a", "t1b"}


def test_list_response_exposes_tier(seeded_db):
    doc = client.get("/api/v1/rag/documents?limit=1", headers=AUTH).json()[0]
    assert "tier" in doc


def test_list_rejects_out_of_range_tier(seeded_db):
    assert client.get("/api/v1/rag/documents?tier=9", headers=AUTH).status_code == 422


def test_stats_reports_by_tier(seeded_db):
    body = client.get("/api/v1/rag/stats", headers=AUTH).json()
    # dict int keys serialise to strings over JSON.
    assert body["documents"]["by_tier"] == {"1": 2, "2": 3}


def test_export_csv_includes_tier_column(seeded_db):
    import csv
    import io

    text = client.get("/api/v1/rag/documents/export.csv?tier=2", headers=AUTH).text
    rows = list(csv.reader(io.StringIO(text)))
    assert "tier" in rows[0]
    assert len(rows) == 4  # header + 3 tier-2 docs
    tier_col = rows[0].index("tier")
    assert {row[tier_col] for row in rows[1:]} == {"2"}
