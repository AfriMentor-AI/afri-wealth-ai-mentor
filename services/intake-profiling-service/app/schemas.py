"""Pydantic v2 request/response schemas for intake-profiling-service (card O2.2).

Step payloads are deliberately free-form strings, not machine enums: the Intake
screen's chips ("Trader", "No formal schooling", "Under 5 hours", ...) are UI copy the
research report treats as "no wrong answer," and voice input can produce a transcribed
variant of a chip label. We validate *presence and shape*, not an exact vocabulary.
"""
from __future__ import annotations

import datetime as dt
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class IntakeStep(str, Enum):
    sector = "sector"
    education_time = "education_time"
    constraints = "constraints"
    confirm = "confirm"


class SectorPayload(BaseModel):
    sector: str = Field(min_length=1, max_length=60)


class EducationTimePayload(BaseModel):
    education_level: str = Field(min_length=1, max_length=60)
    time_available_per_week: str = Field(min_length=1, max_length=60)


class ConstraintsPayload(BaseModel):
    constraints: list[str] = Field(default_factory=list, max_length=20)


class ConfirmPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    business_name: str = Field(min_length=1, max_length=160)
    location: str = Field(default="", max_length=160)


STEP_PAYLOAD_SCHEMA: dict[IntakeStep, type[BaseModel]] = {
    IntakeStep.sector: SectorPayload,
    IntakeStep.education_time: EducationTimePayload,
    IntakeStep.constraints: ConstraintsPayload,
    IntakeStep.confirm: ConfirmPayload,
}


class AnswerSubmitRequest(BaseModel):
    step: IntakeStep
    payload: dict = Field(description="Shape depends on `step` — see STEP_PAYLOAD_SCHEMA.")


class AnswerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step: IntakeStep
    payload: dict
    updated_at: dt.datetime


class SessionResponse(BaseModel):
    id: str
    user_id: str
    status: str
    started_at: dt.datetime
    completed_at: dt.datetime | None
    answers: list[AnswerResponse]


class DiagnosticProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    name: str
    business_name: str
    location: str
    sector: str
    education_level: str
    time_available_per_week: str
    constraints: list[str]
    persona_id: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
