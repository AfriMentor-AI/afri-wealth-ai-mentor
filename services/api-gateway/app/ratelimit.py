"""Per-route rate limiting via a sliding-window counter.

Uses Redis when REDIS_URL is set (shared across gateway replicas); falls back to an
in-process counter for local dev/tests. Keyed by (client-identity, route-prefix).

Card O5.1 / BUG-04: the original implementation used a fixed window
(`bucket = now // window`), which lets a client send up to 2x the configured limit
by timing requests around a window boundary (e.g. 60 requests at second 59, then
another 60 at second 61 — both windows individually under the limit). A sliding
window — count only requests actually within the last `window` seconds, not within
a fixed calendar bucket — closes that gap.
"""
from __future__ import annotations

import time
import uuid

from .config import get_settings

_settings = get_settings()

_redis = None
if _settings.redis_url:
    try:  # optional dependency; gateway still runs without redis
        import redis.asyncio as aioredis

        _redis = aioredis.from_url(_settings.redis_url, decode_responses=True)
    except Exception:  # noqa: BLE001
        _redis = None

# In-memory fallback: {key: [timestamp, ...]} — timestamps within the current window.
_local: dict[str, list[float]] = {}


async def check_rate_limit(identity: str, prefix: str, limit: int, window: int) -> bool:
    """Return True if the request is allowed, False if the limit is exceeded."""
    now = time.time()
    key = f"rl:{identity}:{prefix}"

    if _redis is not None:
        try:
            cutoff = now - window
            pipe = _redis.pipeline()
            pipe.zremrangebyscore(key, 0, cutoff)
            pipe.zadd(key, {f"{now}-{uuid.uuid4().hex}": now})
            pipe.zcard(key)
            pipe.expire(key, window)
            _, _, count, _ = await pipe.execute()
            return count <= limit
        except Exception:
            pass  # Fall back to in-memory counter if redis is offline or unreachable

    timestamps = [t for t in _local.get(key, []) if t > now - window]
    timestamps.append(now)
    _local[key] = timestamps
    # opportunistic cleanup of stale keys
    if len(_local) > 10_000:
        _local.clear()
    return len(timestamps) <= limit


def reset_local() -> None:
    """Test hook."""
    _local.clear()
