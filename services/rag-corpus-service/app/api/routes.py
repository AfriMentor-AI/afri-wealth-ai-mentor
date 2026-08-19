from __future__ import annotations

import csv
import io
import time
from collections.abc import Iterator
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.chroma import get_chroma_collection
from app.db.session import get_db
from app.models.document import Document, DocumentOrigin, DocumentStatus
from app.services.ingestion import ingest_document
from app.services.retrieval import retrieve_chunks
from app.services.telemetry import latency_snapshot, record_query_latency

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])

# Dimension of the all-MiniLM-L6-v2 embeddings ChromaDB computes by default,
# stored as float32. Used to estimate vector-index size in /stats.
EMBED_DIM = 384
BYTES_PER_FLOAT = 4


_CONSOLE_ROLES = {"admin", "researcher", "lead_architect"}


def _require_admin(x_user_roles: str = Header("", alias="X-User-Roles")) -> None:
    """Gate on the RAG Corpus Admin screen's operations (cards O3.5/O4.2).

    These endpoints previously only checked X-User-Id — any authenticated user
    could ingest/delete/export the shared corpus or pull its stats. The gateway
    forwards verified JWT roles as X-User-Roles (same trust boundary _get_user
    relies on for X-User-Id), so this mirrors that pattern rather than inventing
    a new one. POST /query (retrieval for chat) is deliberately NOT gated here —
    every user needs that for normal chat/RAG use. Widened for O4.2's Admin
    Research Console, which Lead Architect/Researcher accounts use alongside
    admin — see docs/deployment/rbac-console-roles.md.
    """
    roles = {r.strip() for r in x_user_roles.split(",") if r.strip()}
    if not roles & _CONSOLE_ROLES:
        raise HTTPException(status_code=403, detail="admin, researcher, or lead_architect required")

# ── Schemas ───────────────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    filename: str = Field(..., max_length=255)
    text: str = Field(..., min_length=1)
    source_origin: DocumentOrigin = DocumentOrigin.general
    figure_id: str | None = Field(None, max_length=100)
    market: str | None = Field(None, max_length=10)
    sector: str | None = Field(None, max_length=100)
    content_type: str | None = Field(None, max_length=50)
    language: str = Field("en", max_length=10)
    # Catalogue metadata surfaced by the admin screen (card C2.2).
    title: str | None = Field(None, max_length=500)
    author: str | None = Field(None, max_length=200)
    published_date: date | None = None
    source_url: str | None = Field(None, max_length=1000)
    channel: str | None = Field(None, max_length=200)

    @field_validator(
        "figure_id", "market", "sector", "content_type",
        "title", "author", "source_url", "channel", "published_date",
        mode="before",
    )
    @classmethod
    def _empty_string_to_none(cls, v):
        """Treat "" as absent.

        The Tier-1 corpus records carry empty strings rather than nulls for
        unset metadata (url and date are empty in 20 of 21 records), and an
        empty string would otherwise fail date parsing or store as "".
        """
        if isinstance(v, str) and not v.strip():
            return None
        return v


class DocumentResponse(BaseModel):
    id: str
    filename: str
    source_origin: str
    figure_id: str | None
    market: str | None
    language: str
    status: str
    chunk_count: int
    error_message: str | None
    created_at: str
    updated_at: str
    title: str | None
    author: str | None
    sector: str | None
    content_type: str | None
    published_date: str | None
    source_url: str | None
    channel: str | None
    byte_size: int

    @classmethod
    def from_orm(cls, doc: Document) -> DocumentResponse:
        return cls(
            id=doc.id,
            filename=doc.filename,
            source_origin=doc.source_origin.value,
            figure_id=doc.figure_id,
            market=doc.market,
            language=doc.language,
            status=doc.status.value,
            chunk_count=doc.chunk_count,
            error_message=doc.error_message,
            created_at=doc.created_at.isoformat(),
            updated_at=doc.updated_at.isoformat(),
            title=doc.title,
            author=doc.author,
            sector=doc.sector,
            content_type=doc.content_type,
            published_date=doc.published_date.isoformat() if doc.published_date else None,
            source_url=doc.source_url,
            channel=doc.channel,
            byte_size=doc.byte_size or 0,
        )

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(5, ge=1, le=20)
    filters: dict | None = None

