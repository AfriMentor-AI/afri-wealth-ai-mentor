import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, Enum as PgEnum
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
    status: Mapped[DocumentStatus] = mapped_column(
        PgEnum(DocumentStatus, name="document_status"),
        default=DocumentStatus.queued,
        nullable=False,
    )
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
