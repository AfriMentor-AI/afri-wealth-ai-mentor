"""Card O5.1 / BUG-02: event publishing must never block the caller's thread,
whether that caller is on the event loop (async handler) or a worker thread
(sync handler, e.g. tag_commitment's httpx.post)."""
from __future__ import annotations

import asyncio
import threading
import time

import pytest

from app import events


@pytest.fixture(autouse=True)
def _no_real_rabbitmq(monkeypatch):
    # RABBITMQ_URL unset in tests already short-circuits _publish_blocking, but
    # patch it too so a slow/absent broker can never make these tests flaky —
    # what's under test is the dispatch mechanism, not delivery.
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(events, "_publish_blocking", lambda rk, p: calls.append((rk, p)))
    return calls


def test_publish_from_async_context_does_not_block_the_event_loop(_no_real_rabbitmq):
    async def scenario():
        started = time.perf_counter()
        events._publish("test.event", {"x": 1})
        # _publish must return immediately — it only schedules work.
        elapsed = time.perf_counter() - started
        assert elapsed < 0.05
        # Let the scheduled task actually run before asserting on it.
        await asyncio.sleep(0.05)

    asyncio.run(scenario())
    assert _no_real_rabbitmq == [("test.event", {"x": 1})]


def test_publish_from_sync_worker_thread_does_not_block(_no_real_rabbitmq):
    """Simulates FastAPI running a plain `def` handler in a worker thread with
    no running event loop — the exact context tag_commitment calls from."""
    result = {}

    def worker():
        started = time.perf_counter()
        events._publish("test.event.sync", {"y": 2})
        result["elapsed"] = time.perf_counter() - started

    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=1.0)

    assert result["elapsed"] < 0.05
    # Give the daemon thread _publish spawned a moment to run.
    time.sleep(0.05)
    assert ("test.event.sync", {"y": 2}) in _no_real_rabbitmq
