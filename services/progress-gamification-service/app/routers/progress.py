"""Progress router — /api/v1/progress (card O3.1)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..badges import BADGE_CATALOG, TRIGGERS
from ..config import get_settings
from ..database import get_db
from ..events import emit_badge_earned
from ..models import ActionEvent, UserBadge
from ..schemas import (
    ActionCreate,
    ActionRecordResponse,
    BadgeAward,
    BadgeWithStatus,
    HeatmapDay,
    ProgressSummary,
    StreakStatResponse,
    WeeklySummaryShare,
)
from ..streaks import build_heatmap, compute_streaks, get_action_dates

router = APIRouter(prefix="/api/v1/progress", tags=["progress"])
settings = get_settings()


def _get_user(x_user_id: str = Header(..., alias="X-User-Id")) -> str:
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing identity header"
        )
    return x_user_id


def _streak_response(db: Session, user_id: str) -> StreakStatResponse:
    dates = get_action_dates(db, user_id)
    current, longest = compute_streaks(dates)
    total = (
        db.scalar(
            select(func.count()).select_from(ActionEvent).where(ActionEvent.user_id == user_id)
        )
        or 0
    )
    last_event_at = db.scalar(
        select(func.max(ActionEvent.created_at)).where(ActionEvent.user_id == user_id)
    )
    return StreakStatResponse(
        user_id=user_id,
        current_streak_days=current,
        longest_streak_days=longest,
        actions_completed_total=total,
        updated_at=last_event_at or dt.datetime.now(tz=dt.UTC),
    )


def _badges_response(db: Session, user_id: str) -> list[BadgeWithStatus]:
    earned = {
        row.badge_id: row.earned_at
        for row in db.query(UserBadge).filter(UserBadge.user_id == user_id).all()
    }
    return [
        BadgeWithStatus(
            id=b.id,
            label=b.label,
            description=b.description,
            icon_name=b.icon_name,
            earned_at=earned.get(b.id),
        )
        for b in BADGE_CATALOG
    ]


def _evaluate_and_award_badges(db: Session, user_id: str) -> list[BadgeAward]:
    """Check every not-yet-earned badge's trigger; award and emit `badge.earned`
    for any that now qualify. Idempotent — never re-awards an already-earned badge."""
    already_earned = {
        row.badge_id for row in db.query(UserBadge).filter(UserBadge.user_id == user_id).all()
    }
    newly_earned: list[BadgeAward] = []
    for badge in BADGE_CATALOG:
        if badge.id in already_earned:
            continue
        if TRIGGERS[badge.id](db, user_id):
            db.add(UserBadge(user_id=user_id, badge_id=badge.id))
            db.commit()
            emit_badge_earned(user_id=user_id, badge_id=badge.id, label=badge.label)
            newly_earned.append(BadgeAward(badge_id=badge.id, label=badge.label))
    return newly_earned


@router.get("", response_model=ProgressSummary)
def get_progress_summary(
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> ProgressSummary:
    dates = get_action_dates(db, user_id)
    heatmap = build_heatmap(dates, window_days=settings.heatmap_window_days)
    return ProgressSummary(
        streak=_streak_response(db, user_id),
        heatmap=[HeatmapDay(**d) for d in heatmap],
        badges=_badges_response(db, user_id),
    )


@router.get("/streak", response_model=StreakStatResponse)
def get_streak(
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> StreakStatResponse:
    return _streak_response(db, user_id)


@router.get("/badges", response_model=list[BadgeWithStatus])
def list_badges(
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> list[BadgeWithStatus]:
    return _badges_response(db, user_id)


@router.post("/actions", response_model=ActionRecordResponse, status_code=status.HTTP_201_CREATED)
def record_action(
    body: ActionCreate,
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> ActionRecordResponse:
    """Record one completed action for the day (card O3.1). Recording the same
    (day, kind) twice is a no-op, not an error — a duplicate tap shouldn't surface
    as a failure to the caller."""
    occurred_on = body.occurred_on or dt.date.today()
    event = ActionEvent(user_id=user_id, occurred_on=occurred_on, kind=body.kind.value)
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()

    newly_earned = _evaluate_and_award_badges(db, user_id)
    return ActionRecordResponse(
        streak=_streak_response(db, user_id), newly_earned_badges=newly_earned
    )


@router.post("/summary/share", response_model=WeeklySummaryShare)
def share_weekly_summary(
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> WeeklySummaryShare:
    """Build the shareable weekly-summary payload (card O3.1 description)."""
    today = dt.date.today()
    week_start = today - dt.timedelta(days=6)
    dates = get_action_dates(db, user_id)
    actions_this_week = sum(1 for d in dates if week_start <= d <= today)
    streak = _streak_response(db, user_id)

    badges_this_week = [
        row.badge_id
        for row in db.query(UserBadge)
        .filter(UserBadge.user_id == user_id, UserBadge.earned_at >= week_start)
        .all()
    ]
    share_text = (
        f"This week I completed {actions_this_week} action"
        f"{'s' if actions_this_week != 1 else ''} on AfriMentor AI "
        f"and I'm on a {streak.current_streak_days}-day streak! 🔥"
    )
    return WeeklySummaryShare(
        user_id=user_id,
        week_start=week_start,
        week_end=today,
        actions_this_week=actions_this_week,
        current_streak_days=streak.current_streak_days,
        badges_earned_this_week=badges_this_week,
        share_text=share_text,
    )
