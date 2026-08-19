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


class ConversationSummary(BaseModel):
    """One row of GET /api/v1/chat/sessions — the multi-mentor conversation
    list. Built by hand (not from_attributes) since last_message_preview/at
    come from a join, not a Conversation column."""

    id: str
    persona_id: str | None
    last_message_preview: str | None
    last_message_at: dt.datetime | None
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


class GuardrailAction(str, Enum):
    """Guardrail outcome for a turn (card C2.4)."""

    allow = "allow"
    disclaim = "disclaim"
    block = "block"


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

    # Guardrail outcome (card C2.4). None when the turn predates C2.4 or when
    # GUARDRAILS_ENABLED is off. "disclaim" tells the client the disclaimer is
    # already appended to ``content`` — it must not add a second one.
    guardrail_action: GuardrailAction | None = None
    guardrail_categories: list[str] = []

    created_at: dt.datetime


# ── Daily Action ──────────────────────────────────────────────────────────────

class DailyActionCreate(BaseModel):
    user_id: str
    action_text: str

class DailyActionUpdate(BaseModel):
    is_completed: bool

class DailyActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    action_text: str
    is_completed: bool
    created_at: dt.datetime

