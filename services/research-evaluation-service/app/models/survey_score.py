"""Financial-knowledge and self-efficacy survey scores for the pilot (card C4.5).

The Big-Three-adapted and FSES-modified instruments (pilot plan §5.2/§5.3) are
administered orally by the field team, pre (T0) and post (T1) — this table
records only the *computed scores* per participant per wave against the same
anonymized `user_hash` C3.5 and ArmAssignment use, so the pilot-data export can
join engagement + persona-consistency + both survey measures into one dataset
without ever storing a raw item response or a real participant identifier.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .audit import Base


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.UTC)


class SurveyScore(Base):
    """One participant's computed survey scores for one wave (T0 or T1).

    ``financial_knowledge_score``: 0-3 correct on the Big-Three-adapted
    instrument (pilot plan §5.2). ``self_efficacy_score``: 6-24, FSES-modified,
    reverse-scored and summed (pilot plan §5.3) — the pilot's primary
    quantitative outcome. Either may be null if that instrument wasn't
    completed for this wave.

    Composite PK (user_hash, wave): re-recording the same participant+wave
    updates the scores rather than erroring, so re-loading a corrected T0/T1
    tracking sheet is idempotent — same upsert semantics as ArmAssignment.
    """

    __tablename__ = "survey_scores"

    user_hash: Mapped[str] = mapped_column(String(16), primary_key=True)
    # "T0" (baseline, pre-exposure) or "T1" (exit) — pilot plan §6.
    wave: Mapped[str] = mapped_column(String(2), primary_key=True)

    financial_knowledge_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    self_efficacy_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    recorded_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def __repr__(self) -> str:
        return (
            f"<SurveyScore user_hash={self.user_hash} wave={self.wave} "
            f"knowledge={self.financial_knowledge_score} "
            f"self_efficacy={self.self_efficacy_score}>"
        )
