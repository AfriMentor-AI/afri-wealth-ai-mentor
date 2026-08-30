"""Card O5.1 / BUG-04: sliding-window rate limiter tests (in-memory fallback path —
no Redis in this test env, matching how the module already degrades)."""
import asyncio

from app import ratelimit


def _run(coro):
    return asyncio.run(coro)


def test_allows_up_to_the_limit(monkeypatch):
    ratelimit.reset_local()
    monkeypatch.setattr(ratelimit.time, "time", lambda: 1000.0)
    for _ in range(5):
        assert _run(ratelimit.check_rate_limit("user:a", "/x", limit=5, window=60)) is True
    assert _run(ratelimit.check_rate_limit("user:a", "/x", limit=5, window=60)) is False


def test_window_boundary_no_longer_allows_double_burst(monkeypatch):
    """The bug this fixes: with a fixed-window counter, sending `limit` requests
    just before a window boundary and another `limit` requests just after lets
    2x `limit` through inside one real `window`-second span. A sliding window
    must reject the second burst."""
    ratelimit.reset_local()
    current_time = {"t": 1000.0}
    monkeypatch.setattr(ratelimit.time, "time", lambda: current_time["t"])

    limit, window = 10, 60
    # First burst: fills the limit right at t=1000.
    for _ in range(limit):
        assert _run(ratelimit.check_rate_limit("user:b", "/x", limit, window)) is True

    # Old fixed-window bug: advancing 2s used to cross into a new 60s bucket
    # (t=1000 -> bucket 16, t=1002 wouldn't, but the classic exploit is sending
    # right before/after a real boundary at a multiple of `window`). Simulate
    # that exact exploit: advance to just past where a fixed window would have
    # rolled over, while still well inside a real sliding 60s window from the
    # first burst.
    current_time["t"] = 1000.0 + (window - 1)  # 59s later — same sliding window
    assert _run(ratelimit.check_rate_limit("user:b", "/x", limit, window)) is False

    # After the sliding window has genuinely elapsed, new requests are allowed again.
    current_time["t"] = 1000.0 + window + 1
    assert _run(ratelimit.check_rate_limit("user:b", "/x", limit, window)) is True


def test_independent_keys_dont_interfere(monkeypatch):
    ratelimit.reset_local()
    monkeypatch.setattr(ratelimit.time, "time", lambda: 2000.0)
    for _ in range(3):
        assert _run(ratelimit.check_rate_limit("user:c", "/goals", limit=3, window=60)) is True
    # Different identity and different route prefix both get their own budget.
    assert _run(ratelimit.check_rate_limit("user:d", "/goals", limit=3, window=60)) is True
    assert _run(ratelimit.check_rate_limit("user:c", "/chat", limit=3, window=60)) is True
