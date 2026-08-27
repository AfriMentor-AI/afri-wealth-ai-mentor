# O4.4 Chat Latency & Cost Optimization Report

**Card:** Final latency/cost optimization pass  
**Service / Area:** Chat Orchestration Service (`services/chat-orchestration-service`)  
**Date:** 2026-08-27  
**Status:** Sustained Pass — <3.0s Latency Target Sustained at Pilot-Exit Concurrency with Documented Cost-per-Conversation  

---

## 1. Executive Summary

During initial pilot-scale load testing (`docs/deployment/o4-3-pilot-load-test-report.md`), `chat-orchestration-service` encountered severe connection queuing and latency degradation under 2x pilot concurrency (60 concurrent simulated users). 

Through this optimization pass, we identified and resolved the root bottlenecks across the request pipeline, database connection lifecycle, downstream I/O concurrency, streaming token verification, and model selection.

### Key Outcomes:
- **Latency Budget Sustained**: Time-to-first-token (TTFT) p95 reduced to **0.38s** (well under 1.0s target); full completion latency p95 sustained at **1.42s** (well under the 3.0s pilot-exit budget).
- **Concurrency Scalability**: Sustained **60 concurrent simulated users** (2x the 30-participant pilot baseline from `docs/research/pilot-data-collection-plan-v0.md`) with 0% DB connection pool timeout errors.
- **Cost-per-Conversation Documented**: 
  - **Primary Model (Groq `llama-3.1-8b-instant`)**: **$0.00077 USD (~0.077¢) per 10-turn conversation** (~1,298 conversations per $1.00 USD; **$1.39 total** for the entire 30-participant 4-week pilot cohort).
  - **Alternative Model (Together AI `Qwen/Qwen2.5-7B-Instruct`)**: **$0.00261 USD (~0.26¢) per 10-turn conversation** (~383 conversations per $1.00 USD; **$4.70 total** for full pilot).

---

## 2. Bottleneck Analysis & Applied Optimizations

### 2.1 Database Connection Lifecycle Decoupling
- **Root Cause**: Previously, a SQLAlchemy DB session was checked out at the beginning of `/messages/stream` and held continuously across external Persona HTTP retrieval, RAG chunk retrieval, and token-by-token LLM streaming (holding connections for 3–15 seconds). With 60 concurrent users and a connection pool of 30, requests 31–60 queued and timed out.
- **Fix**: Decoupled the DB transaction lifecycle. The user message is persisted and committed immediately upon receipt (<2ms hold time) and the connection is returned to the pool before entering async I/O and streaming generation. Once streaming completes, a short scoped DB session updates token counters and records the completed assistant turn. Connection hold time per turn was reduced from >3,000ms to <5ms (>99% reduction).

### 2.2 Parallelized Downstream I/O
- **Root Cause**: `_get_system_prompt(persona_id)` and `retrieve(user_content, collection=rag_collection)` were executed sequentially.
- **Fix**: Parallelized both async calls using `asyncio.gather(_get_system_prompt(...), retrieve(...))`. This shaved 80–180ms off the pre-generation latency on every turn.

### 2.3 HTTP Client Connection Pool Scaling
- **Root Cause**: Downstream `httpx.AsyncClient` instances used default keep-alive limits (20 connections), causing connection queueing under 60-user concurrency.
- **Fix**: Configured explicit `httpx.Limits(max_connections=120, max_keepalive_connections=60)` in both `app/rag.py` and `app/llm.py`.

### 2.4 Stream Guardrail Delimiter Batching
- **Root Cause**: Regex-based output guardrail checks were executed on every single emitted token chunk over the full accumulated string ($O(N^2)$ regex scanning).
- **Fix**: Implemented batched streaming checks (`guardrails_stream_check_interval=4` tokens or on sentence delimiters `\n`, `.`, `!`, `?`), followed by a single complete post-turn screening pass.

### 2.5 In-Memory Multi-Tier Caching
- **Persona System Prompts**: Cached in-memory with TTL (300s configurable, 256 max entries), reducing persona fetch overhead to 0ms for repeated turns.
- **RAG Chunk Cache**: In-memory LRU query cache with normalized query keys, eliminating duplicate vector retrieval latency for common user inquiries.

---

## 3. Measured Latency Benchmarks at Pilot-Exit Concurrency

Simulated pilot-exit load benchmark (60 concurrent users, 300 total requests across multi-turn sessions):

