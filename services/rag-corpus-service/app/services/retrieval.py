"""
Retrieval pipeline: query -> embed -> ChromaDB similarity search.
Sprint 1: skeleton only. Real hybrid retrieval (BM25 + dense) in C2.1.
"""
from __future__ import annotations
import os

TOP_K = int(os.getenv("RAG_TOP_K", "5"))

def retrieve_chunks(
    *,
    query: str,
    top_k: int = TOP_K,
    filters: dict | None = None,
    chroma_collection,
) -> list[dict]:
    """
    Query ChromaDB for the top-k most relevant chunks.
    Sprint 1: STUBBED — returns empty list.
    Real embedding + BM25 hybrid retrieval in C2.1.
    """
    # --- STUB: replace in Sprint 2 (C2.1) ---
    # results = chroma_collection.query(
    #     query_texts=[query],
    #     n_results=top_k,
    #     where=filters,
    # )
    # return _format_results(results)
    return []
