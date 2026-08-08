"""ORM models for intake-profiling-service (card O2.2).

An IntakeSession walks a user through the 4-step Intake flow (sector -> education/time
-> constraints -> confirm); each step's answer is upserted as an IntakeAnswer keyed on
(session_id, step). Completing a session projects its four answers into a
DiagnosticProfile — the structured, one-row-per-user record Chat Orchestration reads for
personalization (matches the shared `Profile` contract in frontend/contract/types.ts).
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.UTC)


class IntakeSession(Base):
    __tablename__ = "intake_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")  # in_progress|completed
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IntakeAnswer(Base):
    __tablename__ = "intake_answers"
    __table_args__ = (UniqueConstraint("session_id", "step", name="uq_answer_session_step"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("intake_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    step: Mapped[str] = mapped_column(String(20), nullable=False)  # see schemas.IntakeStep
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class DiagnosticProfile(Base):
    """One row per user — the structured intake output.

    Card O2.2: GET /profiles/{userId}/diagnostic.
    """

    __tablename__ = "diagnostic_profiles"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    business_name: Mapped[str] = mapped_column(String(160), nullable=False)
    location: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    sector: Mapped[str] = mapped_column(String(60), nullable=False)
    education_level: Mapped[str] = mapped_column(String(60), nullable=False)
    time_available_per_week: Mapped[str] = mapped_column(String(60), nullable=False)
    constraints: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Set later by persona selection (D2.2); intake never writes this itself.
    persona_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
