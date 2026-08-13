from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    kind: str
    title: str
    body: str
    created_at: dt.datetime
    read_at: dt.datetime | None
    delivered_at: dt.datetime


class DailyActionReminderTrigger(BaseModel):
    user_id: str = Field(min_length=1)
    action_title: str | None = None


class StreakAtRiskTrigger(BaseModel):
    user_id: str = Field(min_length=1)
    current_streak_days: int = Field(ge=1)


class SweepResult(BaseModel):
    users_checked: int
    notifications_created: int
