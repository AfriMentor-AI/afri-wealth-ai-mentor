"""Progress Gamification Service — AfriMentor AI (card O3.1).

Owns streaks, the action heatmap, and badge/achievement awarding. Reacts to
activity recorded via POST /api/v1/progress/actions (called by chat-orchestration's
daily-action completion flow and other action sources) and emits `badge.earned` for
downstream consumers (notification-service, research-evaluation-service).
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .database import init_db
from .observability import instrument
from .routers.progress import router as progress_router

settings = get_settings()

SERVICE_NAME = settings.service_name
SERVICE_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AfriMentor AI — Progress Gamification Service",
    version=SERVICE_VERSION,
    description="Streaks, action heatmap, and badge/achievement logic (O3.1).",
    lifespan=lifespan,
)

instrument(app, SERVICE_NAME)

app.include_router(progress_router)


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
        "message": "Progress Gamification Service online",
        "docs": "/docs",
    }
