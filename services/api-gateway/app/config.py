"""Gateway configuration: upstream URLs, JWT verification, rate limits."""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    service_name: str = "api-gateway"
    env: str = os.getenv("APP_ENV", "dev")

    redis_url: str = os.getenv("REDIS_URL", "")
    auth_service_url: str = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")

    jwt_algorithm: str = "RS256"
    jwt_issuer: str = "afrimentor-auth"
    # Optional static public key (PEM); if unset the gateway fetches JWKS from auth.
    jwt_public_key: str = os.getenv("JWT_PUBLIC_KEY", "")

    # Default per-route rate limit (requests per window) unless overridden per route.
    rate_limit_requests: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    rate_limit_window_seconds: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

    upstream_timeout_seconds: float = float(os.getenv("UPSTREAM_TIMEOUT", "15"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
