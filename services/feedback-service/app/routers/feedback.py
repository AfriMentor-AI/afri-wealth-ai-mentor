"""Feedback router — /api/v1/feedback (card O3.3)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import FeedbackPrompt, FeedbackSurvey
from ..schemas import FeedbackPromptResponse, FeedbackSubmit, FeedbackSurveyResponse

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


def _get_user(x_user_id: str = Header(..., alias="X-User-Id")) -> str:
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing identity header"
        )
    return x_user_id


def _resolve_matching_prompt(
    db: Session, user_id: str, trigger: str, context_ref: str | None
) -> None:
    """If this submission answers an open FeedbackPrompt, mark it fulfilled."""
    if trigger == "manual":
        return
    prompt = (
        db.query(FeedbackPrompt)
        .filter(
            FeedbackPrompt.user_id == user_id,
            FeedbackPrompt.trigger == trigger,
            FeedbackPrompt.context_ref == context_ref,
            FeedbackPrompt.fulfilled_at.is_(None),
        )
        .first()
    )
    if prompt:
        prompt.fulfilled_at = dt.datetime.now(tz=dt.UTC)
        db.add(prompt)
        db.commit()


@router.post("", response_model=FeedbackSurveyResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    body: FeedbackSubmit,
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> FeedbackSurvey:
    survey = FeedbackSurvey(
        user_id=user_id,
        nps_score=body.nps_score,
        comment=body.comment,
        voice_note_url=body.voice_note_url,
        trigger=body.trigger,
        context_ref=body.context_ref,
    )
    db.add(survey)
    db.commit()
    db.refresh(survey)

    _resolve_matching_prompt(db, user_id, body.trigger, body.context_ref)
    return survey


@router.get("", response_model=list[FeedbackSurveyResponse])
def list_feedback(
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> list[FeedbackSurvey]:
    return (
        db.query(FeedbackSurvey)
        .filter(FeedbackSurvey.user_id == user_id)
        .order_by(FeedbackSurvey.submitted_at.desc())
        .all()
    )


@router.get("/pending", response_model=list[FeedbackPromptResponse])
def list_pending_prompts(
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> list[FeedbackPrompt]:
    """Open survey prompts for this user — a client polls this to decide whether
    to pop the Feedback Survey modal (card O3.3's "fires automatically" AC)."""
    return (
        db.query(FeedbackPrompt)
        .filter(FeedbackPrompt.user_id == user_id, FeedbackPrompt.fulfilled_at.is_(None))
        .order_by(FeedbackPrompt.created_at.desc())
        .all()
    )


@router.get("/surveys/{survey_id}", response_model=FeedbackSurveyResponse)
def get_survey(
    survey_id: str,
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> FeedbackSurvey:
    survey = db.get(FeedbackSurvey, survey_id)
    if not survey or survey.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Survey not found")
    return survey
