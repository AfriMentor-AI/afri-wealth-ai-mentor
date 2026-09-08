from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import DIFFICULTIES, MEDIA_TYPES


class InsightItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1)
    category: str = Field(min_length=1, max_length=60)
    media_type: str = "text"
    duration_seconds: int = Field(gt=0)
    language: str = Field(default="en", max_length=10)
    difficulty: str = "beginner"
    media_url: str | None = None
    thumbnail_url: str | None = None
    transcript_url: str | None = None

    @field_validator("media_type")
    @classmethod
    def _valid_media_type(cls, v: str) -> str:
        if v not in MEDIA_TYPES:
            raise ValueError(f"media_type must be one of {sorted(MEDIA_TYPES)}")
        return v

    @field_validator("difficulty")
    @classmethod
    def _valid_difficulty(cls, v: str) -> str:
        if v not in DIFFICULTIES:
            raise ValueError(f"difficulty must be one of {sorted(DIFFICULTIES)}")
        return v


class InsightItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    summary: str
    category: str
    media_type: str
    duration_seconds: int
    language: str
    difficulty: str
    media_url: str | None
    thumbnail_url: str | None
    transcript_url: str | None
    created_at: dt.datetime
    is_favorited: bool = False


class InsightProgressUpsert(BaseModel):
    position_seconds: int = Field(ge=0)
    completed: bool = False


class InsightProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    insight_id: str
    position_seconds: int
    completed: bool
    last_accessed_at: dt.datetime
