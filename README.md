# AfriMentor AI

An African financial-mentorship AI platform. A persona-driven mentor ("Chioma") guides
users through intake, goal-setting, and day-to-day financial decisions, backed by
retrieval-augmented generation over a curated corpus — mobile-first and optimised for
low-end devices.

Repository: **[AfriMentor-AI/afri-wealth-ai-mentor](https://github.com/AfriMentor-AI/afri-wealth-ai-mentor)**
· Organisation: **[AfriMentor-AI](https://github.com/AfriMentor-AI)**
· Default branch: `develop`

## 🚀 Live Application

**Deployed Web Application:**
https://afriwealthaimentor.vercel.app/

The deployed application provides access to the AfriMentor AI platform and demonstrates the user-facing financial mentorship experience.

## 📋 Agile Task Board

**Trello Scrum Board:**
https://trello.com/b/idp26vqA/afrimentor-ai-sprint-plan

The Trello board documents the project's agile development process, including tasks carried out by group members, sprint planning, user stories, progress tracking, and completed work.

## Architecture & Technical Documentation

13 backend microservices behind a single API gateway, decomposed by business capability.
- **[docs/architecture/system-architecture.md](docs/architecture/system-architecture.md)** — Complete C4 container, sequence, event topology, storage, and security diagrams.
- **[docs/bug-triage-backlog.md](docs/bug-triage-backlog.md)** — Triaged bug backlog with P0–P3 priority labels ahead of Sprint 5 code freeze.
- **[docs/tech-debt-log.md](docs/tech-debt-log.md)** — Prioritized technical debt log with story points, owners, and sprint allocation.
- **[docs/architecture/sprint-5-hardening-architecture-review.md](docs/architecture/sprint-5-hardening-architecture-review.md)** — Architecture review with Olusegun for Sprint 5 hardening (mTLS, pooling, migrations, DLQ).
- **[docs/retro-phase-1-tech-debt-backlog.md](docs/retro-phase-1-tech-debt-backlog.md)** — Phase 1 engineering retrospective and Phase 2 backlog.
- **[docs/operations/operational-runbooks.md](docs/operations/operational-runbooks.md)** — Incident management (Sev 1–4), component runbooks, triage playbooks, and disaster recovery.
- **[docs/governance/service-ownership.md](docs/governance/service-ownership.md)** — Service ownership RACI, SLOs/SLIs, tier classifications, on-call governance, and ARB processes.
- **[docs/adr/0001-microservices-architecture.md](docs/adr/0001-microservices-architecture.md)** — Foundational architectural decision record.

```
Frontend / Admin ─► api-gateway ─► 12 capability services
                                     (each owns its Postgres DB; RAG also owns ChromaDB)
                    events over RabbitMQ (afrimentor.events)
```

## Runtime model configuration

The current app runtime is configured to call an OpenAI-compatible provider endpoint, not to import a local checkpoint directly from Hugging Face at runtime.

The active default configuration in [.env](.env) is:

```env
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=openai/gpt-oss-20b
LLM_API_KEY=<your-groq-key>
LLM_MAX_TOKENS=2048
LLM_TEMPERATURE=0.7
```

This means the production application layer is currently wired to Groq via the standard `LLM_BASE_URL` / `LLM_MODEL` environment variables. The current live model is GPT-OSS; it does not load the Qwen-trained adapters directly. The canonical trained SFT artifact is `AfriMentor/chioma-sft-v1`, based on `Qwen/Qwen2.5-7B-Instruct`, and can be used when a Qwen-plus-adapter OpenAI-compatible endpoint is deployed.

## Quick start

```bash
git clone https://github.com/AfriMentor-AI/afri-wealth-ai-mentor.git
cd afri-wealth-ai-mentor
docker compose up --build      # boots all 13 services + Postgres + Redis + RabbitMQ + ChromaDB
docker compose ps              # wait for all containers to report "healthy"
```

- Gateway: http://localhost:8000  (docs at `/docs`)
- Services: ports 8001–8012 (see `docker-compose.yml`)
- RabbitMQ management UI: http://localhost:15672 (afrimentor / afrimentor)
- API docs site: `docs/api/` (see [docs/api/README.md](docs/api/README.md))
- Observability: Prometheus :9090, Grafana :3001 (admin/admin), Loki :3100, Jaeger :16686 — see [docs/observability.md](docs/observability.md)

## Repository layout

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for the full layout, branching strategy, and
coding standards.

```
services/    13 FastAPI microservices
frontend/    Next.js 16 + React 19 mobile app
infra/       postgres init, observability config, dev infrastructure
docs/        ADRs (docs/adr), API contracts (docs/api), observability guide
```

## Staging

For services with a shipped v1 (`api-gateway`, `auth-user-service`), see
**[docs/deployment/staging.md](docs/deployment/staging.md)** for the interim staging
overlay and `scripts/deploy-staging.sh`.

## Development

Run and test a single service:

```bash
cd services/auth-user-service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
pytest -q
```

## License

Proprietary — © AfriMentor AI.
