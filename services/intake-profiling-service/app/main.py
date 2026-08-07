"""Intake & Profiling Service — AfriMentor AI (card O2.2).

Backs the 4-step Intake flow (sector -> education/time -> constraints -> confirm) and
exposes the resulting diagnostic profile to Chat Orchestration for personalization.
See docs/adr/0001-microservices-architecture.md.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import init_db
from .observability import instrument
from .routers import intake_router, profiles_router

SERVICE_NAME = "intake-profiling-service"
SERVICE_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # dev/test bootstrap; prod uses Alembic migrations
    yield


app = FastAPI(
    title="AfriMentor AI — Intake Profiling Service",
    version=SERVICE_VERSION,
    description="4-step guided intake and the diagnostic profile it produces.",
    lifespan=lifespan,
)

instrument(app, SERVICE_NAME)

app.include_router(intake_router)
app.include_router(profiles_router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness/readiness probe used by docker-compose and the gateway."""
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "env": os.getenv("APP_ENV", "dev"),
    }


@app.get("/", tags=["meta"])
def root() -> dict:
    return {"service": SERVICE_NAME, "message": "Intake Profiling Service online", "docs": "/docs"}
