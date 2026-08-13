"""Notifications router — /api/v1/notifications (card O3.4, v0 scaffold)."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Notification
from ..schemas import (
    DailyActionReminderTrigger,
    NotificationResponse,
    StreakAtRiskTrigger,
    SweepResult,
)
from ..sweep import run_streak_risk_sweep

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


def _get_user(x_user_id: str = Header(..., alias="X-User-Id")) -> str:
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing identity header"
        )
    return x_user_id


# ── User-facing ──────────────────────────────────────────────────────────────

@router.get("", response_model=list[NotificationResponse])
def list_notifications(
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .all()
    )


def _get_owned_notification(db: Session, notification_id: str, user_id: str) -> Notification:
    n = db.get(Notification, notification_id)
    if not n or n.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return n


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_read(
    notification_id: str,
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> Notification:
    n = _get_owned_notification(db, notification_id, user_id)
    if n.read_at is None:
        n.read_at = dt.datetime.now(tz=dt.UTC)
        db.add(n)
        db.commit()
        db.refresh(n)
    return n


@router.post("/read-all", response_model=list[NotificationResponse])
def mark_all_read(
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> list[Notification]:
    now = dt.datetime.now(tz=dt.UTC)
    unread = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.read_at.is_(None))
        .all()
    )
    for n in unread:
        n.read_at = now
        db.add(n)
    db.commit()
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .all()
    )


# ── Internal trigger endpoints ───────────────────────────────────────────────
# No X-User-Id gate — internal service-to-service calls, same precedent as
# goals-milestones-service's commitment-create endpoint (ADR-0001 §D5). These
# *are* the event contract card O3.4 asks for: whatever calls them (today: ops/
# tests; later: D3.3's daily-action job, a real push integration) doesn't need
# to know how delivery works, only that a notification now exists for the user.

@router.post(
    "/trigger/daily-action-reminder",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
def trigger_daily_action_reminder(
    body: DailyActionReminderTrigger,
    db: Session = Depends(get_db),
) -> Notification:
    title = "Today's action is ready"
    action = body.action_title or "your daily action"
    n = Notification(
        user_id=body.user_id,
        kind="daily_action_reminder",
        title=title,
        body=f"Don't forget to complete {action} today.",
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


@router.post(
    "/trigger/streak-at-risk",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
def trigger_streak_at_risk(
    body: StreakAtRiskTrigger,
    db: Session = Depends(get_db),
) -> Notification:
    n = Notification(
        user_id=body.user_id,
        kind="streak_at_risk",
        title="Your streak is at risk!",
        body=(
            f"You're on a {body.current_streak_days}-day streak — "
            "log an action today to keep it alive."
        ),
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


@router.post("/sweep", response_model=SweepResult)
def sweep(db: Session = Depends(get_db)) -> SweepResult:
    """Synchronous, deterministic entry point for the streak-at-risk sweep the
    background task also runs on a timer — lets ops/tests trigger it on demand."""
    users_checked, notifications_created = run_streak_risk_sweep(db)
    return SweepResult(users_checked=users_checked, notifications_created=notifications_created)
