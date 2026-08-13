"""ORM models for insight-library-service (svc_insight, card O3.2).

InsightItem      — a catalog entry (audio/text) shown on the Insight Library
                    Home/Desktop screens.
InsightFavorite  — a user's bookmark of an InsightItem. Modeled as a join row
                    rather than a boolean on InsightItem since InsightItem is
                    shared/global content and favorites are per-user (matches
                    contract/types.ts's InsightFavorite).
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.UTC)


class InsightItem(Base):
    __tablename__ = "insight_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    # Sector/topic tag, e.g. "Pricing", "Savings", "Bookkeeping" — filterable via
    # ?category= (card O3.2's "Sector/Topic" filter).
    category: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    is_audio: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    media_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class InsightFavorite(Base):
    __tablename__ = "insight_favorites"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    insight_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("insight_items.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
