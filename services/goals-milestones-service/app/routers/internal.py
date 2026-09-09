"""Internal router -- not exposed through the API gateway.

Provides service-to-service endpoints that should only be reachable on the
internal Docker network. No user-identity gate is applied here; callers are
trusted internal services.

Current endpoints
-----------------
POST /internal/commitments/archive-by-conversation/{conversation_id}
    Called by chat-orchestration-service''s archive_session handler to hide
    commitments from the deleted conversation in all user-facing views.
    Also archives any goal whose every commitment is now archived (i.e. the
    goal was solely driven by the deleted conversation).
    Data is retained in the database; only flags are set.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Goal, TaggedCommitment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post(
    "/commitments/archive-by-conversation/{conversation_id}",
    status_code=204,
)
def archive_commitments_by_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
) -> None:
    """Mark all TaggedCommitment rows for *conversation_id* as archived.

    Additionally, any Goal whose every commitment is now archived (meaning
    the goal was entirely driven by the deleted conversation) is itself
    archived so it no longer appears on the Goals overview page.

    Idempotent and best-effort -- a 204 is always returned so the caller
    (chat-orchestration-service) is never blocked by this service.
    """
    # Step 1: archive the commitments for this conversation.
    affected = (
        db.query(TaggedCommitment)
        .filter(
            TaggedCommitment.conversation_id == conversation_id,
            TaggedCommitment.is_archived.is_(False),
        )
        .all()
    )
    if not affected:
        return

    affected_goal_ids = {c.goal_id for c in affected}
    for commitment in affected:
        commitment.is_archived = True

    db.flush()  # write flag changes so the next query sees them

    # Step 2: for every goal touched above, check whether it now has zero
    # non-archived commitments. If so, archive the goal too so it vanishes
    # from the Goals overview page. Goals with at least one surviving
    # commitment from another (active) conversation are left untouched.
    goals_archived = 0
    for goal_id in affected_goal_ids:
        goal = db.get(Goal, goal_id)
        if not goal or goal.status == "archived":
            continue
        has_live_commitment = any(
            not c.is_archived for c in goal.commitments
        )
        if not has_live_commitment:
            goal.status = "archived"
            goals_archived += 1

    db.commit()
    logger.info(
        "Archived %d commitment(s) and %d goal(s) for conversation %s",
        len(affected),
        goals_archived,
        conversation_id,
    )
