"""Security primitives: password hashing, RS256 keypair, JWT issue/verify.

The keypair is loaded from disk when paths are configured, otherwise a keypair is
generated in-process (dev only) so the service is runnable and testable without any
committed secrets (ADR-0001 §D5).
"""
from __future__ import annotations

import datetime as dt
import uuid
from functools import lru_cache

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from passlib.context import CryptContext

from .config import get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


# --------------------------------------------------------------------- passwords
def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


# ------------------------------------------------------------------------- keys
@lru_cache
def _keys() -> tuple[str, str]:
    """Return (private_pem, public_pem). Load from disk or generate for dev."""
    settings = get_settings()
    if settings.jwt_private_key_path and settings.jwt_public_key_path:
        with open(settings.jwt_private_key_path) as f:
            private_pem = f.read()
        with open(settings.jwt_public_key_path) as f:
            public_pem = f.read()
        return private_pem, public_pem

    # Dev fallback: generate an ephemeral keypair (stable for process lifetime).
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


def private_key() -> str:
    return _keys()[0]


def public_key() -> str:
    """Public key served at /auth/.well-known/jwks so the gateway can verify."""
    return _keys()[1]


# ------------------------------------------------------------------------- JWTs
def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.UTC)


def create_access_token(user_id: str, roles: list[str] | None = None) -> str:
    settings = get_settings()
    now = _now()
    payload = {
        "sub": user_id,
        "type": "access",
        "roles": roles or ["user"],
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + dt.timedelta(seconds=settings.access_token_ttl_seconds),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, private_key(), algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """Return (token, jti). The jti is stored server-side to allow revocation."""
    settings = get_settings()
    now = _now()
    jti = str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + dt.timedelta(seconds=settings.refresh_token_ttl_seconds),
        "jti": jti,
    }
    token = jwt.encode(payload, private_key(), algorithm=settings.jwt_algorithm)
    return token, jti


def decode_token(token: str, expected_type: str | None = None) -> dict:
    settings = get_settings()
    claims = jwt.decode(
        token,
        public_key(),
        algorithms=[settings.jwt_algorithm],
        issuer=settings.jwt_issuer,
        options={"require": ["exp", "iat", "sub"]},
    )
    if expected_type and claims.get("type") != expected_type:
        raise jwt.InvalidTokenError(
            f"expected {expected_type} token, got {claims.get('type')}"
        )
    return claims
