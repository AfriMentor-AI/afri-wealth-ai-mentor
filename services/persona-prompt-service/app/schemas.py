from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class PersonaMeta(BaseModel):
    id: str
    slug: str
    display_name: str
    tagline: str
    sector_tags: list[str]
    template_file: str
    is_base: bool
    status: Literal["stable", "beta"] = "stable"


class SelectPersonaRequest(BaseModel):
    session_id: str
    user_name: str = "friend"
    sector: str = "general"
    country: str = "NG"
    income_bracket: str = "lower_mid"
    language: str = "en"


class SelectPersonaResponse(BaseModel):
    persona_id: str
    session_id: str
    display_name: str


class AudioPreviewResponse(BaseModel):
    persona_id: str
    audio_url: str
    note: str = "Stub — real TTS lands in Sprint 3 via Voice Service"


class PromptResponse(BaseModel):
    persona_id: str
    system_prompt: str
