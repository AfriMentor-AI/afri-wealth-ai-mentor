"""RabbitMQ consumer for notification-service.

Listens on the `afrimentor.events` topic exchange and reacts to:
  - commitment.created  → POST /trigger/daily-action-reminder
  - session.completed   → POST /trigger/streak-at-risk (via sweep check)
"""
from __future__ import annotations

import json
import logging
import threading

import pika
import httpx

from .config import get_settings

logger = logging.getLogger(__name__)

_EXCHANGE = "afrimentor.events"
_QUEUE = "notification-service.events"
_BINDING_KEYS = ["commitment.created", "session.completed"]


def _handle(routing_key: str, body: dict, base_url: str) -> None:
    user_id = body.get("user_id")
    if not user_id:
        return

    if routing_key == "commitment.created":
        r = httpx.post(
            f"{base_url}/api/v1/notifications/trigger/daily-action-reminder",
            json={"user_id": user_id, "action_title": body.get("content_preview", "")[:80]},
            timeout=5,
        )
        logger.info("trigger daily-action-reminder for %s: %s", user_id, r.status_code)
    elif routing_key == "session.completed":
        r = httpx.post(f"{base_url}/api/v1/notifications/sweep", timeout=10)
        logger.info("triggered sweep: %s", r.status_code)


def _run(rabbitmq_url: str, base_url: str) -> None:
    try:
        conn = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
        ch = conn.channel()
        ch.exchange_declare(exchange=_EXCHANGE, exchange_type="topic", durable=True)
        ch.queue_declare(queue=_QUEUE, durable=True)
        for key in _BINDING_KEYS:
            ch.queue_bind(queue=_QUEUE, exchange=_EXCHANGE, routing_key=key)

        def on_message(ch, method, _props, body):
            try:
                _handle(method.routing_key, json.loads(body), base_url)
            except Exception:
                logger.exception("consumer: error handling %s", method.routing_key)
            finally:
                ch.basic_ack(delivery_tag=method.delivery_tag)

        ch.basic_qos(prefetch_count=1)
        ch.basic_consume(queue=_QUEUE, on_message_callback=on_message)
        logger.info("notification consumer started, queue=%s", _QUEUE)
        ch.start_consuming()
    except Exception:
        logger.exception("notification consumer exited")


def start_consumer() -> None:
    settings = get_settings()
    if not settings.rabbitmq_url:
        logger.warning("RABBITMQ_URL not set — notification consumer disabled")
        return
    # Use localhost — consumer runs inside this container, no need for external DNS
    base_url = "http://localhost:8012"
    t = threading.Thread(
        target=_run,
        args=(settings.rabbitmq_url, base_url),
        daemon=True,
        name="notification-consumer",
    )
    t.start()
