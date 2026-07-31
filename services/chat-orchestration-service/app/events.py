"""Domain event publisher for chat-orchestration-service.

Publishes to the `afrimentor.events` topic exchange (ADR-0001 §D3).
All publishes are fire-and-forget: a failure logs a warning but never
breaks the request path.

Event envelope:
  { event, version, id, occurredAt, actor, data }
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import uuid

import pika
import pika.exceptions

from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _publish(routing_key: str, payload: dict) -> None:
    """Open a transient connection, publish one message, close."""
    if not settings.rabbitmq_url:
        logger.debug("RABBITMQ_URL not set — skipping event %s", routing_key)
        return
    try:
        params = pika.URLParameters(settings.rabbitmq_url)
        conn = pika.BlockingConnection(params)
        ch = conn.channel()
        ch.exchange_declare(
            exchange=settings.amqp_exchange,
            exchange_type="topic",
            durable=True,
        )
        ch.basic_publish(
            exchange=settings.amqp_exchange,
            routing_key=routing_key,
            body=json.dumps(payload),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,  # persistent
            ),
        )
        conn.close()
    except pika.exceptions.AMQPError as exc:
        logger.warning("Event publish failed [%s]: %s", routing_key, exc)


def _envelope(event: str, actor: str, data: dict) -> dict:
    return {
        "event": event,
        "version": "1",
        "id": str(uuid.uuid4()),
        "occurredAt": dt.datetime.now(tz=dt.UTC).isoformat(),
        "actor": actor,
        "data": data,
    }


def emit_commitment_tag_suggested(
    *,
    conversation_id: str,
    message_id: str,
    user_id: str,
    content: str,
) -> None:
    """Emit `commitment.tag_suggested` when the model proposes tagging a message.

    Consumed by: goals-milestones-service (to surface the 'Tag it' prompt on the
    Chat screen) and research-evaluation-service (for audit).
    """
    payload = _envelope(
        event="commitment.tag_suggested",
        actor=user_id,
        data={
            "conversation_id": conversation_id,
            "message_id": message_id,
            "user_id": user_id,
            "content_preview": content[:200],
        },
    )
    _publish("commitment.tag_suggested", payload)


def emit_session_completed(*, conversation_id: str, user_id: str) -> None:
    """Emit `session.completed` (ADR-0001 event catalogue)."""
    payload = _envelope(
        event="session.completed",
        actor=user_id,
        data={"conversation_id": conversation_id, "user_id": user_id},
    )
    _publish("session.completed", payload)
