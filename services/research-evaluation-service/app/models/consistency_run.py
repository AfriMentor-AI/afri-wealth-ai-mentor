"""ConsistencyRun — stores per-session consistency scores (C3.2)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ReviewStatus(str, Enum):
    """Human-review lifecycle for a session flagged by the manual audit workflow
    (card C4.2). Mirrors :class:`app.models.drift_alert.DriftAlertStatus`'s
    open→acknowledged shape at the per-session grain. Used only for its ``.value``
    string constants; the column stays ``String(20)`` (not a native SQLAlchemy
    ``Enum``) so the additive ``ADD COLUMN IF NOT EXISTS`` migration needs no
    ``CREATE TYPE`` first — see app/main.py:_ensure_consistency_columns.
    """
    pending_review = "pending_review"
    reviewed = "reviewed"


class ConsistencyRun(Base):
    __tablename__ = "consistency_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    # Nullable because chat-orchestration's Conversation.persona_id is itself
    # nullable — an unbound session has no persona, and that is a fact to record,
    # not a value to fabricate.
    persona_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_to_line: Mapped[float] = mapped_column(Float, nullable=False)
    line_to_line: Mapped[float] = mapped_column(Float, nullable=False)
    qa_consistency: Mapped[float] = mapped_column(Float, nullable=False)
    aggregate: Mapped[float] = mapped_column(Float, nullable=False)
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False)
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # Card O4.1 — Research Console "Recent Conversations (Persona Audit)" table.
    # Nullable: rows scored before O4.1 landed have neither field, and that is a
    # fact to record, not backfill with a guess.
    primary_intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Percent deviation of this session's aggregate from its persona's rolling
    # baseline (computed from prior job runs only). Null when no baseline existed
    # yet for the persona at scoring time — e.g. the persona's first-ever run.
    consistency_delta_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Card C4.1 — the literal "CHIOMA alignment" numbers the dashboard shows,
    # both already computed by score_dialogue() and previously discarded.
    #   trait_fit_cosine: cosine similarity of the dialogue's trait vector to
    #     CHIOMA's target profile ("is this the right personality").
    #   composite_score: the 0.5·trait + 0.5·consistency blend.
    # Nullable: rows scored before C4.1 have neither, and that is a fact to
    # record, not backfill with a guess.
    trait_fit_cosine: Mapped[float | None] = mapped_column(Float, nullable=True)
    composite_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    tone_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    fact_retrieval_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Card C4.2 — manual audit workflow. Set at scoring time when a session trips
    # the review flag (see app.drift.evaluate_review_flag): review_status is
    # 'pending_review' until an operator marks it 'reviewed', review_reason records
    # which arm(s) fired ('below_floor' | 'drift' | 'below_floor+drift').
    # Nullable with no default — most sessions aren't flagged, so a null status is
    # the honest "not flagged" fact, deliberately unlike DriftAlert.status's
    # non-null 'open' default (every alert row *is* an alert; not every run is).
    review_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    review_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Indexed: the Sprint-4 dashboard reads the most recent run first.
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )

