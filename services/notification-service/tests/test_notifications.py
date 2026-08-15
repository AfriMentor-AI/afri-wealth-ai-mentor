"""Tests for notification-service (card O3.4, v0 scaffold)."""
from __future__ import annotations

import datetime as dt

import app.sweep as sweep_module

USER_HEADERS = {"X-User-Id": "user-abc"}
OTHER_HEADERS = {"X-User-Id": "user-xyz"}


def _trigger_reminder(client, user_id: str = "user-abc"):
    return client.post(
        "/api/v1/notifications/trigger/daily-action-reminder",
        json={"user_id": user_id, "action_title": "Save 10% of today's profit"},
    )


# ── User-facing endpoints ────────────────────────────────────────────────────

def test_list_requires_identity(client):
    r = client.get("/api/v1/notifications")
    assert r.status_code == 422


def test_trigger_daily_action_reminder_creates_and_lists(client):
    r = _trigger_reminder(client)
    assert r.status_code == 201
    assert r.json()["kind"] == "daily_action_reminder"

    listing = client.get("/api/v1/notifications", headers=USER_HEADERS).json()
    assert len(listing) == 1
    assert listing[0]["read_at"] is None


def test_trigger_streak_at_risk_creates_notification(client):
    r = client.post(
        "/api/v1/notifications/trigger/streak-at-risk",
        json={"user_id": "user-abc", "current_streak_days": 4},
    )
    assert r.status_code == 201
    assert r.json()["kind"] == "streak_at_risk"


def test_notifications_scoped_per_user(client):
    _trigger_reminder(client, "user-abc")
    other_listing = client.get("/api/v1/notifications", headers=OTHER_HEADERS).json()
    assert other_listing == []


def test_mark_read(client):
    _trigger_reminder(client)
    notification_id = client.get("/api/v1/notifications", headers=USER_HEADERS).json()[0]["id"]

    r = client.post(f"/api/v1/notifications/{notification_id}/read", headers=USER_HEADERS)
    assert r.status_code == 200
    assert r.json()["read_at"] is not None


def test_mark_read_requires_ownership(client):
    _trigger_reminder(client, "user-abc")
    notification_id = client.get("/api/v1/notifications", headers=USER_HEADERS).json()[0]["id"]

    r = client.post(f"/api/v1/notifications/{notification_id}/read", headers=OTHER_HEADERS)
    assert r.status_code == 404


def test_mark_all_read(client):
    _trigger_reminder(client)
    client.post(
        "/api/v1/notifications/trigger/streak-at-risk",
        json={"user_id": "user-abc", "current_streak_days": 3},
    )
    r = client.post("/api/v1/notifications/read-all", headers=USER_HEADERS)
    assert r.status_code == 200
    assert all(n["read_at"] is not None for n in r.json())


# ── Streak-at-risk sweep ─────────────────────────────────────────────────────

def test_sweep_creates_notification_when_at_risk(client, monkeypatch):
    _trigger_reminder(client, "user-abc")  # bootstraps "user-abc" into the known-user set
    yesterday = dt.date.today() - dt.timedelta(days=1)
    monkeypatch.setattr(
        sweep_module,
        "_fetch_streak",
        lambda user_id: {
            "current_streak_days": 5,
            "updated_at": dt.datetime.combine(yesterday, dt.time(12, 0), tzinfo=dt.UTC).isoformat(),
        },
    )

    r = client.post("/api/v1/notifications/sweep")
    assert r.status_code == 200
    assert r.json()["notifications_created"] == 1

    kinds = [n["kind"] for n in client.get("/api/v1/notifications", headers=USER_HEADERS).json()]
    assert kinds.count("streak_at_risk") == 1


def test_sweep_skips_when_updated_today(client, monkeypatch):
    _trigger_reminder(client, "user-abc")
    today = dt.datetime.now(tz=dt.UTC)
    monkeypatch.setattr(
        sweep_module,
        "_fetch_streak",
        lambda user_id: {"current_streak_days": 5, "updated_at": today.isoformat()},
    )

    r = client.post("/api/v1/notifications/sweep")
    assert r.json()["notifications_created"] == 0


def test_sweep_skips_zero_streak(client, monkeypatch):
    _trigger_reminder(client, "user-abc")
    yesterday = dt.datetime.now(tz=dt.UTC) - dt.timedelta(days=1)
    monkeypatch.setattr(
        sweep_module,
        "_fetch_streak",
        lambda user_id: {"current_streak_days": 0, "updated_at": yesterday.isoformat()},
    )

    r = client.post("/api/v1/notifications/sweep")
    assert r.json()["notifications_created"] == 0


def test_sweep_does_not_duplicate_same_day(client, monkeypatch):
    _trigger_reminder(client, "user-abc")
    yesterday = dt.datetime.now(tz=dt.UTC) - dt.timedelta(days=1)
    monkeypatch.setattr(
        sweep_module,
        "_fetch_streak",
        lambda user_id: {"current_streak_days": 5, "updated_at": yesterday.isoformat()},
    )

    first = client.post("/api/v1/notifications/sweep")
    second = client.post("/api/v1/notifications/sweep")
    assert first.json()["notifications_created"] == 1
    assert second.json()["notifications_created"] == 0
