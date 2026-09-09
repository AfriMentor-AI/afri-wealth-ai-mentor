from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from .models import DIFFICULTIES, MEDIA_TYPES


class InsightItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1)
    category: str = Field(min_length=1, max_length=60)
    slug: str | None = None
    media_type: str = "text"
    duration_seconds: int = Field(gt=0)
    language: str = Field(default="en", max_length=10)
    difficulty: str = "beginner"
    media_url: str | None = None
    thumbnail_url: str | None = None
    transcript_url: str | None = None
    content: str | None = None
    audio_narration: str | None = None

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
    slug: str | None = None
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
    content: str | None = None
    audio_narration: str | None = None
    created_at: dt.datetime
    is_favorited: bool = False

    @computed_field
    @property
    def is_audio(self) -> bool:
        return self.media_type == "audio"

    @computed_field
    @property
    def duration_minutes(self) -> int:
        return max(1, round(self.duration_seconds / 60))


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
