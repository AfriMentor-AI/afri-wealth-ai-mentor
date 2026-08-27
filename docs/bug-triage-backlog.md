# Code-Freeze Bug Backlog & Triage Report — Sprint 5 Hardening

- **Document Version:** 1.0.0
- **Service / Area:** Engineering Leadership & Platform Governance
- **Date:** 2026-08-27
- **Facilitators / Triage Leads:** Daniel (Lead Software Engineer / Architecture), Olusegun (Product Owner / Platform Infrastructure)
- **Status:** Triaged & Approved Baseline for Sprint 5 Code Freeze
- **Target Milestone:** Sprint 5 Hardening & Production Pilot Readiness

---

## 1. Triage Framework & Severity Taxonomy

To maintain system stability during the Sprint 5 code freeze and pilot onboarding, open bugs are triaged using standard priority ratings (**P0, P1, P2, P3**) with strict resolution SLAs:

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                PRIORITY & SLA TAXONOMY                                   │
├──────────┬─────────────────────────────┬──────────────────────────┬──────────────────────┤
│ Priority │ Definition                  │ Hardening / Pilot Impact │ Target SLA           │
├──────────┼─────────────────────────────┼──────────────────────────┼──────────────────────┤
│ **P0**   │ Blocker / Critical Defect   │ Halts code freeze; data  │ Fix within 24h       │
│          │ System crash, auth bypass,  │ corruption or crash on   │ (Must resolve before │
│          │ data loss, service outage   │ core user journey        │ freeze sign-off)     │
├──────────┼─────────────────────────────┼──────────────────────────┼──────────────────────┤
│ **P1**   │ High Severity               │ Degrades user experience │ Fix within 72h       │
│          │ Broken core feature with no │ or causes intermittent   │ (Targeted for        │
│          │ workaround; memory leak     │ session loss             │ Sprint 5 hardening)  │
├──────────┼─────────────────────────────┼──────────────────────────┼──────────────────────┤
│ **P2**   │ Medium Severity             │ Non-blocking functional  │ Fix in next sprint   │
│          │ Edge-case defect, cosmetic  │ glitch with available    │ cycle (Sprint 5/6)   │
│          │ inconsistency, minor leak   │ fallback/workaround      │                      │
├──────────┼─────────────────────────────┼──────────────────────────┼──────────────────────┤
│ **P3**   │ Low Severity                │ Minor visual polish, log │ Backlog / Scheduled  │
│          │ Typo, documentation drift,  │ noise, non-critical stub │ for post-pilot       │
│          │ non-user-facing polish      │ enhancement              │                      │
└──────────┴─────────────────────────────┴──────────────────────────┴──────────────────────┘
```

---

## 2. Triaged Bug Backlog Summary

| Bug ID | Title | Priority | Affected Service(s) | Primary Owner | Status | Hardening Blocker? |
|---|---|---|---|---|---|---|
| **BUG-01** | Gateway HTTP Client per-request instantiation causes socket exhaustion under high concurrency | **P0** | `api-gateway` | Olusegun | Ready for Fix | **YES (Blocker)** |
| **BUG-02** | Synchronous AMQP `BlockingConnection` in async chat/goal handlers blocks event loop | **P0** | `chat-orchestration-service`, `goals-milestones-service` | Daniel | Ready for Fix | **YES (Blocker)** |
| **BUG-03** | Startup DDL column monkeypatch in `research-evaluation-service` fails on read-only DB replicas | **P1** | `research-evaluation-service` | Chukwuebuka | In Progress | **YES (Hardening)** |
| **BUG-04** | Fixed-window Redis rate limiter in API Gateway allows $2\times$ burst at window boundaries | **P1** | `api-gateway` | Olusegun | Ready for Fix | No (Sprint 5) |
| **BUG-05** | Missing audio format validation and mime transcoding in `voice-service` causes 500 error | **P1** | `voice-service` | Daniel | In Progress | **YES (Hardening)** |
| **BUG-06** | Frontend PWA `mockApi.ts` fallback leak during intermittent network drops on Goal Creation | **P1** | `frontend/` | Grace | In Progress | **YES (Hardening)** |
| **BUG-07** | ChromaDB SQLite lock contention when concurrent document ingestion occurs during chat retrieval | **P2** | `rag-corpus-service` | Chukwuebuka | Triaged | No (Sprint 6) |
| **BUG-08** | Incomplete W3C trace context injection across AMQP headers drops distributed trace links | **P2** | All Services, Shared Library | Chukwuebuka | Triaged | No (Sprint 5) |
| **BUG-09** | Gamification XP calculation race condition on concurrent duplicate `milestone.completed` events | **P2** | `progress-gamification-service` | Grace | Triaged | No (Sprint 5) |
| **BUG-10** | Mobile Safari layout shift on virtual keyboard opening in mentor chat input | **P3** | `frontend/` | Grace | Triaged | No (Post-Freeze) |
| **BUG-11** | Stale CORS headers when preflight `OPTIONS` request contains non-standard custom auth header | **P3** | `api-gateway` | Olusegun | Triaged | No (Post-Freeze) |

---

## 3. Detailed Bug Triage & Root Cause Specifications

### BUG-01: Gateway HTTP Client Per-Request Instantiation
- **Priority:** **P0**
- **Affected Component:** `services/api-gateway/app/main.py`
- **Owner:** Olusegun
- **Symptoms:** Under load testing (60 concurrent users), the API Gateway experiences file descriptor exhaustion and `httpx.PoolTimeout` errors.
- **Root Cause Analysis:** `gateway()` and `events()` handlers initialize a new `httpx.AsyncClient` on every incoming request rather than using a single shared client pool initialized in the application lifespan.
- **Reproduction:** Run 100 concurrent requests against `/api/v1/chat/sessions` via `scripts/load-test/locustfile.py`. Socket count increases linearly until `OSError: [Errno 24] Too many open files`.
- **Hardening Remediation:** Refactor `api-gateway` lifespan to initialize a singleton `httpx.AsyncClient(limits=httpx.Limits(max_connections=500, max_keepalive_connections=100), timeout=30.0)` attached to `app.state.client`.

---

### BUG-02: Synchronous AMQP `BlockingConnection` in Async Event Handlers
- **Priority:** **P0**
- **Affected Component:** `chat-orchestration-service/app/events.py`, `goals-milestones-service/app/events.py`
- **Owner:** Daniel
- **Symptoms:** Chat streaming latency spikes intermittently by 400–800ms when completing a conversation turn.
- **Root Cause Analysis:** The event publisher executes `pika.BlockingConnection(pika.ConnectionParameters(...))` synchronously on the main asyncio thread to emit `chat.turn_completed`, halting the event loop during socket handshake and frame delivery.
- **Reproduction:** Send 10 concurrent chat messages; measure event loop lag using `asyncio` debug mode.
- **Hardening Remediation:** Replace synchronous `pika` with `aio-pika` connection pool or dispatch publishing to `asyncio.to_thread` with a pre-warmed connection pool.

---

### BUG-03: Startup DDL Column Monkeypatch in `research-evaluation-service`
- **Priority:** **P1**
- **Affected Component:** `services/research-evaluation-service/app/main.py`
- **Owner:** Chukwuebuka
- **Symptoms:** Service fails startup with `InternalServerError` if deployed against a read-only database user or replica.
- **Root Cause Analysis:** `_ensure_consistency_columns()` executes raw SQL `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` at container startup instead of using Alembic schema migrations.
- **Reproduction:** Start `research-evaluation-service` with database credentials that lack `ALTER` permissions.
- **Hardening Remediation:** Create initial Alembic revision baseline for `research-evaluation-service` and remove raw DDL from application startup hooks.

---

### BUG-04: Fixed-Window Rate Limiter Boundary-Burst Vulnerability
- **Priority:** **P1**
- **Affected Component:** `services/api-gateway/app/ratelimit.py`
- **Owner:** Olusegun
- **Symptoms:** A client can send $2\times$ the configured rate limit (e.g. 120 requests instead of 60/min) by sending 60 requests at second 59 and 60 requests at second 61.
- **Root Cause Analysis:** Rate limiter calculates Redis bucket as `bucket = int(time.time() // window)`.
- **Reproduction:** Automated script sending bursts at timestamp boundary $T = k \cdot 60 - 1$ and $T = k \cdot 60 + 1$.
- **Hardening Remediation:** Implement Redis sliding-window counter using `ZREMRANGEBYSCORE` and `ZCARD` Lua script.

---

### BUG-05: Missing Audio Format Validation in `voice-service`
- **Priority:** **P1**
- **Affected Component:** `services/voice-service/app/main.py`
- **Owner:** Daniel
- **Symptoms:** Uploading `.webm` or uncompressed `.raw` audio files returns HTTP 500 without a descriptive error payload.
- **Root Cause Analysis:** Endpoint assumes `.wav` PCM format; fails unhandled when passed unsupported container formats from mobile web browsers.
- **Reproduction:** Send POST to `/api/v1/voice/stt` with `audio/webm;codecs=opus` payload.
- **Hardening Remediation:** Add FFmpeg pre-transcoding pipeline and explicit Pydantic/FastAPI MIME-type validation returning `415 Unsupported Media Type` or `422 Unprocessable Entity` with accepted formats list.

---

### BUG-06: Frontend PWA Mock Fallback Leak on Goal Creation
- **Priority:** **P1**
- **Affected Component:** `frontend/lib/api.ts`, `frontend/lib/mockApi.ts`
- **Owner:** Grace
- **Symptoms:** When creating a financial goal during a temporary gateway timeout, the UI silently creates a mock goal in local state without notifying the user that server synchronization failed.
- **Root Cause Analysis:** `catch` block in frontend goal service silently falls back to `mockApi.createGoal()` when `NEXT_PUBLIC_USE_MOCK=false`.
- **Reproduction:** Simulate network drop on `POST /api/v1/goals`; observe goal appearing in UI but not saved to `svc_goals` PostgreSQL.
- **Hardening Remediation:** Remove silent mock fallbacks in production mode; surface explicit retry toast and offline queue banner.

---

### BUG-07: ChromaDB Concurrent Read/Write Contention
- **Priority:** **P2**
- **Affected Component:** `services/rag-corpus-service/app/services/vector_store.py`
- **Owner:** Chukwuebuka
- **Symptoms:** Ingesting new corpus documents while users are querying RAG causes occasional `sqlite3.OperationalError: database is locked`.
- **Root Cause Analysis:** Embedded SQLite backend of ChromaDB has single-writer locking when running within the same process.
- **Reproduction:** Run `ingest_tier1.py` while running concurrent retrieval tests.
- **Hardening Remediation:** Wrap vector additions in retry decorator with jitter and schedule heavy batch ingestions outside active chat traffic windows.

---

### BUG-08: Incomplete W3C Trace Context Propagation
- **Priority:** **P2**
- **Affected Component:** `services/*/app/events.py`
- **Owner:** Chukwuebuka
- **Symptoms:** Asynchronous event consumer traces appear as orphaned roots in Jaeger instead of child spans of the originating HTTP request.
- **Root Cause Analysis:** AMQP headers do not carry OpenTelemetry `traceparent` metadata across `afrimentor.events`.
- **Reproduction:** Trigger a goal completion; inspect Jaeger trace graph for `goals-milestones-service` and `progress-gamification-service`.
- **Hardening Remediation:** Inject OpenTelemetry carrier dictionary into AMQP message properties `headers` during publication, and extract in consumer callback.

---

### BUG-09: Gamification XP Calculation Race Condition
- **Priority:** **P2**
- **Affected Component:** `services/progress-gamification-service/app/services/gamification.py`
- **Owner:** Grace
- **Symptoms:** Rapid duplicate `milestone.completed` events can double-award XP points.
- **Root Cause Analysis:** Consumer lacks idempotent event deduplication check against `event_id` in `svc_progress`.
- **Reproduction:** Publish identical `milestone.completed` event twice with 5ms interval.
- **Hardening Remediation:** Store processed `event_id` in a unique `processed_events` table with database-level uniqueness constraint.

---

### BUG-10: Mobile Safari Virtual Keyboard Layout Shift
- **Priority:** **P3**
- **Affected Component:** `frontend/components/Chat/ChatInput.tsx`
- **Owner:** Grace
- **Symptoms:** On iOS Safari, opening the on-screen keyboard pushes the message header off-screen.
- **Root Cause Analysis:** Missing `interactive-widget=resizes-content` in viewport meta tag.
- **Hardening Remediation:** Update `frontend/app/layout.tsx` viewport configuration.

---

### BUG-11: Stale CORS Headers on Preflight Custom Header
- **Priority:** **P3**
- **Affected Component:** `services/api-gateway/app/main.py`
- **Owner:** Olusegun
- **Symptoms:** Preflight `OPTIONS` requests containing custom debug headers return 400 if header is not explicitly in `allow_headers`.
- **Hardening Remediation:** Include `X-Correlation-Id`, `X-Client-Version`, and `X-Session-Id` in gateway CORS configuration.

---

## 4. Code Freeze Readiness & Verification Checklist

- [x] **P0 Blockers Identified:** BUG-01 and BUG-02 must be patched prior to Sprint 5 code freeze sign-off.
- [x] **P1 Defects Scheduled:** BUG-03, BUG-05, and BUG-06 assigned for Sprint 5 hardening fixes.
- [x] **Regression Test Harness:** Pytest test cases designed for each triaged bug to verify resolution.
- [x] **Sign-off:** Approved by Daniel (Lead SWE) and Olusegun (Product Owner).

