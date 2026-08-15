"""Tests for chat-orchestration-service.

Uses an in-memory SQLite DB and stubs out the LLM call and RabbitMQ publish so
tests run without any external services.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from openai import AuthenticationError

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
    return "Great plan! Let's make it happen.", 10, 5, []


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
    return "That's a great commitment! Let's make it happen.", 10, 5, []


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


# ── RAG citations ─────────────────────────────────────────────────────────────

def _rag_reply_with_citations(*args, **kwargs):
    return "Here is advice grounded in the TEF curriculum.", 20, 8, [
        {"label": "TEF curriculum"},
        {"label": "AfriMentor corpus"},
    ]


def test_citations_returned_in_response(client, session_id):
    with patch("app.routers.chat.chat_completion", side_effect=_rag_reply_with_citations):
        r = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"content": "What does the TEF programme say about working capital?"},
            headers=USER_HEADERS,
        )
    assert r.status_code == 201
    body = r.json()
    assert body["citations"] == [
        {"label": "TEF curriculum"},
        {"label": "AfriMentor corpus"},
    ]


def test_no_citations_when_rag_empty(client, session_id):
    with patch("app.routers.chat.chat_completion", side_effect=_stub_completion):
        r = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"content": "Hello"},
            headers=USER_HEADERS,
        )
    assert r.status_code == 201
    assert r.json()["citations"] == []


# ── Persona binding (D2.2) ────────────────────────────────────────────────────

_MARKET_QUEEN_ID = "00000000-0000-0000-0000-000000000002"


def test_bind_persona_updates_session(client, session_id):
    r = client.patch(
        f"/api/v1/chat/sessions/{session_id}/persona",
        json={"persona_id": _MARKET_QUEEN_ID},
        headers=USER_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["persona_id"] == _MARKET_QUEEN_ID


def test_bind_persona_persists(client, session_id):
    client.patch(
        f"/api/v1/chat/sessions/{session_id}/persona",
        json={"persona_id": _MARKET_QUEEN_ID},
        headers=USER_HEADERS,
    )
    r = client.get(f"/api/v1/chat/sessions/{session_id}", headers=USER_HEADERS)
    assert r.json()["persona_id"] == _MARKET_QUEEN_ID


def test_bind_persona_unknown_session(client):
    r = client.patch(
        "/api/v1/chat/sessions/does-not-exist/persona",
        json={"persona_id": _MARKET_QUEEN_ID},
        headers=USER_HEADERS,
    )
    assert r.status_code == 404


def test_bind_persona_requires_identity(client, session_id):
    r = client.patch(
        f"/api/v1/chat/sessions/{session_id}/persona",
        json={"persona_id": _MARKET_QUEEN_ID},
    )
    assert r.status_code == 422


def test_bind_persona_wrong_user_cannot_rebind_session(client, session_id):
    """Card O3.5 — regression test for the IDOR this session's security pass fixed:
    another authenticated user must not be able to rebind someone else's session."""
    r = client.patch(
        f"/api/v1/chat/sessions/{session_id}/persona",
        json={"persona_id": _MARKET_QUEEN_ID},
        headers={"X-User-Id": "other-user"},
    )
    assert r.status_code == 404

    # And the original session is untouched.
    original = client.get(f"/api/v1/chat/sessions/{session_id}", headers=USER_HEADERS).json()
    assert original["persona_id"] is None


def test_send_message_uses_bound_persona(client, session_id):
    """After binding, chat_completion receives the persona_id."""
    client.patch(
        f"/api/v1/chat/sessions/{session_id}/persona",
        json={"persona_id": _MARKET_QUEEN_ID},
        headers=USER_HEADERS,
    )
    captured = {}

    async def _capture(*args, **kwargs):
        captured.update(kwargs)
        return "Reply.", 5, 3, []

    with patch("app.routers.chat.chat_completion", side_effect=_capture):
        client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"content": "Hello"},
            headers=USER_HEADERS,
        )
    assert captured.get("persona_id") == _MARKET_QUEEN_ID


# ── Tag It / commitment pipeline (D2.3) ─────────────────────────────────────

_GOAL_ID = "goal-001"


@pytest.fixture
def commitment_message_id(client, session_id):
    """Create a session with a commitment-candidate assistant message, return its id."""
    with patch("app.routers.chat.chat_completion", side_effect=_commitment_reply):
        r = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"content": "I will save ₦5,000 every week."},
            headers=USER_HEADERS,
        )
    assert r.json()["is_commitment_candidate"] is True
    return r.json()["id"]


def _mock_goals_ok(commitment_id="commitment-xyz"):
    from unittest.mock import MagicMock
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    mock.json.return_value = {"id": commitment_id, "goal_id": _GOAL_ID}
    return mock


def test_tag_it_returns_commitment(client, session_id, commitment_message_id):
    with (
        patch("app.routers.chat.httpx.post", return_value=_mock_goals_ok()) as mock_post,
        patch("app.routers.chat.emit_commitment_created") as mock_emit,
    ):
        r = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages/{commitment_message_id}/tag",
            json={"goal_id": _GOAL_ID},
            headers=USER_HEADERS,
        )
    assert r.status_code == 201
    body = r.json()
    assert body["commitment_id"] == "commitment-xyz"
    assert body["goal_id"] == _GOAL_ID
    assert body["message_id"] == commitment_message_id
    mock_post.assert_called_once()
    assert _GOAL_ID in mock_post.call_args.args[0]
    mock_emit.assert_called_once()


