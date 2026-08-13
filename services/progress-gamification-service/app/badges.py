"""Badge catalog + trigger rules (card O3.1, Progress Board screen).

The catalog is fixed content (not user data), so it lives in code rather than a
table — matches contract/types.ts's Badge (shared catalog) vs UserBadge (per-user
earned join) split. Each trigger is a pure predicate over a user's ActionEvent
history so it can be unit-tested without standing up the full API.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import ActionEvent
from .streaks import compute_streaks, get_action_dates


@dataclass(frozen=True)
class BadgeDef:
    id: str
    label: str
    description: str
    icon_name: str


BADGE_CATALOG: list[BadgeDef] = [
    BadgeDef(
        id="consistency_queen",
        label="Consistency Queen",
        description="7-day activity streak",
        icon_name="local_fire_department",
    ),
    BadgeDef(
        id="smart_saver",
        label="Smart Saver",
        description="Hit a weekly savings goal",
        icon_name="savings",
    ),
    BadgeDef(
        id="scholar_spirit",
        label="Scholar Spirit",
        description="Finished 5 lessons",
        icon_name="school",
    ),
]

_SCHOLAR_SPIRIT_THRESHOLD = 5
_CONSISTENCY_QUEEN_STREAK = 7


def _count_kind(db: Session, user_id: str, kind: str) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(ActionEvent)
            .where(ActionEvent.user_id == user_id, ActionEvent.kind == kind)
        )
        or 0
    )


def _consistency_queen(db: Session, user_id: str) -> bool:
    current, _longest = compute_streaks(get_action_dates(db, user_id))
    return current >= _CONSISTENCY_QUEEN_STREAK


def _smart_saver(db: Session, user_id: str) -> bool:
    return _count_kind(db, user_id, "savings_goal_met") >= 1


def _scholar_spirit(db: Session, user_id: str) -> bool:
    return _count_kind(db, user_id, "insight_completed") >= _SCHOLAR_SPIRIT_THRESHOLD


TRIGGERS: dict[str, Callable[[Session, str], bool]] = {
    "consistency_queen": _consistency_queen,
    "smart_saver": _smart_saver,
    "scholar_spirit": _scholar_spirit,
}
