"""Diagnostic profile lookup (card O2.2: GET /profiles/{userId}/diagnostic).

Unlike the /intake/sessions routes, this one is also called service-to-service (Chat
Orchestration reading a user's diagnostic profile for personalization) — such calls hit
this service directly on the docker network and carry no `X-User-Id` header at all.
So: if `X-User-Id` is present (i.e. the caller came through the gateway as an end user)
it must match the requested `userId`; if it's absent, the call is trusted as internal.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DiagnosticProfile
from ..schemas import DiagnosticProfileResponse

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


@router.get("/{user_id}/diagnostic", response_model=DiagnosticProfileResponse)
def get_diagnostic_profile(
    user_id: str,
    x_user_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> DiagnosticProfile:
    if x_user_id and x_user_id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot read another user's profile")
    profile = db.get(DiagnosticProfile, user_id)
    if not profile:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no diagnostic profile for this user")
    return profile
