from __future__ import annotations

import datetime as dt
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# ── Goal ──────────────────────────────────────────────────────────────────────

class GoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    deadline: dt.date | None = None


class GoalUpdate(BaseModel):
    """PATCH /api/v1/goals/{id} (card O2.3) — every field optional."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    deadline: dt.date | None = None


class GoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    description: str | None
    status: str
    deadline: dt.date | None
    # Server-computed from this goal's milestones — never accepted on write.
    progress_pct: int
    created_at: dt.datetime
    updated_at: dt.datetime


# ── Milestone (card O2.3) ───────────────────────────────────────────────────

class MilestoneStatus(str, Enum):
    done = "done"
    in_progress = "in_progress"
    blocked = "blocked"
    upcoming = "upcoming"


class MilestoneCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    status: MilestoneStatus = MilestoneStatus.upcoming
    order: int | None = Field(default=None, ge=0)


class MilestoneUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    status: MilestoneStatus | None = None
    order: int | None = Field(default=None, ge=0)


class MilestoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    goal_id: str
    title: str
    status: MilestoneStatus
    order: int
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
