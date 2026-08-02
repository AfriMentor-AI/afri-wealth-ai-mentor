# ADR 0001 — Microservices Architecture & Service Boundaries

- **Status:** Proposed → for review
- **Card:** O1.1 (Sprint 1, 5 pts)
- **Date:** 2026-07-28
- **Author:** Olusegun (Product Owner / Backend)
- **Reviewers:** Daniel (Chat Orchestration), Chukwuebuka (RAG / Evaluation)
- **Depends on:** None
- **Consumed by:** O1.2 (monorepo + compose), O1.3 (gateway + auth), O1.4 (OpenAPI contracts)

---

## 1. Context

AfriMentor AI is a mobile-first African financial-mentorship platform serving low-end
devices across multiple markets, languages and sectors. The product surface spans an
intake/profiling flow, a persona-driven mentor chat backed by RAG, goals & milestones,
gamified progress, an insight library, feedback capture, a research/evaluation console,
and voice interaction.

We need service boundaries that let four engineers (Olusegun, Daniel, Chukwuebuka,
Grace) work in parallel with minimal cross-team blocking, while keeping the operational
footprint small enough to run the whole system with a single `docker-compose up` on a
laptop.

This ADR establishes: (1) the set of services and their boundaries, (2) datastore
strategy, (3) inter-service communication, (4) API Gateway technology, and (5) the
authentication strategy.

## 2. Decision summary

| # | Decision area | Choice |
|---|---|---|
| D1 | Service decomposition | 13 services, decomposed by **business capability** (bounded context), not by layer |
| D2 | Datastore strategy | **Database-per-service** logically; one Postgres instance with a schema/database per service in dev; Redis shared for cache/rate-limit; ChromaDB for vectors |
| D3 | Communication | **Sync REST** for request/response (via gateway); **async event bus (RabbitMQ)** for domain events |
| D4 | API Gateway | **Custom FastAPI gateway** for v1 (routing, JWT verification, rate limiting); revisit Kong/Traefik at scale |
| D5 | Auth strategy | **JWT access + refresh tokens**, RS256 asymmetric; gateway verifies with public key; services trust gateway-forwarded identity headers |

## 3. Service catalogue (13 services)

Decomposition principle: **one service per bounded context**, owning its own data and
exposing a versioned REST API. A service may publish/subscribe to domain events but
never reaches into another service's datastore.

| # | Service | Bounded context / responsibility | Owner |
|---|---|---|---|
| 1 | **api-gateway** | Single ingress. Routing, JWT verification, rate limiting, request/identity forwarding | Olusegun |
| 2 | **auth-user-service** | Signup/login, JWT issue+refresh, user profile (name, age, country, device, sector, education, language, income) | Olusegun |
| 3 | **intake-profiling-service** | Guided intake flow, sector/goal questions, builds the initial user profile & financial context | Olusegun |
| 4 | **chat-orchestration-service** | Orchestrates a mentor turn: assembles persona + RAG context + history, calls LLM, streams reply | Daniel |
| 5 | **persona-prompt-service** | Persona catalogue, archetype selection, system-prompt templating | Daniel |
| 6 | **rag-corpus-service** | Corpus ingestion, chunking, embedding, vector retrieval | Chukwuebuka |
| 7 | **goals-milestones-service** | Goals & milestones CRUD, milestone state machine, publishes `goal.*`/`milestone.*` events | Olusegun |
| 8 | **progress-gamification-service** | XP, streaks, badges, levels; reacts to milestone/session events | Grace |
| 9 | **insight-library-service** | Curated insight articles/cards, categories, bookmarks | Grace |
| 10 | **feedback-service** | Post-session surveys, thumbs, free-text feedback capture | Grace |
| 11 | **research-evaluation-service** | Session auditing, quality scoring, drift detection, research console data | Chukwuebuka |
| 12 | **voice-service** | STT/TTS, audio upload handling, transcription for chat | Daniel |
| 13 | **notification-service** | Push/in-app/email notifications, reacts to domain events | Grace |

## 4. D1 — Decomposition rationale

- **By capability, not layer.** Each team owns end-to-end vertical slices, reducing
  cross-team coupling. Daniel owns the chat path (chat-orchestration, persona-prompt,
  voice); Chukwuebuka owns knowledge & evaluation (rag-corpus, research-evaluation);
  Grace owns engagement (progress-gamification, insight-library, feedback,
  notification); Olusegun owns the platform spine (gateway, auth, intake,
  goals-milestones).
- **Chat orchestration is a separate service from persona and RAG** so the hot,
  latency-sensitive path can scale and be deployed independently of the corpus indexing
  workload.
- **research-evaluation-service is read-mostly** and consumes events + session logs; it
  never sits on the request path so audits/drift detection cannot slow the mentor.

## 5. D2 — Datastore strategy

**Decision: logical database-per-service.**

- Each service owns a **dedicated Postgres database** (`svc_auth`, `svc_intake`,
  `svc_goals`, …). In dev they live in a single Postgres container to save resources;
  in prod they can move to separate instances without code change. No service reads
  another service's tables — cross-service data is obtained via API or events.
