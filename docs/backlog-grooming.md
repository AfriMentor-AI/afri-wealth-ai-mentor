# Backlog Grooming — Sprint 2 commitment & Sprint 3–5 dependency risks (card O1.5)

- **Card:** O1.5 (Sprint 1, 2 pts)
- **Date:** 2026-07-28
- **Facilitator:** Olusegun (Product Owner)
- **Attendees / sign-off:** Olusegun, Daniel, Chukwuebuka, Grace
- **Inputs:** [ADR-0001](adr/0001-microservices-architecture.md) service catalogue, the
  Stitch design screens, and the Sprint-1 deliverables (gateway + auth live, 13 OpenAPI
  contracts).

Estimates use a Fibonacci story-point scale (1, 2, 3, 5, 8, 13). Team velocity is
assumed at ~24 pts/sprint across four engineers until we have two sprints of actuals.

---

## 1. Roadmap at a glance

| Sprint | Theme | Primary services / apps |
|--------|-------|--------------------------|
| 1 ✅ | Platform foundation | api-gateway, auth-user-service, monorepo, CI, OpenAPI |
| 2 | Onboarding & mentor shell | intake-profiling, persona-prompt, chat (shell), frontend intake, admin-console scaffold |
| 3 | Knowledge & live mentor | rag-corpus, chat-orchestration (LLM+RAG), voice |
| 4 | Goals & engagement | goals-milestones, progress-gamification, insight-library |
| 5 | Feedback, research & hardening | feedback, research-evaluation, notification, mTLS/observability |

---

## 2. Sprint 2 — committed backlog (confirmed by all four members)

**Sprint goal:** a user can complete the intake flow, be matched to a persona, and open
a (non-AI) mentor chat shell — end to end through the gateway, on the mobile frontend.

| ID | Story | Assignee | Est | Depends on |
|----|-------|----------|-----|------------|
| S2.1 | intake-profiling-service v1: session + answers + complete, persists profile, emits `intake.completed` | Olusegun | 5 | O1.3 auth, O1.1 events |
| S2.2 | persona-prompt-service v1: persona catalogue + archetype selection + `/personas/select` | Daniel | 5 | O1.4 contract |
| S2.3 | chat-orchestration-service **shell**: session + message store, canned reply (no LLM yet) | Daniel | 3 | S2.2 |
| S2.4 | Frontend: splash → intake chat flow (sector question screen) wired to gateway | Grace | 5 | S2.1, AGENTS.md Next.js docs |
| S2.5 | Frontend: persona selection screen wired to persona-prompt | Grace | 3 | S2.2, S2.4 |
| S2.6 | admin-console app scaffold (Next.js) + auth login | Olusegun | 3 | O1.3 |
| S2.7 | Shared event bus library: publish/consume helpers for RabbitMQ envelope | Chukwuebuka | 3 | O1.1 |
| S2.8 | Physical monorepo move: `/frontend` → `/apps/frontend`, add `/apps/admin-console` | Olusegun | 2 | O1.2 |

**Committed total: 29 pts.** Slightly above nominal velocity; S2.6 is the drop-candidate
if burn-down slips at mid-sprint review.

**Definition of Ready confirmed:** each story has an OpenAPI contract (O1.4), an owner,
and no unresolved external blocker.

---

## 3. Sprint 3–5 provisional scope

### Sprint 3 — Knowledge & live mentor
| ID | Story | Owner | Est |
|----|-------|-------|-----|
| S3.1 | rag-corpus-service: ingest → chunk → embed → store (ChromaDB) | Chukwuebuka | 8 |
| S3.2 | rag-corpus-service: `/rag/query` retrieval API | Chukwuebuka | 5 |
| S3.3 | chat-orchestration: assemble persona+RAG+history, call LLM, stream reply | Daniel | 8 |
| S3.4 | voice-service: STT transcribe + TTS synthesize v1 | Daniel | 5 |
| S3.5 | Frontend: live mentor chat screen + voice input | Grace | 5 |

### Sprint 4 — Goals & engagement
| ID | Story | Owner | Est |
|----|-------|-------|-----|
| S4.1 | goals-milestones-service: CRUD + milestone state machine, emit `goal.*`/`milestone.*` | Olusegun | 8 |
| S4.2 | progress-gamification-service: consume events → XP/streaks/badges | Grace | 8 |
| S4.3 | insight-library-service: articles + categories + bookmarks | Grace | 5 |
| S4.4 | Frontend: goals dashboard, milestone path, progress board | Grace/Olusegun | 8 |

