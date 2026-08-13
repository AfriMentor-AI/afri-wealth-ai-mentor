# Security Hardening Pass — Sprint 3 (card O3.5)

- **Card:** O3.5 (Sprint 3, 3 pts, High priority)
- **Date:** 2026-08-13
- **Scope:** every service live on `develop` at the time of this pass (api-gateway,
  auth-user-service, intake-profiling-service, chat-orchestration-service,
  persona-prompt-service, rag-corpus-service, goals-milestones-service,
  research-evaluation-service, voice-service), plus the four services built earlier
  in Sprint 3 (progress-gamification-service, insight-library-service,
  feedback-service, notification-service — reviewed during their own PRs #75–#78 and
  re-confirmed here).
- **Method:** read every router under `services/*/app/routers/*.py` (or `app/main.py`
  where a service has no `routers/` yet) for authorization gaps, cross-checked each
  service's test suite for negative "other user/role can't touch this" coverage, and
  ran a regex secrets sweep over every tracked file (`scripts/scan-secrets.sh`).

## Acceptance criteria

- **Authz test suite covering all live endpoints passes** — see §1; two real gaps
  found and fixed, each with new regression tests, and the full test suites for every
  touched service are green.
- **Secrets scan finds zero committed secrets** — see §2. One finding, fixed.

## 1. Authorization findings

### 1.1 Fixed — persona-selection IDOR (chat-orchestration-service + persona-prompt-service)

`PATCH /api/v1/chat/sessions/{id}/persona` (`bind_persona` in
`services/chat-orchestration-service/app/routers/chat.py`) had no identity check at
all — its docstring assumed it was only ever reached by an internal
service-to-service call. But its only caller, `POST /api/v1/personas/{id}/select` in
`services/persona-prompt-service/app/routers/personas.py`, is itself reachable through
the API gateway's protected `/api/v1/personas` prefix with a client-supplied
`session_id` in the request body. Any authenticated user (a valid JWT for their own
account) could pass another user's session id and rebind that session's persona.

**Fix:**
- `persona-prompt-service`'s `select_persona` now requires `X-User-Id` and forwards it
  as a header on its call to chat-orchestration-service.
- `chat-orchestration-service`'s `bind_persona` now requires `X-User-Id` and applies
  the same `conv.user_id != user_id → 404` ownership check every other session-scoped
  endpoint in that router already uses.
- New tests: `test_select_persona_requires_identity` +
  `test_select_persona_calls_chat_service`'s header-forwarding assertion
  (persona-prompt-service); `test_bind_persona_requires_identity` +
  `test_bind_persona_wrong_user_cannot_rebind_session`
  (chat-orchestration-service).

### 1.2 Fixed — RAG Corpus Admin endpoints missing role gate (rag-corpus-service)

`POST /documents` (ingest), `GET /documents` (list), `GET /documents/export.csv`,
`GET /stats`, and `DELETE /documents/{id}` in
`services/rag-corpus-service/app/api/routes.py` only checked `X-User-Id` — any
authenticated user, not just an admin, could ingest arbitrary documents into the
shared corpus, bulk-export it, or delete any document. These are explicitly the RAG
Corpus Admin screen's operations (per the sprint plan, gated to Lead
Architect/Researcher roles at the UI layer — the backend never enforced it).

**Fix:** added a `_require_admin` dependency (mirrors the pattern already used in
insight-library-service for catalog authoring) checking `X-User-Roles` — the gateway
forwards this from verified JWT claims the same way it forwards `X-User-Id`, so this
is the same trust boundary, not a new one. Applied to the five admin endpoints above.
`POST /query` (retrieval used by chat) is deliberately **not** gated — every user
needs it for normal chat/RAG use.

New tests: `test_ingest_requires_admin_role`, `test_list_documents_requires_admin_role`,
`test_delete_requires_admin_role`, `test_query_does_not_require_admin_role`
(`test_documents.py`); `test_list_requires_admin_role`,
`test_export_csv_requires_admin_role`, `test_stats_requires_admin_role`
(`test_admin_endpoints.py`). Three pre-existing "missing auth" tests now assert `403`
instead of `422` — with zero headers at all, the role-gate dependency (whose only
param defaults to `""`, not required) resolves and rejects before FastAPI reports the
still-missing required `X-User-Id` header, so 403 fires first. Both are "you're not
getting in," just a different gate catching it.

### 1.3 Checked, no change needed

