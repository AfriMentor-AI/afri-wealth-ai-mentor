"""Auth & User routes: signup, login, refresh, logout, profile, public key.

Refresh tokens are persisted (RefreshToken) and rotated on every /auth/refresh so a
stolen refresh token is single-use (ADR-0001 §D5).
"""
from __future__ import annotations

import datetime as dt

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import security
from ..config import get_settings
from ..database import get_db
from ..models import PasswordResetToken, RefreshToken, User
from ..schemas import (
    LoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequestResponse,
    PasswordResetRequestSchema,
    ProfileUpdateRequest,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _issue_tokens(db: Session, user: User) -> TokenResponse:
    access = security.create_access_token(user.id, user.role_list)
    refresh, jti = security.create_refresh_token(user.id)
    expires_at = dt.datetime.now(tz=dt.UTC) + dt.timedelta(
        seconds=settings.refresh_token_ttl_seconds
    )
    db.add(RefreshToken(jti=jti, user_id=user.id, expires_at=expires_at))
    db.commit()
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_ttl_seconds,
    )


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    exists = db.scalar(select(User).where(User.email == payload.email))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")

    profile = payload.model_dump(exclude={"email", "password"})
    # store enums as their string values
    profile = {k: (v.value if hasattr(v, "value") else v) for k, v in profile.items()}
    user = User(
        email=payload.email,
        password_hash=security.hash_password(payload.password),
        **profile,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    # NOTE: emits user.registered event (RabbitMQ) — wired in Sprint 2.
    return _issue_tokens(db, user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not security.verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account disabled")
    return _issue_tokens(db, user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        claims = security.decode_token(payload.refresh_token, expected_type="refresh")
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid refresh token") from exc

    stored = db.get(RefreshToken, claims["jti"])
    if not stored or stored.revoked:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh token revoked or unknown")

    user = db.get(User, claims["sub"])
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found or disabled")

    # Rotate: revoke the presented token, issue a fresh pair.
    stored.revoked = True
    db.add(stored)
    db.commit()
    return _issue_tokens(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)) -> Response:
    try:
        claims = security.decode_token(payload.refresh_token, expected_type="refresh")
    except jwt.PyJWTError:
        return Response(status_code=status.HTTP_204_NO_CONTENT)  # idempotent no-op
    stored = db.get(RefreshToken, claims["jti"])
    if stored and not stored.revoked:
        stored.revoked = True
        db.add(stored)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _current_user(
    db: Session, authorization: str | None
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        claims = security.decode_token(token, expected_type="access")
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid access token") from exc
    user = db.get(User, claims["sub"])
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found or disabled")
    return user


@router.get("/me", response_model=UserResponse)
def me(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    user = _current_user(db, authorization)
    return _user_to_response(user)


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: ProfileUpdateRequest,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    user = _current_user(db, authorization)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(user, field, value.value if hasattr(value, "value") else value)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_to_response(user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_me(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Response:
    user = _current_user(db, authorization)
    user.is_active = False
    db.add(user)
    # Revoke every outstanding refresh token so existing sessions can't keep renewing.
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False)
    ).update({"revoked": True})
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/password-reset/request", response_model=PasswordResetRequestResponse)
def request_password_reset(
    payload: PasswordResetRequestSchema, db: Session = Depends(get_db)
) -> PasswordResetRequestResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    reset_token: str | None = None
    if user and user.is_active:
        # A fresh request supersedes any earlier one, so a still-unexpired token from a
        # prior request can't linger as a second valid way in.
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id, PasswordResetToken.used.is_(False)
        ).update({"used": True})
        raw, token_hash = security.generate_reset_token()
        expires_at = dt.datetime.now(tz=dt.UTC) + dt.timedelta(
            seconds=settings.password_reset_ttl_seconds
        )
        db.add(
            PasswordResetToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at)
        )
        db.commit()
        # NOTE: no email provider is wired up yet — delivery is a future integration.
        # Outside prod we return the raw token directly so the flow is exercisable.
        if settings.env != "prod":
            reset_token = raw
    # Same response whether or not the email is registered, so the endpoint can't be
    # used to enumerate accounts.
    return PasswordResetRequestResponse(reset_token=reset_token)


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(
    payload: PasswordResetConfirmRequest, db: Session = Depends(get_db)
) -> Response:
    token_hash = security.hash_reset_token(payload.reset_token)
    stored = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    now = dt.datetime.now(tz=dt.UTC)
    # SQLite drops tzinfo on round-trip (dev/test); Postgres preserves it (staging/prod).
    expires_at = stored.expires_at if stored else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=dt.UTC)
    if not stored or stored.used or expires_at < now:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid or expired reset token")

    user = db.get(User, stored.user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid or expired reset token")

    user.password_hash = security.hash_password(payload.new_password)
    stored.used = True
    db.add(user)
    db.add(stored)
    # A password reset invalidates every outstanding session, not just the token used.
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False)
    ).update({"revoked": True})
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        roles=user.role_list,
        is_active=user.is_active,
        created_at=user.created_at,
        name=user.name,
        age=user.age,
        country=user.country,
        device_type=user.device_type,
        sector_interest=user.sector_interest,
        education_level=user.education_level,
        language=user.language,
        income_bracket=user.income_bracket,
    )


@router.get("/.well-known/jwks", tags=["meta"])
def public_key_pem() -> dict:
    """Expose the RS256 public key so the gateway can verify access tokens."""
    return {"algorithm": settings.jwt_algorithm, "public_key_pem": security.public_key()}
