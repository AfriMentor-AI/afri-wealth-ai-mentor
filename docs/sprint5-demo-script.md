# Sprint 5 Review — Demo Script

Date: 2026-08-30
No live stakeholder audience was available for this review, so this is the written
walkthrough in lieu of a live demo — the golden-path flow across both frontends,
narrated as it would be presented.

## 1. User PWA — first-time user journey

1. **Welcome/Splash** (`/welcome`) — mobile-first carousel introducing AfriMentor.
2. **Intake** (`/intake`, 4 steps) — sector (Trader/Tech/Fashion-Retail/Agriculture/Creative),
   education/time, constraints, confirm. Persists a diagnostic profile
   (`intake-profiling-service`) used for personalization downstream.
3. **Persona Selection** — choose a mentor (CHIOMA or one of 5 sub-personas, KWAME beta).
   "Hear an example" plays a real TTS preview per persona (`voice-service`).
4. **Chat** — multi-turn conversation with the selected mentor. A reply grounded in
   the RAG corpus shows a source-pill ("Based on TEF curriculum"). Saying "I will
   save 10% of today's profit" triggers a commitment-tag suggestion; confirming
   "Yes, Tag It" creates a real commitment against an active goal, visible
   immediately on the Goals screen — no page refresh.
5. **Goals & Milestone Path** — the tagged commitment now appears under the goal's
   "Tagged Commitments" list; milestone status can be advanced
   (Vision Foundation → Legal Readiness → Operations → Launch).
6. **Daily Action Card** — a personalized, goal-aware action generated overnight
   for the user (e.g. "Save 10% of today's profit"), not generic copy.
7. **Progress Board** — streak counter, action heatmap, badges (Consistency Queen,
   Smart Saver, Scholar Spirit) awarded on real trigger conditions.
8. **Insight Library** — search/filter by sector/topic/audio/text; favoriting persists.
9. **Feedback Survey** — fires automatically on a milestone-completion event
   (accessible dialog: focus-managed, closes on Escape, per O5.2's a11y pass).

Session note: auth now persists across a server restart with a 7-hour idle timeout
(fixed this cycle — previously every restart silently logged every user out).

## 2. Admin Research Console — internal, role-gated

1. **RAG Corpus Admin** — document index (title/sector/country/author/date/status),
   upload, filter, CSV export matching the table columns exactly, index-health
   stats (size, vector count, inference latency).
2. **Persona Consistency Dashboard** — live-updating aggregate CHIOMA alignment
   score sourced from real sessions; Tone Match / Fact Retrieval widgets on a
   rolling 24h basis; "New Manual Audit" and "Filter by Drift" both wired to real
   backend logic, not placeholders; drift-threshold alert fires when a session's
   consistency delta crosses the configured threshold.

## 3. What's under the hood (engineering highlights)

- 13 independently deployable services behind one gateway (JWT + rate limiting),
  RabbitMQ event bus, per-service Postgres.
- 4 alignment conditions run and compared end-to-end (baseline prompting → SFT →
  contrastive learning → RLHF/DPO); the RLHF/DPO checkpoint is what's live in
  production CHIOMA today.
- Safety/harmlessness red-team suite run against all 4 conditions with no
  regression vs. an unaligned baseline.
- Sprint 5 closed a real regression sweep (2 P0s, 2 P1s fixed) and a real
  security hardening pass (every backend/datastore was reachable from the LAN;
  now loopback-only except the gateway).

## 4. Known open items (stated plainly, not glossed over)

- Chat p95 latency does not currently meet the <3s target under real LLM
  inference — see `docs/qa/sprint5-chat-latency-followup.md`.
- Production cutover (Oracle Cloud + Vercel) is prepped but not executed.
- The research paper is not yet ready for arXiv submission — see
  `docs/mvp-scope-closure-report.md`'s G-track section.
