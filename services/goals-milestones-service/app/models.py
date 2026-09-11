"""ORM models for goals-milestones-service (svc_goals).

Goal              — a user's financial goal.
Milestone         — a step on a goal's path (card O2.3), shown on the Goal Milestone
                    Path screen; Goal.progress_pct is computed from these, not stored.
TaggedCommitment  — a chat message the user confirmed as a commitment,
                    linked to a goal and surfaced on the Goal Milestone Path screen.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.UTC)


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "active" | "completed" | "abandoned"
    status: Mapped[str] = mapped_column(String(20), default="active")
    deadline: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    commitments: Mapped[list[TaggedCommitment]] = relationship(
        "TaggedCommitment", back_populates="goal", order_by="TaggedCommitment.created_at"
    )
    milestones: Mapped[list[Milestone]] = relationship(
        "Milestone", back_populates="goal", order_by="Milestone.order",
        cascade="all, delete-orphan",
    )


# Matches frontend/contract/types.ts MilestoneStatus.
MILESTONE_STATUSES = ("done", "in_progress", "blocked", "upcoming")


class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    goal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("goals.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="upcoming")
    order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    goal: Mapped[Goal] = relationship("Goal", back_populates="milestones")


class TaggedCommitment(Base):
    __tablename__ = "tagged_commitments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    goal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("goals.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    # Source identifiers from chat-orchestration-service
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    message_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # Set to True when the source conversation is deleted (archived) by the user.
    # Data is retained for admin oversight; this flag hides it from user-facing views.
    is_archived: Mapped[bool] = mapped_column(default=False, nullable=False)

    goal: Mapped[Goal] = relationship("Goal", back_populates="commitments")
