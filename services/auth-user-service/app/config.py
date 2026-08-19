"""Configuration for auth-user-service (card O1.3).

RSA keys for RS256 JWT signing are generated at runtime in dev if not provided,
so no private key is ever committed (ADR-0001 §D5).
"""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    service_name: str = "auth-user-service"
    env: str = os.getenv("APP_ENV", "dev")

    database_url: str = os.getenv(
        "DATABASE_URL", "sqlite+pysqlite:///./auth_dev.db"
    )
    redis_url: str = os.getenv("REDIS_URL", "")

    # JWT / RS256
    jwt_algorithm: str = "RS256"
    jwt_issuer: str = "afrimentor-auth"
    access_token_ttl_seconds: int = int(os.getenv("ACCESS_TOKEN_TTL", str(15 * 60)))
    # Sliding idle timeout, not a fixed session length: /auth/refresh rotates
    # and reissues a fresh refresh token expiring `refresh_token_ttl_seconds`
    # from that moment (see routers/auth.py::_issue_tokens), so a session that
    # keeps refreshing stays alive indefinitely and only expires after this
    # long with *no* activity at all.
    refresh_token_ttl_seconds: int = int(os.getenv("REFRESH_TOKEN_TTL", str(7 * 60 * 60)))
    jwt_private_key_path: str = os.getenv("JWT_PRIVATE_KEY_PATH", "")
    jwt_public_key_path: str = os.getenv("JWT_PUBLIC_KEY_PATH", "")
    # Dev-only fallback when the two paths above aren't set (no real keypair
    # provisioned) — see security.py::_keys(). Persisted to survive container
    # restarts; must be a path a Docker volume mounts, not the ephemeral layer.
    dev_key_dir: str = os.getenv("DEV_KEY_DIR", "./dev_keys")

    # Password reset
    password_reset_ttl_seconds: int = int(os.getenv("PASSWORD_RESET_TTL", str(30 * 60)))


@lru_cache
def get_settings() -> Settings:
    return Settings()
