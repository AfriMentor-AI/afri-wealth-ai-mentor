"""Persona Prompt Service — AfriMentor AI (card D2.2).

Exposes persona catalogue, session binding, audio preview stub, and
rendered system-prompt endpoint consumed by chat-orchestration-service.
"""
from fastapi import FastAPI

from .config import get_settings
from .routers.personas import router as personas_router

SERVICE_NAME = "persona-prompt-service"
SERVICE_VERSION = "1.0.0"

app = FastAPI(
    title="AfriMentor AI — Persona Prompt Service",
    version=SERVICE_VERSION,
    description="Persona catalogue, session binding, and prompt rendering.",
)

app.include_router(personas_router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    settings = get_settings()
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "env": settings.env,
    }


@app.get("/", tags=["meta"])
def root() -> dict:
    return {"service": SERVICE_NAME, "message": "Persona Prompt Service online", "docs": "/docs"}
