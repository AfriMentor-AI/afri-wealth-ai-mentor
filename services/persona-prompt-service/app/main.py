"""Persona Prompt Service — AfriMentor AI (cards C1.4, D1.3 & D2.2).

Exposes persona catalogue, session binding, audio preview stub, and
rendered system-prompt endpoint consumed by chat-orchestration-service,
plus the machine-readable CHIOMA persona spec and its assembled prompt.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.loader import PersonaProfileSpec, load_persona_profile
from app.prompts import build_system_prompt

from .config import get_settings
from .observability import instrument
from .routers.personas import router as personas_router

SERVICE_NAME = "persona-prompt-service"
SERVICE_VERSION = "1.0.0"

app = FastAPI(
    title="AfriMentor AI — Persona Prompt Service",
    version=SERVICE_VERSION,
    description="Persona catalogue, session binding, prompt rendering, and profile specs.",
)

instrument(app, SERVICE_NAME)

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
    return {
        "service": SERVICE_NAME,
        "message": "Persona Prompt Service online",
        "docs": "/docs",
    }


@app.get("/personas/chioma", response_model=PersonaProfileSpec, tags=["personas"])
def get_chioma_profile() -> PersonaProfileSpec:
    """Return the canonical CHIOMA target personality profile specification (card C1.4)."""
    try:
        return load_persona_profile()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/personas/chioma/prompt", tags=["personas"])
def get_chioma_prompt() -> dict[str, str]:
    """Return the CHIOMA system prompt assembled from the target spec (card D1.3)."""
    try:
        profile = load_persona_profile()
        prompt = build_system_prompt(profile)
        return {
            "profile_id": profile.profile_id,
            "profile_version": profile.profile_version,
            "system_prompt": prompt,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
