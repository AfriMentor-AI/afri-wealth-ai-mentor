# Technical Debt Log & Remediation Matrix — Sprint 5 Hardening & Phase 2

- **Document Version:** 1.0.0
- **Service / Area:** Engineering Leadership
- **Date:** 2026-08-27
- **Authors:** Daniel (Lead Software Engineer / Conversational Systems), Olusegun (Product Owner / Platform Spine & Infrastructure)
- **Status:** Published & Approved Baseline
- **Related Documents:**
  - [System Architecture](architecture/system-architecture.md)
  - [Service Ownership & Governance](governance/service-ownership.md)
  - [Bug Backlog & Triage Report](bug-triage-backlog.md)
  - [Sprint 5 Hardening Architecture Review](architecture/sprint-5-hardening-architecture-review.md)

---

## 1. Technical Debt Management Framework

Technical debt items are categorized by architectural tier, scored with Fibonacci story points (1, 2, 3, 5, 8, 13), assigned to domain leads, and triaged using standard priority ratings (**P0, P1, P2, P3**):

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                               TECH DEBT PRIORITY RUBRIC                                 │
├──────────┬─────────────────────────────┬────────────────────────────────────────────────┤
│ Priority │ Category                    │ Criteria & Action                              │
├──────────┼─────────────────────────────┼────────────────────────────────────────────────┤
│ **P0**   │ Architectural Bottleneck    │ High-concurrency or data integrity blocker.    │
│          │ / Immediate Stability       │ Must resolve in Sprint 5 / Sprint 6 hardening. │
├──────────┼─────────────────────────────┼────────────────────────────────────────────────┤
│ **P1**   │ Scalability & Testing Debt  │ Core subsystem limitation (pooler, voice,      │
│          │                             │ rate limiter, contract tests). Target Sprint 7.│
├──────────┼─────────────────────────────┼───────────────────────────┬────────────────────┤
│ **P2**   │ Performance & Observability │ L2 cache, distributed tracing, secrets vault,   │
│          │ Debt                        │ admin audit UI. Target Sprint 8.               │
├──────────┼─────────────────────────────┼────────────────────────────────────────────────┤
│ **P3**   │ Developer Experience &      │ Monorepo build acceleration, PWA offline sync, │
│          │ Client Optimization         │ mobile bundle hardening. Target Sprint 9.      │
└──────────┴─────────────────────────────┴────────────────────────────────────────────────┘
```

---

## 2. Comprehensive Technical Debt Registry

| ID | Title | Priority | Category | Est (pts) | Primary Owner | Target Sprint | Impacted Services / Components |
|---|---|---|---|---|---|---|---|
| **TD-01** | Universal Alembic Migration Harness | **P0** | Database / SRE | 8 | Olusegun | Sprint 6 | 10 Microservices (Intake, Goals, Progress, Library, Feedback, Persona, Notification, Research, Voice) |
| **TD-02** | Async AMQP Event Bus with `aio-pika` & DLQ | **P0** | Messaging / Perf | 5 | Daniel | Sprint 6 | Chat, Goals, Progress, Feedback, Research, Notification, Shared Lib |
| **TD-03** | API Gateway Connection Pool & Proxy Modernization | **P0** | Gateway / Ingress | 5 | Olusegun | Sprint 5/6 | `services/api-gateway` |
| **TD-04** | Full End-to-End PWA Frontend Integration | **P0** | Frontend / UX | 8 | Grace | Sprint 6 | `frontend/` (Intake, Goals, Milestones, Gamification, Library) |
| **TD-05** | Voice Service Async Engine & African Dialect STT/TTS | **P1** | AI / Voice | 8 | Daniel | Sprint 7 | `services/voice-service`, `frontend/` |
| **TD-06** | Dedicated PgBouncer Connection Pooler Deployment | **P1** | Infrastructure | 5 | Olusegun | Sprint 7 | PostgreSQL, Infrastructure, Staging/Prod Compose |
| **TD-07** | Distributed Sliding-Window Rate Limiter & Redis Cluster | **P1** | Gateway / Sec | 3 | Olusegun | Sprint 7 | `services/api-gateway`, Redis |
| **TD-08** | Automated OpenAPI Contract Testing in CI (Pact/Dredd) | **P1** | Testing / QA | 5 | Chukwuebuka | Sprint 7 | CI/CD Pipeline, All 13 Microservices |
| **TD-09** | Distributed Redis L2 Caching for RAG & Persona Systems | **P2** | Performance | 5 | Chukwuebuka | Sprint 8 | `chat-orchestration-service`, `rag-corpus-service`, `persona-prompt-service` |
| **TD-10** | End-to-End W3C TraceContext Distributed Tracing | **P2** | Observability | 5 | Chukwuebuka | Sprint 8 | All 13 Services, RabbitMQ Consumers, OpenTelemetry, Jaeger |
| **TD-11** | Automated Secret Rotation & Vault/KMS Key Management | **P2** | Security | 5 | Olusegun | Sprint 8 | `auth-user-service`, `api-gateway`, Deployment Scripts |
| **TD-12** | Admin Console Drift Auditing & Corpus Annotation UI | **P2** | Admin / Research | 5 | Grace / Ebuka | Sprint 8 | `apps/admin-research-console`, `research-evaluation-service` |
| **TD-13** | PWA Offline Sync & Background IndexedDB Replay | **P3** | Frontend / PWA | 5 | Grace | Sprint 9 | `frontend/` (Service Worker, IndexedDB Sync Queue) |
| **TD-14** | Turborepo Monorepo & Multi-Service Build Acceleration | **P3** | Developer Exp | 3 | Olusegun | Sprint 9 | Monorepo Root, Docker BuildKit, GitHub Actions |
| **TD-15** | Mobile Performance & Low-End Android Bundle Hardening | **P3** | Frontend / Perf | 3 | Grace | Sprint 9 | `frontend/`, Lighthouse CI, Webpack/Next.js Bundler |

---

## 3. Detailed Technical Debt Specifications & Acceptance Criteria

### TD-01: Universal Alembic Migration Harness for Remaining 10 Microservices
- **Priority:** **P0**
- **Points:** 8
- **Owner:** Olusegun (Platform & DB)
- **Technical Context:** 10 microservices currently rely on `Base.metadata.create_all()` and ad-hoc runtime monkeypatches (e.g. `_ensure_consistency_columns`), making schema evolution and rollback impossible without manual SQL scripts.
- **Acceptance Criteria:**
  1. Standard `alembic.ini` and `env.py` configured for all 10 microservices.
  2. Initial baseline migration files (`0001_initial_schema.py`) generated and verified against test SQLite/Postgres.
  3. `alembic upgrade head` integrated into service container entrypoints.
  4. CI automated migration upgrade/downgrade test harness passing on PRs.

---

### TD-02: Asynchronous AMQP Event Bus with `aio-pika`, Connection Pooling & DLQ
- **Priority:** **P0**
- **Points:** 5
- **Owner:** Daniel (Conversational Systems & Backend)
- **Technical Context:** Services currently instantiate synchronous `pika.BlockingConnection` instances per event, blocking the async event loop during message dispatch.
- **Acceptance Criteria:**
  1. Replace synchronous `pika` publishers with pooled `aio-pika.RobustConnection`.
  2. Declare and route failed events to Dead-Letter Exchanges (`afrimentor.dlx`) and DLQs after 3 retry attempts with exponential backoff.
  3. Propagate W3C `traceparent` headers across all published event envelopes.
  4. Benchmark 1,000 concurrent event publications without event loop latency spikes.

---

### TD-03: API Gateway HTTP Client Connection Pooling & Proxy Modernization
- **Priority:** **P0**
- **Points:** 5
- **Owner:** Olusegun (Ingress & Gateway)
- **Technical Context:** `services/api-gateway/app/main.py` creates a new `httpx.AsyncClient` on every incoming request, leading to socket exhaustion under load.
- **Acceptance Criteria:**
  1. Singleton `httpx.AsyncClient` lifecycle managed via FastAPI `@asynccontextmanager` lifespan.
  2. Connection pooling configured with `max_connections=500` and `max_keepalive_connections=100`.
  3. Generic chunked/SSE proxying for all upstream streaming endpoints.
  4. Dynamic CORS origins configured via environment variables.

---

### TD-04: Full End-to-End PWA Frontend API Integration
- **Priority:** **P0**
- **Points:** 8
- **Owner:** Grace (Frontend Lead)
- **Technical Context:** Intake, Goals, Milestones, Gamification, and Insights screens still rely heavily on `frontend/lib/mockApi.ts`.
- **Acceptance Criteria:**
  1. 100% of PWA user flows wired to the live API Gateway (`/api/v1/*`).
  2. Zero imports of `mockApi.ts` in production builds (`NEXT_PUBLIC_USE_MOCK=false`).
  3. SWR/React Query caching with optimistic updates implemented for goals and gamification XP.
  4. End-to-end integration tests passing against live microservices.

---

### TD-05: Voice Service Async Engine & African Dialect STT/TTS
- **Priority:** **P1**
- **Points:** 8
- **Owner:** Daniel (AI & Voice)
- **Technical Context:** `services/voice-service` is a synchronous prototype using Google Speech Recognition and gTTS, lacking West African accent support and background worker queues.
- **Acceptance Criteria:**
  1. Integrate Whisper STT fine-tuned on African accented English, Nigerian Pidgin, and Swahili.
  2. Asynchronous task execution via Celery/Redis for audio transcode and inference.
  3. Audio streaming via WebSocket/SSE with p95 round-trip latency $< 2.5\text{s}$.

---

### TD-06: Dedicated PgBouncer Connection Pooler Deployment
- **Priority:** **P1**
- **Points:** 5
- **Owner:** Olusegun (Infrastructure & SRE)
- **Technical Context:** Microservice connection pools consume excessive PostgreSQL backend processes under concurrent load.
- **Acceptance Criteria:**
  1. Deploy PgBouncer in transaction pooling mode in `docker-compose.yml` and staging environments.
  2. Restrict total native PostgreSQL backend connections to $< 50$ under 500 concurrent client simulations.
  3. Export PgBouncer pool metrics to Prometheus.

---

### TD-07: Distributed Sliding-Window Rate Limiter & Redis Cluster
- **Priority:** **P1**
- **Points:** 3
- **Owner:** Olusegun (Gateway & Security)
- **Acceptance Criteria:**
  1. Lua-scripted sliding window log in Redis replacing fixed-window buckets.
  2. Standardized `RateLimit-*` response headers conforming to IETF drafts.
  3. Tiered limits based on JWT roles (`anonymous`, `user`, `admin`).

---

### TD-08: Automated OpenAPI Contract Testing in CI (Pact / Dredd)
- **Priority:** **P1**
- **Points:** 5
- **Owner:** Chukwuebuka (QA & Evaluation)
- **Acceptance Criteria:**
  1. Automated Schemathesis/Dredd contract verification added to GitHub Actions workflow.
  2. 100% of endpoints in `docs/api/*.yaml` verified against live FastAPI response schemas.
  3. Automatic build failure on breaking contract drift.

---

### TD-09 to TD-15: Medium & Long-Term Roadmap Items (P2 / P3)
- **TD-09 (P2, 5 pts, Ebuka):** Multi-tier Redis L2 caching with AMQP event-driven cache invalidation.
- **TD-10 (P2, 5 pts, Ebuka):** End-to-end W3C OpenTelemetry distributed tracing across HTTP and AMQP.
- **TD-11 (P2, 5 pts, Olusegun):** Vault/KMS automated RS256 JWT key rotation and secret management.
- **TD-12 (P2, 5 pts, Grace/Ebuka):** Admin Research Console persona drift review & qualitative scoring UI.
- **TD-13 (P3, 5 pts, Grace):** PWA offline IndexedDB transaction sync queue and background replay.
- **TD-14 (P3, 3 pts, Olusegun):** Turborepo and multi-stage Docker BuildKit caching to reduce CI build times by $\ge 60\%$.
- **TD-15 (P3, 3 pts, Grace):** Low-end Android bundle optimization with initial JS size $< 120\text{KB}$ gzipped.

---

## 4. Engineering Capacity Allocation

```
Sprint 5 Hardening Capacity Allocation:
├── Critical Bug Remediation (P0/P1): 30% (BUG-01, BUG-02, BUG-05)
├── Hardening Tech Debt (TD-03, mTLS, Tracing): 40%
└── Feature Finalization (Feedback & Eval): 30%
```

