"""RAG Corpus Service — AfriMentor AI.
C1.1: service skeleton with ingestion pipeline, document metadata,
and retrieval stub. Chroma embedding wired in C2.1.
"""
import logging
import os
import time

from fastapi import FastAPI

from app.api.routes import router
from app.db.session import Base, engine
from app.models.document import Document  # noqa: F401

from .observability import instrument

logger = logging.getLogger(__name__)
SERVICE_NAME = "rag-corpus-service"
SERVICE_VERSION = "0.1.0"

app = FastAPI(
    title="AfriMentor AI - RAG Corpus Service",
    version=SERVICE_VERSION,
    description="Corpus ingestion, chunking, embedding, vector retrieval. See ADR-0001.",
)

instrument(app, SERVICE_NAME)

@app.on_event("startup")
def create_tables():
    max_retries = 10
    for attempt in range(max_retries):
        try:
            Base.metadata.create_all(bind=engine, checkfirst=True)
            logger.info("Database tables created successfully.")
            return
        except Exception as e:
            err_msg = str(e).lower()
            if "already exists" in err_msg or "duplicateobject" in err_msg or "duplicatetable" in err_msg:
                logger.info("Database tables/enums already exist, proceeding.")
                return
            if attempt < max_retries - 1:
                logger.warning("DB not ready, retrying in 3s... (%s)", e)
                time.sleep(3)
            else:
                logger.error("Failed to create tables after %d attempts.", max_retries)
                raise

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
