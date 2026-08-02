"""
Ingestion pipeline: text -> chunks -> embeddings -> ChromaDB.
C1.1: chunking + ChromaDB write wired. Embedding uses ChromaDB's
default all-MiniLM-L6-v2 model (no external API key needed in dev).
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
    Chunk text and write to ChromaDB.
    Returns number of chunks written.
    If chroma_collection is None (tests), skips the Chroma write.
    """
    chunks = chunk_text(text)
    if not chunks:
        return 0

    ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
    metadatas = [
        build_chunk_metadata(doc_id, source_origin, figure_id, market, language, i)
        for i in range(len(chunks))
    ]

    if chroma_collection is not None:
        chroma_collection.add(
            documents=chunks,
            ids=ids,
            metadatas=metadatas,
        )

    return len(chunks)
