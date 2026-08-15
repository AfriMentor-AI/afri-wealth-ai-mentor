"""ORM models for feedback-service (svc_feedback, card O3.3).

FeedbackSurvey  — one submission of the Feedback Survey modal (NPS-style, 1-10),
                  matching contract/types.ts's FeedbackSurvey.
FeedbackPrompt  — "a survey is now due" marker. Created when an upstream trigger
                  (e.g. `milestone.completed`) fires; resolved when the matching
                  submission arrives. A client polls GET /feedback/pending to know
                  whether to pop the survey modal.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.UTC)


class FeedbackSurvey(Base):
    __tablename__ = "feedback_surveys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    nps_score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    voice_note_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # What caused this submission — "milestone_completed" | "manual", etc.
    trigger: Mapped[str] = mapped_column(String(40), default="manual")
    # Opaque reference into the triggering context (e.g. a milestone id) — lets a
    # submission resolve the FeedbackPrompt it was answering.
    context_ref: Mapped[str | None] = mapped_column(String(36), nullable=True)
    submitted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class FeedbackPrompt(Base):
    __tablename__ = "feedback_prompts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    trigger: Mapped[str] = mapped_column(String(40), nullable=False)
    context_ref: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    fulfilled_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
