from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class FeedbackSubmit(BaseModel):
    nps_score: int = Field(ge=1, le=10)
    comment: str | None = Field(default=None, max_length=2000)
    voice_note_url: str | None = None
    # When set, resolves the open FeedbackPrompt with a matching (user, trigger,
    # context_ref) — omit for an unprompted/manual submission.
    trigger: str = "manual"
    context_ref: str | None = None


class FeedbackSurveyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    nps_score: int
    comment: str | None
    voice_note_url: str | None
    trigger: str
    context_ref: str | None
    submitted_at: dt.datetime


class FeedbackPromptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    trigger: str
    context_ref: str | None
    created_at: dt.datetime
