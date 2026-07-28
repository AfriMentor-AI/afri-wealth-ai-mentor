"""JWT verification at the edge.

The gateway obtains the RS256 public key either from static config or by fetching the
auth-service JWKS endpoint (cached). It never holds the private key (ADR-0001 §D5).
"""
from __future__ import annotations

import httpx
import jwt

from .config import get_settings

_settings = get_settings()
_cached_public_key: str | None = _settings.jwt_public_key or None


async def _load_public_key() -> str:
    global _cached_public_key
    if _cached_public_key:
        return _cached_public_key
    url = f"{_settings.auth_service_url}/auth/.well-known/jwks"
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        _cached_public_key = resp.json()["public_key_pem"]
    return _cached_public_key


class TokenError(Exception):
    pass


async def verify_access_token(token: str) -> dict:
    """Return verified claims or raise TokenError."""
    try:
        key = await _load_public_key()
    except Exception as exc:  # noqa: BLE001 - surface as auth failure
        raise TokenError(f"cannot load verification key: {exc}") from exc

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[_settings.jwt_algorithm],
            issuer=_settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc

    if claims.get("type") != "access":
        raise TokenError("not an access token")
    return claims


def reset_key_cache() -> None:
    """Test hook."""
    global _cached_public_key
    _cached_public_key = _settings.jwt_public_key or None
