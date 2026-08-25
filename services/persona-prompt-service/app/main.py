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


# card C4.4: profile ids gated behind ENABLE_BETA_PERSONAS until promoted to stable.
_BETA_PROFILE_IDS = {"kwame"}


def _check_profile_visible(profile_id: str) -> None:
    if profile_id in _BETA_PROFILE_IDS and not get_settings().enable_beta_personas:
        raise HTTPException(status_code=404, detail="Persona not found")


@app.get("/personas/{profile_id}", response_model=PersonaProfileSpec, tags=["personas"])
def get_persona_profile(profile_id: str) -> PersonaProfileSpec:
    """Return the canonical target personality profile specification for a persona
    (card C1.4 for CHIOMA, generalized under card C4.4 for additional personas)."""
    _check_profile_visible(profile_id)
    try:
        return load_persona_profile(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Persona not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/personas/{profile_id}/prompt", tags=["personas"])
def get_persona_prompt(profile_id: str) -> dict[str, str]:
    """Return the system prompt assembled from a persona's target spec (card D1.3)."""
    _check_profile_visible(profile_id)
    try:
        profile = load_persona_profile(profile_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Persona not found") from exc
    try:
        prompt = build_system_prompt(profile)
        return {
            "profile_id": profile.profile_id,
            "profile_version": profile.profile_version,
            "system_prompt": prompt,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
