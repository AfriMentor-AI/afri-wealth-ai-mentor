"""Tests for the RAG Corpus Admin backend (card C2.2).

These run against an in-memory SQLite database rather than the live Postgres, so
the filter/export/stats logic is exercised for real without requiring
`docker compose up`. ChromaDB is stubbed where /stats needs it.
"""
from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.db.session import Base
from app.main import app
from app.models.document import Document, DocumentOrigin, DocumentStatus
from app.services import telemetry

client = TestClient(app)
AUTH = {"X-User-Id": "user-test-123", "X-User-Roles": "admin"}
NON_ADMIN_AUTH = {"X-User-Id": "user-test-456"}

# doc_id, title, author, sector, market, content_type, status, chunks, bytes
SEED = [
    ("d1", "Building Dangote Group", "Aliko Dangote", "Manufacturing & Trade",
     "NG", "video_transcript", DocumentStatus.ready, 12, 4000),
    ("d2", "The Smart Money Woman", "Arese Ugwu", "Financial Literacy",
     "NG", "video_transcript", DocumentStatus.ready, 8, 2500),
    ("d3", "Fashion as Industry", "Deola Sagoe", "Fashion & Textile",
     "NG", "video_transcript", DocumentStatus.ready, 5, 1500),
    ("d4", "Leadership in Africa", "Fred Swaniker", "Education & Leadership",
     "GH", "video_transcript", DocumentStatus.ready, 9, 3000),
    ("d5", "Broken Upload", "Unknown Speaker", "Fashion & Manufacturing",
     "KE", "interview_transcript", DocumentStatus.failed, 0, 100),
]


