from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


# ── Goal ──────────────────────────────────────────────────────────────────────

class GoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None


class GoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    description: str | None
    status: str
    created_at: dt.datetime
    updated_at: dt.datetime


# ── Tagged Commitment ─────────────────────────────────────────────────────────

class CommitmentCreate(BaseModel):
    """Body for POST /api/v1/goals/{goal_id}/commitments.

    Called by chat-orchestration-service when the user confirms 'Yes, Tag It'.
    """
    user_id: str
    conversation_id: str
    message_id: str
    content: str = Field(min_length=1, max_length=2000)


class CommitmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    goal_id: str
    user_id: str
    conversation_id: str
    message_id: str
    content: str
    created_at: dt.datetime