- **Redis** (shared) — gateway rate-limit counters, session/refresh-token cache, hot
  read caches. Keys namespaced per service (`svc:auth:*`).
- **ChromaDB** (vector store) — owned exclusively by rag-corpus-service for embeddings.
- **Object/audio storage** — local volume in dev (voice-service), S3-compatible in prod.

Datastore ownership table:

| Service | Primary store | Notes |
|---|---|---|
| auth-user-service | Postgres `svc_auth` | users, credentials, refresh tokens |
| intake-profiling-service | Postgres `svc_intake` | intake sessions, answers |
| chat-orchestration-service | Postgres `svc_chat` | conversations, messages |
| persona-prompt-service | Postgres `svc_persona` | personas, prompt templates |
| rag-corpus-service | Postgres `svc_rag` + **ChromaDB** | doc metadata + vectors |
| goals-milestones-service | Postgres `svc_goals` | goals, milestones |
| progress-gamification-service | Postgres `svc_progress` | xp, streaks, badges |
| insight-library-service | Postgres `svc_insight` | articles, bookmarks |
| feedback-service | Postgres `svc_feedback` | surveys, responses |
| research-evaluation-service | Postgres `svc_research` | audits, scores, drift |
| voice-service | Postgres `svc_voice` + object store | audio metadata + files |
| notification-service | Postgres `svc_notify` | notifications, delivery log |
| api-gateway | (stateless) + Redis | no owned DB; Redis for rate limits |

**Rejected:** single shared database. Rejected because it re-couples teams at the schema
level and defeats independent deploy/scale — the primary reason we are going
microservices.

## 6. D3 — Communication

**Decision: sync REST for queries/commands, async events (RabbitMQ) for facts.**

- **Synchronous REST/JSON** for anything the caller needs an answer to now (client →
  gateway → service; occasional service → service such as chat-orchestration →
  persona-prompt and → rag-corpus). Timeouts + retries with backoff; no unbounded fan-out.
- **Asynchronous domain events** over **RabbitMQ** (topic exchange `afrimentor.events`)
  for state facts other contexts react to. Chosen over Kafka for v1: lower operational
  weight, simpler local dev, adequate throughput; migration path to Kafka exists if
  ordering/replay at scale demands it.

Event catalogue (v1):

| Event | Published by | Consumed by |
|---|---|---|
| `user.registered` | auth-user-service | intake-profiling, notification |
| `intake.completed` | intake-profiling-service | persona-prompt, goals-milestones |
| `goal.created` | goals-milestones-service | progress-gamification, notification |
| `milestone.completed` | goals-milestones-service | progress-gamification, notification, research-evaluation |
| `session.completed` | chat-orchestration-service | feedback, research-evaluation, progress-gamification |
| `session.audited` | research-evaluation-service | notification (internal/admin) |
| `drift.detected` | research-evaluation-service | notification (internal/admin), persona-prompt |
| `feedback.submitted` | feedback-service | research-evaluation |

Events are JSON with a common envelope: `{ event, version, id, occurredAt, actor, data }`.

## 7. D4 — API Gateway

**Decision: custom FastAPI gateway for v1.**

- Responsibilities: routing table (path → upstream service), JWT signature/expiry
  verification (public key), per-route rate limiting (Redis token bucket), and forwarding
  a trusted identity header (`X-User-Id`, `X-User-Roles`) to upstreams.
- Rationale: keeps the whole stack in one language (Python/FastAPI) for a 4-person team,
  zero new runtime to learn, trivial local dev, and full control over JWT/identity
  forwarding semantics.
- **Rejected for v1:** Kong / Traefik. More capable (plugins, native rate-limit) but add
  operational surface and config learning cost not justified at current scale.
  **Revisit** when we need declarative plugins, canary routing, or >1 gateway replica —
  the routing table is kept as data (`routes.py`) so a migration is mechanical.

## 8. D5 — Authentication

**Decision: JWT access + refresh, RS256, gateway-verified.**

- auth-user-service **issues** a short-lived access token (15 min) and a long-lived
  refresh token (30 days). Signed with **RS256** (private key in auth-service only).
- **Gateway verifies** every request to a protected route using the **public key**;
  unauthenticated/expired requests are rejected at the edge (401) and never reach
  upstreams. Public routes (`/auth/*`, health) are allow-listed.
- Gateway injects `X-User-Id` / `X-User-Roles` from verified claims; **upstream services
  trust these headers because only the gateway is network-reachable** (services are on an
  internal network, not exposed).
- Refresh tokens are stored server-side (Redis + Postgres) to support revocation/logout;
  `/auth/refresh` rotates them.
- **mTLS** between gateway and services is **deferred** to a later hardening ADR — in dev
  the internal Docker network provides isolation; mTLS is the prod follow-up.

## 9. Per-service tech stack

Default stack unless noted: **Python 3.12 + FastAPI + SQLAlchemy + Alembic + Pydantic v2**,
**Postgres 16**, packaged as a Docker image, tested with **pytest**.

