"""Personas router — /api/v1/personas."""
from __future__ import annotations

from pathlib import Path

import httpx
import yaml
from fastapi import APIRouter, Header, HTTPException, status

from ..config import get_settings
from ..renderer import render_persona_prompt
from ..schemas import (
    AudioPreviewResponse,
    PersonaMeta,
    PromptResponse,
    SelectPersonaRequest,
    SelectPersonaResponse,
)

router = APIRouter(prefix="/api/v1/personas", tags=["personas"])

_PERSONAS_FILE = Path(__file__).resolve().parents[1] / "prompts" / "personas.yaml"


def _load_personas() -> list[PersonaMeta]:
    data = yaml.safe_load(_PERSONAS_FILE.read_text(encoding="utf-8"))
    return [PersonaMeta(**p) for p in data["personas"]]


def _find_persona(persona_id: str) -> PersonaMeta:
    for p in _load_personas():
        if p.id == persona_id:
            return p
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")


@router.get("", response_model=list[PersonaMeta])
def list_personas() -> list[PersonaMeta]:
    return _load_personas()


@router.post(
    "/{persona_id}/select",
    response_model=SelectPersonaResponse,
    status_code=status.HTTP_200_OK,
)
def select_persona(
    persona_id: str,
    body: SelectPersonaRequest,
    x_user_id: str = Header(..., alias="X-User-Id"),
) -> SelectPersonaResponse:
    """Bind a persona to a chat session.

    Calls PATCH /api/v1/chat/sessions/{session_id}/persona on chat-orchestration-service
    so subsequent LLM turns use the matching prompt template from D1.3.

    Card O3.5: requires and forwards X-User-Id so chat-orchestration-service can
    verify the caller owns `body.session_id` — this endpoint is reachable through
    the gateway's protected `/api/v1/personas` prefix with an attacker-controllable
    session_id, so skipping identity here would let any authenticated user rebind
    another user's session.
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing identity header"
        )
    persona = _find_persona(persona_id)
    settings = get_settings()

    url = f"{settings.chat_service_url}/api/v1/chat/sessions/{body.session_id}/persona"
    try:
        resp = httpx.patch(
            url,
            json={"persona_id": persona_id},
            headers={"X-User-Id": x_user_id},
            timeout=5.0,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Chat service error: {exc.response.text}",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Chat service unreachable: {exc}",
        ) from exc

    return SelectPersonaResponse(
        persona_id=persona_id,
        session_id=body.session_id,
        display_name=persona.display_name,
    )


@router.get("/{persona_id}/preview", response_model=AudioPreviewResponse)
def audio_preview(persona_id: str) -> AudioPreviewResponse:
    """Stub 'Hear an example' — returns placeholder audio URL.

    Real TTS wired in Sprint 3 via Voice Service.
    """
    _find_persona(persona_id)
    return AudioPreviewResponse(
        persona_id=persona_id,
        audio_url=f"https://cdn.placeholder.afrimentor.ai/audio/personas/{persona_id}/preview.mp3",
    )


@router.get("/{persona_id}/prompt", response_model=PromptResponse)
def get_prompt(
    persona_id: str,
    user_name: str = "friend",
    sector: str = "general",
    country: str = "NG",
    income_bracket: str = "lower_mid",
    language: str = "en",
) -> PromptResponse:
    """Render the system prompt for a persona — consumed by chat-orchestration-service."""
    persona = _find_persona(persona_id)
    rendered = render_persona_prompt(
        persona.template_file,
        user_name=user_name,
        sector=sector,
        country=country,
        income_bracket=income_bracket,
        language=language,
    )
    return PromptResponse(persona_id=persona_id, system_prompt=rendered)
