"""DriftAlert — persona-level drift alerts (card O4.1).

One row per persona per nightly job run whose mean consistency score deviated
from that persona's rolling baseline by more than the configured threshold —
the "Drift Threshold Alert: CHIOMA Persona" widget on the Research Console.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DriftAlertStatus(str, Enum):
    open = "open"
    acknowledged = "acknowledged"


class DriftAlert(Base):
    __tablename__ = "drift_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    persona_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    baseline_aggregate: Mapped[float] = mapped_column(Float, nullable=False)
    current_aggregate: Mapped[float] = mapped_column(Float, nullable=False)
    delta_pct: Mapped[float] = mapped_column(Float, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DriftAlertStatus.open.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
