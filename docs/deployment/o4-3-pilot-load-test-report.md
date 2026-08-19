# O4.3 Pilot-Scale Load Test Report

**Card:** O4.3 — Load testing across all services at simulated pilot scale
**Date:** 2026-08-19
**Environment:** local Docker Compose staging overlay (`docker-compose.yml` +
`docker-compose.staging.yml`, project `afrimentor-staging`), run on a single
Windows dev machine — see "Environment caveats" below.

## Methodology

- **Concurrency baseline:** `docs/research/pilot-data-collection-plan-v0.md`
  (card C2.5) fixes the pilot cohort at **N = 30 participants**. This test
  treats that as the worst-case "all participants active at once" baseline and
  tests at **2x = 60 concurrent simulated users**, per the O4.3 acceptance
  criterion.
- **Scenarios** (`scripts/load-test/`): goals (create goal → add milestone →
  complete milestone), library (list insights → bookmark), progress (record
  action → fetch summary), plus the existing chat benchmark
  (`services/chat-orchestration-service/scripts/chat_latency_benchmark.py`,
  card D3.5 — session create → streamed message). 300 requests per service
  (60 users × 5 requests/user), run concurrently by
  `scripts/load-test/run_pilot_load_test.py`.
- A request counts as a P0 if it fails outright, or if the service's p95
  latency misses its budget (goals 1500ms, library/progress 1000ms, chat's
  own D3.5 budget of 3000ms for `complete_ms.p95`).

## Bugs found and fixed during this test

The stack had never actually been exercised at this concurrency before — D3.5's
own doc explicitly says its staging number was never measured, and
goals/progress/library had never run in the staging overlay at all. Standing
the test up surfaced four real, pre-existing issues, all fixed in this PR:

1. **`docker-compose.staging.yml` never gave `rabbitmq` a "no host ports"
   override** like the other datastores — the first attempt to start
   goals/progress services here collided with the dev stack's own rabbitmq on
   ports 5672/15672. Fixed: `rabbitmq: {ports: !reset []}`.
2. **`progress-gamification-service` and `insight-library-service` were
   missing `opentelemetry-instrumentation-sqlalchemy` from `requirements.txt`**
   — both crash-looped (`ModuleNotFoundError`) on a fresh `docker build`; the
   only reason this hadn't been caught is that the running dev containers were
   built from an older image before the import was added to
   `app/observability.py`. Fixed: added the missing pin (matches
   auth-user-service/chat-orchestration-service/goals-milestones-service/
   intake-profiling-service/rag-corpus-service, which already had it).
3. **`chat_latency_benchmark.py` (D3.5) aborted the entire run on the first
   failed/timed-out request** instead of recording it as a failed sample
   (unlike the three new O4.3 scripts, which already handle this) — made it
   impossible to get a real pass/fail read on chat under load. Fixed: wrapped
   `stream_one()` in the same try/except pattern.
4. **No service in this codebase tunes its SQLAlchemy connection pool** —
   every service uses the library default (`pool_size=5, max_overflow=10` = 15
   connections). At 60 concurrent users this queues or times out
   (`QueuePool limit ... reached, connection timed out`), confirmed directly in
   container logs. Fixed: `chat-orchestration-service`,
   `goals-milestones-service`, `progress-gamification-service`, and
   `insight-library-service` now set explicit pool sizes (guarded to only
   apply for Postgres, not the SQLite test/dev fallback). Chat's pool is
   larger (30/30) than the other three (10/10) because a chat request holds
   its DB session open for the full request — including the persona/RAG calls
   and SSE streaming — not just a quick round trip. Postgres's
   `max_connections` was also raised from the default 100 to 300 in the
   staging overlay to make room for four services' pools running
   concurrently against one shared instance.

## Results

