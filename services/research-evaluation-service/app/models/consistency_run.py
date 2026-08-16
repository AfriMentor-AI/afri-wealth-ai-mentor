"""ConsistencyRun — stores per-session consistency scores (C3.2)."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.session import Base


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
    # Indexed: the Sprint-4 dashboard reads the most recent run first.
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
