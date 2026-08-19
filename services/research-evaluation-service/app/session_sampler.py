"""C3.2 — Session sampler.

Reads completed conversations and their messages from the
chat-orchestration-service database and converts them into
:class:`~app.metrics.schemas.Dialogue` objects the C1.3 metric suite can score.

The chat service persists only ``user`` and ``assistant`` messages — the persona
system prompt is assembled at inference time and never written to the messages
table. So the ``system_prompt`` anchor for the prompt-to-line metric is sourced
here from :func:`app.llm.fetch_system_prompt`, the same helper the baseline
experiment runner uses (persona-prompt-service, with a local fallback).
"""
from __future__ import annotations

import logging
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.llm import fetch_system_prompt
from app.metrics.profile import load_profile
from app.metrics.schemas import Dialogue, Speaker, Turn

logger = logging.getLogger(__name__)

CHAT_DB_URL = os.getenv(
    "CHAT_DB_URL",
    "postgresql+psycopg://afrimentor:afrimentor@localhost:5432/svc_chat",
)

_chat_engine = None


def _get_chat_engine():
    global _chat_engine
    if _chat_engine is None:
        _chat_engine = create_engine(CHAT_DB_URL, pool_pre_ping=True)
    return _chat_engine


def _dialogue_from_conversation(
    conv_id: str,
    persona_id: str | None,
    msg_rows: list,
    system_prompt: str,
) -> Dialogue | None:
    """Build a scorable Dialogue from raw message rows, or None if too thin.

    Rows are ``(role, content, sequence)`` ordered by sequence. System rows are
    dropped (the prompt anchor is supplied separately) and blank turns are skipped
    so a stray empty message cannot fail validation for the whole conversation.
    """
    turns: list[Turn] = []
    for role, content, _seq in msg_rows:
        if role == "system":
            continue
        if not content or not content.strip():
            continue
        speaker = Speaker.mentor if role == "assistant" else Speaker.user
        turns.append(Turn(speaker=speaker, text=content))

    # Consistency metrics need conversation, not a single utterance.
    if len(turns) < 2:
        return None

    return Dialogue(
        dialogue_id=conv_id,
        system_prompt=system_prompt,
        persona_id=persona_id,
        turns=turns,
    )


def sample_completed_sessions(limit: int = 20) -> list[Dialogue]:
    """Return up to ``limit`` recently completed conversations as Dialogues.

    Resilient by design: a chat-DB outage returns ``[]`` rather than raising, so a
    scheduled scoring run degrades to "no data" instead of crashing the service.
    """
    try:
        engine = _get_chat_engine()
        db = sessionmaker(bind=engine)()
    except Exception as exc:
        logger.error("Failed to connect to chat DB: %s", exc)
        return []

    try:
        conv_rows = db.execute(
            text(
                """
                SELECT id, persona_id
                FROM conversations
                WHERE status = 'completed'
                ORDER BY updated_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        ).fetchall()

        if not conv_rows:
            logger.info("No completed conversations found in chat DB")
            return []

        # One CHIOMA persona in v0, so the anchor is fetched once and reused.
        system_prompt, provenance = fetch_system_prompt(load_profile())
        logger.info("System-prompt anchor sourced from %s", provenance)

        dialogues: list[Dialogue] = []
        for conv_id, persona_id in conv_rows:
            msg_rows = db.execute(
                text(
                    """
                    SELECT role, content, sequence
                    FROM messages
                    WHERE conversation_id = :conv_id
                    ORDER BY sequence ASC
                    """
                ),
                {"conv_id": conv_id},
            ).fetchall()

            dialogue = _dialogue_from_conversation(
                conv_id, persona_id, msg_rows, system_prompt
            )
            if dialogue is not None:
                dialogues.append(dialogue)

        logger.info("Sampled %d scorable sessions from chat DB", len(dialogues))
        return dialogues

    except Exception as exc:
        logger.error("Failed to sample sessions from chat DB: %s", exc)
        return []
    finally:
        db.close()
