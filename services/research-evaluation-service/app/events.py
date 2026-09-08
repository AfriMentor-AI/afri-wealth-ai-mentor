"""Event consumers for research-evaluation-service.

Listens to domain events from the afrimentor.events RabbitMQ topic exchange.
Currently handles:
  - session.completed: Record anonymized session metrics for pilot evaluation
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime

import pika
import pika.exceptions
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from .config import get_settings
from .db.session import SessionLocal
from .models import SessionMetric, anonymize_user_id

logger = logging.getLogger(__name__)
settings = get_settings()

# Chat-orchestration-service DB, read directly to derive real session duration and
# message count for the engagement measures (card C3.5). Mirrors the same env var
# + default that app/session_sampler.py uses for the consistency scorer.
CHAT_DB_URL = None


def _get_chat_engine():
    """Lazily build the chat DB engine. Import is deferred so the service can run
    (and its tests can pass) when the chat DB is unreachable/unconfigured."""
    global CHAT_DB_URL
    from .session_sampler import CHAT_DB_URL as SAMPLER_CHAT_DB_URL

    if CHAT_DB_URL is None:
        CHAT_DB_URL = SAMPLER_CHAT_DB_URL
    return create_engine(CHAT_DB_URL, pool_pre_ping=True)


def _get_session_duration_and_message_count(conversation_id: str) -> tuple[int, int]:
    """Fetch conversation duration (seconds) and message count from the chat DB.

    Duration is `updated_at - created_at` on the conversation; message count is the
    number of non-system messages in that conversation. On any failure (chat DB
    down, conversation missing, malformed row) this returns ``(0, 0)`` rather than
    raising — a metric ingestion problem must not take down the consumer for a
    session that the scorer's own sampler will also treat tolerantly.
    """
    if not conversation_id:
        return 0, 0
    try:
        engine = _get_chat_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT c.created_at, c.updated_at,
                           (SELECT COUNT(*) FROM messages m
                             WHERE m.conversation_id = c.id
                               AND m.role <> 'system') AS message_count
                    FROM conversations c
                    WHERE c.id = :conv_id
                    """
                ),
                {"conv_id": conversation_id},
            ).fetchone()
        if row is None:
            logger.warning("No conversation %s in chat DB", conversation_id)
            return 0, 0

        created_at, updated_at, message_count = row
        duration = _duration_between(created_at, updated_at)
        return duration, int(message_count or 0)
    except Exception as exc:  # noqa: BLE001 - degrade to zeros, never raise
        logger.warning("Failed to fetch session metrics for %s: %s", conversation_id, exc)
        return 0, 0


def _duration_between(created_at, updated_at) -> int:
    """Seconds between two timestamps, tolerating datetime objects or ISO strings
    (SQLite adapters may hand dates back as strings). Returns 0 on any gap/mismatch."""
    if created_at is None or updated_at is None:
        return 0
    try:
        if not isinstance(created_at, datetime):
            created_at = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        if not isinstance(updated_at, datetime):
            updated_at = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
    except ValueError:
        return 0
    # SQLite timestamps are naive; treat them as UTC so the subtraction is valid.
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return max(0, int((updated_at - created_at).total_seconds()))


def handle_session_completed(
    *,
    conversation_id: str | None,
    user_id: str | None,
    occurred_at: str | None,
    db: Session | None = None,
) -> None:
    """Handle session.completed event by recording anonymized metrics.

    Args:
        conversation_id: ID of the completed conversation
        user_id: User who completed the session (will be anonymized)
        occurred_at: ISO timestamp when session completed
        db: SQLAlchemy session (will create new if None)

    Raises:
        ValueError: if a required field is missing. ``None``/empty ``conversation_id``
            or a missing ``occurred_at`` are permanent message defects — raising here
            lets the consumer nack-without-requeue (or skip) rather than looping.
    """
    if not conversation_id or not occurred_at or not user_id:
        raise ValueError(
            "session.completed missing required field(s): "
            f"conversation_id={conversation_id!r} occurred_at={occurred_at!r} user_id={user_id!r}"
        )

    if db is None:
        db = SessionLocal()
        close_db = True
    else:
        close_db = False

    try:
        # Parse event timestamp. Normalise a trailing 'Z' (RFC3339) to the +00:00
        # offset Python's fromisoformat expects.
        event_dt = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
        session_date = event_dt.date()

        # Fetch session details (duration, message count)
        duration_seconds, message_count = _get_session_duration_and_message_count(
            conversation_id
        )

        # Anonymize user ID (research_salt for consistency across runs)
        user_hash = anonymize_user_id(user_id)

        # Create metric record
        metric = SessionMetric(
            user_hash=user_hash,
            session_date=session_date,
            session_duration_seconds=duration_seconds,
            message_count=message_count,
            conversation_id=conversation_id,
        )

        db.add(metric)
        db.commit()

        logger.info(
            "Recorded session metric: user_hash=%s date=%s duration=%ds messages=%d",
            user_hash,
            session_date,
            duration_seconds,
            message_count,
        )
    except ValueError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Failed to record session metric for %s: %s", conversation_id, exc)
        raise
    finally:
        if close_db:
            db.close()


