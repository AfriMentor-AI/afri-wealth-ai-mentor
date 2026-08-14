"""ORM models for chat-orchestration-service (svc_chat).

Conversation  — one per user session; tracks persona, status, and token usage.
Message       — ordered turns within a conversation (user / assistant / system).
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.UTC)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)

    # Persona & RAG context — populated by Sprint 2–3 integrations.
    # Stored as opaque IDs so the router can pass them back to downstream services.
    persona_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    rag_collection: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # "active" | "completed" | "archived"
    status: Mapped[str] = mapped_column(String(20), default="active")

    # Cumulative token usage for cost tracking
    total_prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_completion_tokens: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    messages: Mapped[list[Message]] = relationship(
        "Message", back_populates="conversation", order_by="Message.sequence"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    # "user" | "assistant" | "system"
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    # Set to True when the model proposes this message as a commitment (Tag it).
    # The commitment.tag_suggested event is emitted at write time when True.
    is_commitment_candidate: Mapped[bool] = mapped_column(
        # SQLAlchemy Boolean stored as Integer for SQLite compat
        Integer, default=0
    )

    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)

    # List of {"label": str} dicts — rendered as source-pills on the Chat screen.
    # Empty list when no RAG chunks were retrieved for this turn.
    citations: Mapped[list] = mapped_column(JSON, default=list)

    # Guardrail outcome for this turn (card C2.4): "allow" | "disclaim" | "block".
    # NULL on rows written before C2.4 and whenever GUARDRAILS_ENABLED is off,
    # which is why it is nullable rather than defaulted to "allow" — an unscreened
    # turn and an allowed one are different facts, and the research evaluation
    # needs to tell them apart.
    guardrail_action: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Risk category ids that fired, e.g. ["specific_instrument"]. Empty when allowed.
    guardrail_categories: Mapped[list] = mapped_column(JSON, default=list)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="messages")


class DailyAction(Base):
    __tablename__ = "daily_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    action_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_completed: Mapped[bool] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
