"""Pydantic v2 schemas for chat-orchestration-service."""
from __future__ import annotations

import datetime as dt
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


# ── Conversation ──────────────────────────────────────────────────────────────

class ConversationCreate(BaseModel):
    """Body for POST /api/v1/chat/sessions."""
    persona_id: str | None = Field(default=None, description="Resolved in Sprint 2")
    rag_collection: str | None = Field(default=None, description="Resolved in Sprint 3")


class PersonaBindRequest(BaseModel):
    """Body for PATCH /api/v1/chat/sessions/{id}/persona.

    Internal — called by persona-prompt-service.
    """
    persona_id: str


class TagItRequest(BaseModel):
    """Body for POST /api/v1/chat/sessions/{id}/messages/{msg_id}/tag.

    The frontend sends this when the user taps 'Yes, Tag It' on a commitment suggestion.
    goal_id must be the active goal shown on the Goal Milestone Path screen.
    """
    goal_id: str


class TagItResponse(BaseModel):
    commitment_id: str
    goal_id: str
    message_id: str


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    persona_id: str | None
    rag_collection: str | None
    status: str
    total_prompt_tokens: int
    total_completion_tokens: int
    created_at: dt.datetime
    updated_at: dt.datetime


# ── Message ───────────────────────────────────────────────────────────────────

class MessageCreate(BaseModel):
    """Body for POST /api/v1/chat/sessions/{id}/messages."""
    content: str = Field(min_length=1, max_length=4096)


class Citation(BaseModel):
    """A single source-pill shown under a mentor message.

    ``label`` is the human-readable text, e.g. "TEF curriculum" or "AfriMentor corpus".
    """
    label: str


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    role: MessageRole
    content: str
    sequence: int
    is_commitment_candidate: bool
    prompt_tokens: int
    completion_tokens: int
    citations: list[Citation] = []
    created_at: dt.datetime
