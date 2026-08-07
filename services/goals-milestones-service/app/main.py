"""Goals & Milestones Service — AfriMentor AI (card D2.3).

Owns goals CRUD and tagged commitments. Receives commitment.tag_suggested
events (via chat-orchestration-service's Tag It endpoint) and persists them
as TaggedCommitment rows linked to the user's active goal, then emits
commitment.created for downstream consumers (progress, notifications, research).
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .database import init_db
from .routers.goals import router as goals_router
from .routers.milestones import router as milestones_router

settings = get_settings()

SERVICE_NAME = settings.service_name
SERVICE_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AfriMentor AI — Goals & Milestones Service",
    version=SERVICE_VERSION,
    description="Goals CRUD and tagged commitments pipeline (D2.3).",
    lifespan=lifespan,
)

app.include_router(goals_router)
app.include_router(milestones_router)


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
    return {"service": SERVICE_NAME, "message": "Goals & Milestones Service online", "docs": "/docs"}