@pytest.fixture
def db_session():
    """In-memory SQLite seeded with the sample catalogue.

    StaticPool keeps every connection pointed at the same in-memory database,
    which SQLite otherwise scopes per-connection.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()

    for i, (doc_id, title, author, sector, market, ctype, status, chunks, size) in enumerate(SEED):
        session.add(Document(
            id=doc_id,
            filename=f"{doc_id}.txt",
            source_origin=DocumentOrigin.entrepreneur_corpus,
            figure_id=author.lower().replace(" ", "_"),
            market=market,
            language="en",
            title=title,
            author=author,
            sector=sector,
            content_type=ctype,
            published_date=date(2026, 1, i + 1),
            source_url=None,
            channel=None,
            byte_size=size,
            status=status,
            chunk_count=chunks,
            # Distinct timestamps so ordering by created_at desc is deterministic.
            created_at=datetime(2026, 1, i + 1, tzinfo=UTC),
            updated_at=datetime(2026, 1, i + 1, tzinfo=UTC),
        ))
    session.commit()

    def _override():
        yield session

    app.dependency_overrides[routes.get_db] = _override
    try:
        yield session
    finally:
        app.dependency_overrides.pop(routes.get_db, None)
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def stub_chroma(monkeypatch):
    """Stand in for a live ChromaDB collection with a known vector count."""
    class _Collection:
        name = "afrimentor_corpus"

        def count(self):
            return 34  # sum of SEED chunk counts

    monkeypatch.setattr(routes, "get_chroma_collection", lambda: _Collection())
    return 34


# ── Auth ──────────────────────────────────────────────────────────────────────

def test_export_csv_missing_auth_returns_403():
    # Card O3.5: now admin-gated — with zero headers the role check rejects
    # before the still-missing required X-User-Id is reported, so 403 not 422.
    assert client.get("/api/v1/rag/documents/export.csv").status_code == 403


def test_stats_missing_auth_returns_403():
    assert client.get("/api/v1/rag/stats").status_code == 403


# Card O3.5: these admin-catalogue endpoints used to accept any authenticated
# user (no X-User-Roles check) — a non-admin could list/export/see stats on
# the shared corpus.

def test_list_requires_admin_role(db_session):
    r = client.get("/api/v1/rag/documents", headers=NON_ADMIN_AUTH)
    assert r.status_code == 403


def test_export_csv_requires_admin_role(db_session):
    r = client.get("/api/v1/rag/documents/export.csv", headers=NON_ADMIN_AUTH)
    assert r.status_code == 403


def test_stats_requires_admin_role(db_session, stub_chroma):
    r = client.get("/api/v1/rag/stats", headers=NON_ADMIN_AUTH)
    assert r.status_code == 403


# ── Listing + filters ─────────────────────────────────────────────────────────

def test_list_returns_all_with_total_count_header(db_session):
    r = client.get("/api/v1/rag/documents", headers=AUTH)
    assert r.status_code == 200
    assert len(r.json()) == len(SEED)
    assert r.headers["X-Total-Count"] == str(len(SEED))


def test_list_exposes_new_catalogue_fields(db_session):
    r = client.get("/api/v1/rag/documents?q=Dangote", headers=AUTH)
    doc = r.json()[0]
    assert doc["title"] == "Building Dangote Group"
    assert doc["author"] == "Aliko Dangote"
    assert doc["sector"] == "Manufacturing & Trade"
    assert doc["content_type"] == "video_transcript"
    assert doc["published_date"] == "2026-01-01"
    assert doc["byte_size"] == 4000


def test_filter_by_market(db_session):
    r = client.get("/api/v1/rag/documents?market=NG", headers=AUTH)
    assert len(r.json()) == 3
    assert {d["market"] for d in r.json()} == {"NG"}


def test_filter_by_status(db_session):
    r = client.get("/api/v1/rag/documents?status=failed", headers=AUTH)
    assert [d["id"] for d in r.json()] == ["d5"]


def test_filter_by_content_type(db_session):
    r = client.get("/api/v1/rag/documents?content_type=interview_transcript", headers=AUTH)
    assert [d["id"] for d in r.json()] == ["d5"]


def test_filter_by_sector_matches_compound_labels(db_session):
    """sector=fashion must hit both "Fashion & Textile" and "Fashion & Manufacturing"."""
    r = client.get("/api/v1/rag/documents?sector=fashion", headers=AUTH)
    assert {d["id"] for d in r.json()} == {"d3", "d5"}


def test_search_matches_title_and_author(db_session):
    by_title = client.get("/api/v1/rag/documents?q=Smart Money", headers=AUTH).json()
    assert [d["id"] for d in by_title] == ["d2"]

    by_author = client.get("/api/v1/rag/documents?q=Swaniker", headers=AUTH).json()
    assert [d["id"] for d in by_author] == ["d4"]


def test_search_is_case_insensitive(db_session):
    assert len(client.get("/api/v1/rag/documents?q=dangote", headers=AUTH).json()) == 1


def test_filters_combine(db_session):
    r = client.get("/api/v1/rag/documents?market=NG&status=ready&sector=fashion", headers=AUTH)
    assert [d["id"] for d in r.json()] == ["d3"]


def test_pagination_limits_body_but_not_total_count(db_session):
    r = client.get("/api/v1/rag/documents?limit=2", headers=AUTH)
    assert len(r.json()) == 2
    # The header reports the full filtered set, not the page.
    assert r.headers["X-Total-Count"] == str(len(SEED))


def test_offset_walks_the_result_set(db_session):
    first = client.get("/api/v1/rag/documents?limit=2", headers=AUTH).json()
    second = client.get("/api/v1/rag/documents?limit=2&offset=2", headers=AUTH).json()
    assert {d["id"] for d in first} & {d["id"] for d in second} == set()


def test_limit_over_maximum_rejected(db_session):
    assert client.get("/api/v1/rag/documents?limit=501", headers=AUTH).status_code == 422


# ── CSV export ────────────────────────────────────────────────────────────────

def _parse_csv(body: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(body)))


def test_export_csv_headers_and_row_count(db_session):
    r = client.get("/api/v1/rag/documents/export.csv", headers=AUTH)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]

    rows = _parse_csv(r.text)
    assert rows[0] == routes.CSV_COLUMNS
    assert len(rows) == len(SEED) + 1  # header + one row per document


def test_export_csv_row_values(db_session):
    rows = _parse_csv(client.get("/api/v1/rag/documents/export.csv?q=Dangote", headers=AUTH).text)
    assert len(rows) == 2
    row = dict(zip(rows[0], rows[1]))
    assert row["title"] == "Building Dangote Group"
    assert row["author"] == "Aliko Dangote"
    assert row["sector"] == "Manufacturing & Trade"
    assert row["market"] == "NG"
    assert row["published_date"] == "2026-01-01"


def test_export_csv_honours_filters(db_session):
    rows = _parse_csv(client.get("/api/v1/rag/documents/export.csv?market=NG", headers=AUTH).text)
    assert len(rows) == 4  # header + 3 Nigerian documents


def test_export_csv_ignores_limit(db_session):
    """An export is the whole filtered set — limit is a table concern, not an export one."""
    rows = _parse_csv(client.get("/api/v1/rag/documents/export.csv?limit=1", headers=AUTH).text)
    assert len(rows) == len(SEED) + 1


# ── Stats ─────────────────────────────────────────────────────────────────────

def test_stats_document_counts(db_session, stub_chroma):
    body = client.get("/api/v1/rag/stats", headers=AUTH).json()
    docs = body["documents"]
    assert docs["total"] == len(SEED)
    assert sum(docs["by_status"].values()) == docs["total"]
    assert docs["by_status"] == {"ready": 4, "failed": 1}
    assert docs["by_country"] == {"NG": 3, "GH": 1, "KE": 1}
    assert docs["total_chunks"] == sum(s[7] for s in SEED)


def test_stats_index_size(db_session, stub_chroma):
    body = client.get("/api/v1/rag/stats", headers=AUTH).json()
    size = body["index_size"]
    assert size["document_bytes"] == sum(s[8] for s in SEED)
    assert size["vector_bytes"] == stub_chroma * routes.EMBED_DIM * routes.BYTES_PER_FLOAT
    assert size["total_bytes"] == size["document_bytes"] + size["vector_bytes"]
    # The vector figure is computed, not measured — the response says so.
    assert size["vector_bytes_is_estimate"] is True


def test_stats_vector_count(db_session, stub_chroma):
    vectors = client.get("/api/v1/rag/stats", headers=AUTH).json()["vectors"]
    assert vectors["active_count"] == stub_chroma
    assert vectors["collection"] == "afrimentor_corpus"
    assert vectors["embedding_dim"] == routes.EMBED_DIM


def test_stats_degrades_when_chroma_unavailable(db_session, monkeypatch):
    """Postgres figures must survive a ChromaDB outage rather than 500ing."""
    def _boom():
        raise ConnectionError("chroma unreachable")

    monkeypatch.setattr(routes, "get_chroma_collection", _boom)
    r = client.get("/api/v1/rag/stats", headers=AUTH)

    assert r.status_code == 200
    body = r.json()
    assert body["vectors"]["active_count"] is None
    assert body["index_size"]["vector_bytes"] is None
    assert body["index_size"]["total_bytes"] is None
    # Real Postgres numbers still reported.
    assert body["documents"]["total"] == len(SEED)
    assert body["index_size"]["document_bytes"] == sum(s[8] for s in SEED)


# ── Latency telemetry ─────────────────────────────────────────────────────────

def test_latency_snapshot_empty_window():
    telemetry.reset()
    snapshot = telemetry.latency_snapshot()
    assert snapshot["sample_count"] == 0
    assert snapshot["p50"] == 0.0


def test_latency_snapshot_percentiles():
    telemetry.reset()
    for value in range(1, 101):
        telemetry.record_query_latency(float(value))

    snapshot = telemetry.latency_snapshot()
    assert snapshot["sample_count"] == 100
    assert snapshot["p50"] == 50.0
    assert snapshot["p95"] == 95.0
    assert snapshot["mean"] == 50.5


def test_latency_window_is_bounded():
    telemetry.reset()
    for value in range(telemetry.LATENCY_WINDOW + 50):
        telemetry.record_query_latency(float(value))
    assert telemetry.latency_snapshot()["sample_count"] == telemetry.LATENCY_WINDOW


def test_stats_reports_latency_samples(db_session, stub_chroma):
    telemetry.reset()
    telemetry.record_query_latency(40.0)
    telemetry.record_query_latency(60.0)

    latency = client.get("/api/v1/rag/stats", headers=AUTH).json()["latency_ms"]
    assert latency["sample_count"] == 2
    assert latency["mean"] == 50.0
