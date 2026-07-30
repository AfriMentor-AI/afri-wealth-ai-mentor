"""Per-route rate limiting via a fixed-window counter.

Uses Redis when REDIS_URL is set (shared across gateway replicas); falls back to an
in-process counter for local dev/tests. Keyed by (client-identity, route-prefix).
"""
from __future__ import annotations

import time

from .config import get_settings

_settings = get_settings()

_redis = None
if _settings.redis_url:
    try:  # optional dependency; gateway still runs without redis
        import redis.asyncio as aioredis

        _redis = aioredis.from_url(_settings.redis_url, decode_responses=True)
    except Exception:  # noqa: BLE001
        _redis = None

# In-memory fallback: {key: (window_start, count)}
_local: dict[str, tuple[int, int]] = {}


async def check_rate_limit(identity: str, prefix: str, limit: int, window: int) -> bool:
    """Return True if the request is allowed, False if the limit is exceeded."""
    now = int(time.time())
    bucket = now // window
    key = f"rl:{identity}:{prefix}:{bucket}"

    if _redis is not None:
        count = await _redis.incr(key)
        if count == 1:
            await _redis.expire(key, window)
        return count <= limit

    window_start, count = _local.get(key, (bucket, 0))
    count += 1
    _local[key] = (window_start, count)
    # opportunistic cleanup of old buckets
    if len(_local) > 10_000:
        _local.clear()
    return count <= limit


def reset_local() -> None:
    """Test hook."""
    _local.clear()
