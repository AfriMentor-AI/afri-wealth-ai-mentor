"""Pydantic v2 request/response schemas for auth-user-service.

These mirror the shared TypeScript contract (G1.3). Enums keep profile values aligned
with the intake flow (sector chips: Trader/Tech/Fashion-Retail/Agriculture/Creative).
"""
from __future__ import annotations

import datetime as dt
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DeviceType(str, Enum):
    low_end = "low_end"
    mid = "mid"
    high = "high"
    desktop = "desktop"


class SectorInterest(str, Enum):
    trader = "trader"
    tech = "tech"
    fashion_retail = "fashion_retail"
    agriculture = "agriculture"
    creative = "creative"
    other = "other"


class EducationLevel(str, Enum):
    none = "none"
    primary = "primary"
    secondary = "secondary"
    vocational = "vocational"
    tertiary = "tertiary"


class IncomeBracket(str, Enum):
    low = "low"
    lower_mid = "lower_mid"
    mid = "mid"
    upper_mid = "upper_mid"
    high = "high"


class ProfileFields(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    age: int | None = Field(default=None, ge=13, le=120)
    country: str | None = Field(
        default=None, min_length=2, max_length=2, description="ISO 3166-1 alpha-2"
    )
    device_type: DeviceType | None = None
    sector_interest: SectorInterest | None = None
    education_level: EducationLevel | None = None
    language: str | None = Field(default=None, max_length=10, description="BCP-47, e.g. en, sw, yo")
    income_bracket: IncomeBracket | None = None


class SignupRequest(ProfileFields):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(ProfileFields):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    roles: list[str]
    is_active: bool
    created_at: dt.datetime


class ProfileUpdateRequest(ProfileFields):
    """PATCH /auth/me — every field optional; only supplied fields are updated."""


class PasswordResetRequestSchema(BaseModel):
    email: EmailStr


class PasswordResetRequestResponse(BaseModel):
    detail: str = "if that email is registered, a reset link has been issued"
    # Only populated outside prod, where there is no email provider wired up yet
    # (card O2.1 note): lets the flow be exercised end-to-end in dev/test/staging.
    reset_token: str | None = None


class PasswordResetConfirmRequest(BaseModel):
    reset_token: str
    new_password: str = Field(min_length=8, max_length=128)
