"""Security primitives: password hashing, RS256 keypair, JWT issue/verify.

The keypair is loaded from disk when paths are configured, otherwise a keypair is
generated in-process (dev only) so the service is runnable and testable without any
committed secrets (ADR-0001 §D5).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import secrets
import uuid
from functools import lru_cache
from pathlib import Path

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


# ------------------------------------------------------------ password reset tokens
def generate_reset_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hash). Only the hash is ever persisted."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_reset_token(raw)


def hash_reset_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


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

    # Dev fallback: previously an in-process-only keypair, regenerated (and every
    # outstanding token invalidated) on every restart. Persisted under
    # `dev_key_dir` instead so a container restart/rebuild reuses the same
    # keypair — that directory must be a Docker volume, not the writable layer,
    # to survive `down`/recreate, not just `stop`/`start` (see docker-compose.yml).
    key_dir = Path(settings.dev_key_dir)
    private_path = key_dir / "jwt_private_key.pem"
    public_path = key_dir / "jwt_public_key.pem"
    if private_path.exists() and public_path.exists():
        return private_path.read_text(), public_path.read_text()

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
    key_dir.mkdir(parents=True, exist_ok=True)
    private_path.write_text(private_pem)
    public_path.write_text(public_pem)
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