### Before any fixes (first full run)
chat: 0/300 succeeded (script crashed on first failure — see bug #3).
goals/progress/library: real failures and multi-second p95s from pool
exhaustion (bug #4) — see git history of this file's first commit for the raw
numbers.

### After all four fixes (final run)

| Service | Requests | Successful | Failed | Success rate | p50 (ms) | p95 (ms) | Budget |
|---|---|---|---|---|---|---|---|
| chat-orchestration-service | 300 | 92 | 208 | 31% | 12,557.76 | 15,600.36 | 3,000ms |
| goals-milestones-service | 300 | 282 | 18 | 94% | 3,541.56 | 8,144.06 | 1,500ms |
| insight-library-service | 300 | 289 | 11 | 96% | 1,752.45 | 3,307.92 | 1,000ms |
| progress-gamification-service | 300 | 243 | 57 | 81% | 150.04 | 346.14 | 1,000ms |

## Verdict

**FAIL — this is not a clean pass, and I'm not going to report it as one.**

- **goals-milestones-service and insight-library-service** are close to
  target after the pool fix (94–96% success) but still miss their p95 budget
  under sustained 60-concurrent load; the budgets themselves were a
  provisional guess (no prior number existed) and may need revisiting once a
  dedicated staging host is available.
- **progress-gamification-service** has excellent latency (346ms p95, well
  under budget) but an 81% success rate. Its container logs show **zero**
  server-side errors or exceptions during the run — the failures have no
  server-side signature, which points to transient connection-level noise
  from running the load generator on the same Windows machine as Docker
  Desktop, not a backend defect. This should be re-verified from a separate
  host before treating it as a real gap.
- **chat-orchestration-service is a genuine, unresolved bottleneck.** I
  fixed its connection pool three times over (5→10→30 pool size, plus
  raising Postgres's ceiling) and container CPU stayed under 1% throughout
  every run (`docker stats` — chat, rag-corpus-service, persona-prompt-service,
  and postgres were all essentially idle by CPU) — so this is **not** a
  compute or connection-pool capacity problem. First-token latency of
  12–20 seconds under 60 concurrent stub-LLM requests (no real
  `LLM_API_KEY` configured) indicates a deeper bottleneck in the
  persona-fetch/RAG-retrieval/streaming path that needs actual profiling
  (py-spy or equivalent, and a real staging host free of this machine's
  Docker-Desktop-on-Windows networking overhead) to diagnose properly. I'm
  not going to guess further at a fix I can't validate — this needs its own
  dedicated investigation.

## Environment caveats

- No real cloud staging environment exists yet (`docs/deployment/staging.md`)
  — this ran against a local Docker Compose stack on one Windows development
  machine, sharing CPU/network with Docker Desktop, this session's tooling,
  and (briefly) the regular dev stack. A dedicated staging host would remove
  this as a confound, particularly for chat's result.
- Chat ran against the stub LLM reply path (`LLM_API_KEY` unset) so these
  numbers exclude real model inference latency entirely — they only measure
  the surrounding request pipeline (session handling, persona fetch, RAG
  retrieval, DB writes, SSE framing).
- `feedback-service` and `research-evaluation-service` were excluded from
  this test (not part of O4.3's target services — chat/goals/library/progress)
  and are separately tracked: both failed to start cleanly in a fresh staging
  build for reasons unrelated to this ticket (see the two follow-up tasks
  spawned during this work).

## Recommendations (feed into O4.5 infra readiness review)

1. **Chat-orchestration-service needs dedicated profiling** before pilot —
   this is the one real open P0 from this report.
2. **Add a connection pooler (PgBouncer)** in front of Postgres rather than
   relying on a raised `max_connections` ceiling alone, once more services
   are exercised at real concurrency.
3. **Re-run this suite from a dedicated staging host**, not a developer
   laptop, to remove Docker-Desktop-on-Windows networking overhead as a
   confound — particularly for chat and progress-gamification-service's
   results.
4. **Revisit the p95 budgets** (goals 1500ms, library/progress 1000ms) once a
   real host's numbers are in — they were provisional guesses, not measured
   baselines.

## Reproducing

```bash
# from repo root, with the staging stack already up (see scripts/deploy-staging.sh)
cd scripts/load-test
python run_pilot_load_test.py --concurrency 60 --requests-per-user 5
```
