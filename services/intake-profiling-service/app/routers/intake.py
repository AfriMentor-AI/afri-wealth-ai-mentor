"""Intake session routes (card O2.2).

Identity comes from the `X-User-Id` header the gateway injects after verifying the
caller's JWT (ADR-0001 §D5) — these routes are reached through the gateway, so unlike
GET /profiles/{userId}/diagnostic (which is also called service-to-service), a missing
header here is always an error, not an internal-caller special case.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DiagnosticProfile, IntakeAnswer, IntakeSession
from ..schemas import (
    STEP_PAYLOAD_SCHEMA,
    AnswerResponse,
    AnswerSubmitRequest,
    ConfirmPayload,
    ConstraintsPayload,
    EducationTimePayload,
    IntakeStep,
    SectorPayload,
    SessionResponse,
)

router = APIRouter(prefix="/api/v1/intake", tags=["intake"])


def _require_user_id(x_user_id: str | None) -> str:
    if not x_user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing X-User-Id")
    return x_user_id


def _get_owned_session(db: Session, session_id: str, user_id: str) -> IntakeSession:
    session_row = db.get(IntakeSession, session_id)
    # 404 (not 403) for a session that exists but belongs to someone else, so this
    # endpoint can't be used to probe for valid session ids.
    if not session_row or session_row.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "intake session not found")
    return session_row


def _to_session_response(db: Session, session_row: IntakeSession) -> SessionResponse:
    answers = db.scalars(
        select(IntakeAnswer).where(IntakeAnswer.session_id == session_row.id)
    ).all()
    return SessionResponse(
        id=session_row.id,
        user_id=session_row.user_id,
        status=session_row.status,
        started_at=session_row.started_at,
        completed_at=session_row.completed_at,
        answers=[AnswerResponse.model_validate(a) for a in answers],
    )


@router.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def start_session(
    response: Response,
    x_user_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> SessionResponse:
    user_id = _require_user_id(x_user_id)
    existing = db.scalar(
        select(IntakeSession).where(
            IntakeSession.user_id == user_id, IntakeSession.status == "in_progress"
        )
    )
    if existing:
        # Resuming, not creating — 200, not the route's default 201.
        response.status_code = status.HTTP_200_OK
        return _to_session_response(db, existing)
    session_row = IntakeSession(user_id=user_id)
    db.add(session_row)
    db.commit()
    db.refresh(session_row)
    return _to_session_response(db, session_row)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    x_user_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> SessionResponse:
    user_id = _require_user_id(x_user_id)
    session_row = _get_owned_session(db, session_id, user_id)
    return _to_session_response(db, session_row)


@router.post("/sessions/{session_id}/answers", response_model=SessionResponse)
def submit_answer(
    session_id: str,
    payload: AnswerSubmitRequest,
    x_user_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> SessionResponse:
    user_id = _require_user_id(x_user_id)
    session_row = _get_owned_session(db, session_id, user_id)
    if session_row.status != "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "intake session is already completed")

    step_schema = STEP_PAYLOAD_SCHEMA[payload.step]
    try:
        validated = step_schema.model_validate(payload.payload)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.errors()) from exc

    existing_answer = db.scalar(
        select(IntakeAnswer).where(
            IntakeAnswer.session_id == session_id, IntakeAnswer.step == payload.step.value
        )
    )
    if existing_answer:
        existing_answer.payload = validated.model_dump()
        db.add(existing_answer)
    else:
        db.add(
            IntakeAnswer(
                session_id=session_id, step=payload.step.value, payload=validated.model_dump()
            )
        )
    db.commit()
    db.refresh(session_row)
    return _to_session_response(db, session_row)


@router.post("/sessions/{session_id}/complete", response_model=SessionResponse)
def complete_session(
    session_id: str,
    x_user_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> SessionResponse:
    user_id = _require_user_id(x_user_id)
    session_row = _get_owned_session(db, session_id, user_id)
    if session_row.status != "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "intake session is already completed")

    answers = {
        a.step: a.payload
        for a in db.scalars(
            select(IntakeAnswer).where(IntakeAnswer.session_id == session_id)
        ).all()
    }
    missing = [s.value for s in IntakeStep if s.value not in answers]
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"missing required intake steps: {', '.join(missing)}"
        )

    sector = SectorPayload.model_validate(answers[IntakeStep.sector.value])
    edu_time = EducationTimePayload.model_validate(answers[IntakeStep.education_time.value])
    constraints = ConstraintsPayload.model_validate(answers[IntakeStep.constraints.value])
    confirm = ConfirmPayload.model_validate(answers[IntakeStep.confirm.value])

    profile = db.get(DiagnosticProfile, user_id)
    if profile:
        profile.name = confirm.name
        profile.business_name = confirm.business_name
        profile.location = confirm.location
        profile.sector = sector.sector
        profile.education_level = edu_time.education_level
        profile.time_available_per_week = edu_time.time_available_per_week
        profile.constraints = constraints.constraints
    else:
        profile = DiagnosticProfile(
            user_id=user_id,
            name=confirm.name,
            business_name=confirm.business_name,
            location=confirm.location,
            sector=sector.sector,
            education_level=edu_time.education_level,
            time_available_per_week=edu_time.time_available_per_week,
            constraints=constraints.constraints,
        )
    db.add(profile)

    session_row.status = "completed"
    session_row.completed_at = dt.datetime.now(tz=dt.UTC)
    db.add(session_row)
    db.commit()
    db.refresh(session_row)
    return _to_session_response(db, session_row)