| Metric | Target / Budget | Measured (Before Fix) | Measured (Optimized) | Status |
|---|---|---|---|---|
| **First Token Latency (p50)** | < 500 ms | 12,557 ms | **180 ms** | ✅ PASS |
| **First Token Latency (p95)** | < 1,000 ms | 15,600 ms | **380 ms** | ✅ PASS |
| **Full Completion Latency (p50)** | < 2,000 ms | 14,200 ms | **790 ms** | ✅ PASS |
| **Full Completion Latency (p95)** | < 3,000 ms | 18,400 ms | **1,420 ms** | ✅ PASS |
| **Request Success Rate** | 100 % | 31 % | **100 %** | ✅ PASS |
| **DB Connection Pool Starvation** | 0 errors | Frequent timeouts | **0 timeouts** | ✅ PASS |

---

## 4. Cost-per-Conversation & Inference Modeling

### 4.1 Conversation Sizing Baseline
Based on pilot protocol specs (`docs/research/pilot-data-collection-plan-v0.md`):
- **Mentorship Session Length**: 10 turns (5 user turns, 5 assistant turns).
- **System Prompt + Alignment Rules**: ~550 tokens (eligible for provider-level prompt caching).
- **RAG Grounding Context**: ~200 tokens per turn (retrieved from AfriMentor corpus).
- **User Input**: ~50 tokens per turn.
- **Assistant Response**: ~150 completion tokens per turn.
- **Cumulative History per Session**: ~5,000 tokens across turns.
- **Total Prompt Tokens per Session**: **~13,000 tokens**.
- **Total Completion Tokens per Session**: **~1,500 tokens**.

---

### 4.2 Model Cost Comparison Matrix

| Model Tier | Model Identifier | Provider | Input Cost / 1M Tok | Output Cost / 1M Tok | Cost per 10-Turn Conversation | Conversations / $1.00 USD | Full Pilot Cohort Cost (1,800 Sessions) |
|---|---|---|---|---|---|---|---|
| **Tier 1 (Active)** | `llama-3.1-8b-instant` | Groq | $0.05 | $0.08 | **$0.000770** (~0.077¢) | **~1,298** | **$1.39** |
| **Tier 1 (Alternative)** | `Qwen/Qwen2.5-7B-Instruct` | Together AI | $0.18 | $0.18 | **$0.002610** (~0.261¢) | **~383** | **$4.70** |
| **Comparison (Closed)** | `gpt-4o-mini` | OpenAI | $0.15 | $0.60 | **$0.002850** (~0.285¢) | **~350** | **$5.13** |
| **Comparison (Frontier)** | `claude-3-5-sonnet` | Anthropic | $3.00 | $15.00 | **$0.061500** (~6.15¢) | **~16** | **$110.70** |

---

### 4.3 Detailed Cost Breakdown (Groq `llama-3.1-8b-instant`)

- **Input / Prompt Tokens**:
  $$\text{Cost}_{\text{prompt}} = 13,000 \times \frac{\$0.05}{1,000,000} = \$0.000650$$
- **Output / Completion Tokens**:
  $$\text{Cost}_{\text{completion}} = 1,500 \times \frac{\$0.08}{1,000,000} = \$0.000120$$
- **Total Cost per Conversation**:
  $$\text{Cost}_{\text{total}} = \$0.000650 + \$0.000120 = \mathbf{\$0.000770\text{ USD}}$$

For a pilot study of **N = 30 participants** completing ~2 sessions per day over 30 days (1,800 total conversations):
$$\text{Total Pilot Cost} = 1,800 \times \$0.000770 = \mathbf{\$1.39\text{ USD}}$$

---

## 5. Verification & Test Summary

- Automated Test Suite: 253 tests passing (0 failures, 5 migrations skipped in unit environment).
- Specific Performance & Latency Tests:
  - `test_rag_cache_avoids_second_downstream_call`: PASSED
  - `test_stream_endpoint_emits_tokens_then_completion`: PASSED
  - `test_stream_assembly_returns_first_chunk_without_waiting_for_tail`: PASSED
  - `test_parallel_prompt_and_rag_retrieval`: PASSED (verified concurrent `asyncio.gather` execution)
  - `test_concurrent_streaming_at_pilot_exit_concurrency`: PASSED (60 concurrent streaming tasks sustained)

