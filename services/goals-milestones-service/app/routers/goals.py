"""Goals router — /api/v1/goals."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..events import emit_commitment_created
from ..models import Goal, TaggedCommitment
from ..schemas import CommitmentCreate, CommitmentResponse, GoalCreate, GoalResponse

router = APIRouter(prefix="/api/v1/goals", tags=["goals"])


def _get_user(x_user_id: str = Header(..., alias="X-User-Id")) -> str:
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing identity header"
        )
    return x_user_id


# ── Goals ─────────────────────────────────────────────────────────────────────

@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(
    body: GoalCreate,
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> Goal:
    goal = Goal(user_id=user_id, title=body.title, description=body.description)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.get("", response_model=list[GoalResponse])
def list_goals(
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> list[Goal]:
    return db.query(Goal).filter(Goal.user_id == user_id, Goal.status == "active").all()


@router.get("/{goal_id}", response_model=GoalResponse)
def get_goal(
    goal_id: str,
    user_id: str = Depends(_get_user),
    db: Session = Depends(get_db),
) -> Goal:
    goal = db.get(Goal, goal_id)
    if not goal or goal.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return goal


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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Message already tagged as a commitment",
        ) from err
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
    on the Goal Milestone Path screen."""
    goal = db.get(Goal, goal_id)
    if not goal or goal.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return goal.commitments
