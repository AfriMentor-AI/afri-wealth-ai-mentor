"""C2.1 — cross-encoder reranker and sector/content-type metadata."""
import os

import pytest

os.environ.setdefault("CHROMA_URL", "http://localhost:8100")

from app.services import reranker as rr
from app.services.ingestion import build_chunk_metadata, normalize_sector
from app.services.retrieval import _apply_metadata_filter

# ── Sector normalization ─────────────────────────────────────────────────────

def test_normalize_sector_splits_compound_labels():
    assert normalize_sector("Fashion & Textile") == "fashion,textile"
    assert normalize_sector("FinTech & Payments") == "fintech,payments"
    assert normalize_sector("Consumer Goods & Manufacturing") == "consumer_goods,manufacturing"


def test_normalize_sector_handles_empty():
    assert normalize_sector(None) == ""
    assert normalize_sector("") == ""


def test_build_chunk_metadata_includes_new_fields():
    meta = build_chunk_metadata(
        "d1", "entrepreneur_corpus", "dangote", "NG", "en", 0,
        sector="Manufacturing & Trade", content_type="video_transcript",
    )
    assert meta["sector"] == "manufacturing,trade"
    assert meta["sector_label"] == "Manufacturing & Trade"
    assert meta["content_type"] == "video_transcript"
    # country_code aliases market so either filter key works.
    assert meta["country_code"] == "NG" == meta["market"]


def test_build_chunk_metadata_defaults_are_chroma_safe():
    """ChromaDB rejects None metadata values — every field must be a scalar."""
    meta = build_chunk_metadata("d1", "general", None, None, "en", 0)
    assert all(v is not None for v in meta.values())
    assert meta["sector"] == ""
    assert meta["market"] == "general"

# ── Sector filtering (set-wise) ──────────────────────────────────────────────

def test_sector_filter_matches_any_token():
    meta = {"sector": normalize_sector("Fashion & Textile")}
    assert _apply_metadata_filter({"sector": "fashion"}, meta) is True
    assert _apply_metadata_filter({"sector": "textile"}, meta) is True


def test_sector_filter_rejects_unrelated_sector():
    meta = {"sector": normalize_sector("FinTech & Payments")}
    assert _apply_metadata_filter({"sector": "fashion"}, meta) is False


def test_sector_filter_accepts_list_of_sectors():
    meta = {"sector": normalize_sector("Education & Leadership")}
    assert _apply_metadata_filter({"sector": ["fashion", "education"]}, meta) is True
    assert _apply_metadata_filter({"sector": ["fashion", "fintech"]}, meta) is False


def test_sector_filter_normalizes_multiword_request():
    meta = {"sector": normalize_sector("Consumer Goods & Manufacturing")}
    assert _apply_metadata_filter({"sector": "consumer goods"}, meta) is True


def test_combined_sector_and_country_filter():
    meta = build_chunk_metadata(
        "d1", "entrepreneur_corpus", "kenneth_ize", "NG", "en", 0,
        sector="Fashion & Textile", content_type="video_transcript",
    )
    assert _apply_metadata_filter({"sector": "fashion", "country_code": "NG"}, meta) is True
    assert _apply_metadata_filter({"sector": "fashion", "country_code": "GH"}, meta) is False

# ── Reranker scoring helpers (no model load) ─────────────────────────────────

def test_figure_bonus_when_query_names_the_entrepreneur():
    chunk = {"content": "He built a commodity trading business.",
             "metadata": {"figure_id": "dangote"}}
    assert rr._affinity_bonus("how did dangote start", chunk) >= rr.FIGURE_BONUS


def test_no_figure_bonus_for_different_entrepreneur():
    chunk = {"content": "Fashion design in Lagos.",
             "metadata": {"figure_id": "kenneth_ize"}}
    assert rr._affinity_bonus("how did dangote start", chunk) == 0.0


def test_expression_bonus_when_register_matches():
    chunk = {"content": "My hustle started small in the market.", "metadata": {}}
    assert rr._affinity_bonus("how to grow my hustle", chunk) == pytest.approx(rr.EXPRESSION_BONUS)


def test_no_expression_bonus_when_chunk_lacks_the_term():
    chunk = {"content": "Standard business advice about capital.", "metadata": {}}
    assert rr._affinity_bonus("how to grow my hustle", chunk) == 0.0


def test_figure_tokens_ignores_short_fragments():
    assert rr._figure_tokens("tara_fela_durotoye") == ["tara", "fela", "durotoye"]
    assert rr._figure_tokens("") == []

# ── Rerank fallback behaviour ────────────────────────────────────────────────

def test_rerank_empty_candidates():
    assert rr.rerank(query="q", expanded_query="q", candidates=[], top_k=3) == []


def test_rerank_disabled_preserves_stage1_order(monkeypatch):
    monkeypatch.setattr(rr, "RERANK_ENABLED", False)
    candidates = [{"content": f"c{i}", "score": 1.0 - i / 10} for i in range(5)]
    out = rr.rerank(query="q", expanded_query="q", candidates=candidates, top_k=3)
    assert [c["content"] for c in out] == ["c0", "c1", "c2"]


def test_rerank_falls_back_when_model_unavailable(monkeypatch):
    monkeypatch.setattr(rr, "RERANK_ENABLED", True)
    monkeypatch.setattr(rr, "get_reranker", lambda: None)
    candidates = [{"content": f"c{i}", "score": 1.0 - i / 10} for i in range(5)]
    out = rr.rerank(query="q", expanded_query="q", candidates=candidates, top_k=2)
    assert [c["content"] for c in out] == ["c0", "c1"]


def test_rerank_falls_back_when_model_raises(monkeypatch):
    class Boom:
        def predict(self, pairs):
            raise RuntimeError("model exploded")

    monkeypatch.setattr(rr, "RERANK_ENABLED", True)
    monkeypatch.setattr(rr, "get_reranker", lambda: Boom())
    candidates = [{"content": "a", "score": 0.9}, {"content": "b", "score": 0.1}]
    out = rr.rerank(query="q", expanded_query="q", candidates=candidates, top_k=2)
    assert [c["content"] for c in out] == ["a", "b"]


def test_rerank_reorders_by_model_score(monkeypatch):
    """A stage-1 loser that the cross-encoder likes must be promoted."""
    class Stub:
        def predict(self, pairs):
            # Second candidate scores far higher despite worse stage-1 rank.
            return [0.1, 9.0]

    monkeypatch.setattr(rr, "RERANK_ENABLED", True)
    monkeypatch.setattr(rr, "get_reranker", lambda: Stub())
    candidates = [
        {"content": "weak but ranked first", "score": 0.9, "metadata": {}},
        {"content": "strong but ranked second", "score": 0.1, "metadata": {}},
    ]
    out = rr.rerank(query="q", expanded_query="q", candidates=candidates, top_k=2)
    assert out[0]["content"] == "strong but ranked second"
    assert out[0]["retrieval_method"] == "hybrid_rrf_rerank"
    assert out[0]["rerank_score"] == 9.0
    assert out[0]["hybrid_score"] == 0.1  # stage-1 score preserved
