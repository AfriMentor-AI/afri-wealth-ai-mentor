"""
Ingestion pipeline: text -> chunks -> embeddings -> ChromaDB.
Sprint 1: chunking logic is production-ready.
Chroma write is stubbed until C2.1 wires the real embedding model.
"""
from __future__ import annotations
import os
from langchain.text_splitter import RecursiveCharacterTextSplitter

CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "600"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "80"))

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)

def chunk_text(text: str) -> list[str]:
    """Split raw text into overlapping chunks."""
    return _splitter.split_text(text)

def build_chunk_metadata(
    doc_id: str,
    source_origin: str,
    figure_id: str | None,
    market: str | None,
    language: str,
    chunk_index: int,
) -> dict:
    """Build the metadata dict stored alongside each vector in ChromaDB."""
    return {
        "doc_id": doc_id,
        "source_origin": source_origin,
        "figure_id": figure_id or "",
        "market": market or "general",
        "language": language,
        "chunk_index": chunk_index,
    }

def ingest_document(
    *,
    doc_id: str,
    text: str,
    source_origin: str,
    figure_id: str | None,
    market: str | None,
    language: str,
    chroma_collection,
) -> int:
    """
    Chunk text and write embeddings to ChromaDB.
    Returns number of chunks written.

    Sprint 1: Chroma write is STUBBED.
    Replace the stub block with real embedding call in C2.1.
    """
    chunks = chunk_text(text)
    if not chunks:
        return 0

    ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
    metadatas = [
        build_chunk_metadata(doc_id, source_origin, figure_id, market, language, i)
        for i in range(len(chunks))
    ]

    # --- STUB: replace with real embedding in Sprint 2 (C2.1) ---
    # chroma_collection.add(documents=chunks, ids=ids, metadatas=metadatas)
    # ---

    return len(chunks)
