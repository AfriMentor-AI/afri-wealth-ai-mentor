"""RAG Corpus Service — AfriMentor AI.
C1.1: service skeleton with ingestion pipeline, document metadata,
and retrieval stub. Chroma embedding wired in C2.1.
"""
import os
from fastapi import FastAPI
from app.api.routes import router

SERVICE_NAME = "rag-corpus-service"
SERVICE_VERSION = "0.1.0"

app = FastAPI(
    title="AfriMentor AI — RAG Corpus Service",
    version=SERVICE_VERSION,
    description="Corpus ingestion, chunking, embedding, vector retrieval. See ADR-0001.",
)

app.include_router(router)

@app.get("/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "env": os.getenv("APP_ENV", "dev"),
    }

@app.get("/", tags=["meta"])
def root() -> dict:
    return {"service": SERVICE_NAME, "docs": "/docs"}