| Service | Language / Framework | Datastore | Extra |
|---|---|---|---|
| api-gateway | Python 3.12 / FastAPI + httpx | Redis | JWT (pyjwt), token-bucket rate limit |
| auth-user-service | Python 3.12 / FastAPI | Postgres + Redis | passlib/bcrypt, pyjwt (RS256) |
| intake-profiling-service | Python 3.12 / FastAPI | Postgres | — |
| chat-orchestration-service | Python 3.12 / FastAPI | Postgres | openai, httpx, SSE streaming |
| persona-prompt-service | Python 3.12 / FastAPI | Postgres | Jinja2 prompt templates |
| rag-corpus-service | Python 3.12 / FastAPI | Postgres + ChromaDB | langchain, chromadb, embeddings |
| goals-milestones-service | Python 3.12 / FastAPI | Postgres | RabbitMQ publisher |
| progress-gamification-service | Python 3.12 / FastAPI | Postgres | RabbitMQ consumer |
| insight-library-service | Python 3.12 / FastAPI | Postgres | — |
| feedback-service | Python 3.12 / FastAPI | Postgres | RabbitMQ pub/sub |
| research-evaluation-service | Python 3.12 / FastAPI | Postgres | RabbitMQ consumer, scoring |
| voice-service | Python 3.12 / FastAPI | Postgres + object store | python-multipart, pydub |
| notification-service | Python 3.12 / FastAPI | Postgres | RabbitMQ consumer |
| **frontend** (app) | TypeScript / Next.js 16 + React 19 + Tailwind v4 | — | mobile-first, PWA |
| **admin-console** (app) | TypeScript / Next.js 16 | — | research + RAG admin |

Shared infra: **Postgres 16**, **Redis 7**, **RabbitMQ 3**, **ChromaDB**.

## 10. Service boundary diagram

```
                                   ┌─────────────────────────────┐
        Frontend (Next.js)  ─────► │        api-gateway          │
        Admin Console       ─────► │  routing · JWT verify ·     │
                                   │  rate limit · identity fwd  │
                                   └──────────────┬──────────────┘
                                                  │ REST (+ X-User-Id)
        ┌───────────────┬───────────────┬────────┼────────┬───────────────┬───────────────┐
        ▼               ▼               ▼        ▼        ▼               ▼               ▼
 ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
 │ auth-user  │ │  intake    │ │   chat     │ │ persona  │ │ rag-corpus │ │  goals     │ │ progress   │
 │ svc_auth   │ │ svc_intake │ │ svc_chat   │ │svc_persona│ │svc_rag +   │ │ svc_goals  │ │svc_progress│
 │ +Redis     │ │            │ │            │ │          │ │ ChromaDB   │ │            │ │            │
 └─────┬──────┘ └─────┬──────┘ └──┬─────┬───┘ └────▲─────┘ └─────▲──────┘ └─────┬──────┘ └────▲───────┘
       │              │           │     │          │             │              │             │
       │        ┌─────────────┐   │     └── REST ──┘      REST ──┘              │             │
       │        │   voice     │   │  (persona + rag lookups by chat)           │             │
       │        │ svc_voice   │◄──┘                                            │             │
       │        └─────────────┘                                                │             │
       │                                                                       │             │
 ┌─────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────────┐           │             │
 │  insight    │ │ feedback   │ │ research-  │ │  notification    │           │             │
 │ svc_insight │ │svc_feedback│ │ evaluation │ │  svc_notify      │           │             │
 │             │ │            │ │ svc_research│ │                  │           │             │
 └─────────────┘ └─────┬──────┘ └────▲───┬───┘ └────────▲─────────┘           │             │
                       │             │   │              │                     │             │
                       │             │   │              │                     │             │
        ═══════════════╧═════════════╧═══╧══════════════╧═════════════════════╧═════════════╧═══
                       RabbitMQ  topic exchange  "afrimentor.events"
        events: user.registered · intake.completed · goal.created · milestone.completed ·
                session.completed · session.audited · drift.detected · feedback.submitted

  Legend:  ───►  synchronous REST      ═══  asynchronous events (RabbitMQ)
           Each box = one service + its OWNED datastore (no cross-service DB access).
```

## 11. Consequences

**Positive:** parallel team ownership; independent deploy/scale of the chat hot path;
small local footprint (one compose file); clear data ownership; mechanical path to
Kong/Kafka/mTLS later.

**Negative / trade-offs:** more moving parts than a monolith; eventual consistency across
services via events; trusted-header auth requires strict network isolation (services must
never be publicly reachable); operating RabbitMQ + Chroma + Postgres + Redis in dev.

**Follow-up ADRs:** 0002 mTLS & service-to-service auth hardening; 0003 Kafka migration
criteria; 0004 multi-region data residency per market.

## 12. Sign-off

| Reviewer | Role | Status |
|---|---|---|
| Daniel | Chat Orchestration | ☐ pending |
| Chukwuebuka | RAG / Evaluation | ☐ pending |
