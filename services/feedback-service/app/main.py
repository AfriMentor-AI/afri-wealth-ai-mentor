"""Feedback Service — AfriMentor AI (card O3.3).

Owns NPS-style feedback capture, milestone-triggered survey prompts, and
free-text/voice-note storage matching the Feedback Survey modal. Consumes
`milestone.completed` (emitted by goals-milestones-service) to create a pending
FeedbackPrompt automatically.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .consumer import start_consumer_thread
from .database import init_db
from .observability import instrument
from .routers.feedback import router as feedback_router

settings = get_settings()

SERVICE_NAME = settings.service_name
SERVICE_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_consumer_thread()
    yield


app = FastAPI(
    title="AfriMentor AI — Feedback Service",
    version=SERVICE_VERSION,
    description="NPS surveys, milestone-triggered prompts, and feedback capture (O3.3).",
    lifespan=lifespan,
)

instrument(app, SERVICE_NAME)

app.include_router(feedback_router)


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
        "message": "Feedback Service online",
        "docs": "/docs",
    }