class QueryResponse(BaseModel):
    query: str
    results: list[dict]
    total: int

# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/documents", status_code=201, response_model=DocumentResponse)
def ingest(
    body: IngestRequest,
    db: Session = Depends(get_db),
    x_user_id: str = Header(..., alias="X-User-Id"),
    _admin: None = Depends(_require_admin),
):
    """Ingest a document into the RAG corpus."""
    doc = Document(
        filename=body.filename,
        source_origin=body.source_origin,
        figure_id=body.figure_id,
        market=body.market,
        language=body.language,
        status=DocumentStatus.processing,
        title=body.title,
        author=body.author,
        sector=body.sector,
        content_type=body.content_type,
        published_date=body.published_date,
        source_url=body.source_url,
        channel=body.channel,
        byte_size=len(body.text.encode("utf-8")),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        collection = get_chroma_collection()
        chunk_count = ingest_document(
            doc_id=doc.id,
            text=body.text,
            source_origin=body.source_origin.value,
            figure_id=body.figure_id,
            market=body.market,
            language=body.language,
            sector=body.sector,
            content_type=body.content_type,
            chroma_collection=collection,
        )
        doc.chunk_count = chunk_count
        doc.status = DocumentStatus.ready
    except Exception as exc:
        doc.status = DocumentStatus.failed
        doc.error_message = str(exc)[:500]

    db.commit()
    db.refresh(doc)
    return DocumentResponse.from_orm(doc)


def _apply_filters(
    query,
    *,
    q: str | None,
    sector: str | None,
    market: str | None,
    status: DocumentStatus | None,
    content_type: str | None,
):
    """Apply the admin catalogue filters to a Document query.

    Shared by GET /documents and GET /documents/export.csv so the exported rows
    always match what the table is showing.
    """
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Document.title.ilike(like),
                Document.author.ilike(like),
                Document.filename.ilike(like),
            )
        )
    if sector:
        # Substring match: stored labels are compound ("Fashion & Textile"), so
        # sector=fashion should hit both that and "Fashion & Manufacturing".
        query = query.filter(Document.sector.ilike(f"%{sector}%"))
    if market:
        query = query.filter(Document.market == market)
    if status:
        query = query.filter(Document.status == status)
    if content_type:
        query = query.filter(Document.content_type == content_type)
    return query


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents(
    response: Response,
    db: Session = Depends(get_db),
    x_user_id: str = Header(..., alias="X-User-Id"),
    _admin: None = Depends(_require_admin),
    q: str | None = Query(None, max_length=200, description="Search title, author, filename"),
    sector: str | None = Query(None, max_length=100),
    market: str | None = Query(None, max_length=10),
    status: DocumentStatus | None = Query(None),
    content_type: str | None = Query(None, max_length=50),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List ingested documents, newest first.

    The unpaginated total for the current filter set is returned in the
    ``X-Total-Count`` header; the body stays a plain list.
    """
    query = _apply_filters(
        db.query(Document),
        q=q, sector=sector, market=market, status=status, content_type=content_type,
    )
    total = query.count()
    docs = (
        query.order_by(Document.created_at.desc()).offset(offset).limit(limit).all()
    )
    response.headers["X-Total-Count"] = str(total)
    return [DocumentResponse.from_orm(d) for d in docs]


# Column order for the admin CSV export. Declared once so the header row and
# the value rows cannot drift apart.
CSV_COLUMNS = [
    "id", "title", "author", "sector", "market", "content_type",
    "published_date", "status", "chunk_count", "byte_size", "language",
    "source_origin", "figure_id", "channel", "source_url", "filename",
    "created_at",
]


@router.get("/documents/export.csv", response_class=StreamingResponse)
def export_documents_csv(
    db: Session = Depends(get_db),
    x_user_id: str = Header(..., alias="X-User-Id"),
    _admin: None = Depends(_require_admin),
    q: str | None = Query(None, max_length=200),
    sector: str | None = Query(None, max_length=100),
    market: str | None = Query(None, max_length=10),
    status: DocumentStatus | None = Query(None),
    content_type: str | None = Query(None, max_length=50),
):
    """Export the filtered document catalogue as CSV.

    Takes the same filters as GET /documents but no limit — an export is the
    whole filtered set. Streamed so a large corpus doesn't materialise the
    entire file in memory.
    """
    query = _apply_filters(
        db.query(Document),
        q=q, sector=sector, market=market, status=status, content_type=content_type,
    )
    docs = query.order_by(Document.created_at.desc()).all()

    def rows() -> Iterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        def flush() -> str:
            buffer.seek(0)
            chunk = buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            return chunk

        writer.writerow(CSV_COLUMNS)
        yield flush()
        for doc in docs:
            payload = DocumentResponse.from_orm(doc)
            writer.writerow([getattr(payload, column) for column in CSV_COLUMNS])
            yield flush()

    return StreamingResponse(
        rows(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="rag-corpus.csv"'},
    )


@router.get("/stats", response_model=dict)
def stats(
    db: Session = Depends(get_db),
    x_user_id: str = Header(..., alias="X-User-Id"),
    _admin: None = Depends(_require_admin),
):
    """Index-health figures for the admin stats panel.

    ``vector_bytes`` is an estimate computed from the vector count and embedding
    dimension, not a measured on-disk size; ``document_bytes`` is the real total
    of ingested raw text. Vector fields degrade to null when ChromaDB is
    unreachable rather than failing the whole response.
    """
    total_documents = db.query(func.count(Document.id)).scalar() or 0
    document_bytes = db.query(func.coalesce(func.sum(Document.byte_size), 0)).scalar() or 0
    total_chunks = db.query(func.coalesce(func.sum(Document.chunk_count), 0)).scalar() or 0

    def group_counts(column) -> dict:
        rows = db.query(column, func.count(Document.id)).group_by(column).all()
        return {(key.value if hasattr(key, "value") else key or "unknown"): count
                for key, count in rows}

    vector_count = None
    collection_name = None
    try:
        collection = get_chroma_collection()
        vector_count = collection.count()
        collection_name = collection.name
    except Exception:
        pass  # Chroma down — report null vectors, keep the Postgres figures.

    vector_bytes = (
        vector_count * EMBED_DIM * BYTES_PER_FLOAT if vector_count is not None else None
    )
    return {
        "documents": {
            "total": total_documents,
            "total_chunks": total_chunks,
            "by_status": group_counts(Document.status),
            "by_country": group_counts(Document.market),
            "by_sector": group_counts(Document.sector),
        },
        "vectors": {
            "active_count": vector_count,
            "collection": collection_name,
            "embedding_dim": EMBED_DIM,
        },
        "index_size": {
            "document_bytes": int(document_bytes),
            "vector_bytes": vector_bytes,
            "total_bytes": (
                int(document_bytes) + vector_bytes if vector_bytes is not None else None
            ),
            "vector_bytes_is_estimate": True,
        },
        "latency_ms": latency_snapshot(),
    }


@router.delete("/documents/{doc_id}", response_model=dict)
def delete_document(
    doc_id: str,
    db: Session = Depends(get_db),
    x_user_id: str = Header(..., alias="X-User-Id"),
    _admin: None = Depends(_require_admin),
):
    """Delete a document and its vectors from the corpus."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        collection = get_chroma_collection()
        # Delete all chunks belonging to this document
        collection.delete(where={"doc_id": doc.id})
    except Exception:
        pass  # Chroma delete is best-effort; Postgres delete always proceeds
    db.delete(doc)
    db.commit()
    return {"deleted": doc_id}


@router.post("/query", response_model=QueryResponse)
def query(
    body: QueryRequest,
    db: Session = Depends(get_db),
    x_user_id: str = Header(..., alias="X-User-Id"),
):
    """Retrieve relevant chunks for a query."""
    try:
        collection = get_chroma_collection()
    except Exception:
        collection = None
    started = time.perf_counter()
    results = retrieve_chunks(
        query=body.query,
        top_k=body.top_k,
        filters=body.filters,
        chroma_collection=collection,
    )
    # Feeds the "Inference Latency" tile on the admin screen.
    record_query_latency((time.perf_counter() - started) * 1000)
    return QueryResponse(query=body.query, results=results, total=len(results))
