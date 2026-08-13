"""Streak/heatmap computation — pure functions over a user's activity dates.

Kept free of DB session plumbing beyond the one query in `get_action_dates` so the
math (the part most worth getting right and testing thoroughly) doesn't need a
database fixture to exercise.
"""
from __future__ import annotations

import datetime as dt
from itertools import pairwise

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ActionEvent


def get_action_dates(db: Session, user_id: str) -> list[dt.date]:
    """One entry per logged event (not deduped) so callers that want per-day
    *counts* (the heatmap) can, while `compute_streaks` dedupes internally for
    callers that only care which days had *any* activity."""
    rows = db.scalars(
        select(ActionEvent.occurred_on).where(ActionEvent.user_id == user_id)
    ).all()
    return sorted(rows)


def compute_streaks(dates: list[dt.date], *, today: dt.date | None = None) -> tuple[int, int]:
    """Return (current_streak_days, longest_streak_days) over a sorted, deduped list
    of activity dates.

    Current streak counts back from today (or yesterday, if today has no activity
    yet — the streak isn't broken until a full day passes with nothing logged).
    """
    if not dates:
        return 0, 0
    today = today or dt.date.today()
    unique_days = sorted(set(dates))

    longest = 1
    run = 1
    for prev, curr in pairwise(unique_days):
        if (curr - prev).days == 1:
            run += 1
        else:
            run = 1
        longest = max(longest, run)

    last_active = unique_days[-1]
    gap_from_today = (today - last_active).days
    if gap_from_today > 1:
        return 0, longest  # streak already broken — more than a day of silence

    current = 1
    for i in range(len(unique_days) - 1, 0, -1):
        if (unique_days[i] - unique_days[i - 1]).days == 1:
            current += 1
        else:
            break
    return current, longest


def build_heatmap(
    dates: list[dt.date], *, window_days: int, today: dt.date | None = None
) -> list[dict]:
    """Per-day activity counts for the trailing `window_days`, oldest first — feeds
    the Progress Board's action heatmap. Days with no activity are included with
    count 0 so the client can render a fixed-width grid."""
    today = today or dt.date.today()
    counts: dict[dt.date, int] = {}
    for d in dates:
        counts[d] = counts.get(d, 0) + 1
    start = today - dt.timedelta(days=window_days - 1)
    days = [start + dt.timedelta(days=offset) for offset in range(window_days)]
    return [{"date": d.isoformat(), "count": counts.get(d, 0)} for d in days]
