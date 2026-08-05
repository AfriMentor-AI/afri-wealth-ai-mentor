from __future__ import annotations

import logging
import os
import re

from rank_bm25 import BM25Okapi

from app.services.lexicon import expand_query
from app.services.reranker import rerank

logger = logging.getLogger(__name__)

TOP_K = int(os.getenv("RAG_TOP_K", "5"))
DENSE_WEIGHT = float(os.getenv("RAG_DENSE_WEIGHT", "0.7"))
BM25_WEIGHT = float(os.getenv("RAG_BM25_WEIGHT", "0.3"))
RRF_K = int(os.getenv("RAG_RRF_K", "60"))
CANDIDATE_MULTIPLIER = int(os.getenv("RAG_CANDIDATE_MULTIPLIER", "4"))


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer for BM25."""
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


def _rrf_score(rank: int, k: int = RRF_K) -> float:
    """Reciprocal Rank Fusion score for a given rank (1-indexed)."""
    return 1.0 / (k + rank)


# Metadata keys whose stored value is a comma-joined token set rather than a
# single scalar. A filter matches if ANY requested token is present, so
# sector="fashion" hits both "Fashion & Textile" and "Fashion & Manufacturing".
MULTI_VALUE_KEYS = {"sector"}


def _as_token_set(value: str | None) -> set[str]:
    if not value:
        return set()
    return {t.strip().lower() for t in str(value).split(",") if t.strip()}


def _apply_metadata_filter(
    filters: dict | None,
    meta: dict,
) -> bool:
    """Return True if chunk metadata passes all filters.

    Scalar keys match by equality; a list value means "any of". Keys in
    MULTI_VALUE_KEYS hold comma-joined token sets and match on set overlap.
    """
    if not filters:
        return True
    for key, value in filters.items():
        wanted = value if isinstance(value, list) else [value]

        if key in MULTI_VALUE_KEYS:
            stored = _as_token_set(meta.get(key))
            requested = {str(v).strip().lower().replace(" ", "_") for v in wanted}
            if not (stored & requested):
                return False
            continue

        if meta.get(key) not in wanted:
            return False
    return True


def retrieve_chunks(
    *,
    query: str,
    top_k: int = TOP_K,
    filters: dict | None = None,
    chroma_collection,
) -> list[dict]:
    """Hybrid BM25 + dense retrieval with RRF score fusion and reranking.

    Strategy:
    1. Expand query with African English / local expression equivalents.
    2. Fetch CANDIDATE_MULTIPLIER * top_k candidates from ChromaDB (dense).
    3. Apply metadata pre-filter on the candidate pool.
    4. Build a BM25 index over the filtered candidate pool.
    5. Score candidates with BM25.
    6. Fuse dense and BM25 ranks using Reciprocal Rank Fusion.
    7. Rerank with cross-encoder (query + chunk content jointly scored).
    8. Return the top_k highest-scoring chunks with merged metadata.
    """
    if chroma_collection is None:
        return []

    try:
        total = chroma_collection.count()
        if total == 0:
            return []

        # Step 1: Expand query with local expression equivalents
        expanded = expand_query(query)

        # Step 2: Fetch candidate pool from ChromaDB (dense retrieval)
        n_candidates = min(top_k * CANDIDATE_MULTIPLIER, total)
        raw = chroma_collection.query(
            query_texts=[expanded],
            n_results=n_candidates,
            include=["documents", "metadatas", "distances", "embeddings"],
        )

        if not raw or not raw.get("documents") or not raw["documents"][0]:
            return []

        docs = raw["documents"][0]
        ids = raw["ids"][0]
        metas = raw["metadatas"][0]
        distances = raw["distances"][0]

        # Step 3: Apply metadata pre-filter
        filtered = [
            (doc, chunk_id, meta, dist)
            for doc, chunk_id, meta, dist in zip(docs, ids, metas, distances, strict=False)
            if _apply_metadata_filter(filters, meta)
        ]

        if not filtered:
            logger.warning(
                "All %d candidates filtered out by metadata filters: %s", len(docs), filters
            )
            return []

        f_docs, f_ids, f_metas, f_dists = zip(*filtered, strict=False)

        # Step 4 & 5: BM25 scoring over filtered candidate pool
        tokenized_corpus = [_tokenize(d) for d in f_docs]
        tokenized_query = _tokenize(expanded)

        bm25 = BM25Okapi(tokenized_corpus)
        bm25_scores = bm25.get_scores(tokenized_query)

        # Step 6: RRF fusion
        # Dense ranks: lower distance = better rank
        dense_ranked = sorted(range(len(f_docs)), key=lambda i: f_dists[i])
        # BM25 ranks: higher score = better rank
        bm25_ranked = sorted(range(len(f_docs)), key=lambda i: bm25_scores[i], reverse=True)

        dense_rank_map = {idx: rank + 1 for rank, idx in enumerate(dense_ranked)}
        bm25_rank_map = {idx: rank + 1 for rank, idx in enumerate(bm25_ranked)}

        fused_scores: dict[int, float] = {}
        for i in range(len(f_docs)):
            dense_rrf = _rrf_score(dense_rank_map[i]) * DENSE_WEIGHT
            bm25_rrf = _rrf_score(bm25_rank_map[i]) * BM25_WEIGHT
            fused_scores[i] = dense_rrf + bm25_rrf

        # Sort by fused score and build candidate dicts for reranking
        top_indices = sorted(fused_scores, key=lambda i: fused_scores[i], reverse=True)
        candidates = []
        for i in top_indices:
            dense_score = round(1.0 - f_dists[i], 4) if f_dists[i] is not None else None
            candidates.append({
                "chunk_id": f_ids[i],
                "content": f_docs[i],
                "metadata": f_metas[i],
                "score": round(fused_scores[i], 6),
                "dense_score": dense_score,
                "bm25_score": round(float(bm25_scores[i]), 4),
                "retrieval_method": "hybrid_rrf",
            })

        # Step 7 & 8: Rerank with cross-encoder and return top_k
        return rerank(
            query=query,
            expanded_query=expanded,
            candidates=candidates,
            top_k=top_k,
        )

    except Exception as e:
        logger.error("Hybrid retrieval error: %s", e, exc_info=True)
        return []
