"""ORM models for insight-library-service (svc_insight, card O3.2).

InsightItem      — catalog entry (text / audio / video).
InsightFavorite  — per-user bookmark of an InsightItem.
InsightProgress  — per-user playback position + completion flag for audio/video.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

MEDIA_TYPES = {"text", "audio", "video"}
DIFFICULTIES = {"beginner", "intermediate", "advanced"}


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.UTC)


class InsightItem(Base):
    __tablename__ = "insight_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    # "text" | "audio" | "video"
    media_type: Mapped[str] = mapped_column(String(10), index=True, nullable=False, default="text")
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(10), index=True, nullable=False, default="en")
    # "beginner" | "intermediate" | "advanced"
    difficulty: Mapped[str] = mapped_column(
        String(12), index=True, nullable=False, default="beginner"
    )
    slug: Mapped[str | None] = mapped_column(String(100), unique=True, index=True, nullable=True)
    media_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Low-bandwidth / accessibility fallback for audio and video
    transcript_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Full lesson text / curriculum and audio narration script
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_narration: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class InsightFavorite(Base):
    __tablename__ = "insight_favorites"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    insight_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("insight_items.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class InsightProgress(Base):
    """Tracks playback position and completion for audio/video items per user."""
    __tablename__ = "insight_progress"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    insight_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("insight_items.id", ondelete="CASCADE"), primary_key=True
    )
    position_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_accessed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
