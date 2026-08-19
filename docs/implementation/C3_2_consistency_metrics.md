# Behavioral Consistency Metrics Implementation — Card C3.2

## Overview

Automate behavioral-consistency scoring over a sample of **real** multi-turn
staging sessions (not just curated examples) and persist the results so the
Research Console dashboard (Sprint 4) has real data to display.

Three sub-scores are computed per session, each in `[0, 1]` (from the C1.3 metric
suite, after Abdulhai et al. 2025):

- **prompt-to-line** — do the mentor's replies stay faithful to the persona's
  system prompt?
- **line-to-line** — do successive mentor turns stay consistent with one another?
- **Q&A consistency** — does each mentor reply stay on-topic with the user turn
  it answers?

An unweighted mean of the three is stored as `aggregate`.

The scores are produced by a **nightly job** and written to the
research-evaluation-service database, keyed by a per-run `job_run_id` so the
dashboard can read a coherent snapshot.

> **v0 scorer.** Sub-scores use the `LexicalScorer` (bag-of-words cosine) — it
> measures vocabulary overlap, not meaning. Card C2.3 replaces it with an
> embedding scorer; the schema and job are unchanged when it lands.

## Architecture

### Components

```
research-evaluation-service
  └─ APScheduler cron  (02:00 UTC nightly)
       │
       └─► run_consistency_job(sample_size)
            │
            ├─► session_sampler.sample_completed_sessions()
            │     └─ reads chat-orchestration DB (svc_chat)  ── conversations + messages
            │     └─ fetch_system_prompt()  ── persona-prompt-service (local fallback)
            │
            ├─► metrics.report.score_dialogue()   ── C1.3 suite (LexicalScorer v0)
            │
            └─► persists one ConsistencyRun per session   ── svc_research
                     │
                     └─► GET /api/v1/metrics/consistency   ── Research Console (Sprint 4)
```

### Data Flow

1. **Trigger**: The in-process APScheduler fires `run_consistency_job` nightly at
   02:00 UTC. It can also be called directly (tests, manual backfill).
2. **Sample**: `sample_completed_sessions(limit)` queries the chat DB for the most
   recently completed conversations and their messages.
3. **Anchor**: The persona **system prompt** — needed by prompt-to-line — is not
   stored in the chat `messages` table (it is assembled at inference time), so it
   is fetched once per run from `fetch_system_prompt()` (persona-prompt-service,
   with a local fallback) and reused as the anchor for every dialogue.
4. **Build**: Each conversation becomes a `Dialogue` (system_prompt + ordered
   turns + `persona_id`). Blank turns are skipped; conversations with fewer than
   two usable turns are dropped (a single utterance has no consistency to score).
5. **Score**: `score_dialogue()` runs the C1.3 suite, returning per-metric scores
   plus warnings (e.g. "line-to-line not measurable: fewer than 2 mentor turns").
6. **Store**: One `ConsistencyRun` row per scored session, all sharing the run's
   `job_run_id`.
7. **Serve**: `GET /api/v1/metrics/consistency` returns the latest run's per-session
   rows and run-level means for the dashboard.

## Implementation Details

### Models

#### ConsistencyRun
```python
class ConsistencyRun(Base):
    __tablename__ = "consistency_runs"

    id: str                  # PK, uuid4
    job_run_id: str          # groups all sessions scored in one run (indexed)
    conversation_id: str     # source conversation from the chat DB (indexed)
    persona_id: str | None   # nullable — an unbound session has no persona
    prompt_to_line: float    # [0, 1]
    line_to_line: float      # [0, 1]
    qa_consistency: float    # [0, 1]
    aggregate: float         # unweighted mean of the three
    turn_count: int          # number of scored turns
    warnings_json: str       # JSON list of non-fatal scoring warnings
    scored_at: datetime      # when the row was written (indexed; dashboard reads newest-first)
```

`persona_id` is nullable because chat-orchestration's `Conversation.persona_id`
is itself nullable — an unbound session has no persona, and that is a fact to
record, not a value to fabricate.

