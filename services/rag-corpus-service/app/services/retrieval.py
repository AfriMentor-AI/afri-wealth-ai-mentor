from __future__ import annotations
import os
import logging

logger = logging.getLogger(__name__)
TOP_K = int(os.getenv("RAG_TOP_K", "5"))

def retrieve_chunks(
    *,
    query: str,
    top_k: int = TOP_K,
    filters: dict | None = None,
    chroma_collection,
) -> list[dict]:
    if chroma_collection is None:
        return []
    try:
        results = chroma_collection.query(
            query_texts=[query],
            n_results=min(top_k, chroma_collection.count()),
            where=filters if filters else None,
        )
        chunks = []
        if not results or not results.get("documents"):
            return []
        docs = results["documents"][0]
        ids = results["ids"][0]
        metas = results["metadatas"][0]
        distances = results["distances"][0] if results.get("distances") else [None]*len(docs)
        for doc, chunk_id, meta, dist in zip(docs, ids, metas, distances):
            chunks.append({
                "chunk_id": chunk_id,
                "content": doc,
                "metadata": meta,
                "score": round(1 - dist, 4) if dist is not None else None,
            })
        return chunks
    except Exception as e:
        logger.error("Retrieval error: %s", e)
        return []
