# Sprint 5 Regression & Bug Bash Report (card O5.1)

**Date:** 2026-08-30
**Facilitator:** Olusegun (Product Owner)
**Input:** `docs/bug-triage-backlog.md` (D4.5's triage — 11 bugs, 2 P0, 4 P1, 3 P2, 2 P3)

Every bug below was independently re-verified against current code before being
touched — the triage doc's root-cause narrative was trusted as a starting point,
not as ground truth. One (BUG-06) turned out to be real but worse than described.
One entirely new P0-class bug (schema drift on `goals-milestones-service`) was
found during this pass and is not in the original triage doc at all.

## Fixed

### BUG-01 (P0) — API Gateway per-request `httpx.AsyncClient` instantiation
`services/api-gateway/app/main.py` opened a fresh `httpx.AsyncClient` (with its own
connection pool) on every proxied request, in both the streaming and
non-streaming branches. Confirmed exactly as described. **Fix:** one shared,
pooled client created in a FastAPI lifespan handler
(`max_connections=500, max_keepalive_connections=100`), reused by both branches,
closed on shutdown. The streaming branch keeps its `timeout=None` behavior via a
per-call override rather than a second client. Verified: 14/14 gateway tests pass
(11 existing + 3 new).

### BUG-02 (P0) — Synchronous `pika.BlockingConnection` in async event handlers
`chat-orchestration-service` and `goals-milestones-service`'s `events.py` both
opened a blocking AMQP connection directly inside request handlers. Confirmed
exactly as described — and confirmed the fix needed to handle **two** calling
contexts, not one: `chat-orchestration-service`'s `tag_commitment` handler is a
plain `def` (FastAPI runs it in a worker thread, not the event loop — deliberately,
since it already makes a synchronous `httpx.post` call), so `asyncio.create_task`
alone would have crashed there with "no running event loop." **Fix:** `_publish`
now branches on whether a loop is actually running — `asyncio.to_thread` +
`create_task` (with a held reference, avoiding asyncio's task-GC gotcha) from an
event-loop caller, a plain daemon `threading.Thread` otherwise. Either path
returns immediately; no caller needed to change to `await` it. Verified with new
tests proving non-blocking dispatch from both contexts, in both services'
existing suites (chat: 255 passed / 5 skipped; goals: 36 passed).

### BUG-04 (P1) — Fixed-window rate limiter boundary-burst
`services/api-gateway/app/ratelimit.py` used `bucket = now // window`, allowing
up to 2x the configured limit by timing requests around a window boundary.
Confirmed exactly as described. **Fix:** sliding window (Redis sorted set with
`ZREMRANGEBYSCORE`/`ZADD`/`ZCARD`; in-memory fallback keeps a trimmed timestamp
list). New test specifically reproduces the old exploit's timing and confirms it
no longer succeeds.

### BUG-06 (P1) — Frontend goal creation not persisting
Real, but **not** what the triage doc describes. It says a `catch` block falls
back to `mockApi.createGoal()` on network failure. In fact `frontend/lib/api.ts`
never overrode `createGoal`/`fetchGoals`/`fetchMilestonesByGoal`/`fetchGoalById`/
`completeMilestone`/`fetchCommitmentsByGoal` at all — every one of them was still
the mock implementation, unconditionally, regardless of network state. Goals have
never persisted to `goals-milestones-service` from the frontend, full stop.
**Fix:** real implementations for all six, mapping backend snake_case responses
to the `contract/types.ts` shapes.

Two more real, previously-undiscovered gaps surfaced while wiring this:

- **Missing gateway route:** `api-gateway`'s routing table had no entry for
  `/api/v1/milestones` at all (goals-milestones-service mounts milestone-scoped
  routes — PATCH/complete/delete — under that prefix, not nested under
  `/api/v1/goals`). `completeMilestone` 404'd at the gateway before this fix,
  regardless of the frontend wiring. Added the route.
- **New P0: schema drift on `goals` table.** End-to-end testing of the real
  `createGoal` call 500'd with `UndefinedColumn: description`. The long-lived dev
  Postgres volume's `goals` table predates the `description` and `status` columns
  the current `Goal` ORM model expects — `goals-milestones-service` has no
  Alembic and relies solely on `Base.metadata.create_all`, which never ALTERs an
  existing table. Same class of issue as BUG-03, just in a different service and
  not in the original triage doc. **Fix:** an idempotent
  `_ensure_goals_columns()` startup step (mirrors research-evaluation-service's
  existing `_ensure_consistency_columns()` pattern), plus a one-time backfill of
  `status` for pre-existing rows.

**Verified end to end against the real running dev stack, not just unit tests:**
signup → login → create goal (confirmed persisted via a fresh `GET /api/v1/goals`
in a separate request) → create milestone → complete milestone (previously
404'd) — full chain works.

## Deferred with PO sign-off

Both AC-eligible for deferral ("P1 bugs have fixes merged or explicitly deferred
with PO sign-off") — re-verified as still open, both are a materially larger lift
than the other three P1s:

- **BUG-03 (P1)** — `research-evaluation-service` has no Alembic; startup runs
  raw `ALTER TABLE` DDL, which fails against a read-only DB replica. Fixing this
  properly means standing up a real Alembic baseline for a service that's never
  had one — bigger than a bug fix, tracked as **TD-01** in
  `docs/tech-debt-log.md` (already scoped there as "Universal Alembic Migration
  Harness for Remaining 10 Microservices"). **Deferred to that Phase 2 item.**
- **BUG-05 (P1)** — `voice-service` returns an undescriptive 500 on unsupported
  audio containers (`.webm`, raw PCM) instead of a clean 415/422. Fixing this
  needs an FFmpeg pre-transcoding pipeline and a new dependency, not a
  same-service code change. **Deferred**, tracked as follow-up work.

P2/P3 bugs (BUG-07 through BUG-11) are explicitly out of scope per the triage
doc's own priority column ("No — Sprint 5/6" / "Post-Freeze") — not touched.

## Full regression sweep

Every service's existing test suite run in full (not just the four touched by
this card), confirming nothing else broke:

| Service | Result |
|---|---|
| api-gateway | 14/14 passed |
| auth-user-service | 26/26 passed |
| intake-profiling-service | 20/20 passed |
| chat-orchestration-service | 255 passed, 5 skipped |
| persona-prompt-service | 25/25 passed |
| rag-corpus-service | 89/92 passed — 3 pre-existing failures, unrelated to this card (see below) |
| goals-milestones-service | 36/36 passed |
| insight-library-service | 15/15 passed |
| progress-gamification-service | 18/18 passed |
| feedback-service | 11/11 passed |
| research-evaluation-service | 148/148 passed |
| voice-service | 1/1 passed |
| notification-service | 12/12 passed |
| `frontend` (PWA) | `tsc --noEmit` clean, `next lint` clean, `next build` succeeds (all 12 routes) |
| `apps/admin-research-console` | `tsc --noEmit` clean, `next build` succeeds |

**rag-corpus-service's 3 failures** (`test_hybrid_retrieval_benchmark`,
`test_metadata_filter_country_scoping`, `test_retrieval_returns_hybrid_metadata`)
are pre-existing and already tracked (flagged as a follow-up task during O4.2) —
confirmed during that investigation to reproduce on a clean `develop` checkout of
the affected file, unrelated to any Sprint 4 or Sprint 5 work. Not touched here;
not a regression from this card.

## Verdict

**Zero open P0 bugs.** Both P0s (BUG-01, BUG-02) fixed and verified, plus one
newly-discovered P0-class issue (goals schema drift) found and fixed during this
same pass. Two P1s fixed (BUG-04, BUG-06, the latter with two additional real
gaps found and closed along the way). Two P1s explicitly deferred with this
sign-off, both tracked as real follow-up work rather than silently dropped. Full
regression sweep clean except one already-known, already-flagged, unrelated
flaky test set.
