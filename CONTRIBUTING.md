# Contributing to AfriMentor AI

Welcome. This is the monorepo for AfriMentor AI — an African financial-mentorship
platform. Read this before opening your first PR.

## 1. Repository layout

```
/services/              13 backend microservices (FastAPI, Python 3.12)
  api-gateway/            edge: routing, JWT verification, rate limiting
  auth-user-service/      signup/login, JWT + refresh, user profile
  intake-profiling-service/
  chat-orchestration-service/
  persona-prompt-service/
  rag-corpus-service/
  goals-milestones-service/
  progress-gamification-service/
  insight-library-service/
  feedback-service/
  research-evaluation-service/
  voice-service/
  notification-service/
/frontend/              Next.js 16 + React 19 mobile-first app  (→ moves to /apps/frontend)
/apps/                  frontend + admin-console (admin-console lands Sprint 2)
/infra/                 postgres init, keys, shared dev infrastructure
/docs/                  ADRs and API docs
  adr/                    architecture decision records
  api/                    generated OpenAPI docs site
/.github/               CI workflows, PR & issue templates
docker-compose.yml      one-command local dev stack
```

> The Sprint-1 monorepo keeps the existing `/frontend` at the root while backend
> services move under `/services`. The physical move to `/apps/frontend` +
> `/apps/admin-console` is scheduled with the admin-console work in Sprint 2 to avoid
> churning the (customised) Next.js build mid-sprint. The layout above is the target.

## 2. Prerequisites

- Docker + Docker Compose v2
- Python 3.12 (for running/testing a single service outside Docker)
- Node 20 (for the frontend)

## 3. Running the stack

```bash
docker compose up --build
```

This boots all 13 service stubs plus Postgres, Redis, RabbitMQ and ChromaDB. Every
container has a health check; wait for them to report `healthy`:

```bash
docker compose ps
```

Each service exposes `GET /health` and interactive docs at `/docs`. The gateway is on
`http://localhost:8000`; individual services are on `8001`–`8012` (see
`docker-compose.yml`).

### Running one service locally

```bash
cd services/auth-user-service
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
pytest -q
```

## 4. Branching strategy — trunk-based

We practise **trunk-based development**:

- `main` is always releasable and protected. No direct pushes.
- Create **short-lived feature branches** off the latest `main`. Keep them under ~2 days
  of work; rebase on `main` frequently.
- Naming: `<type>/<card>-<slug>`, e.g. `feat/O1.3-auth-service`, `fix/O1.2-compose-health`.
  Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`.
- Open a PR early (draft is fine). Small PRs merge faster.
- Squash-merge into `main`. Delete the branch after merge.

### Branch protection (configured on `main`)
- Require the `ci-ok` status check to pass.
- Require at least one approving review from the owning area (see below).
- Require branches to be up to date before merging.

## 5. Code ownership & reviewers

Per [ADR-0001](docs/adr/0001-microservices-architecture.md):

| Area | Services | Owner / reviewer |
|------|----------|------------------|
| Platform spine | api-gateway, auth-user-service, intake-profiling-service, goals-milestones-service | **Olusegun** |
| Chat path | chat-orchestration-service, persona-prompt-service, voice-service | **Daniel** |
| Knowledge & eval | rag-corpus-service, research-evaluation-service | **Chukwuebuka** |
| Engagement & UI | progress-gamification-service, insight-library-service, feedback-service, notification-service, frontend | **Grace** |

## 6. Commit messages

Conventional-commit style: `type(scope): summary`, e.g.
`feat(auth): add refresh-token rotation`. Keep the summary imperative and under ~72 chars.

## 7. Coding standards

- **Python:** `ruff` for lint/format; type hints on public functions; Pydantic v2 models
  for request/response bodies. Tests with `pytest`; every service keeps `tests/` green.
- **API changes:** update the service's OpenAPI contract in the same PR
  (`docs/api/<service>.yaml`). See card O1.4.
- **No secrets in git.** Use env vars and `.env` (gitignored). Dev keys are generated at
  runtime, never committed.

## 8. CI

`.github/workflows/ci.yml` runs on every PR: for each changed service it runs
`ruff check` → `pytest` → `docker build` (and pushes on merge to `main`). The aggregate
`ci-ok` job is the required check that blocks merge on failure.
