"""ORM models for progress-gamification-service (svc_progress, card O3.1).

ActionEvent  — one row per user activity on a given day (a completed daily action,
               an insight marked finished, a savings goal met). Streaks and the
               action heatmap are both derived from this table, never stored
               redundantly, so there's a single source of truth to keep in sync.
UserBadge    — earned-badge join rows. The badge catalog itself (label, description,
               trigger rule) is a static list in badges.py, not a table — it's fixed
               content, not user data, matching contract/types.ts's Badge/UserBadge
               split (Badge is shared catalog, UserBadge is the per-user join).
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Date, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.UTC)


# Matches the `kind` values badges.py's trigger rules key off of.
ACTION_KINDS = ("daily_action", "insight_completed", "savings_goal_met")


class ActionEvent(Base):
    __tablename__ = "action_events"
    __table_args__ = (
        # A user can log at most one event of a given kind per day — recording the
        # same day's daily action twice must not inflate the streak or badge counts.
        UniqueConstraint("user_id", "occurred_on", "kind", name="uq_action_user_day_kind"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    occurred_on: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class UserBadge(Base):
    __tablename__ = "user_badges"
    __table_args__ = (UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    badge_id: Mapped[str] = mapped_column(String(50), nullable=False)
    earned_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
