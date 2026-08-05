"""
C2.1 Benchmark — Hybrid retrieval accuracy test.
Acceptance criterion: relevant Tier-1 document in top-3 results >= 80% of the time.
"""
import os
import pytest

os.environ.setdefault("CHROMA_URL", "http://localhost:8100")

from app.services.retrieval import (
    _apply_metadata_filter,
    _rrf_score,
    _tokenize,
    retrieve_chunks,
)

# ── Unit tests (no ChromaDB needed) ──────────────────────────────────────────

def test_tokenize():
    assert _tokenize("Hello, World! 123") == ["hello", "world", "123"]
    assert _tokenize("") == []

def test_rrf_score():
    assert _rrf_score(1) > _rrf_score(2) > _rrf_score(10)
    assert 0 < _rrf_score(1) < 1

def test_metadata_filter_pass():
    meta = {"country_code": "NG", "source_origin": "entrepreneur_corpus"}
    assert _apply_metadata_filter({"country_code": "NG"}, meta) is True
    assert _apply_metadata_filter({"country_code": ["NG", "GH"]}, meta) is True

def test_metadata_filter_fail():
    meta = {"country_code": "NG", "source_origin": "entrepreneur_corpus"}
    assert _apply_metadata_filter({"country_code": "ZA"}, meta) is False
    assert _apply_metadata_filter({"country_code": ["ZA", "KE"]}, meta) is False

def test_metadata_filter_none():
    assert _apply_metadata_filter(None, {"country_code": "NG"}) is True

def test_retrieve_chunks_no_collection():
    result = retrieve_chunks(query="test", chroma_collection=None)
    assert result == []

# ── Benchmark tests (requires live ChromaDB + ingested corpus) ────────────────

BENCHMARK_QUERIES = [
    {
        "query": "how did Dangote start his business with no money",
        "expected_figures": ["dangote"],
        "expected_keywords": ["dangote", "commodity", "trading", "nigeria"],
    },
    {
        "query": "how to start a fashion business in Nigeria",
        "expected_figures": ["kenneth_ize", "deola_sagoe", "adenike_ogunlesi", "alakija"],
        "expected_keywords": ["fashion", "design", "nigeria", "textile"],
    },
    {
        "query": "how to save money and build financial discipline",
        "expected_figures": ["arese_ugwu"],
        "expected_keywords": ["save", "budget", "financial", "money"],
    },
    {
        "query": "persistence and resilience in African business",
        "expected_figures": ["masiyiwa", "alakija", "dangote"],
        "expected_keywords": ["resilience", "persist", "challenge", "fight"],
    },
    {
        "query": "women entrepreneurs in Africa building businesses from scratch",
        "expected_figures": ["tara_fela_durotoye", "adenike_ogunlesi", "alakija", "arese_ugwu"],
        "expected_keywords": ["women", "female", "entrepreneur", "business"],
    },
    {
        "query": "FinTech and mobile payments in Nigeria",
        "expected_figures": ["mitchell_elegbe", "shola_akinlade", "aboyeji"],
        "expected_keywords": ["fintech", "payment", "mobile", "nigeria"],
    },
    {
        "query": "how to reinvest profits and grow a small business",
        "expected_figures": ["dangote", "elumelu"],
        "expected_keywords": ["reinvest", "profit", "grow", "business"],
    },
    {
        "query": "mentorship and education for African leaders",
        "expected_figures": ["fred_swaniker", "patrick_awuah", "elumelu"],
        "expected_keywords": ["mentor", "education", "leader", "africa"],
    },
    {
        "query": "wholesale trade pricing and stock management Nigeria market",
        "expected_figures": [],
        "expected_keywords": ["price", "stock", "market", "trade", "wholesale"],
    },
    {
        "query": "African entrepreneur who built from nothing to billionaire",
        "expected_figures": ["dangote", "masiyiwa", "alakija", "elumelu"],
        "expected_keywords": ["built", "started", "nothing", "billion", "africa"],
    },
]


def _collection():
    """Get the live ChromaDB collection. Skip if not available."""
    try:
        from app.db.chroma import get_chroma_collection
        return get_chroma_collection()
    except Exception:
        return None


def _chunk_is_relevant(chunk: dict, query_spec: dict) -> bool:
    """A chunk is relevant if it matches an expected figure OR contains expected keywords."""
    meta = chunk.get("metadata", {})
    content = chunk.get("content", "").lower()

    # Check figure match
    figure = meta.get("figure_id", "")
    if figure and figure in query_spec["expected_figures"]:
        return True

    # Check keyword match (at least 2 keywords must appear)
    keywords = query_spec["expected_keywords"]
    hits = sum(1 for kw in keywords if kw in content)
    return hits >= 2


@pytest.mark.skipif(
    _collection() is None,
    reason="ChromaDB not available — run docker compose up first",
)
def test_hybrid_retrieval_benchmark():
    """
    Acceptance criterion: relevant document in top-3 >= 80% of queries.
    """
    collection = _collection()
    if collection is None or collection.count() == 0:
        pytest.skip("No documents in ChromaDB")

    hits = 0
    total = len(BENCHMARK_QUERIES)
    failures = []

    for spec in BENCHMARK_QUERIES:
        results = retrieve_chunks(
            query=spec["query"],
            top_k=3,
            chroma_collection=collection,
        )
        relevant = any(_chunk_is_relevant(r, spec) for r in results)
        if relevant:
            hits += 1
        else:
            failures.append(spec["query"])

    accuracy = hits / total
    print("Benchmark accuracy: {}/{} = {:.1%}".format(hits, total, accuracy))
    if failures:
        print("Failed queries:")
        for f in failures:
            print("  - " + f)

    assert accuracy >= 0.80, (
        "Hybrid retrieval accuracy " + str(round(accuracy*100,1)) + "% below 80% threshold. "
        f"Failed: {failures}"
    )


@pytest.mark.skipif(
    _collection() is None,
    reason="ChromaDB not available — run docker compose up first",
)
def test_metadata_filter_country_scoping():
    """Acceptance criterion: filtering by country returns correctly scoped results."""
    collection = _collection()
    if collection is None or collection.count() == 0:
        pytest.skip("No documents in ChromaDB")

    results = retrieve_chunks(
        query="business entrepreneurship success",
        top_k=5,
        filters={"market": "NG"},
        chroma_collection=collection,
    )

    assert len(results) > 0, "Expected results for Nigerian filter"
    for r in results:
        assert r["metadata"].get("market") == "NG", (
            f"Expected market=NG but got {r['metadata'].get('market')}"
        )


@pytest.mark.skipif(
    _collection() is None,
    reason="ChromaDB not available — run docker compose up first",
)
def test_retrieval_returns_hybrid_metadata():
    """Results must include hybrid scoring fields."""
    collection = _collection()
    if collection is None or collection.count() == 0:
        pytest.skip("No documents in ChromaDB")

    results = retrieve_chunks(
        query="how to start a business",
        top_k=3,
        chroma_collection=collection,
    )

    assert len(results) > 0
    for r in results:
        assert "score" in r
        assert "dense_score" in r
        assert "bm25_score" in r
        assert r.get("retrieval_method") == "hybrid_rrf_rerank"
