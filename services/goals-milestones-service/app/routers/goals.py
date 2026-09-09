"""Goals router — /api/v1/goals."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..events import emit_commitment_created
from ..models import Goal, Milestone, TaggedCommitment
from ..schemas import (
    CommitmentCreate,
    CommitmentResponse,
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    MilestoneCreate,
    MilestoneResponse,
)

router = APIRouter(prefix="/api/v1/goals", tags=["goals"])


def _get_user(x_user_id: str = Header(..., alias="X-User-Id")) -> str:
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing identity header"
        )
    return x_user_id


def _get_owned_goal(db: Session, goal_id: str, user_id: str) -> Goal:
    goal = db.get(Goal, goal_id)
    if not goal or goal.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return goal


def _progress_pct(goal: Goal) -> int:
    """% of this goal's milestones with status "done" (card O2.3) — 0 if none yet."""
    if not goal.milestones:
        return 0
    done = sum(1 for m in goal.milestones if m.status == "done")
    return round(done / len(goal.milestones) * 100)


def _goal_response(goal: Goal) -> GoalResponse:
    return GoalResponse(
        id=goal.id,
        user_id=goal.user_id,
        title=goal.title,
        description=goal.description,
        status=goal.status,
        deadline=goal.deadline,
        progress_pct=_progress_pct(goal),
        created_at=goal.created_at,
        updated_at=goal.updated_at,
    )


def next_milestone_order(db: Session, goal_id: str) -> int:
    max_order = db.scalar(select(func.max(Milestone.order)).where(Milestone.goal_id == goal_id))
    return 0 if max_order is None else max_order + 1


# ── Goals ─────────────────────────────────────────────────────────────────────

@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(
    body: GoalCreate,
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> GoalResponse:
    goal = Goal(
        user_id=user_id, title=body.title, description=body.description, deadline=body.deadline
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return _goal_response(goal)


@router.get("", response_model=list[GoalResponse])
def list_goals(
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> list[GoalResponse]:
    goals = db.query(Goal).filter(Goal.user_id == user_id, Goal.status == "active").all()
    return [_goal_response(g) for g in goals]


@router.get("/{goal_id}", response_model=GoalResponse)
def get_goal(
    goal_id: str,
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> GoalResponse:
    goal = _get_owned_goal(db, goal_id, user_id)
    return _goal_response(goal)


@router.patch("/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: str,
    body: GoalUpdate,
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> GoalResponse:
    goal = _get_owned_goal(db, goal_id, user_id)
    updates = body.model_dump(exclude_unset=True)
    # title is required (NOT NULL) — an explicit `"title": null` is meaningless, so
    # treat it as omitted rather than crashing the DB constraint. description/deadline
    # are genuinely nullable, so null there is a legitimate "clear it".
    if updates.get("title") is None:
        updates.pop("title", None)
    for field, value in updates.items():
        setattr(goal, field, value)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return _goal_response(goal)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_goal(
    goal_id: str,
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> Response:
    goal = _get_owned_goal(db, goal_id, user_id)
    db.delete(goal)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Milestones (card O2.3) ──────────────────────────────────────────────────

@router.post(
    "/{goal_id}/milestones", response_model=MilestoneResponse, status_code=status.HTTP_201_CREATED
)
def add_milestone(
    goal_id: str,
    body: MilestoneCreate,
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> Milestone:
    goal = _get_owned_goal(db, goal_id, user_id)
    order = body.order if body.order is not None else next_milestone_order(db, goal.id)
    milestone = Milestone(goal_id=goal.id, title=body.title, status=body.status.value, order=order)
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return milestone


@router.get("/{goal_id}/milestones", response_model=list[MilestoneResponse])
def list_milestones(
    goal_id: str,
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> list[Milestone]:
    goal = _get_owned_goal(db, goal_id, user_id)
    return sorted(goal.milestones, key=lambda m: m.order)


# ── Tagged Commitments ────────────────────────────────────────────────────────

@router.post(
    "/{goal_id}/commitments",
    response_model=CommitmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_commitment(
    goal_id: str,
    body: CommitmentCreate,
    db: Session = Depends(get_db),
) -> TaggedCommitment:
    """Create a tagged commitment linked to a goal.

    Called internally by chat-orchestration-service when the user confirms
    'Yes, Tag It'. No X-User-Id gate — internal network call (ADR-0001 §D5).
    """
    goal = db.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")

    commitment = TaggedCommitment(
        goal_id=goal_id,
        user_id=body.user_id,
        conversation_id=body.conversation_id,
        message_id=body.message_id,
        content=body.content,
    )
    db.add(commitment)
    try:
        db.commit()
    except IntegrityError as err:
        db.rollback()
        # The message_id unique constraint fired. Check whether the existing
        # row is archived (its source conversation was deleted). If so,
        # re-activate it under the new goal rather than blocking the user.
        existing = (
            db.query(TaggedCommitment)
            .filter(TaggedCommitment.message_id == body.message_id)
            .first()
        )
        if existing and existing.is_archived:
            existing.goal_id = goal_id
            existing.conversation_id = body.conversation_id
            existing.content = body.content
            existing.is_archived = False
            db.commit()
            db.refresh(existing)
            commitment = existing
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Message already tagged as a commitment",
            ) from err
    else:
        db.refresh(commitment)

    emit_commitment_created(
        commitment_id=commitment.id,
        goal_id=goal_id,
        user_id=body.user_id,
        conversation_id=body.conversation_id,
        message_id=body.message_id,
        content_preview=body.content,
    )

    return commitment


@router.get("/{goal_id}/commitments", response_model=list[CommitmentResponse])
def list_commitments(
    goal_id: str,
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> list[TaggedCommitment]:
    """List tagged commitments for a goal — feeds the 'Tagged Commitments' list
    on the Goal Milestone Path screen.

    Commitments whose source conversation has been deleted (archived) by the
    user are excluded. The underlying rows are retained in the database for
    admin oversight; only is_archived=True rows are hidden here.
    """
    goal = db.get(Goal, goal_id)
    if not goal or goal.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return [c for c in goal.commitments if not c.is_archived]