class EventConsumer:
    """Consumes domain events from RabbitMQ and dispatches to handlers."""

    def __init__(self):
        self.url = settings.rabbitmq_url
        self.exchange = settings.amqp_exchange or "afrimentor.events"
        self.running = False

    def _on_message(self, ch, method, properties, body: bytes) -> None:
        """Handle incoming message from RabbitMQ.

        A permanently-bad message (missing required fields — a ``ValueError`` from
        the handler) is nacked *without* requeue so a malformed event cannot loop
        forever; transient errors (DB down, unexpected shape) requeue for retry.
        """
        try:
            payload = json.loads(body.decode())
            event = payload.get("event")

            logger.debug("Received event: %s", event)

            if event == "session.completed":
                data = payload.get("data", {}) or {}
                handle_session_completed(
                    conversation_id=data.get("conversation_id"),
                    user_id=data.get("user_id"),
                    occurred_at=payload.get("occurredAt") or payload.get("occurred_at"),
                )

            # Acknowledge the message
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except ValueError as exc:
            # Permanent defect — drop instead of poisoning the queue with retries.
            logger.error("Dropping malformed session.completed message: %s", exc)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as exc:
            logger.error("Error processing event: %s", exc, exc_info=True)
            # Transient error — requeue for retry
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def start(self) -> None:
        """Start consuming events (blocks until stop() is called)."""
        if not self.url:
            logger.warning("RABBITMQ_URL not set — event consumer disabled")
            return
        
        try:
            params = pika.URLParameters(self.url)
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            
            # Declare exchange
            ch.exchange_declare(
                exchange=self.exchange,
                exchange_type="topic",
                durable=True,
            )
            
            # Declare queue for this service
            queue_name = f"{settings.service_name}.session_metrics"
            ch.queue_declare(queue=queue_name, durable=True)
            
            # Bind to routing key
            ch.queue_bind(
                queue=queue_name,
                exchange=self.exchange,
                routing_key="session.completed",
            )
            
            # Set QoS
            ch.basic_qos(prefetch_count=1)
            
            # Start consuming
            logger.info(
                "Starting event consumer on %s (queue=%s, routing_key=session.completed)",
                self.exchange,
                queue_name,
            )
            self.running = True
            ch.basic_consume(queue=queue_name, on_message_callback=self._on_message)
            ch.start_consuming()
        except pika.exceptions.AMQPError as exc:
            logger.error("Event consumer error: %s", exc)
            raise
        except KeyboardInterrupt:
            logger.info("Event consumer interrupted")
            self.running = False
        finally:
            if ch and conn:
                conn.close()

    def stop(self) -> None:
        """Stop consuming events."""
        self.running = False


def start_consumer_thread() -> None:
    """Start the session-metrics consumer on a daemon thread in the background.

    A no-op when ``RABBITMQ_URL`` is unset so the service (and its test suite) can
    run without a broker; mirrors the feedback-service consumer wiring.
    """
    consumer = EventConsumer()
    if not consumer.url:
        logger.warning("RABBITMQ_URL not set — event consumer disabled")
        return
    thread = threading.Thread(
        target=consumer.start,
        name="session-metrics-consumer",
        daemon=True,
    )
    thread.start()
    logger.info("Started session-metrics consumer thread (daemon)")