- **goals-milestones-service, intake-profiling-service, auth-user-service,
  api-gateway** — reference-quality: every user-scoped endpoint uses the
  `_get_owned_*`/404-not-403 pattern, full negative-test coverage already present,
  JWT verified at the edge with client-supplied `X-User-Id`/`X-User-Roles` stripped
  before forwarding, rate limiting applied per-route.
- **chat-orchestration-service** (aside from `bind_persona`, §1.1) — `get_session`,
  `send_message`, `list_messages`, `tag_commitment` all correctly scope on
  `conv.user_id != user_id`.
- **goals-milestones-service's `POST /goals/{id}/commitments`** — no identity gate,
  but this is a genuine internal call (the record is *created*, scoped to a
  caller-supplied `user_id` that only ever originates from
  chat-orchestration-service's own already-authenticated request) — not the same
  shape of bug as §1.1, where the *caller itself* was a public, gateway-routed,
  unauthenticated-w.r.t.-ownership endpoint.
- **research-evaluation-service, voice-service** — both still stub services (health
  endpoint only); nothing user-facing to audit yet.
- **Gateway rate limiting** (`services/api-gateway/app/ratelimit.py` +
  `routes.py`) — every protected route has an effective limit (explicit
  `rate_limit` or the gateway default); no gap found, no change made.
- **progress-gamification-service, insight-library-service, feedback-service,
  notification-service** (Sprint 3, this branch's siblings) — re-confirmed
  ownership scoping on every user-scoped endpoint, admin-role gating on
  insight-library-service's catalog authoring, and that the internal `/trigger/*` /
  commitment-style endpoints follow the same documented internal-call precedent as
  goals-milestones-service.

## 2. Secrets scan

`scripts/scan-secrets.sh` — new tool, sweeps every `git`-tracked file (so
`.gitignore`d content like local `.env`/`.venv` is never in scope) for AWS keys, PEM
private-key blocks, and provider-prefixed API keys (Groq `gsk_`, OpenAI `sk-`, Google
`AIza`, Slack `xox*`) that aren't obviously placeholders.

**Finding — fixed:** `.env.example` had a real-format Groq API key
(`LLM_API_KEY=your-gsk_...`) — a genuine key with `your-` prefixed onto it, which
reads as a placeholder but isn't one; the key material was live. Replaced with a
real placeholder (`LLM_API_KEY=your-groq-api-key-here`, matching the pattern already
used in `research/README.md`).

**⚠️ Action needed — not something this PR can do:** treat that Groq API key as
compromised (it was public in the repo, including in prior history) and **rotate it**
in the Groq dashboard. This is a credential-rotation action outside what a PR can
fix — flagging here so it's visibly a checklist item, not silently resolved by the
`.env.example` edit alone.

**Self-correction:** an independent review pass on this PR's own diff (before
merge) found that the *first* version of `scan-secrets.sh` would not have caught
the leak above — its placeholder filter matched against the whole grep line, not
the matched secret token, so a real key with `your-` glued directly onto it (the
exact disguise pattern that caused the original leak) got excluded by the `your-`
placeholder rule despite containing live key material. Confirmed empirically
(the original leaked line piped through the old filter came back "clean") and
fixed by matching the placeholder filter against the extracted token only,
re-verified against both the original leaked line (now flagged) and the genuine
placeholder in `research/README.md` (still correctly excluded).

**Clean:** no AWS keys, no committed PEM/private-key blocks, no other
provider-prefixed tokens found. `.gitignore` correctly excludes `.env`/`.env.*` while
allowlisting `.env.example`; `git ls-files | grep -E '\.env$'` returns nothing (only
`.env.example` and `frontend/.env.example` are tracked).
`docker-compose.yml`'s hardcoded `POSTGRES_PASSWORD`/`GF_SECURITY_ADMIN_PASSWORD` are
local-dev-only defaults, not reachable outside the compose network, and
`docker-compose.staging.yml` already requires `GF_SECURITY_ADMIN_PASSWORD` with no
default — noted, not a finding.

## 3. Follow-ups (not blocking this PR)

- Rotate the Groq API key that was exposed (see §2).
- `.github/CODEOWNERS` currently routes `progress-gamification-service`,
  `insight-library-service`, `feedback-service`, `notification-service`, and
  `frontend/` to `@kagajugrace` (Grace) — doesn't match this sprint's stated
  ownership (Olusegun for Sprint 3's O3.x cards). Reconcile separately.
