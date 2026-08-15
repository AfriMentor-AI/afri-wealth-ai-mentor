"""Domain event publisher for progress-gamification-service."""
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


def emit_badge_earned(*, user_id: str, badge_id: str, label: str) -> None:
    """Emit `badge.earned` when a user first qualifies for a badge.

    Consumed by: notification-service (future push), research-evaluation-service
    (engagement audit).
    """
    payload = _envelope(
        event="badge.earned",
        actor=user_id,
        data={"user_id": user_id, "badge_id": badge_id, "label": label},
    )
    _publish("badge.earned", payload)
