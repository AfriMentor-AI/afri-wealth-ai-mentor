"""Persistence for baseline evaluation experiments (card C2.3).

An :class:`ExperimentRun` is one invocation of ``scripts/run_trait_fit.py`` against
a given model. Each run fans out to several :class:`TraitFitReport` rows — one for
the probe-based trait estimate, plus one per scored dialogue — so probe-derived and
behaviourally-derived personality can be compared within a run rather than merged
(Han et al. 2025 find the two diverge).

Metric *definitions* live in :mod:`app.metrics` and stay storage-agnostic; this
module only records their output.
"""

from __future__ import annotations

import datetime as dt
import enum

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base




def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.UTC)


class ExperimentStatus(str, enum.Enum):
    """Lifecycle of an experiment run.

    A row is written as ``running`` *before* scoring starts, so a process that
    crashes mid-run leaves evidence rather than vanishing.
    """

    running = "running"
    completed = "completed"
    failed = "failed"


class ExperimentRun(Base):
    """One baseline evaluation run against one model."""

    __tablename__ = "experiment_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    model_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)

    # Which target profile the run scored against. Recorded per-run because the
    # CHIOMA profile is versioned — scores are only comparable within a version.
    profile_id: Mapped[str] = mapped_column(String(80), nullable=False)
    profile_version: Mapped[str] = mapped_column(String(40), nullable=False)

    # Similarity backend name (LexicalScorer in v0, an embedding scorer later).
    # Numbers from different backends are not comparable, so this is not optional.
    scorer: Mapped[str] = mapped_column(String(80), nullable=False)

    status: Mapped[ExperimentStatus] = mapped_column(
        Enum(ExperimentStatus, native_enum=False, length=20),
        default=ExperimentStatus.running,
        nullable=False,
        index=True,
    )

    # Defaulted, not just nullable: it is assigned after the row is committed, so a
    # failure during probe loading would otherwise leave it unset.
    probe_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    completed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Truncated to 500 chars by the caller before assignment.
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    reports: Mapped[list[TraitFitReport]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<ExperimentRun id={self.id} name={self.name!r} "
            f"model={self.model_id!r} status={self.status.value}>"
        )


class TraitFitReport(Base):
    """One scored artifact within a run — a probe set or a single dialogue."""

    __tablename__ = "trait_fit_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("experiment_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )

    #: ``"probes"`` (self-reported) or ``"dialogue"`` (behaviourally expressed).
    source: Mapped[str] = mapped_column(String(20), index=True, nullable=False)

    cosine_similarity: Mapped[float] = mapped_column(Float, nullable=False)
    mean_absolute_error: Mapped[float] = mapped_column(Float, nullable=False)

    # Nullable by design: the composite blends trait fit with behavioral
    # consistency, and consistency is undefined for a probe set (no dialogue).
    composite_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Null when the report scored zero traits, so worst_trait had nothing to pick.
    worst_trait: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # Serialized list[TraitScore] and list[str]. Stored as JSON text rather than
    # relational columns: these are read back whole for display, never queried
    # per-trait, and Text keeps the table portable across SQLite and Postgres.
    per_trait_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    run: Mapped[ExperimentRun] = relationship(back_populates="reports")

    def __repr__(self) -> str:
        return (
            f"<TraitFitReport id={self.id} run_id={self.run_id} "
            f"source={self.source!r} cosine={self.cosine_similarity:.4f}>"
        )
