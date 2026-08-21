"""Event consumers for research-evaluation-service.

Listens to domain events from the afrimentor.events RabbitMQ topic exchange.
Currently handles:
  - session.completed: Record anonymized session metrics for pilot evaluation
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

import pika
import pika.exceptions
from sqlalchemy.orm import Session

from .config import get_settings
from .db.session import SessionLocal
from .models import SessionMetric, anonymize_user_id

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_session_duration_and_message_count(conversation_id: str) -> tuple[int, int]:
    """Fetch conversation details from local cache or API.
    
    For now, returns (0, 0) as a placeholder. In Sprint 5, this will:
      1. Query the chat-orchestration-service database
      2. Calculate duration from created_at/updated_at
      3. Count messages
    
    Later: consider a shared session cache or API call to chat-orchestration.
    """
    # TODO(C3.5): Fetch conversation details from chat-orchestration-service
    # This is a placeholder; real implementation will query Conversation model.
    logger.warning(
        "Session duration fetch not yet implemented; using defaults for %s",
        conversation_id,
    )
    return 0, 0  # placeholder: (duration_seconds, message_count)


def handle_session_completed(
    *,
    conversation_id: str,
    user_id: str,
    occurred_at: str,
    db: Session | None = None,
) -> None:
    """Handle session.completed event by recording anonymized metrics.
    
    Args:
        conversation_id: ID of the completed conversation
        user_id: User who completed the session (will be anonymized)
        occurred_at: ISO timestamp when session completed
        db: SQLAlchemy session (will create new if None)
    """
    if db is None:
        db = SessionLocal()
        close_db = True
    else:
        close_db = False
    
    try:
        # Parse event timestamp
        event_dt = datetime.fromisoformat(occurred_at.replace('Z', '+00:00'))
        session_date = event_dt.date()
        
        # Fetch session details (duration, message count)
        duration_seconds, message_count = _get_session_duration_and_message_count(
            conversation_id
        )
        
        # Anonymize user ID
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
        """Handle incoming message from RabbitMQ."""
        try:
            payload = json.loads(body.decode())
            event = payload.get("event")
            
            logger.debug("Received event: %s", event)
            
            if event == "session.completed":
                data = payload.get("data", {})
                handle_session_completed(
                    conversation_id=data.get("conversation_id"),
                    user_id=data.get("user_id"),
                    occurred_at=payload.get("occurredAt", ""),
                )
            
            # Acknowledge the message
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as exc:
            logger.error("Error processing event: %s", exc, exc_info=True)
            # Negative acknowledgement: requeue for retry
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
