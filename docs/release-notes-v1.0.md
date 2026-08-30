# AfriMentor AI — Release Notes v1.0

**Release date:** 2026-08-30
**Scope:** MVP delivered across 5 sprints (2026-07-27 → 2026-08-30), compiled from the real commit and PR history on `develop` (137 merged PRs at time of writing). This is what actually shipped, not the original sprint plan — see [`mvp-scope-closure-report.md`](mvp-scope-closure-report.md) for the plan-vs-delivered diff, including the items that did **not** ship.

---

## Sprint 1 — Foundation, Frontend MVP & Architecture (2026-07-27 – 2026-08-02)

- Microservices Architecture Decision Record: 13 independently deployable services behind a single `api-gateway`, per-service Postgres, JWT auth, RabbitMQ event bus.
- Monorepo, Docker Compose dev environment (13 service stubs + Postgres/Redis/ChromaDB), and CI/CD (GitHub Actions: lint → test → build per service).
- API Gateway skeleton + Auth & User Service v1 (signup/login/refresh, JWT).
- OpenAPI contracts drafted for all 13 services; Redocly docs site.
- Full frontend PWA scaffolded from the Stitch design export — all 11 screens (Splash, Intake, Persona Selection, Chat, Daily Action, Goals, Progress, Insight Library, Feedback), mobile-first with desktop breakpoints, mock data layer.
- "Heritage-Forward" design system: Tailwind theme, light/dark mode, reusable component primitives.
- Shared TypeScript/OpenAPI frontend-backend contract.
- RAG Corpus Service skeleton; first 5 Tier-1 documents ingested (TEF curriculum, Dangote case studies, SMEDAN, AfDB).
- Personality-consistency metric suite v0 (trait-fit + behavioral-consistency scoring); CHIOMA target Big Five profile published as a machine-readable spec.
- Base LLM hosting decision; 6 persona prompt templates drafted (CHIOMA + 5 mentors).
- Research paper repo, outline, Introduction and Related Work drafts started.

## Sprint 2 — Core Services Live, RAG v1 & Related Work (2026-08-03 – 2026-08-09)

- Auth & User Service v1 fully implemented (profile CRUD, password reset, Alembic migrations) and staging-deployed.
- Intake & Profiling Service v1 (4-step diagnostic profile).
- Goals & Milestones Service v1 — full CRUD + status-transition state machine.
- Goals/Intake screens wired to live APIs (mock layer removed for these three screens).
- Observability stack stood up: Prometheus, Grafana, Loki, Promtail, Jaeger.
- RAG Corpus Service v1: hybrid BM25 + dense retrieval with reciprocal-rank-fusion and cross-encoder reranking; RAG Corpus Admin backend endpoints (document index, upload, CSV export, stats).
- RAG retrieval + citation formatting wired into Chat Orchestration; persona selection & session binding; commitment-tagging pipeline (chat → Goals event).
- Alignment condition #1 (baseline persona prompting) implemented and evaluated.
- Guardrails module v1: high-risk-advice filter + auto-disclaimers, plus an output-only AI-disclosure category.
- Trait-level fit metric computed end-to-end against the CHIOMA target profile.
- Branch protection, review SLAs, and Alembic adopted as the schema-migration standard for chat-orchestration-service.
- Pilot data-collection plan drafted (eligibility, consent, pre/post survey instrument).

## Sprint 3 — Chat Goes Live, Voice, Insight Library, Pilot Launch (2026-08-10 – 2026-08-16)

