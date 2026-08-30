# O5.2 follow-up: chat p95 latency measurement (real LLM inference)

Date: 2026-08-30
Scope: closes the measurement gap left by O5.2 (`docs/a11y-hardening-pass.md`) — that
pass verified accessibility, build/lint, and a RAG-timeout fix, but never actually
measured chat latency against the AC's `<3s p95` target. This doc does that
measurement and reports the result honestly, including that it does not meet target.

## Why this wasn't measured during O5.2

At the time O4.3's pilot load-test report was written, `LLM_API_KEY` was not
configured, so all prior chat-latency numbers were against the stub reply path
(near-instant, not representative). Mid-way through this session a real, live Groq
API key was confirmed present in `.env` and in the running
`chat-orchestration-service` container — for the first time, a genuine measurement
against real LLM inference was possible.

## Method

`services/chat-orchestration-service/scripts/chat_latency_benchmark.py` against the
service directly (`http://localhost:8003`), streaming responses, measuring
time-to-first-token and time-to-complete. The script's own exit code encodes the
AC (`0` if `complete_ms.p95 < 3000`, else `2`).

## Results

**Single user, 5 sequential requests** (isolates raw per-request latency from any
concurrency contention):

| metric | p50 | p95 | mean |
|---|---|---|---|
| first_token_ms | 1323.73 | 3579.19 | 1754.89 |
| complete_ms | 2001.07 | **4211.95** | 2762.88 |

**5 concurrent users, 10 requests:**

| metric | p50 | p95 | mean |
|---|---|---|---|
| first_token_ms | 5318.96 | 11702.26 | 7189.06 |
| complete_ms | 5388.54 | **11702.84** | 7572.30 |

Both runs exceed the 3s p95 target — the AC is **not met** against real inference.
Latency degrades sharply under even light concurrency (4.2s → 11.7s p95 at just 5
concurrent users), which is not proportional to the added load.

## Root cause

Not an application-level bug:

- `chat-orchestration-service` logs show **no** `LLM unavailable`/fallback warnings
  during these runs — the responses are genuine model completions, not the stub path.
- `get_llm_client()` (`app/llm.py`) already uses a single module-level `AsyncOpenAI`
  client with connection pooling (`HTTP_POOL_MAX_CONNECTIONS`) — not the
  per-request-client pattern that caused BUG-01 in the gateway.
- System-prompt fetch and RAG retrieval already run concurrently via
  `asyncio.gather()`, not serially, before the LLM call.
- The sharp degradation under light concurrency, with no application-side
  serialization point in the request path, is consistent with **provider-side
  rate limiting/queuing** on the configured Groq API key's tier — not something
  fixable in this codebase without a different provider tier or model.

## Disposition

Logged as a real, unresolved gap against O5.2's AC — not silently marked done.
Recommended as a Phase 2 item: either move to a paid/higher-tier Groq plan (or a
different low-latency provider) sized for pilot-scale concurrent chat traffic, or
add client-side request queuing/backpressure so p95 degrades gracefully rather than
un-bounded under load. Tracked in `docs/mvp-scope-closure-report.md` and
`docs/phase-2-roadmap.md`.
