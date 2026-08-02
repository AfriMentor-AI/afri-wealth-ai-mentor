from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.document import Document, DocumentStatus, DocumentOrigin
from app.services.ingestion import ingest_document
from app.services.retrieval import retrieve_chunks

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])

# ── Schemas ───────────────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    filename: str = Field(..., max_length=255)
    text: str = Field(..., min_length=1)
    source_origin: DocumentOrigin = DocumentOrigin.general
    figure_id: Optional[str] = Field(None, max_length=100)
    market: Optional[str] = Field(None, max_length=10)
    language: str = Field("en", max_length=10)

class DocumentResponse(BaseModel):
    id: str
    filename: str
    source_origin: str
    figure_id: Optional[str]
    market: Optional[str]
    language: str
    status: str
    chunk_count: int
    error_message: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_orm(cls, doc: Document) -> "DocumentResponse":
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
        )

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(5, ge=1, le=20)
    filters: Optional[dict] = None

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
):
    """Ingest a document into the RAG corpus."""
    doc = Document(
        filename=body.filename,
        source_origin=body.source_origin,
        figure_id=body.figure_id,
        market=body.market,
        language=body.language,
        status=DocumentStatus.processing,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        chunk_count = ingest_document(
            doc_id=doc.id,
            text=body.text,
            source_origin=body.source_origin.value,
            figure_id=body.figure_id,
            market=body.market,
            language=body.language,
            chroma_collection=None,
        )
        doc.chunk_count = chunk_count
        doc.status = DocumentStatus.ready
    except Exception as exc:
        doc.status = DocumentStatus.failed
        doc.error_message = str(exc)[:500]

    db.commit()
    db.refresh(doc)
    return DocumentResponse.from_orm(doc)


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents(
    db: Session = Depends(get_db),
    x_user_id: str = Header(..., alias="X-User-Id"),
):
    """List all ingested documents."""
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    return [DocumentResponse.from_orm(d) for d in docs]


@router.delete("/documents/{doc_id}", response_model=dict)
def delete_document(
    doc_id: str,
    db: Session = Depends(get_db),
    x_user_id: str = Header(..., alias="X-User-Id"),
):
    """Delete a document and its vectors from the corpus."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)
    db.commit()
    return {"deleted": doc_id}


@router.post("/query", response_model=QueryResponse)
def query(
    body: QueryRequest,
    db: Session = Depends(get_db),
    x_user_id: str = Header(..., alias="X-User-Id"),
):
    """Retrieve relevant chunks for a query. Sprint 1: returns stub empty list."""
    results = retrieve_chunks(
        query=body.query,
        top_k=body.top_k,
        filters=body.filters,
        chroma_collection=None,
    )
    return QueryResponse(query=body.query, results=results, total=len(results))