### Session sampler

`app/session_sampler.py` reads the chat service's database directly (chat owns
the turns and no event carries them):

```python
# Most recently completed conversations
SELECT id, persona_id
FROM conversations
WHERE status = 'completed'
ORDER BY updated_at DESC
LIMIT :limit

# Messages for each conversation, in order
SELECT role, content, sequence
FROM messages
WHERE conversation_id = :conv_id
ORDER BY sequence ASC
```

Design points:
- **System-prompt anchor**: sourced from `fetch_system_prompt(load_profile())`,
  the same helper the C2.3 baseline runner uses. Fetched **once per run** (one
  CHIOMA persona in v0) after confirming there is at least one conversation to
  score.
- **Filtering**: system rows dropped; blank/whitespace-only turns skipped; a
  conversation yielding `< 2` usable turns returns `None` and is excluded.
- **Resilience**: a chat-DB outage is caught and returns `[]` rather than raising,
  so a scheduled run degrades to a `no_data` status instead of crashing the
  service.

### Nightly job

`app/consistency_job.py` — `run_consistency_job(sample_size=20)`:

1. `load_profile()` and `sample_completed_sessions(limit=sample_size)`.
2. If no dialogues → return `{"status": "no_data", "session_count": 0, ...}`.
3. Per dialogue, `score_dialogue(dialogue, profile=profile)`; build and add a
   `ConsistencyRun`. A per-dialogue `try/except` means one unscorable session
   cannot abort the batch.
4. `commit()` and return a summary: `run_id`, `session_count`, `mean_aggregate`,
   `started_at`, `completed_at`, `status`.

### Scheduler

`app/main.py` arms the job on startup with APScheduler's `BackgroundScheduler`
(threaded — correct for a blocking, synchronous DB job):

```python
_scheduler = BackgroundScheduler(timezone="UTC")
_scheduler.add_job(
    run_consistency_job, "cron", hour=2, minute=0,
    kwargs={"sample_size": settings.consistency_sample_size},
    id="nightly_consistency", replace_existing=True,
)
_scheduler.start()
```

Startup is guarded by `settings.enable_scheduler` (so tests and one-off
containers can disable it), and a `shutdown` handler stops the scheduler so a
reload or `docker stop` exits cleanly.

### API Endpoint

#### GET /api/v1/metrics/consistency

Behavioral consistency scores for the Research Console dashboard.

**Query Parameters:**
- `limit` (optional, default 50, 1–500): max per-session rows to return.
- `job_run_id` (optional): report a specific run; defaults to the most recent.

Means are computed over **every** session in the run; `sessions` is capped at
`limit` rows.

**Response:**
```json
{
  "job_run_id": "3f2a…",
  "session_count": 12,
  "scored_at": "2026-08-16T02:00:04+00:00",
  "aggregates": {
    "mean_prompt_to_line": 0.7421,
    "mean_line_to_line": 0.6883,
    "mean_qa_consistency": 0.7005,
    "mean_aggregate": 0.7103
  },
  "sessions": [
    {
      "conversation_id": "conv-abc123",
      "persona_id": "chioma",
      "prompt_to_line": 0.75,
      "line_to_line": 0.70,
      "qa_consistency": 0.71,
      "aggregate": 0.72,
      "turn_count": 8,
      "scored_at": "2026-08-16T02:00:04+00:00"
    }
  ]
}
```

When no runs exist yet, the endpoint returns `job_run_id: null`,
`session_count: 0`, zeroed aggregates, and `sessions: []` (HTTP 200).

## Configuration

### Environment Variables