### Sprint 5 — Feedback, research & hardening
| ID | Story | Owner | Est |
|----|-------|-------|-----|
| S5.1 | feedback-service: surveys + submission, emit `feedback.submitted` | Grace | 5 |
| S5.2 | research-evaluation-service: session audit + quality scoring | Chukwuebuka | 8 |
| S5.3 | research-evaluation-service: drift detection + `drift.detected` | Chukwuebuka | 5 |
| S5.4 | notification-service: consume events → in-app/push notifications | Grace | 5 |
| S5.5 | Hardening: mTLS gateway↔services (ADR-0002), observability/tracing | Olusegun | 8 |

---

## 4. Dependency risk log (Sprints 3–5)

| # | Risk | Sprint | Likelihood | Impact | Mitigation |
|---|------|--------|------------|--------|------------|
| R1 | **LLM provider latency/cost/quota** blocks chat-orchestration (S3.3) | 3 | Med | High | Abstract behind a provider interface; add response caching + timeouts; load-test early; keep the S2.3 canned-reply path as a fallback flag |
| R2 | **Embedding model choice churns** the vector schema after ingestion (S3.1/S3.2) | 3 | Med | High | Freeze the embedding model + dimensions in an ADR before S3.1; store model id per vector; write a re-index job so a model swap is recoverable |
| R3 | **RAG → chat contract drift**: chat depends on `/rag/query` shape (S3.3 ⟵ S3.2) | 3 | Med | Med | Lock the query/response contract in O1.4 YAML first; Daniel + Chukwuebuka sign off before either starts; contract test in CI |
| R4 | **Voice on low-end devices**: audio upload size/format + STT accuracy for accents (S3.4) | 3 | High | Med | Constrain to short clips + compressed formats; cap upload size at the gateway; pilot with target-market audio samples; graceful text fallback |
| R5 | **Event-bus reliability**: progress/gamification correctness depends on not losing `milestone.completed` (S4.2 ⟵ S4.1) | 4 | Med | High | Durable queues + consumer acks + dead-letter queue; idempotent consumers keyed on event id; replay tooling |
| R6 | **Eventual-consistency UX**: gamification updates lag the goal action, confusing users (S4.2/S4.4) | 4 | Med | Med | Optimistic UI on the goal action; reconcile on event arrival; show a subtle "syncing" state per design system |
| R7 | **Frontend depends on the customised Next.js** (`AGENTS.md`) — unknown breaking changes slow every UI story (S2.4+, S3.5, S4.4) | 2–4 | High | Med | Budget a Sprint-2 spike to read `node_modules/next/dist/docs/`; capture gotchas in a frontend README; pair on the first screen |
| R8 | **Research/eval needs labelled data**: drift detection (S5.3) has no baseline until enough sessions exist | 5 | High | Med | Start logging session traces from Sprint 3 (S3.3) so a corpus accrues; define drift metrics in Sprint 4; seed with synthetic sessions if volume is low |
| R9 | **mTLS rollout breaks local dev / compose** (S5.5) | 5 | Med | Med | Make mTLS env-gated (off by default in dev); document cert-gen in `infra/`; roll out service-by-service behind the gateway |
| R10 | **Monorepo move churn** (S2.8) breaks CI paths / imports for in-flight branches | 2 | Med | Low | Do the move at sprint start on a quiet branch; update CI path filters in the same PR; announce a short merge freeze |
| R11 | **Notification provider (push/email) integration** external account & keys not provisioned (S5.4) | 5 | Med | Low | Provision provider accounts in Sprint 4; abstract behind a notifier interface; in-app notifications ship first, external channels behind a flag |

**Cross-cutting mitigation:** every inter-service dependency must have its OpenAPI/event
contract merged and signed off **one sprint before** the consuming story starts (extends
the O1.4 discipline). Contract tests in CI guard against silent drift.

---

## 5. Decisions & actions

- ✅ Sprint 2 backlog (29 pts) committed by Olusegun, Daniel, Chukwuebuka, Grace.
- ⏩ **Action (Olusegun):** raise ADR-0002 (mTLS) and an embedding-model ADR before Sprint 3.
- ⏩ **Action (Daniel + Chukwuebuka):** finalise the `/rag/query` contract in `docs/api`
  before Sprint 3 planning (mitigates R3).
- ⏩ **Action (Grace):** Sprint-2 spike on the customised Next.js; publish gotchas (R7).
- ⏩ **Action (Chukwuebuka):** begin session-trace logging in S3.3 to seed eval data (R8).

## 6. Sign-off

| Member | Role | Sprint 2 commit | Risk log reviewed |
|--------|------|-----------------|-------------------|
| Olusegun | PO / Backend | ☐ | ☐ |
| Daniel | Chat | ☐ | ☐ |
| Chukwuebuka | RAG / Eval | ☐ | ☐ |
| Grace | Frontend | ☐ | ☐ |
