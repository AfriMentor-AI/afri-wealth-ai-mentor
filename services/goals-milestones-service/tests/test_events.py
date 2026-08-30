"""Card O5.1 / BUG-02: event publishing must never block the caller's thread,
whether that caller is on the event loop (async handler) or a worker thread
(sync handler)."""
from __future__ import annotations

import asyncio
import threading
import time

import pytest

from app import events


@pytest.fixture(autouse=True)
def _no_real_rabbitmq(monkeypatch):
    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(events, "_publish_blocking", lambda rk, p: calls.append((rk, p)))
    return calls


def test_publish_from_async_context_does_not_block_the_event_loop(_no_real_rabbitmq):
    async def scenario():
        started = time.perf_counter()
        events._publish("test.event", {"x": 1})
        elapsed = time.perf_counter() - started
        assert elapsed < 0.05
        await asyncio.sleep(0.05)

    asyncio.run(scenario())
    assert _no_real_rabbitmq == [("test.event", {"x": 1})]


def test_publish_from_sync_worker_thread_does_not_block(_no_real_rabbitmq):
    result = {}

    def worker():
        started = time.perf_counter()
        events._publish("test.event.sync", {"y": 2})
        result["elapsed"] = time.perf_counter() - started

    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=1.0)

    assert result["elapsed"] < 0.05
    time.sleep(0.05)
    assert ("test.event.sync", {"y": 2}) in _no_real_rabbitmq
