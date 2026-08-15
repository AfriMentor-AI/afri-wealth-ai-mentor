from __future__ import annotations

import datetime as dt
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

# ── Actions ──────────────────────────────────────────────────────────────────

class ActionKind(str, Enum):
    daily_action = "daily_action"
    insight_completed = "insight_completed"
    savings_goal_met = "savings_goal_met"


class ActionCreate(BaseModel):
    kind: ActionKind
    # Defaults to today (server clock) when omitted — callers backfilling seed/test
    # history can set this explicitly.
    occurred_on: dt.date | None = None


class BadgeAward(BaseModel):
    badge_id: str
    label: str


# ── Streak ───────────────────────────────────────────────────────────────────

class StreakStatResponse(BaseModel):
    user_id: str
    current_streak_days: int
    longest_streak_days: int
    actions_completed_total: int
    updated_at: dt.datetime


class ActionRecordResponse(BaseModel):
    streak: StreakStatResponse
    newly_earned_badges: list[BadgeAward]


class HeatmapDay(BaseModel):
    date: dt.date
    count: int


# ── Badges ───────────────────────────────────────────────────────────────────

class BadgeWithStatus(BaseModel):
    id: str
    label: str
    description: str
    icon_name: str
    earned_at: dt.datetime | None


# ── Summary ──────────────────────────────────────────────────────────────────

class ProgressSummary(BaseModel):
    streak: StreakStatResponse
    heatmap: list[HeatmapDay]
    badges: list[BadgeWithStatus]


# ── Weekly summary share ────────────────────────────────────────────────────

class WeeklySummaryShare(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    week_start: dt.date
    week_end: dt.date
    actions_this_week: int
    current_streak_days: int
    badges_earned_this_week: list[str]
    share_text: str = Field(
        description="Pre-formatted, human-readable summary suitable for sharing."
    )
