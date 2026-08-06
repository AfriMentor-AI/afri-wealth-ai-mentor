"""Domain event publisher for goals-milestones-service."""
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
    if not settings.rabbitmq_url:
        logger.debug("RABBITMQ_URL not set — skipping event %s", routing_key)
        return
    try:
        conn = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
        ch = conn.channel()
        ch.exchange_declare(
            exchange=settings.amqp_exchange, exchange_type="topic", durable=True
        )
        ch.basic_publish(
            exchange=settings.amqp_exchange,
            routing_key=routing_key,
            body=json.dumps(payload),
            properties=pika.BasicProperties(
                content_type="application/json", delivery_mode=2
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


def emit_commitment_created(
    *,
    commitment_id: str,
    goal_id: str,
    user_id: str,
    conversation_id: str,
    message_id: str,
    content_preview: str,
) -> None:
    """Emit `commitment.created` after the user confirms 'Yes, Tag It'.

    Consumed by: progress-gamification-service (XP award), notification-service,
    research-evaluation-service (audit).
    """
    payload = _envelope(
        event="commitment.created",
        actor=user_id,
        data={
            "commitment_id": commitment_id,
            "goal_id": goal_id,
            "user_id": user_id,
            "conversation_id": conversation_id,
            "message_id": message_id,
            "content_preview": content_preview[:200],
        },
    )
    _publish("commitment.created", payload)
