"""Tests for the session.completed event consumer and handler (card F4)."""
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text

from app.db.session import Base, SessionLocal, engine
from app.events import (
    EventConsumer,
    _get_session_duration_and_message_count,
    handle_session_completed,
    start_consumer_thread,
)
from app.models import SessionMetric


@pytest.fixture
def db():
    """Create a fresh test database session."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def chat_engine():
    """An in-memory chat DB mirroring the conversations/messages shape the handler
    reads for duration + message count."""
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE conversations (
                    id TEXT PRIMARY KEY,
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY,
                    conversation_id TEXT,
                    role TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO conversations (id, created_at, updated_at) VALUES "
                "('conv-1', :created, :updated)"
            ),
            {
                "created": datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC),
                "updated": datetime(2026, 1, 1, 10, 5, 30, tzinfo=UTC),
            },
        )
        conn.execute(
            text(
                "INSERT INTO messages (conversation_id, role) VALUES "
                "('conv-1', 'user'), ('conv-1', 'assistant'), ('conv-1', 'system')"
            )
        )
    return engine


def test_get_session_duration_and_message_count(chat_engine, monkeypatch):
    monkeypatch.setattr("app.events._get_chat_engine", lambda: chat_engine)
    duration, count = _get_session_duration_and_message_count("conv-1")
    assert duration == 330  # 5m30s
    assert count == 2  # system message excluded


def test_get_session_duration_empty_conversation(chat_engine, monkeypatch):
    monkeypatch.setattr("app.events._get_chat_engine", lambda: chat_engine)
    duration, count = _get_session_duration_and_message_count("missing")
    assert (duration, count) == (0, 0)


def test_get_session_duration_no_conversation_id():
    assert _get_session_duration_and_message_count("") == (0, 0)


def test_handle_session_completed_records_metric(chat_engine, db, monkeypatch):
    monkeypatch.setattr("app.events._get_chat_engine", lambda: chat_engine)
    handle_session_completed(
        conversation_id="conv-1",
        user_id="user-123",
        occurred_at="2026-01-01T10:05:30Z",
        db=db,
    )
    metric = db.query(SessionMetric).one()
    assert metric.conversation_id == "conv-1"
    assert metric.session_duration_seconds == 330
    assert metric.message_count == 2
    assert metric.session_date == datetime(2026, 1, 1).date()
    assert metric.user_hash != "user-123"  # user id is anonymized
    assert len(metric.user_hash) == 16


def test_handle_session_completed_missing_fields_raises(db):
    with pytest.raises(ValueError):
        handle_session_completed(
            conversation_id=None,
            user_id="u",
            occurred_at="2026-01-01T10:00:00Z",
            db=db,
        )
    with pytest.raises(ValueError):
        handle_session_completed(
            conversation_id="c",
            user_id="u",
            occurred_at=None,
            db=db,
        )


def test_handle_session_completed_no_chat_db_still_records(db, monkeypatch):
    # Chat DB failure must degrade to zeros, not prevent metric recording.
    def boom():
        raise RuntimeError("chat db down")

    monkeypatch.setattr("app.events._get_chat_engine", boom)
    handle_session_completed(
        conversation_id="conv-x",
        user_id="user-456",
        occurred_at="2026-02-01T12:00:00Z",
        db=db,
    )
    metric = db.query(SessionMetric).one()
    assert metric.conversation_id == "conv-x"
    assert metric.session_duration_seconds == 0
    assert metric.message_count == 0


def test_start_consumer_thread_is_noop_without_rabbitmq(monkeypatch):
    # With an empty RABBITMQ_URL the consumer must not attempt a broker connection.
    monkeypatch.setattr(
        "app.events.settings", type("S", (), {"rabbitmq_url": "", "amqp_exchange": "e"})()
    )
    started = []
    monkeypatch.setattr(
        "app.events.EventConsumer.start", lambda self: started.append(True) or None
    )
    start_consumer_thread()
    assert started == []  # no-op: no url, so start() never invoked


def test_consumer_builds_url_attr(monkeypatch):
    monkeypatch.setattr(
        "app.events.settings", type("S", (), {"rabbitmq_url": "", "amqp_exchange": "e"})()
    )
    consumer = EventConsumer()
    assert consumer.url == ""
    assert consumer.exchange == "e"
