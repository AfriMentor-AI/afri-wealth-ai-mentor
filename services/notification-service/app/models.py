"""ORM model for notification-service (svc_notify, card O3.4 — v0 scaffold).

One row per notification, delivered/logged immediately (no real push integration
yet — see the module docstring in main.py for the v0 scope).
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base

# Matches the trigger endpoints — daily_action_reminder | streak_at_risk.
NOTIFICATION_KINDS = ("daily_action_reminder", "streak_at_risk")


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.UTC)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set at creation — delivery is stubbed/logged for this v0, not a real push
    # send, so "delivered" and "created" are the same moment (card O3.4).
    delivered_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
