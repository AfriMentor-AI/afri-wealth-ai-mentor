"""Study-arm assignment for the Proposal 2 pilot (card C4.5).

The allocation sequence itself (block randomisation within stratum) is generated
and held offline per `docs/research/pilot-data-collection-plan-v0.md` §3.3 — this
table only records the *result* of that process against the same anonymized
`user_hash` the C3.5 engagement telemetry uses, so the pilot-data export can filter
and label rows by arm without ever storing a real participant identifier.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from .audit import Base


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.UTC)


class ArmAssignment(Base):
    """Which study arm (A or B) one anonymized participant was allocated to.

    One row per participant — re-recording the same ``user_hash`` updates the arm
    rather than erroring, so re-submitting an enrolment sheet is idempotent.
    """

    __tablename__ = "arm_assignments"

    # Same SHA256 hash SessionMetric.user_hash uses (anonymize_user_id), so the
    # two tables join on identical values without a foreign key across services.
    user_hash: Mapped[str] = mapped_column(String(16), primary_key=True)

    # "A" (AfriMentor prototype) or "B" (generic LLM control) — see pilot plan §1.
    arm: Mapped[str] = mapped_column(String(1), nullable=False)

    assigned_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def __repr__(self) -> str:
        return f"<ArmAssignment user_hash={self.user_hash} arm={self.arm}>"
