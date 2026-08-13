"""Tests for progress-gamification-service (card O3.1)."""
from __future__ import annotations

import datetime as dt

from app.badges import BADGE_CATALOG
from app.streaks import build_heatmap, compute_streaks

USER_HEADERS = {"X-User-Id": "user-abc"}
OTHER_HEADERS = {"X-User-Id": "user-xyz"}


def _record(client, occurred_on: dt.date, kind: str = "daily_action", headers=USER_HEADERS):
    return client.post(
        "/api/v1/progress/actions",
        json={"kind": kind, "occurred_on": occurred_on.isoformat()},
        headers=headers,
    )


# ── Pure streak math ─────────────────────────────────────────────────────────

def test_compute_streaks_consecutive_days():
    today = dt.date(2026, 8, 16)
    dates = [today - dt.timedelta(days=i) for i in range(5)]  # 5-day run ending today
    current, longest = compute_streaks(dates, today=today)
    assert current == 5
    assert longest == 5


def test_compute_streaks_gap_breaks_current_but_not_longest():
    today = dt.date(2026, 8, 16)
    # A 10-day run three weeks ago, then a gap, then nothing today.
    old_run = [today - dt.timedelta(days=30 + i) for i in range(10)]
    current, longest = compute_streaks(old_run, today=today)
    assert current == 0
    assert longest == 10


def test_compute_streaks_today_not_required_yesterday_counts():
    today = dt.date(2026, 8, 16)
    dates = [today - dt.timedelta(days=1), today - dt.timedelta(days=2)]
    current, _ = compute_streaks(dates, today=today)
    assert current == 2  # streak isn't broken until a full day passes with nothing


def test_compute_streaks_empty():
    assert compute_streaks([]) == (0, 0)


def test_build_heatmap_window_and_counts():
    today = dt.date(2026, 8, 16)
    dates = [today, today, today - dt.timedelta(days=2)]
    heatmap = build_heatmap(dates, window_days=7, today=today)
    assert len(heatmap) == 7
    by_date = {d["date"]: d["count"] for d in heatmap}
    assert by_date[today.isoformat()] == 2
    assert by_date[(today - dt.timedelta(days=2)).isoformat()] == 1
    assert by_date[(today - dt.timedelta(days=1)).isoformat()] == 0


# ── API: recording actions + streak/heatmap ─────────────────────────────────

def test_record_action_requires_identity(client):
    # No X-User-Id header at all — FastAPI's own required-header validation
    # rejects this before the route body runs (422), same as goals-milestones-service.
    r = client.post("/api/v1/progress/actions", json={"kind": "daily_action"})
    assert r.status_code == 422


def test_record_action_updates_streak(client):
    r = _record(client, dt.date.today())
    assert r.status_code == 201
    body = r.json()
    assert body["streak"]["current_streak_days"] == 1
    assert body["streak"]["actions_completed_total"] == 1


def test_record_action_same_day_kind_twice_is_idempotent(client):
    today = dt.date.today()
    _record(client, today)
    r = _record(client, today)
    assert r.status_code == 201
    assert r.json()["streak"]["actions_completed_total"] == 1


def test_seeded_activity_history_reflected_in_streak_and_heatmap(client):
    today = dt.date.today()
    for i in range(6):
        _record(client, today - dt.timedelta(days=i))

    r = client.get("/api/v1/progress/streak", headers=USER_HEADERS)
    assert r.status_code == 200
    assert r.json()["current_streak_days"] == 6

    r = client.get("/api/v1/progress", headers=USER_HEADERS)
    assert r.status_code == 200
    heatmap = r.json()["heatmap"]
    active_days = [d for d in heatmap if d["count"] > 0]
    assert len(active_days) == 6


def test_streaks_are_per_user(client):
    today = dt.date.today()
    _record(client, today, headers=USER_HEADERS)
    r = client.get("/api/v1/progress/streak", headers=OTHER_HEADERS)
    assert r.json()["current_streak_days"] == 0


# ── Badges ───────────────────────────────────────────────────────────────────

def test_badge_catalog_has_three_badges():
    assert {b.id for b in BADGE_CATALOG} == {
        "consistency_queen",
        "smart_saver",
        "scholar_spirit",
    }


def test_badges_start_locked(client):
    r = client.get("/api/v1/progress/badges", headers=USER_HEADERS)
    assert r.status_code == 200
    assert all(b["earned_at"] is None for b in r.json())


def test_consistency_queen_awarded_at_seven_day_streak(client):
    today = dt.date.today()
    for i in range(6):
        r = _record(client, today - dt.timedelta(days=i))
    assert r.json()["newly_earned_badges"] == []

    r = _record(client, today - dt.timedelta(days=6))  # 7th consecutive day
    awarded = {a["badge_id"] for a in r.json()["newly_earned_badges"]}
    assert "consistency_queen" in awarded

    badges = client.get("/api/v1/progress/badges", headers=USER_HEADERS).json()
    cq = next(b for b in badges if b["id"] == "consistency_queen")
    assert cq["earned_at"] is not None


def test_smart_saver_awarded_on_savings_goal_met(client):
    r = _record(client, dt.date.today(), kind="savings_goal_met")
    awarded = {a["badge_id"] for a in r.json()["newly_earned_badges"]}
    assert awarded == {"smart_saver"}


def test_scholar_spirit_awarded_after_five_insights(client):
    today = dt.date.today()
    for i in range(4):
        r = _record(client, today - dt.timedelta(days=i), kind="insight_completed")
    assert r.json()["newly_earned_badges"] == []

    r = _record(client, today - dt.timedelta(days=4), kind="insight_completed")
    awarded = {a["badge_id"] for a in r.json()["newly_earned_badges"]}
    assert "scholar_spirit" in awarded


def test_badge_not_re_awarded_once_earned(client):
    r = _record(client, dt.date.today(), kind="savings_goal_met")
    assert {a["badge_id"] for a in r.json()["newly_earned_badges"]} == {"smart_saver"}

    r = _record(client, dt.date.today(), kind="daily_action")
    assert r.json()["newly_earned_badges"] == []


# ── Weekly summary share ─────────────────────────────────────────────────────

def test_weekly_summary_share(client):
    today = dt.date.today()
    for i in range(3):
        _record(client, today - dt.timedelta(days=i))

    r = client.post("/api/v1/progress/summary/share", headers=USER_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["actions_this_week"] == 3
    assert body["current_streak_days"] == 3
    assert str(body["actions_this_week"]) in body["share_text"]
