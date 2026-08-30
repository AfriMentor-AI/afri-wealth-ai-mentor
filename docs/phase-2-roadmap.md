# Post-MVP Phase 2 Roadmap

Date: 2026-08-30
Prepared by: Olusegun (Product Owner), per card **O5.5**.
Sources consolidated: `docs/retro-phase-1-tech-debt-backlog.md` (TD-01–TD-15),
`docs/bug-triage-backlog.md` (deferred P1s), `docs/security-hardening-pass-O5.3.md`
(deferred security items), `docs/qa/sprint5-chat-latency-followup.md` (new this
session), the sprint plan's own named stretch items, and
`docs/mvp-scope-closure-report.md`'s open gaps.

This is a consolidation, not a re-derivation — TD-01 through TD-15 keep their IDs
and full specs in the retro doc; this roadmap re-prioritizes them against what
actually shipped in Sprint 5, since three of them were partially resolved by O5.1's
bug bash after the retro doc was written (2026-08-27, three days before O5.1 landed).

## What changed since the retro doc was written

| ID | Was | Now | Why |
|---|---|---|---|
| TD-03 | P0, open | **Resolved** | O5.1/BUG-01 put a single pooled `httpx.AsyncClient` on the gateway's lifespan — exactly TD-03's target architecture. Closing this item; no further Phase 2 work needed. |
| TD-07 | P1, open | **Resolved** | O5.1/BUG-04 replaced the fixed-window Redis counter with a sliding-window (sorted-set / in-memory) implementation. TD-07's extra scope (tiered per-role limits, RFC 6585 headers) is real but minor — downgraded to P2, see TD-07b below. |
| TD-02 | P0, open | **Partially resolved** | O5.1/BUG-02 stopped `pika.BlockingConnection` from blocking the event loop (dual-path `asyncio.to_thread`/`threading.Thread` dispatch) in chat-orchestration and goals-milestones. The underlying symptom (request-path blocking) is gone, but the full `aio-pika` + DLQ + correlation-ID target architecture is not built — kept open, downgraded from P0 to P1 since the acute risk is already mitigated. |
| TD-04 | P0, open | **Partially resolved** | O5.1/BUG-06 wired `createGoal`/`fetchGoals`/`fetchMilestonesByGoal`/`completeMilestone`/`fetchCommitmentsByGoal` to the real `goals-milestones-service` — goals were previously never persisting at all. Insights, Gamification badges/streaks, and parts of Intake likely still resolve through `mockApi.ts` — kept open at P0, scope narrowed to those remaining areas. |

## Consolidated Phase 2 backlog

### P0 — must do first (Sprint 6)

| ID | Title | Pts | Owner | Note |
|---|---|---|---|---|
| **PROD-DEPLOY** | Execute the real O5.3 cutover (Oracle Cloud + Vercel) | 5 | Olusegun | Network-isolation hardening is done and verified live; the actual cloud deployment never executed this cycle — blocked on Oracle/Vercel account creation only the PO can do. Carries the O5.3 rollback-dry-run requirement forward unchanged. |
| TD-01 | Universal Alembic migration harness (10 services) | 8 | Olusegun | Unchanged from retro doc — `_ensure_*_columns()` monkeypatches (research-evaluation-service, and the newly-added one in goals-milestones-service from O5.1) are exactly the failure mode this closes. |
| TD-04 | Finish PWA live-API wiring (Insights, Gamification, remaining Intake) | 5 *(narrowed from 8)* | Grace | Goals slice already closed by O5.1/BUG-06 — see above. |
| TD-02 | `aio-pika` event bus + DLQ | 3 *(narrowed from 5)* | Daniel | Blocking symptom already fixed by O5.1 — remaining scope is DLQ + correlation IDs + the other 3 publishers (progress, feedback, research) that never got the `asyncio.to_thread` treatment. |

### P1 (Sprint 6–7)

