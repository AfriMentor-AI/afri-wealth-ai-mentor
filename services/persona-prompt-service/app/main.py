"""Persona Prompt Service — AfriMentor AI microservice (cards C1.4 & D1.3).

Publishes the machine-readable CHIOMA persona spec and prompt assembly endpoints.
"""

from __future__ import annotations

import os
from fastapi import FastAPI, HTTPException

from app.loader import PersonaProfileSpec, load_persona_profile
from app.prompts import build_system_prompt

SERVICE_NAME = "persona-prompt-service"
SERVICE_VERSION = "0.1.0"

app = FastAPI(
    title="AfriMentor AI — Persona Prompt Service",
    version=SERVICE_VERSION,
    description="Manages versioned persona profile specifications and system prompt assembly.",
)


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
