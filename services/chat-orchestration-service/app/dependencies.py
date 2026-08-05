"""FastAPI dependencies for chat-orchestration-service.

`get_current_user` trusts the X-User-Id header injected by the API gateway after
JWT verification (ADR-0001 §D5). Services are not publicly reachable, so this is safe.
"""
from __future__ import annotations

from fastapi import Header, HTTPException, status


def get_current_user(x_user_id: str = Header(..., alias="X-User-Id")) -> str:
    """Return the authenticated user-id forwarded by the gateway."""
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing identity header",
        )
    return x_user_id
