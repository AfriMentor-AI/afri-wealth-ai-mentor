from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class InsightItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1)
    category: str = Field(min_length=1, max_length=60)
    duration_minutes: int = Field(gt=0)
    is_audio: bool = False
    media_url: str | None = None


class InsightItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    summary: str
    category: str
    duration_minutes: int
    is_audio: bool
    media_url: str | None
    created_at: dt.datetime
    # Present only in contexts where the caller's identity is known (list/get
    # endpoints) — whether this item is in the current user's bookmarks.
    is_favorited: bool = False
