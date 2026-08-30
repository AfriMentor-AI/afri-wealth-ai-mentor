"""Domain event publisher for chat-orchestration-service.

Publishes to the `afrimentor.events` topic exchange (ADR-0001 §D3).
All publishes are fire-and-forget: a failure logs a warning but never
breaks the request path.

Event envelope:
  { event, version, id, occurredAt, actor, data }
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import threading
import uuid

import pika
import pika.exceptions

from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# asyncio only holds a *weak* reference to a task created via create_task — with
# nothing else referencing it, it can be garbage-collected mid-flight. Holding a
# strong reference here (and dropping it via the done-callback) is the standard
# fire-and-forget pattern per the asyncio docs.
_background_tasks: set[asyncio.Task] = set()


def _publish_blocking(routing_key: str, payload: dict) -> None:
    """Open a transient connection, publish one message, close.

    Synchronous (pika has no asyncio API) — always called via `_publish()`'s
    `asyncio.to_thread`, never directly from a route handler. See `_publish`.
    """
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


def _publish(routing_key: str, payload: dict) -> None:
    """Schedule the blocking publish off-thread instead of running it inline
    (card O5.1 / BUG-02). `pika.BlockingConnection` was previously called
    directly from route handlers — the TCP/AMQP handshake and publish stalled
    whichever thread called it for every other in-flight request on that
    thread.

    Callers span both `async def` handlers (running on the event loop thread)
    and plain `def` handlers (FastAPI runs those in a worker thread with no
    running loop of its own — e.g. tag_commitment's synchronous httpx.post
    call is exactly why it's a sync handler in the first place). Both need a
    non-blocking dispatch, so this branches on whether a loop is actually
    running rather than assuming one: `asyncio.to_thread` + `create_task` from
    the loop thread, a plain daemon `threading.Thread` otherwise. Either way
    this function itself stays synchronous and immediate, so no caller needs
    to change to `await` it — matching the "fire-and-forget" contract this
    module already documents.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        threading.Thread(
            target=_publish_blocking, args=(routing_key, payload), daemon=True
        ).start()
        return

    task = loop.create_task(asyncio.to_thread(_publish_blocking, routing_key, payload))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


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


def emit_commitment_created(
    *,
    commitment_id: str,
    goal_id: str,
    user_id: str,
    conversation_id: str,
    message_id: str,
    content_preview: str,
) -> None:
    """Emit `commitment.created` after goals-milestones-service persists the tag.

    Consumed by: progress-gamification-service, notification-service,
    research-evaluation-service.
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
