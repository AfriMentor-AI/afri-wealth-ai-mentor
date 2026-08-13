"""Insight Library Service — AfriMentor AI (card O3.2).

Owns the content catalog (audio/text insight items), search/filter, and
per-user favorites/bookmarks shown on the Insight Library Home/Desktop screens.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .database import SessionLocal, init_db
from .observability import instrument
from .routers.insights import router as insights_router
from .seed import seed_if_empty

settings = get_settings()

SERVICE_NAME = settings.service_name
SERVICE_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="AfriMentor AI — Insight Library Service",
    version=SERVICE_VERSION,
    description="Content catalog, search/filter, and favorites (O3.2).",
    lifespan=lifespan,
)

instrument(app, SERVICE_NAME)

app.include_router(insights_router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "env": settings.env,
    }


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "service": SERVICE_NAME,
        "message": "Insight Library Service online",
        "docs": "/docs",
    }
