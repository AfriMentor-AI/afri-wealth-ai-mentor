"""Tests for goals-milestones-service (card D2.3)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine, get_db
from app.main import app

USER_HEADERS = {"X-User-Id": "user-abc"}
OTHER_HEADERS = {"X-User-Id": "user-xyz"}


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


@pytest.fixture
def goal_id(client):
    r = client.post("/api/v1/goals", json={"title": "Save ₦500k"}, headers=USER_HEADERS)
    assert r.status_code == 201
    return r.json()["id"]


# ── Health ────────────────────────────────────────────────────────────────────

def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "goals-milestones-service"


# ── Goals ─────────────────────────────────────────────────────────────────────

def test_create_goal(client):
    r = client.post(
        "/api/v1/goals",
        json={"title": "Save ₦500k", "description": "Emergency fund"},
        headers=USER_HEADERS,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Save ₦500k"
    assert body["user_id"] == "user-abc"
    assert body["status"] == "active"


def test_list_goals(client, goal_id):
    r = client.get("/api/v1/goals", headers=USER_HEADERS)
    assert r.status_code == 200
    assert any(g["id"] == goal_id for g in r.json())


def test_get_goal_wrong_user(client, goal_id):
    r = client.get(f"/api/v1/goals/{goal_id}", headers=OTHER_HEADERS)
    assert r.status_code == 404


def test_get_goal_includes_progress_pct(client, goal_id):
    r = client.get(f"/api/v1/goals/{goal_id}", headers=USER_HEADERS)
    assert r.json()["progress_pct"] == 0


def test_create_goal_with_deadline(client):
    r = client.post(
        "/api/v1/goals",
        json={"title": "Start a Poultry Business", "deadline": "2026-12-01"},
        headers=USER_HEADERS,
    )
    assert r.status_code == 201
    assert r.json()["deadline"] == "2026-12-01"


def test_update_goal_partial(client, goal_id):
    r = client.patch(
        f"/api/v1/goals/{goal_id}", json={"deadline": "2026-11-15"}, headers=USER_HEADERS
    )
    assert r.status_code == 200
    body = r.json()
    assert body["deadline"] == "2026-11-15"
    assert body["title"] == "Save ₦500k"  # untouched


def test_update_goal_ignores_explicit_null_title(client, goal_id):
    """title is NOT NULL — an explicit `"title": null` must not crash the request."""
    r = client.patch(f"/api/v1/goals/{goal_id}", json={"title": None}, headers=USER_HEADERS)
    assert r.status_code == 200
    assert r.json()["title"] == "Save ₦500k"


def test_update_goal_requires_ownership(client, goal_id):
    r = client.patch(
        f"/api/v1/goals/{goal_id}", json={"title": "Hijacked"}, headers=OTHER_HEADERS
    )
    assert r.status_code == 404


def test_delete_goal(client, goal_id):
    r = client.delete(f"/api/v1/goals/{goal_id}", headers=USER_HEADERS)
    assert r.status_code == 204
    r2 = client.get(f"/api/v1/goals/{goal_id}", headers=USER_HEADERS)
    assert r2.status_code == 404


def test_delete_goal_requires_ownership(client, goal_id):
    r = client.delete(f"/api/v1/goals/{goal_id}", headers=OTHER_HEADERS)
    assert r.status_code == 404


def test_delete_goal_cascades_milestones(client, goal_id):
    client.post(
        f"/api/v1/goals/{goal_id}/milestones", json={"title": "Step 1"}, headers=USER_HEADERS
    )
    client.delete(f"/api/v1/goals/{goal_id}", headers=USER_HEADERS)
    r = client.get(f"/api/v1/goals/{goal_id}/milestones", headers=USER_HEADERS)
    assert r.status_code == 404


# ── Tagged Commitments ────────────────────────────────────────────────────────

def _commitment_payload(message_id: str = "msg-001") -> dict:
    return {
        "user_id": "user-abc",
        "conversation_id": "conv-001",
        "message_id": message_id,
        "content": "I will save ₦5,000 every week starting Monday.",
    }


def test_create_commitment(client, goal_id):
    with patch("app.routers.goals.emit_commitment_created") as mock_emit:
        r = client.post(
            f"/api/v1/goals/{goal_id}/commitments",
            json=_commitment_payload(),
        )
    assert r.status_code == 201
    body = r.json()
    assert body["goal_id"] == goal_id
    assert body["message_id"] == "msg-001"
    assert body["content"] == "I will save ₦5,000 every week starting Monday."
    mock_emit.assert_called_once()
    call_kw = mock_emit.call_args.kwargs
    assert call_kw["goal_id"] == goal_id
    assert call_kw["message_id"] == "msg-001"


def test_create_commitment_unknown_goal(client):
    r = client.post(
        "/api/v1/goals/does-not-exist/commitments",
        json=_commitment_payload(),
    )
    assert r.status_code == 404


def test_duplicate_message_tag_rejected(client, goal_id):
    with patch("app.routers.goals.emit_commitment_created"):
        client.post(f"/api/v1/goals/{goal_id}/commitments", json=_commitment_payload())
        r = client.post(f"/api/v1/goals/{goal_id}/commitments", json=_commitment_payload())
    assert r.status_code == 409


def test_list_commitments(client, goal_id):
    with patch("app.routers.goals.emit_commitment_created"):
        client.post(f"/api/v1/goals/{goal_id}/commitments", json=_commitment_payload("msg-001"))
        client.post(f"/api/v1/goals/{goal_id}/commitments", json=_commitment_payload("msg-002"))
    r = client.get(f"/api/v1/goals/{goal_id}/commitments", headers=USER_HEADERS)
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_commitments_wrong_user(client, goal_id):
    r = client.get(f"/api/v1/goals/{goal_id}/commitments", headers=OTHER_HEADERS)
    assert r.status_code == 404


def test_commitment_event_payload(client, goal_id):
    with patch("app.routers.goals.emit_commitment_created") as mock_emit:
        client.post(f"/api/v1/goals/{goal_id}/commitments", json=_commitment_payload())
    kw = mock_emit.call_args.kwargs
    assert kw["conversation_id"] == "conv-001"
    assert kw["user_id"] == "user-abc"
    assert "commitment_id" in kw