| ID | Title | Pts | Owner | Note |
|---|---|---|---|---|
| **CHAT-LATENCY** | Chat p95 latency under real inference | 5 | Daniel | New this session — real measurement (not the stub path) shows p95 4.2s single-user / 11.7s at 5-concurrent-user, against the <3s target. Root-caused to provider-side (Groq) rate limiting, not an app bug. Options: paid/higher-tier plan sized for pilot concurrency, a different low-latency provider, or client-side request queuing so degradation is graceful. See `docs/qa/sprint5-chat-latency-followup.md`. |
| BUG-03 | research-evaluation-service startup DDL → real Alembic baseline | — | Olusegun | Deferred from O5.1 with PO sign-off; folds naturally into TD-01. |
| BUG-05 | voice-service audio-format validation (needs FFmpeg transcoding) | — | Daniel | Deferred from O5.1 with PO sign-off. |
| SEC-01 | Dependency CVE remediation (90 findings across 13 services) | 8 | Olusegun | From O5.3's hardening pass — chromadb, starlette, python-multipart, pyjwt, jinja2, langchain all carry known advisories. Needs a coordinated FastAPI/dependency bump across every service, not a single-service patch. |
| SEC-02 | LLM prompt-injection defense | 3 | Daniel | `chat-orchestration-service`'s RAG context-injection has no "untrusted reference data" directive; the red-team dataset has no prompt-injection category. |
| SEC-03 | Gateway `TrustedHostMiddleware` + body-size limits | 2 | Olusegun | Only CORS is configured today; Host-header poisoning is a direct hit without it. |
| SEC-04 | Dependency-scan CI job (pip-audit/npm-audit) | 3 | Olusegun | `scripts/scan-secrets.sh` exists and is clean; no dependency-vulnerability gate exists yet. |
| TD-05 | Voice service async engine + African-dialect STT/TTS | 8 | Daniel | Unchanged from retro doc. |
| TD-06 | PgBouncer connection pooler | 5 | Olusegun | Unchanged. |
| TD-07b | Tiered per-role rate limits + RFC 6585 headers | 2 *(narrowed from 3)* | Olusegun | Core sliding-window algorithm already shipped in O5.1. |
| TD-08 | Automated OpenAPI contract testing in CI | 5 | Chukwuebuka | Unchanged. |
| **PAPER** | Complete and submit the research paper | 8 | Grace | Largest single gap from the closure report: Method section and Abstract are stubs, no separated Methodology section, no statistical-significance results, no reproducibility appendix, no arXiv submission. |

### P2 (Sprint 7–8)

| ID | Title | Pts | Owner |
|---|---|---|---|
| TD-09 | Redis L2 caching (RAG + persona) | 5 | Chukwuebuka |
| TD-10 | End-to-end W3C TraceContext tracing | 5 | Chukwuebuka |
| TD-11 | Secret rotation / Vault-KMS | 5 | Olusegun |
| TD-12 | Admin console drift-auditing UI | 5 | Grace/Chukwuebuka |

### P3 (Sprint 8–9)

| ID | Title | Pts | Owner |
|---|---|---|---|
| TD-13 | PWA offline sync (IndexedDB replay) | 5 | Grace |
| TD-14 | Turborepo / build acceleration | 3 | Olusegun |
| TD-15 | Mobile perf / low-end Android hardening | 3 | Grace |

## Sprint plan's own named stretch items

| Item | Status |
|---|---|
| Local-language support (Pidgin/Yoruba/Swahili beyond the mentor persona's own register-mirroring) | Not started — new Phase 2 item, no existing card |
| Community tab | Not started — never had a Sprint 1–5 card; net-new for Phase 2 |
| Tier-2 RAG expansion | **Underway** — C3.4 started Tier-2 ingestion + refresh-cycle automation this cycle; continue expanding source coverage |
| Additional mentor personas beyond KWAME | KWAME (beta) shipped in C4.4; further personas are net-new for Phase 2 |

## Suggested Phase 2 sprint allocation

Keeping the retro doc's 70/30 feature/debt split as the starting assumption, but
front-loading PROD-DEPLOY and the finished-scope items (TD-04 narrowed, TD-02
narrowed) since they're smaller than originally estimated:

- **Sprint 6:** PROD-DEPLOY, TD-01, TD-04 (narrowed), TD-02 (narrowed), CHAT-LATENCY
- **Sprint 7:** SEC-01 through SEC-04, TD-05, TD-06, TD-07b, TD-08, PAPER (start)
- **Sprint 8:** PAPER (finish + submit), TD-09, TD-10, TD-11, TD-12
- **Sprint 9:** TD-13, TD-14, TD-15, Community tab discovery, local-language support discovery