```bash
# This service's own database (defaults to SQLite for tests/bare runs)
DATABASE_URL=postgresql+psycopg://afrimentor:afrimentor@postgres:5432/svc_research

# Chat-orchestration DB the sampler reads (C3.2). Defaults to localhost for bare
# runs; docker-compose points it at the postgres service.
CHAT_DB_URL=postgresql+psycopg://afrimentor:afrimentor@postgres:5432/svc_chat

# Persona source for the system-prompt anchor (falls back to a local prompt if unset)
PERSONA_SERVICE_URL=http://persona-prompt-service:8004

# Nightly scheduler (card C3.2). Disable in tests/one-off containers.
ENABLE_SCHEDULER=true
CONSISTENCY_SAMPLE_SIZE=20
```

### Docker Compose

The `research-evaluation-service` block in `docker-compose.yml` sets `CHAT_DB_URL`
to the shared `postgres` service so the nightly job can reach the chat DB. The
scheduler starts automatically on container startup (`ENABLE_SCHEDULER` defaults
to `true`).

## Database Migration

No Alembic migration is required. The `consistency_runs` table is created
automatically via SQLAlchemy's `Base.metadata.create_all()` on startup —
`ConsistencyRun` is imported in `app/models/__init__.py` so it is registered on
the shared `Base` before `create_all` runs.

## Testing

```bash
cd services/research-evaluation-service
.venv/bin/python -m pytest tests/test_consistency_metrics.py -v
```

Tests cover:
- **Model** — `ConsistencyRun` field round-trip.
- **Sampler** — empty on chat-DB outage; rows → valid Dialogues carrying the
  system-prompt anchor and `persona_id`; short/blank conversations filtered;
  no system-prompt fetch attempted when there are no completed conversations.
- **Job** (in-memory SQLite) — stores one row per scored dialogue; `no_data`
  status when the sampler yields nothing; rows are queryable by `conversation_id`.
- **Endpoint** — reports the latest run with correct means; empty-state shape.

In-memory SQLite tests use `poolclass=StaticPool` so the single shared connection
survives across threads — `TestClient` runs sync endpoints in a worker thread
separate from the one that created the tables.

## Usage Example

### Manual run (backfill / smoke test)

```python
from app.consistency_job import run_consistency_job

summary = run_consistency_job(sample_size=20)
# {'run_id': '3f2a…', 'session_count': 12, 'mean_aggregate': 0.7103,
#  'started_at': '…', 'completed_at': '…', 'status': 'completed'}
```

### Querying scores

```bash
# Latest run
curl "http://localhost:8010/api/v1/metrics/consistency"

# A specific run, capped at 100 per-session rows
curl "http://localhost:8010/api/v1/metrics/consistency?job_run_id=3f2a...&limit=100"
```

## Next Steps

1. **Embedding scorer (C2.3)** — swap the `LexicalScorer` for a semantic scorer;
   the sampler, job, schema, and endpoint are unchanged.
2. **Dashboard wiring (Sprint 4)** — the Research Console consumes
   `GET /api/v1/metrics/consistency`; add trend-over-time once several nightly
   runs have accumulated.
3. **Run-level history** — an endpoint listing `job_run_id`s and their means for
   plotting consistency over time.
4. **Sampling strategy** — v0 takes the most recent N completed sessions; later
   work may stratify by persona or sample at random for less recency bias.
5. **Migrations** — if this service adopts Alembic, add a migration for
   `consistency_runs` rather than relying on `create_all`.

## Acceptance Criteria Met ✓

- [x] Consistency scores computed over a sample of **real** sessions (sampled
      from the chat DB, not curated examples)
- [x] prompt-to-line, line-to-line, and Q&A consistency each scored per session
- [x] Runs **nightly** (APScheduler cron, 02:00 UTC)
- [x] Results **stored** (`consistency_runs`) and queryable per run / per
      conversation
- [x] Real data exposed for the Research Console dashboard (`GET
      /api/v1/metrics/consistency`)

## References

- Card C1.3: Consistency metric suite (`app/metrics/consistency.py`)
- Card C2.3: Embedding scorer (replaces the v0 lexical scorer)
- Card C3.5: Session metrics (sibling job/endpoint in this service)
- Abdulhai et al. 2025 — behavioral consistency metrics
- ADR-0001: Microservices Architecture
