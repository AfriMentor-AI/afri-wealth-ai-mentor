"""Integration tests for the C2.4 guardrail hooks in the chat request path.

Separate from test_guardrails.py, which unit-tests the module: these drive the
real endpoint and assert on what the pipeline actually does — most importantly
that a blocked turn never reaches RAG retrieval or the LLM.

Fixtures mirror tests/test_chat.py so both files behave identically.
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

BLOCKED_PROMPT = "Which crypto should I put my savings into?"
BENIGN_PROMPT = "How do I price my products so I actually make a profit?"


@pytest.fixture
def session_id(client):
    return client.post("/api/v1/chat/sessions", json={}, headers=USER_HEADERS).json()["id"]


def _stub_completion(*args, **kwargs):
    return "Great plan! Let's make it happen.", 10, 5, []


def _send(client, session_id, content):
    return client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={"content": content},
        headers=USER_HEADERS,
    )


# ── Blocked input short-circuits the pipeline ─────────────────────────────────

def test_blocked_input_never_calls_the_llm(client, session_id):
    """The whole point of the pre-hook: no generation on a high-risk query."""
    with patch("app.routers.chat.chat_completion", side_effect=_stub_completion) as llm:
        r = _send(client, session_id, BLOCKED_PROMPT)
    assert r.status_code == 201
    llm.assert_not_called()


def test_blocked_input_never_reaches_the_rag_corpus(client, session_id):
    """"Blocks retrieval" per the card — the query must not hit the corpus at all."""
    with (
        patch("app.rag.retrieve") as retrieve,
        patch("app.routers.chat.chat_completion", side_effect=_stub_completion),
    ):
        _send(client, session_id, BLOCKED_PROMPT)
    retrieve.assert_not_called()


def test_blocked_input_returns_in_persona_refusal(client, session_id):
    with patch("app.routers.chat.chat_completion", side_effect=_stub_completion):
        body = _send(client, session_id, BLOCKED_PROMPT).json()
    assert body["role"] == "assistant"
    assert body["guardrail_action"] == "block"
    assert "crypto_speculation" in body["guardrail_categories"]
    # Refusal, not an error payload, and it offers a way forward.
    assert "error" not in body["content"].lower()
    assert len(body["content"]) > 80


def test_blocked_turn_reports_zero_tokens(client, session_id):
    with patch("app.routers.chat.chat_completion", side_effect=_stub_completion):
        body = _send(client, session_id, BLOCKED_PROMPT).json()
    assert body["prompt_tokens"] == 0
    assert body["completion_tokens"] == 0
    assert body["citations"] == []


def test_blocked_turn_emits_no_commitment_event(client, session_id):
    """A refused high-risk turn must not become a tracked goal."""
    prompt = "I will put all my savings into bitcoin next week."
    with (
        patch("app.routers.chat.chat_completion", side_effect=_stub_completion),
        patch("app.routers.chat.emit_commitment_tag_suggested") as emit,
    ):
        body = _send(client, session_id, prompt).json()
    assert body["guardrail_action"] == "block"
    assert body["is_commitment_candidate"] is False
    emit.assert_not_called()


def test_blocked_turn_is_persisted_and_listed(client, session_id):
    with patch("app.routers.chat.chat_completion", side_effect=_stub_completion):
        _send(client, session_id, BLOCKED_PROMPT)
    messages = client.get(
        f"/api/v1/chat/sessions/{session_id}/messages", headers=USER_HEADERS
    ).json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["guardrail_action"] == "block"


# ── Output screening ──────────────────────────────────────────────────────────

def _unsafe_reply(*args, **kwargs):
    return "You should buy Dangote shares — guaranteed to double your money.", 10, 5, []


def _investment_reply(*args, **kwargs):
    return "Diversification means spreading your investment across different areas.", 10, 5, []


def test_unsafe_model_output_is_replaced_on_benign_input(client, session_id):
    """Innocuous question, unsafe generated answer — only the post-hook can catch this."""
    with patch("app.routers.chat.chat_completion", side_effect=_unsafe_reply):
        body = _send(client, session_id, BENIGN_PROMPT).json()
    assert body["guardrail_action"] == "block"
    assert "Dangote" not in body["content"]


def test_investment_adjacent_reply_gets_a_disclaimer(client, session_id):
    with patch("app.routers.chat.chat_completion", side_effect=_investment_reply):
        body = _send(client, session_id, BENIGN_PROMPT).json()
    assert body["guardrail_action"] == "disclaim"
    assert "Diversification means" in body["content"]
    assert "licensed" in body["content"].lower()


def test_disclaimer_is_not_duplicated(client, session_id):
    with patch("app.routers.chat.chat_completion", side_effect=_investment_reply):
        body = _send(client, session_id, "Tell me about investing generally.").json()
    assert body["content"].lower().count("not a licensed financial adviser") <= 1


# ── Allowed turns are untouched ───────────────────────────────────────────────

def test_benign_turn_is_allowed_and_unmodified(client, session_id):
    with patch("app.routers.chat.chat_completion", side_effect=_stub_completion):
        body = _send(client, session_id, BENIGN_PROMPT).json()
    assert body["guardrail_action"] == "allow"
    assert body["guardrail_categories"] == []
    assert body["content"] == "Great plan! Let's make it happen."


def test_commitment_still_flows_on_allowed_turns(client, session_id):
    """Guardrails must not break D2.3's commitment pipeline for ordinary turns."""
    with (
        patch("app.routers.chat.chat_completion", side_effect=_stub_completion),
        patch("app.routers.chat.emit_commitment_tag_suggested") as emit,
    ):
        body = _send(client, session_id, "I will save 5000 naira every week.").json()
    assert body["guardrail_action"] == "allow"
    assert body["is_commitment_candidate"] is True
    emit.assert_called_once()


# ── Kill switch ───────────────────────────────────────────────────────────────

def test_disabling_guardrails_restores_prior_behaviour(client, session_id):
    """GUARDRAILS_ENABLED=false must leave the pre-C2.4 pipeline exactly as it was."""
    from app.config import Settings

    disabled = Settings(guardrails_enabled=False)
    with (
        patch("app.routers.chat.get_settings", return_value=disabled),
        patch("app.routers.chat.chat_completion", side_effect=_unsafe_reply) as llm,
    ):
        body = _send(client, session_id, BLOCKED_PROMPT).json()

    llm.assert_called_once()
    assert body["guardrail_action"] is None
    assert body["guardrail_categories"] == []
    assert "Dangote" in body["content"]
