"""Cross-encoder reranker, tuned for African English and local expressions.

Stage 2 of retrieval. Hybrid RRF (stage 1) is cheap and recall-oriented; it
fuses two rankings but never reads the query and a chunk *together*. The
cross-encoder does, scoring each (query, chunk) pair jointly, which is what
separates a chunk that merely shares vocabulary with the query from one that
actually answers it.

Tuning for the corpus is three adjustments on top of the base model:

1. Query expansion — local expressions are mapped to standard-English
   equivalents before scoring (see ``lexicon``), because the base model is
   trained on standard English web text.
2. Expression bonus — a chunk that uses the same local expression as the query
   is rewarded, recovering register-match that expansion alone would wash out.
3. Figure affinity — a chunk whose ``figure_id`` is named in the query is
   rewarded, since learners often ask about entrepreneurs by name.

The model is loaded lazily and cached process-wide; the first call pays the
load, subsequent calls do not. If the model cannot be loaded (no weights
cached, no network), reranking degrades to a no-op and stage-1 order is
returned unchanged — retrieval keeps working, it is just less precise.
"""
from __future__ import annotations

import logging
import os
import re
import threading

from app.services.lexicon import find_expressions

logger = logging.getLogger(__name__)

RERANK_ENABLED = os.getenv("RAG_RERANK_ENABLED", "true").lower() == "true"
RERANK_MODEL = os.getenv("RAG_RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
RERANK_MAX_LENGTH = int(os.getenv("RAG_RERANK_MAX_LENGTH", "512"))
# Cross-encoder logits are unbounded (roughly -12..+12 here); the bonuses are
# scaled to nudge ordering between near-ties, not to override the model.
EXPRESSION_BONUS = float(os.getenv("RAG_RERANK_EXPRESSION_BONUS", "0.75"))
FIGURE_BONUS = float(os.getenv("RAG_RERANK_FIGURE_BONUS", "1.5"))

_model = None
_model_failed = False
_model_lock = threading.Lock()


def get_reranker():
    """Return the cached CrossEncoder, or None if it cannot be loaded.

    Thread-safe and negative-cached: a failed load is not retried, so a
    request path never repeatedly blocks on a missing model.
    """
    global _model, _model_failed
    if _model is not None or _model_failed:
        return _model
    with _model_lock:
        if _model is not None or _model_failed:
            return _model
        try:
            from sentence_transformers import CrossEncoder

            logger.info("Loading reranker model: %s", RERANK_MODEL)
            _model = CrossEncoder(RERANK_MODEL, max_length=RERANK_MAX_LENGTH)
            logger.info("Reranker model loaded.")
        except Exception as e:
            logger.warning(
                "Reranker unavailable (%s) — falling back to hybrid RRF order.", e
            )
            _model_failed = True
    return _model


def _figure_tokens(figure_id: str) -> list[str]:
    """Split a figure_id ("tara_fela_durotoye") into its name parts."""
    return [t for t in re.split(r"[_\-\s]+", (figure_id or "").lower()) if len(t) > 2]


def _affinity_bonus(query: str, chunk: dict) -> float:
    """Corpus-specific score adjustments layered on the cross-encoder logit."""
    bonus = 0.0
    q_lower = (query or "").lower()
    content = (chunk.get("content") or "").lower()
    meta = chunk.get("metadata") or {}

    # Register match: query and chunk share a local expression.
    q_expr = set(find_expressions(q_lower))
    if q_expr and q_expr & set(find_expressions(content)):
        bonus += EXPRESSION_BONUS

    # Named-figure match: the query mentions this chunk's entrepreneur.
    tokens = _figure_tokens(meta.get("figure_id", ""))
    if tokens and any(re.search(r"\b" + re.escape(t) + r"\b", q_lower) for t in tokens):
        bonus += FIGURE_BONUS

    return bonus


def rerank(
    *,
    query: str,
    expanded_query: str,
    candidates: list[dict],
    top_k: int,
) -> list[dict]:
    """Rescore ``candidates`` with the cross-encoder and return the best ``top_k``.

    ``query`` is the user's original text (used for expression/figure matching,
    which must not see the injected expansion terms); ``expanded_query`` is what
    the cross-encoder scores. Returns the stage-1 order truncated to ``top_k``
    when reranking is disabled or the model is unavailable.
    """
    if not candidates:
        return []
    if not RERANK_ENABLED:
        return candidates[:top_k]

    model = get_reranker()
    if model is None:
        return candidates[:top_k]

    try:
        pairs = [(expanded_query, c.get("content", "")) for c in candidates]
        scores = model.predict(pairs)
    except Exception as e:
        logger.error("Reranking failed (%s) — keeping hybrid RRF order.", e)
        return candidates[:top_k]

    reranked = []
    for candidate, raw in zip(candidates, scores):
        base = float(raw)
        bonus = _affinity_bonus(query, candidate)
        enriched = dict(candidate)
        enriched["rerank_score"] = round(base, 4)
        enriched["rerank_bonus"] = round(bonus, 4)
        enriched["score"] = round(base + bonus, 4)
        # Preserve the pre-rerank fused score for debugging/telemetry.
        enriched["hybrid_score"] = candidate.get("score")
        enriched["retrieval_method"] = "hybrid_rrf_rerank"
        reranked.append(enriched)

    reranked.sort(key=lambda c: c["score"], reverse=True)
    return reranked[:top_k]
