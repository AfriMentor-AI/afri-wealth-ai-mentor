"""Milestone-id-scoped routes: update, complete, delete (card O2.3)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..events import emit_milestone_completed
from ..models import Milestone
from ..schemas import MilestoneResponse, MilestoneUpdate
from .goals import _get_owned_goal, _get_user

router = APIRouter(prefix="/api/v1/milestones", tags=["milestones"])


def _get_owned_milestone(db: Session, milestone_id: str, user_id: str) -> Milestone:
    milestone = db.get(Milestone, milestone_id)
    if not milestone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")
    _get_owned_goal(db, milestone.goal_id, user_id)  # raises 404 if not owned
    return milestone


@router.patch("/{milestone_id}", response_model=MilestoneResponse)
def update_milestone(
    milestone_id: str,
    body: MilestoneUpdate,
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> Milestone:
    milestone = _get_owned_milestone(db, milestone_id, user_id)
    was_done = milestone.status == "done"
    updates = body.model_dump(exclude_unset=True)
    # title/status/order are all NOT NULL — an explicit null for any of them is
    # meaningless, so treat it the same as omitted rather than crashing the DB
    # constraint.
    for field in ("title", "status", "order"):
        if updates.get(field) is None:
            updates.pop(field, None)
    for field, value in updates.items():
        setattr(milestone, field, value.value if hasattr(value, "value") else value)
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    if milestone.status == "done" and not was_done:
        emit_milestone_completed(
            milestone_id=milestone.id,
            goal_id=milestone.goal_id,
            user_id=user_id,
            title=milestone.title,
        )
    return milestone


@router.post("/{milestone_id}/complete", response_model=MilestoneResponse)
def complete_milestone(
    milestone_id: str,
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> Milestone:
    milestone = _get_owned_milestone(db, milestone_id, user_id)
    was_done = milestone.status == "done"
    milestone.status = "done"
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    if not was_done:
        emit_milestone_completed(
            milestone_id=milestone.id,
            goal_id=milestone.goal_id,
            user_id=user_id,
            title=milestone.title,
        )
    return milestone


@router.delete("/{milestone_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_milestone(
    milestone_id: str,
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> Response:
    milestone = _get_owned_milestone(db, milestone_id, user_id)
    db.delete(milestone)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