def test_tag_it_emits_correct_event_fields(client, session_id, commitment_message_id):
    with (
        patch("app.routers.chat.httpx.post", return_value=_mock_goals_ok("c-999")),
        patch("app.routers.chat.emit_commitment_created") as mock_emit,
    ):
        client.post(
            f"/api/v1/chat/sessions/{session_id}/messages/{commitment_message_id}/tag",
            json={"goal_id": _GOAL_ID},
            headers=USER_HEADERS,
        )
    kw = mock_emit.call_args.kwargs
    assert kw["commitment_id"] == "c-999"
    assert kw["goal_id"] == _GOAL_ID
    assert kw["user_id"] == "user-abc"
    assert kw["conversation_id"] == session_id
    assert kw["message_id"] == commitment_message_id


def test_tag_it_non_candidate_rejected(client, session_id):
    """Tagging a non-candidate message must return 422."""
    with patch("app.routers.chat.chat_completion", side_effect=_stub_completion):
        r = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"content": "Tell me about savings."},
            headers=USER_HEADERS,
        )
    msg_id = r.json()["id"]
    r2 = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages/{msg_id}/tag",
        json={"goal_id": _GOAL_ID},
        headers=USER_HEADERS,
    )
    assert r2.status_code == 422


def test_tag_it_wrong_session(client, session_id, commitment_message_id):
    other_sid = client.post(
        "/api/v1/chat/sessions", json={}, headers={"X-User-Id": "user-xyz"}
    ).json()["id"]
    r = client.post(
        f"/api/v1/chat/sessions/{other_sid}/messages/{commitment_message_id}/tag",
        json={"goal_id": _GOAL_ID},
        headers={"X-User-Id": "user-xyz"},
    )
    assert r.status_code == 404


def test_tag_it_goals_service_unreachable(client, session_id, commitment_message_id):
    import httpx as _httpx
    with patch(
        "app.routers.chat.httpx.post",
        side_effect=_httpx.RequestError("connection refused"),
    ):
        r = client.post(
            f"/api/v1/chat/sessions/{session_id}/messages/{commitment_message_id}/tag",
            json={"goal_id": _GOAL_ID},
            headers=USER_HEADERS,
        )
    assert r.status_code == 503


def test_rag_retrieve_called_with_user_content(client, session_id):
    """rag.retrieve must be called with the user's message text."""
    with (
        patch("app.llm.retrieve", return_value=[]) as mock_retrieve,
        patch("app.llm.get_llm_client"),  # prevent real OpenAI call
    ):
        # LLM_API_KEY is empty in test env so the stub path runs;
        # retrieve is still awaited before the stub branch.
        client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"content": "How do I build an emergency fund?"},
            headers=USER_HEADERS,
        )
    mock_retrieve.assert_awaited_once_with(
        "How do I build an emergency fund?", collection=None
    )


def test_rag_context_injected_into_prompt(client, session_id):
    """When chunks are returned, a second system message must appear in the
    messages list passed to the LLM containing the chunk text."""
    from fastapi.testclient import TestClient as _TC

    from app.database import SessionLocal, get_db
    from app.main import app as _app
    from app.rag import RagResult

    chunks = [RagResult(content="Save 20% of income.", source_label="TEF curriculum", score=0.9)]
    captured: list = []

    async def _fake_create(**kwargs):
        captured.extend(kwargs["messages"])
        raise RuntimeError("stop")

    def _override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    _app.dependency_overrides[get_db] = _override_db
    safe_client = _TC(_app, raise_server_exceptions=False)

    with (
        patch("app.llm.retrieve", return_value=chunks),
        patch("app.llm.get_llm_client") as mock_client,
        patch("app.llm.settings") as mock_settings,
    ):
        mock_client.return_value.chat.completions.create.side_effect = _fake_create
        mock_settings.llm_api_key = "fake-key"
        mock_settings.commitment_keywords = []
        mock_settings.llm_model = "test"
        mock_settings.llm_max_tokens = 512
        mock_settings.llm_temperature = 0.7
        safe_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"content": "How do I save?"},
            headers=USER_HEADERS,
        )

    _app.dependency_overrides.clear()

    rag_messages = [m for m in captured if "TEF curriculum" in m.get("content", "")]
    assert rag_messages, "RAG context system message not found in LLM messages list"


def test_invalid_llm_api_key_falls_back_to_stub(client, session_id):
    """A bad provider key should degrade to a safe stub response instead of 500."""
    with (
        patch("app.llm.retrieve", return_value=[]),
        patch(
            "app.routers.chat.chat_completion",
            wraps=__import__("app.llm", fromlist=["chat_completion"]).chat_completion,
        ) as wrapped,
    ):
        def _raise_invalid_key_exception(**kwargs):
            raise Exception("Invalid API Key")

        mock_client = type("Client", (), {})()
        mock_client.chat = type(
            "Chat",
            (),
            {
                "completions": type(
                    "Completions",
                    (),
                    {"create": staticmethod(_raise_invalid_key_exception)},
                )
            },
        )()

        with (
            patch("app.llm.get_llm_client", return_value=mock_client),
            patch("app.llm.settings") as mock_settings,
        ):
            mock_settings.llm_api_key = "bad-key"
            mock_settings.llm_model = "test"
            mock_settings.llm_max_tokens = 512
            mock_settings.llm_temperature = 0.7
            mock_settings.commitment_keywords = []
            r = client.post(
                f"/api/v1/chat/sessions/{session_id}/messages",
                json={"content": "How do I save?"},
                headers=USER_HEADERS,
            )

    assert r.status_code == 201
    assert "LLM unavailable" in r.json()["content"]
    wrapped.assert_called_once()
