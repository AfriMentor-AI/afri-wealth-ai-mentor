"""
Ingestion pipeline: text -> chunks -> embeddings -> ChromaDB.
C1.1: chunking + ChromaDB write wired. Embedding uses ChromaDB's
default all-MiniLM-L6-v2 model (no external API key needed in dev).
"""
from __future__ import annotations
import os
import re
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

_SECTOR_SPLIT_RE = re.compile(r"[&/,]| and ")


def normalize_sector(sector: str | None) -> str:
    """Normalize a compound sector label into comma-joined lowercase tokens.

    Corpus sectors arrive as compound labels ("Fashion & Textile",
    "FinTech & Payments"). ChromaDB metadata values must be scalars, so the
    tokens are stored as a comma-joined string and matched set-wise by
    ``_apply_metadata_filter``. That lets a filter of ``sector="fashion"``
    hit both "Fashion & Textile" and "Fashion & Manufacturing".
    """
    if not sector:
        return ""
    parts = [p.strip().lower().replace(" ", "_") for p in _SECTOR_SPLIT_RE.split(sector)]
    return ",".join(p for p in parts if p)


def build_chunk_metadata(
    doc_id: str,
    source_origin: str,
    figure_id: str | None,
    market: str | None,
    language: str,
    chunk_index: int,
    sector: str | None = None,
    content_type: str | None = None,
) -> dict:
    """Build the metadata dict stored alongside each vector in ChromaDB."""
    return {
        "doc_id": doc_id,
        "source_origin": source_origin,
        "figure_id": figure_id or "",
        "market": market or "general",
        # country_code is an alias of market so filters can use either name.
        "country_code": market or "general",
        "sector": normalize_sector(sector),
        "sector_label": sector or "",
        "content_type": (content_type or "").lower(),
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
    sector: str | None = None,
    content_type: str | None = None,
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
        build_chunk_metadata(
            doc_id,
            source_origin,
            figure_id,
            market,
            language,
            i,
            sector=sector,
            content_type=content_type,
        )
        for i in range(len(chunks))
    ]

    if chroma_collection is not None:
        chroma_collection.add(
            documents=chunks,
            ids=ids,
            metadatas=metadatas,
        )

    return len(chunks)
