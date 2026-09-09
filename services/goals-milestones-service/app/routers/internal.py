"""Internal router — not exposed through the API gateway.

Provides service-to-service endpoints that should only be reachable on the
internal Docker network. No user-identity gate is applied here; callers are
trusted internal services.

Current endpoints
-----------------
POST /internal/commitments/archive-by-conversation/{conversation_id}
    Called by chat-orchestration-service''s archive_session handler to hide
    commitments from the deleted conversation in all user-facing views.
    Data is retained in the database; only the is_archived flag is set.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import TaggedCommitment

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

    This is a best-effort, idempotent operation. If no rows match the
    conversation_id the call still succeeds (204). The commitments are
    never deleted — is_archived=True hides them from user-facing list
    endpoints while keeping the data available for admin oversight.
    """
    affected = (
        db.query(TaggedCommitment)
        .filter(
            TaggedCommitment.conversation_id == conversation_id,
            TaggedCommitment.is_archived.is_(False),
        )
        .all()
    )
    for commitment in affected:
        commitment.is_archived = True
    if affected:
        db.commit()
        logger.info(
            "Archived %d commitment(s) for conversation %s",
            len(affected),
            conversation_id,
        )
