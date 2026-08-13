"""Tests for feedback-service (card O3.3)."""
from __future__ import annotations

from app.consumer import process_milestone_completed
from app.database import SessionLocal

USER_HEADERS = {"X-User-Id": "user-abc"}
OTHER_HEADERS = {"X-User-Id": "user-xyz"}

MILESTONE_COMPLETED_EVENT = {
    "event": "milestone.completed",
    "data": {
        "milestone_id": "m-1",
        "goal_id": "g-1",
        "user_id": "user-abc",
        "title": "Legal Readiness",
    },
}


# ── Submit / retrieve ────────────────────────────────────────────────────────

def test_submit_feedback_requires_identity(client):
    r = client.post("/api/v1/feedback", json={"nps_score": 8})
    assert r.status_code == 422


def test_submit_and_retrieve_feedback(client):
    r = client.post(
        "/api/v1/feedback", json={"nps_score": 9, "comment": "Loved it"}, headers=USER_HEADERS
    )
    assert r.status_code == 201
    body = r.json()
    assert body["nps_score"] == 9
    assert body["trigger"] == "manual"

    listing = client.get("/api/v1/feedback", headers=USER_HEADERS).json()
    assert len(listing) == 1
    assert listing[0]["comment"] == "Loved it"


def test_nps_score_out_of_range_rejected(client):
    r = client.post("/api/v1/feedback", json={"nps_score": 11}, headers=USER_HEADERS)
    assert r.status_code == 422


def test_feedback_is_scoped_per_user(client):
    client.post("/api/v1/feedback", json={"nps_score": 7}, headers=USER_HEADERS)
    other_listing = client.get("/api/v1/feedback", headers=OTHER_HEADERS).json()
    assert other_listing == []


def test_get_survey_not_found_for_other_user(client):
    submitted = client.post(
        "/api/v1/feedback", json={"nps_score": 7}, headers=USER_HEADERS
    ).json()
    r = client.get(f"/api/v1/feedback/surveys/{submitted['id']}", headers=OTHER_HEADERS)
    assert r.status_code == 404


# ── Milestone-completion trigger (consumer + pending prompts) ──────────────

def test_process_milestone_completed_creates_prompt():
    db = SessionLocal()
    try:
        prompt = process_milestone_completed(db, MILESTONE_COMPLETED_EVENT)
        assert prompt.user_id == "user-abc"
        assert prompt.trigger == "milestone_completed"
        assert prompt.context_ref == "m-1"
    finally:
        db.close()


def test_milestone_completion_surfaces_as_pending_prompt(client):
    db = SessionLocal()
    try:
        process_milestone_completed(db, MILESTONE_COMPLETED_EVENT)
    finally:
        db.close()

    r = client.get("/api/v1/feedback/pending", headers=USER_HEADERS)
    assert r.status_code == 200
    prompts = r.json()
    assert len(prompts) == 1
    assert prompts[0]["trigger"] == "milestone_completed"
    assert prompts[0]["context_ref"] == "m-1"


def test_pending_prompts_are_scoped_per_user(client):
    db = SessionLocal()
    try:
        process_milestone_completed(db, MILESTONE_COMPLETED_EVENT)
    finally:
        db.close()

    r = client.get("/api/v1/feedback/pending", headers=OTHER_HEADERS)
    assert r.json() == []


def test_submitting_against_prompt_resolves_it(client):
    db = SessionLocal()
    try:
        process_milestone_completed(db, MILESTONE_COMPLETED_EVENT)
    finally:
        db.close()

    r = client.post(
        "/api/v1/feedback",
        json={"nps_score": 10, "trigger": "milestone_completed", "context_ref": "m-1"},
        headers=USER_HEADERS,
    )
    assert r.status_code == 201

    pending = client.get("/api/v1/feedback/pending", headers=USER_HEADERS).json()
    assert pending == []


def test_submitting_unrelated_manual_feedback_does_not_resolve_prompt(client):
    db = SessionLocal()
    try:
        process_milestone_completed(db, MILESTONE_COMPLETED_EVENT)
    finally:
        db.close()

    client.post("/api/v1/feedback", json={"nps_score": 5}, headers=USER_HEADERS)

    pending = client.get("/api/v1/feedback/pending", headers=USER_HEADERS).json()
    assert len(pending) == 1
