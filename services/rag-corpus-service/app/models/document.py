import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Integer, String
from sqlalchemy import Enum as PgEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class DocumentStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    ready = "ready"
    failed = "failed"

class DocumentOrigin(str, enum.Enum):
    entrepreneur_corpus = "entrepreneur_corpus"
    trade_guide = "trade_guide"
    financial_literacy = "financial_literacy"
    vocational = "vocational"
    general = "general"

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_origin: Mapped[DocumentOrigin] = mapped_column(
        PgEnum(DocumentOrigin, name="document_origin"), nullable=False
    )
    figure_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    market: Mapped[str | None] = mapped_column(String(10), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    # Corpus tier (card C3.4). 1 = Tier-1 entrepreneur transcripts (C1.2/C2.2);
    # 2 = Tier-2 reference reports (statistics bureaus, Brookings AGI, Mo Ibrahim,
    # Afrobarometer, AfDB, sector guides, podcast transcripts). Defaults to 1 so
    # existing rows and ad-hoc ingests stay Tier-1 without a backfill.
    tier: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # ── Admin/catalogue fields (card C2.2) ────────────────────────────────────
    # Sourced from corpus.jsonl metadata; all nullable so ad-hoc ingests that
    # only supply filename+text keep working.
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    author: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Raw human-readable label ("Fashion & Textile"). The normalized, filterable
    # form lives in Chroma metadata — see ingestion.normalize_sector.
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    published_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Raw text size, used by /stats to report real corpus bytes.
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[DocumentStatus] = mapped_column(
        PgEnum(DocumentStatus, name="document_status"),
        default=DocumentStatus.queued,
        nullable=False,
    )
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
