"""Tests for chat-orchestration-service.

Uses an in-memory SQLite DB and stubs out the LLM call and RabbitMQ publish so
tests run without any external services.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine, get_db
from app.main import app

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(fresh_db):
    def _override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


USER_HEADERS = {"X-User-Id": "user-abc"}

# ── Health ────────────────────────────────────────────────────────────────────

def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["service"] == "chat-orchestration-service"


# ── Sessions ──────────────────────────────────────────────────────────────────

def test_create_session(client):
    r = client.post("/api/v1/chat/sessions", json={}, headers=USER_HEADERS)
    assert r.status_code == 201
    body = r.json()
    assert body["user_id"] == "user-abc"
    assert body["status"] == "active"


def test_get_session(client):
    sid = client.post("/api/v1/chat/sessions", json={}, headers=USER_HEADERS).json()["id"]
    r = client.get(f"/api/v1/chat/sessions/{sid}", headers=USER_HEADERS)
    assert r.status_code == 200
    assert r.json()["id"] == sid


def test_get_session_not_found(client):
    r = client.get("/api/v1/chat/sessions/does-not-exist", headers=USER_HEADERS)
    assert r.status_code == 404


def test_get_session_wrong_user(client):
    sid = client.post("/api/v1/chat/sessions", json={}, headers=USER_HEADERS).json()["id"]
    r = client.get(f"/api/v1/chat/sessions/{sid}", headers={"X-User-Id": "other-user"})
    assert r.status_code == 404


# ── Messages ──────────────────────────────────────────────────────────────────

@pytest.fixture
def session_id(client):
    return client.post("/api/v1/chat/sessions", json={}, headers=USER_HEADERS).json()["id"]


def _stub_completion(*args, **kwargs):
    return "Great plan! Let's make it happen.", 10, 5


def test_send_message_returns_assistant_reply(client, session_id):
    with patch("app.routers.chat.chat_completion", side_effect=_stub_completion):
        r = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"content": "How do I save more money?"},
            headers=USER_HEADERS,
        )
    assert r.status_code == 201
    body = r.json()
    assert body["role"] == "assistant"
    assert "Great plan" in body["content"]
    assert body["is_commitment_candidate"] is False


def test_list_messages(client, session_id):
    with patch("app.routers.chat.chat_completion", side_effect=_stub_completion):
        client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"content": "Hello"},
            headers=USER_HEADERS,
        )
    r = client.get(f"/api/v1/chat/sessions/{session_id}/messages", headers=USER_HEADERS)
    assert r.status_code == 200
    roles = [m["role"] for m in r.json()]
    assert roles == ["user", "assistant"]


# ── Commitment event ──────────────────────────────────────────────────────────

def _commitment_reply(*args, **kwargs):
    return "That's a great commitment! Let's make it happen.", 10, 5


def test_commitment_event_emitted(client, session_id):
    with (
        patch("app.routers.chat.chat_completion", side_effect=_commitment_reply),
        patch("app.routers.chat.emit_commitment_tag_suggested") as mock_emit,
    ):
        r = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"content": "I will save ₦5,000 every week starting Monday."},
            headers=USER_HEADERS,
        )
    assert r.status_code == 201
    assert r.json()["is_commitment_candidate"] is True
    mock_emit.assert_called_once()
    call_kwargs = mock_emit.call_args.kwargs
    assert call_kwargs["conversation_id"] == session_id
    assert call_kwargs["user_id"] == "user-abc"


def test_no_commitment_event_for_normal_reply(client, session_id):
    with (
        patch("app.routers.chat.chat_completion", side_effect=_stub_completion),
        patch("app.routers.chat.emit_commitment_tag_suggested") as mock_emit,
    ):
        client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"content": "Tell me about savings."},
            headers=USER_HEADERS,
        )
    mock_emit.assert_not_called()