- Chat Orchestration Service v1 live end-to-end (message → RAG retrieval → persona-prompted LLM call → response + citation), wired to the real Chat screen.
- Progress & Gamification, Insight Library, Feedback, and Notification (v0) services all implemented.
- Voice Service integration: speech-to-text for chat/intake input, text-to-speech for persona previews.
- Daily Action generation job (scheduled, per-user, goal-aware).
- Security hardening pass: 2 IDOR/authorization gaps fixed, a leaked key rotated.
- Alignment condition #2 (supervised persona fine-tuning) and condition #3 (persona-aware contrastive learning) implemented and evaluated.
- Behavioral-consistency metrics automated over real multi-turn staging sessions (not just toy dialogues).
- Persona-vector probing in model activations (stretch item) delivered.
- Tier-2 RAG ingestion started; anonymized session-metric logging instrumented for pilot quantitative measures.

## Sprint 4 — Research Console, RLHF Condition, Mid-Pilot (2026-08-17 – 2026-08-23)

- Research & Evaluation Service backend: session audit-log storage + drift-threshold alerting.
- Admin Research Console frontend stood up (RBAC-gated), wired to real backend data — RAG Corpus Admin + Persona Consistency Dashboard.
- Pilot-scale load testing across chat/goals/progress/library services.
- Data export & reporting endpoints (RAG Corpus Admin CSV export, anonymized pilot-data export).
- Sprint 5 infra readiness review (backup strategy + restore drill, incident runbook).
- Alignment condition #4 (personality-focused RLHF/DPO) implemented; persona-consistency metrics incorporated into the reward signal.
- Full comparative evaluation across all 4 alignment conditions; Tone Match and Fact Retrieval scoring pipeline.
- Manual audit workflow ("New Manual Audit" / "Filter by Drift") and safety/harmlessness check suite across all 4 conditions.
- KWAME (beta) stood up as the second mentor persona.
- Mid-pilot quantitative data checkpoint delivered (financial-knowledge, self-efficacy, engagement — Groups A & B).
- Desktop-responsive layouts across all screens; multi-mentor conversation list.
- Auth session persistence fixed: JWT signing key now persists across restarts; 7-hour idle-timeout sessions (previously ephemeral, invalidated on every server restart).

## Sprint 5 — Pilot Close-out, Hardening & Paper Submission (2026-08-24 – 2026-08-30)

- Full regression + bug bash across all 13 services and both frontends: 2 P0s and 2 P1s fixed (unbounded HTTP client churn under load, event-bus publish blocking the event loop, rate-limiter burst-at-window-boundary, goals data never actually persisting from the frontend), 2 P1s explicitly deferred with PO sign-off. Zero open P0s.
- Accessibility & performance hardening: WCAG 2.1 AA label/dialog fixes, a font-double-load fix, and a RAG-retrieval timeout fix.
- Security hardening: every backend service and datastore in the dev Compose stack (including an unauthenticated ChromaDB) was reachable from the whole LAN, bypassing the gateway entirely — locked down to loopback-only except the gateway's single ingress port.
- Best-performing alignment condition (RLHF/DPO) deployed to production CHIOMA; final latency/cost optimization pass.
- Technical documentation handoff: architecture diagrams, operational runbooks, service-ownership doc.
- Bug triage and technical-debt log published ahead of code freeze.
- Mid-pilot checkpoint extended with per-arm (Group A/B) breakdowns.

---

## Known gaps at v1.0 (see closure report for full detail)

- **Production deployment (O5.3)** — the network-isolation hardening prerequisite is done; the actual Oracle Cloud + Vercel cutover has not yet executed. It requires account-creation steps only the product owner can perform.
- **Research paper (G-track)** — Introduction, Related Work, Results, Discussion and Conclusion are drafted; the Method/System section and the Abstract are still stubs, no Methodology section was separated out, and no arXiv submission exists. Not ready for `G5.3` (assembly/internal review) or `G5.4` (submission).
- **Chat latency AC (O5.2)** — real LLM inference (now configured with a live provider key, for the first time this cycle) measures p95 ~4.2s single-user / ~11.7s at light (5-user) concurrency against the <3s target — not met. Root-caused to provider-side rate limiting, not an application bug. See [`qa/sprint5-chat-latency-followup.md`](qa/sprint5-chat-latency-followup.md).
