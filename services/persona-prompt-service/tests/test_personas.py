"""Tests for persona-prompt-service (card D2.2)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_CHIOMA_ID = "00000000-0000-0000-0000-000000000001"
_MARKET_QUEEN_ID = "00000000-0000-0000-0000-000000000002"
_KWAME_ID = "00000000-0000-0000-0000-000000000007"
_UNKNOWN_ID = "00000000-0000-0000-0000-000000000099"
USER_HEADERS = {"X-User-Id": "user-abc"}


# ── List ──────────────────────────────────────────────────────────────────────

def test_list_personas_returns_all():
    r = client.get("/api/v1/personas")
    assert r.status_code == 200
    personas = r.json()
    assert len(personas) == 6
    slugs = {p["slug"] for p in personas}
    assert "chioma-base" in slugs
    assert "market-queen" in slugs


def test_list_personas_shape():
    r = client.get("/api/v1/personas")
    p = r.json()[0]
    for field in ("id", "slug", "display_name", "tagline", "sector_tags", "template_file",
                   "is_base", "status"):
        assert field in p


# ── Beta gating (card C4.4) ────────────────────────────────────────────────────

def test_list_personas_hides_beta_by_default():
    r = client.get("/api/v1/personas")
    assert r.status_code == 200
    slugs = {p["slug"] for p in r.json()}
    assert "kwame-base" not in slugs


def test_list_personas_includes_beta_when_flag_enabled(beta_personas_enabled):
    r = client.get("/api/v1/personas")
    assert r.status_code == 200
    personas = r.json()
    assert len(personas) == 7
    kwame = next(p for p in personas if p["slug"] == "kwame-base")
    assert kwame["status"] == "beta"
    assert kwame["display_name"] == "Kwame"


def test_select_beta_persona_hidden_by_default():
    r = client.post(
        f"/api/v1/personas/{_KWAME_ID}/select",
        json={"session_id": "sess-123"},
        headers=USER_HEADERS,
    )
    assert r.status_code == 404


def test_preview_beta_persona_hidden_by_default():
    r = client.get(f"/api/v1/personas/{_KWAME_ID}/preview")
    assert r.status_code == 404


def test_prompt_beta_persona_hidden_by_default():
    r = client.get(f"/api/v1/personas/{_KWAME_ID}/prompt")
    assert r.status_code == 404


def test_select_beta_persona_when_flag_enabled(beta_personas_enabled):
    with patch("app.routers.personas.httpx.patch", side_effect=_mock_patch_ok):
        r = client.post(
            f"/api/v1/personas/{_KWAME_ID}/select",
            json={"session_id": "sess-456"},
            headers=USER_HEADERS,
        )
    assert r.status_code == 200
    assert r.json()["display_name"] == "Kwame"


def test_prompt_beta_persona_when_flag_enabled(beta_personas_enabled):
    r = client.get(
        f"/api/v1/personas/{_KWAME_ID}/prompt",
        params={"user_name": "Kojo"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["persona_id"] == _KWAME_ID
    assert "Kojo" in body["system_prompt"]


# ── Select / bind ─────────────────────────────────────────────────────────────

def _mock_patch_ok(*args, **kwargs):
    mock = MagicMock()
    mock.raise_for_status.return_value = None
    return mock


def test_select_persona_calls_chat_service():
    with patch("app.routers.personas.httpx.patch", side_effect=_mock_patch_ok) as mock_patch:
        r = client.post(
            f"/api/v1/personas/{_MARKET_QUEEN_ID}/select",
            json={"session_id": "sess-123"},
            headers=USER_HEADERS,
        )
    assert r.status_code == 200
    body = r.json()
    assert body["persona_id"] == _MARKET_QUEEN_ID
    assert body["session_id"] == "sess-123"
    assert body["display_name"] == "The Market Queen"
    mock_patch.assert_called_once()
    call_url = mock_patch.call_args.args[0]
    assert "sess-123" in call_url
    assert mock_patch.call_args.kwargs["json"] == {"persona_id": _MARKET_QUEEN_ID}
    # Card O3.5: identity must be forwarded so chat-orchestration-service can
    # verify session ownership — without this, select_persona would let any
    # authenticated user rebind another user's chat session (fixed IDOR).
    assert mock_patch.call_args.kwargs["headers"] == {"X-User-Id": "user-abc"}


def test_select_persona_requires_identity():
    r = client.post(
        f"/api/v1/personas/{_MARKET_QUEEN_ID}/select",
        json={"session_id": "sess-123"},
    )
    assert r.status_code == 422


def test_select_unknown_persona_returns_404():
    r = client.post(
        f"/api/v1/personas/{_UNKNOWN_ID}/select",
        json={"session_id": "sess-123"},
        headers=USER_HEADERS,
    )
    assert r.status_code == 404


def test_select_persona_chat_service_unreachable():
    import httpx as _httpx

    with patch(
        "app.routers.personas.httpx.patch",
        side_effect=_httpx.RequestError("connection refused"),
    ):
        r = client.post(
            f"/api/v1/personas/{_MARKET_QUEEN_ID}/select",
            json={"session_id": "sess-123"},
            headers=USER_HEADERS,
        )
    assert r.status_code == 503


# ── Audio preview ─────────────────────────────────────────────────────────────

def test_audio_preview_returns_stub_url():
    r = client.get(f"/api/v1/personas/{_CHIOMA_ID}/preview")
    assert r.status_code == 200
    body = r.json()
    assert body["persona_id"] == _CHIOMA_ID
    assert _CHIOMA_ID in body["audio_url"]
    assert "note" in body


def test_audio_preview_unknown_persona():
    r = client.get(f"/api/v1/personas/{_UNKNOWN_ID}/preview")
    assert r.status_code == 404


# ── Rendered prompt ───────────────────────────────────────────────────────────

def test_get_prompt_renders_template():
    r = client.get(
        f"/api/v1/personas/{_MARKET_QUEEN_ID}/prompt",
        params={"user_name": "Amara", "sector": "trader", "country": "GH"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["persona_id"] == _MARKET_QUEEN_ID
    assert "Amara" in body["system_prompt"]
    assert len(body["system_prompt"]) > 100


def test_get_prompt_unknown_persona():
    r = client.get(f"/api/v1/personas/{_UNKNOWN_ID}/prompt")
    assert r.status_code == 404
