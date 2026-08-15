"""Anonymized session metrics for pilot quantitative measures (card C3.5).

Tracks three required metrics:
  - Sessions per day
  - Average session length
  - Time on-task (message count proxy)

All user identifiers are anonymized via SHA256 hash to allow aggregation
without exposing PII.
"""
from __future__ import annotations

import datetime as dt
import hashlib

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .audit import Base


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.UTC)


def anonymize_user_id(user_id: str, salt: str | None = None) -> str:
    """Hash user_id to an anonymized identifier.
    
    Uses SHA256 with an optional salt. Falls back to getting salt from
    the Config object for consistency across runs.
    """
    if salt is None:
        # Import here to avoid circular imports
        from ..config import get_settings
        settings = get_settings()
        salt = settings.research_salt
    
    combined = f"{user_id}:{salt}"
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


class SessionMetric(Base):
    """One anonymized session from event stream.
    
    Created when session.completed event is received; contains the exact
    data points needed for Proposal 2 pilot evaluation.
    """

    __tablename__ = "session_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Anonymized user identifier (SHA256 hash)
    user_hash: Mapped[str] = mapped_column(String(16), index=True, nullable=False)

    # Session date (for grouping "sessions per day")
    session_date: Mapped[dt.date] = mapped_column(index=True, nullable=False)

    # Session duration in seconds (for "average session length")
    session_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    # Number of messages in session (proxy for "time on-task")
    # Includes both user and mentor turns
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Conversation ID (NOT anonymized, used only for audit/debugging)
    # Can be removed if strict data minimization is required
    conversation_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)

    # Record when this metric was ingested
    recorded_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def __repr__(self) -> str:
        return (
            f"<SessionMetric user_hash={self.user_hash} "
            f"duration={self.session_duration_seconds}s "
            f"messages={self.message_count} "
            f"date={self.session_date}>"
        )
