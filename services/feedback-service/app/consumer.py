"""RabbitMQ consumer for `milestone.completed` (card O3.3).

Wired as a background thread from main.py's lifespan; no-ops (never connects)
when RABBITMQ_URL is unset — same convention every event producer in this
monorepo uses for local/dev/test runs without a broker.
"""
from __future__ import annotations

import json
import logging
import threading

import pika
import pika.exceptions
from sqlalchemy.orm import Session

from .config import get_settings
from .database import SessionLocal
from .models import FeedbackPrompt

logger = logging.getLogger(__name__)
settings = get_settings()


def process_milestone_completed(db: Session, payload: dict) -> FeedbackPrompt:
    """Pure handler for a decoded `milestone.completed` event body: records a
    pending feedback prompt for that user. Called directly by tests, and by the
    pika message callback in production — the actual "survey fires automatically"
    behaviour the card asks for."""
    data = payload.get("data", payload)
    prompt = FeedbackPrompt(
        user_id=data["user_id"],
        trigger="milestone_completed",
        context_ref=data.get("milestone_id"),
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


def _on_message(channel, method, _properties, body: bytes) -> None:
    db = SessionLocal()
    try:
        payload = json.loads(body)
        process_milestone_completed(db, payload)
    except Exception:  # noqa: BLE001 - a bad message must not kill the consumer thread
        logger.exception("Failed to process milestone.completed message")
    finally:
        db.close()
    channel.basic_ack(delivery_tag=method.delivery_tag)


def _run_consumer() -> None:
    try:
        conn = pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))
        channel = conn.channel()
        channel.exchange_declare(
            exchange=settings.amqp_exchange, exchange_type="topic", durable=True
        )
        channel.queue_declare(queue=settings.amqp_queue, durable=True)
        channel.queue_bind(
            queue=settings.amqp_queue,
            exchange=settings.amqp_exchange,
            routing_key="milestone.completed",
        )
        channel.basic_consume(queue=settings.amqp_queue, on_message_callback=_on_message)
        logger.info("feedback-service: consuming milestone.completed")
        channel.start_consuming()
    except pika.exceptions.AMQPError:
        logger.warning("milestone.completed consumer stopped — broker unavailable", exc_info=True)


def start_consumer_thread() -> threading.Thread | None:
    """Call once from lifespan. No-ops (returns None) when RABBITMQ_URL is unset."""
    if not settings.rabbitmq_url:
        logger.debug("RABBITMQ_URL not set — milestone.completed consumer disabled")
        return None
    thread = threading.Thread(target=_run_consumer, daemon=True)
    thread.start()
    return thread
