"""Streak-at-risk sweep (card O3.4 — v0 scaffold).

Bootstraps its candidate user set from this service's own Notification table
(anyone we've already notified) since no "list all users" endpoint exists
anywhere in this codebase yet — a known v0 limitation, resolved once a real
user directory or a smarter trigger source (e.g. the future daily-action job)
exists to seed the set instead.
"""
from __future__ import annotations

import datetime as dt
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Notification

logger = logging.getLogger(__name__)
settings = get_settings()


def _known_user_ids(db: Session) -> list[str]:
    return list(db.scalars(select(Notification.user_id).distinct()).all())


def _already_notified_today(db: Session, user_id: str, kind: str) -> bool:
    today = dt.date.today()
    start_of_day = dt.datetime(today.year, today.month, today.day, tzinfo=dt.UTC)
    row = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.kind == kind,
            Notification.created_at >= start_of_day,
        )
        .first()
    )
    return row is not None


def _fetch_streak(user_id: str) -> dict | None:
    try:
        resp = httpx.get(
            f"{settings.progress_service_url}/api/v1/progress/streak",
            headers={"X-User-Id": user_id},
            timeout=settings.upstream_timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError:
        logger.warning("streak fetch failed for user %s", user_id, exc_info=True)
        return None


def _is_at_risk(streak: dict, *, today: dt.date | None = None) -> bool:
    """A streak is "at risk" once it hasn't been extended today: current streak
    is nonzero but the last recorded action wasn't today."""
    today = today or dt.date.today()
    if streak.get("current_streak_days", 0) <= 0:
        return False
    updated_at = dt.datetime.fromisoformat(streak["updated_at"])
    return updated_at.date() < today


def run_streak_risk_sweep(db: Session) -> tuple[int, int]:
    """Check every known user's streak and notify anyone at risk who hasn't
    already been notified today. Returns (users_checked, notifications_created)."""
    user_ids = _known_user_ids(db)
    created = 0
    for user_id in user_ids:
        if _already_notified_today(db, user_id, "streak_at_risk"):
            continue
        streak = _fetch_streak(user_id)
        if not streak or not _is_at_risk(streak):
            continue
        days = streak["current_streak_days"]
        db.add(
            Notification(
                user_id=user_id,
                kind="streak_at_risk",
                title="Your streak is at risk!",
                body=f"You're on a {days}-day streak — log an action today to keep it alive.",
            )
        )
        db.commit()
        created += 1
    return len(user_ids), created
