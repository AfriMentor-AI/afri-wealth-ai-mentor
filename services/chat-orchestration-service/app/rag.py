"""RAG Corpus Service client for chat-orchestration-service.

Calls POST /api/v1/rag/query on the rag-corpus-service and returns a list of
RagResult objects. Falls back to an empty list when the service URL is not
configured or the request fails, so the chat path is never blocked by RAG
unavailability.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Maximum number of chunks to retrieve per turn. Kept small to stay within
# the LLM context budget (LLM_MAX_TOKENS default 512).
RAG_TOP_K = 3


@dataclass(frozen=True)
class RagResult:
    content: str
    # Human-readable label for the source-pill, e.g. "TEF curriculum"
    source_label: str
    score: float


def _source_label(metadata: dict) -> str:
    """Derive a human-readable citation label from chunk metadata.

    Priority: title > channel > source_origin > filename > "AfriMentor corpus".
    The label is what appears in the 'Based on …' source pill on the Chat screen.
    """
    for key in ("title", "channel", "source_origin", "filename"):
        value = metadata.get(key)
        if value and str(value).strip():
            return str(value).strip()
    return "AfriMentor corpus"


async def retrieve(
    query: str,
    *,
    collection: str | None = None,
    top_k: int = RAG_TOP_K,
) -> list[RagResult]:
    """Query the RAG corpus service and return ranked chunks.

    Args:
        query: The user's message text used as the retrieval query.
        collection: Optional collection/filter hint (reserved for Sprint 3
            per-persona corpus partitioning; unused today).
        top_k: Maximum number of chunks to return.

    Returns:
        List of RagResult, empty when RAG is unavailable or corpus is empty.
    """
    if not settings.rag_service_url:
        logger.debug("RAG_SERVICE_URL not set — skipping retrieval")
        return []

    payload: dict = {"query": query, "top_k": top_k}
    if collection:
        payload["filters"] = {"collection": collection}

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(
                f"{settings.rag_service_url}/api/v1/rag/query",
                json=payload,
                headers={"X-User-Id": "chat-orchestration-service"},
            )
            response.raise_for_status()
    except Exception as exc:
        logger.warning("RAG retrieval failed: %s", exc)
        return []

    data = response.json()
    results: list[RagResult] = []
    for chunk in data.get("results", []):
        meta = chunk.get("metadata") or {}
        results.append(
            RagResult(
                content=chunk.get("content", ""),
                source_label=_source_label(meta),
                score=float(chunk.get("score", 0.0)),
            )
        )
    return results
