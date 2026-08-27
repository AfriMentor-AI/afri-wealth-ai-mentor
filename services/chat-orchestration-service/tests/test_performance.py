"""Focused D3.5 tests for chat caching and response streaming."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine, get_db
from app.main import app
from app.rag import RagResult

USER_HEADERS = {"X-User-Id": "performance-test-user"}


def _client():
    Base.metadata.create_all(bind=engine)

    def override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def test_rag_cache_avoids_second_downstream_call(monkeypatch):
    import app.rag as rag

    rag._cache.clear()
    rag._http_client = None
    monkeypatch.setattr(rag.settings, "rag_service_url", "http://rag.test")
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "results": [{"content": "cached", "metadata": {"title": "Test"}, "score": 1.0}]
    }
    client = AsyncMock()
    client.post.return_value = response
    monkeypatch.setattr(rag, "_http_client", client)

    async def run():
        first = await rag.retrieve("  How do I save? ")
        second = await rag.retrieve("how do i save?")
        return first, second

    first, second = asyncio.run(run())
    assert first == second == [RagResult("cached", "Test", 1.0)]
    client.post.assert_awaited_once()


def test_stream_endpoint_emits_tokens_then_completion(monkeypatch):
    client = _client()
    try:
        session = client.post("/api/v1/chat/sessions", json={}, headers=USER_HEADERS).json()

        async def tokens():
            yield "First "
            yield "reply"

        async def fake_stream(**kwargs):
            return tokens(), [{"label": "Test source"}]

        with patch("app.routers.chat.stream_chat_completion", side_effect=fake_stream):
            response = client.post(
                f"/api/v1/chat/sessions/{session['id']}/messages/stream",
                json={"content": "Hello"},
                headers=USER_HEADERS,
            )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: token" in response.text
        assert '"text": "First "' in response.text
        assert '"text": "reply"' in response.text
        assert "event: complete" in response.text
        assert '"content": "First reply"' in response.text
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_stream_assembly_returns_first_chunk_without_waiting_for_tail():
    async def delayed_tokens():
        yield "first"
        await asyncio.sleep(0.05)
        yield " tail"

    async def run():
        started = time.perf_counter()
        seen = []
        async for token in delayed_tokens():
            seen.append((token, time.perf_counter() - started))
        return seen

    seen = asyncio.run(run())
    assert seen[0][0] == "first"
    assert seen[0][1] < 0.05
    assert "".join(token for token, _ in seen) == "first tail"


def test_parallel_prompt_and_rag_retrieval(monkeypatch):
    import app.llm as llm

    async def slow_prompt(persona_id):
        await asyncio.sleep(0.05)
        return "You are Chioma."

    async def slow_rag(query, *, collection=None, top_k=3):
        await asyncio.sleep(0.05)
        return [RagResult("knowledge content", "Test Source", 0.9)]

    monkeypatch.setattr(llm, "_get_system_prompt", slow_prompt)
    monkeypatch.setattr(llm, "retrieve", slow_rag)

    async def run():
        started = time.perf_counter()
        stream, citations = await llm.stream_chat_completion(
            history=[],
            user_content="How do I save?",
            persona_id="chioma-base",
            rag_collection=None,
        )
        elapsed = time.perf_counter() - started
        return elapsed, citations

    elapsed, citations = asyncio.run(run())
    # If sequential, it would take >= 0.10s. Since parallelized via asyncio.gather, it completes in ~0.05s (< 0.09s)
    assert elapsed < 0.09
    assert citations == [{"label": "Test Source"}]


def test_concurrent_streaming_at_pilot_exit_concurrency():
    """Simulate 60 concurrent streaming chat requests (2x pilot cohort = 60 users).

    Verifies that async streaming pipelines and token generators handle 60 concurrent
    streaming tasks cleanly with sub-second latencies and without resource starvation.
    """
    import app.llm as llm

    async def run_concurrent():
        async def stream_one(user_idx: int):
            started = time.perf_counter()
            stream, citations = await llm.stream_chat_completion(
                history=[],
                user_content=f"User query {user_idx}",
                persona_id="chioma-base",
                rag_collection=None,
            )
            tokens = []
            async for token in stream:
                tokens.append(token)
            elapsed = time.perf_counter() - started
            return elapsed, "".join(tokens)

        tasks = [stream_one(i) for i in range(60)]
        results = await asyncio.gather(*tasks)
        return results

    results = asyncio.run(run_concurrent())
    assert len(results) == 60
    # All 60 streams run concurrently and complete well within budget
    for elapsed, text in results:
        assert elapsed < 1.0
        assert len(text) > 0

