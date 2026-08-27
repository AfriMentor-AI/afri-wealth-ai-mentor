# AfriMentor AI

An African financial-mentorship AI platform. A persona-driven mentor ("Chioma") guides
users through intake, goal-setting, and day-to-day financial decisions, backed by
retrieval-augmented generation over a curated corpus — mobile-first and optimised for
low-end devices.

Repository: **[AfriMentor-AI/afri-wealth-ai-mentor](https://github.com/AfriMentor-AI/afri-wealth-ai-mentor)**
· Organisation: **[AfriMentor-AI](https://github.com/AfriMentor-AI)**
· Default branch: `develop`

## Architecture & Technical Documentation

13 backend microservices behind a single API gateway, decomposed by business capability.
- **[docs/architecture/system-architecture.md](docs/architecture/system-architecture.md)** — Complete C4 container, sequence, event topology, storage, and security diagrams.
- **[docs/retro-phase-1-tech-debt-backlog.md](docs/retro-phase-1-tech-debt-backlog.md)** — Phase 1 engineering retrospective and prioritized Phase 2 technical debt backlog.
- **[docs/operations/operational-runbooks.md](docs/operations/operational-runbooks.md)** — Incident management (Sev 1–4), component runbooks, triage playbooks, and disaster recovery.
- **[docs/governance/service-ownership.md](docs/governance/service-ownership.md)** — Service ownership RACI, SLOs/SLIs, tier classifications, on-call governance, and ARB processes.
- **[docs/adr/0001-microservices-architecture.md](docs/adr/0001-microservices-architecture.md)** — Foundational architectural decision record.

```
Frontend / Admin ─► api-gateway ─► 12 capability services
                                     (each owns its Postgres DB; RAG also owns ChromaDB)
                    events over RabbitMQ (afrimentor.events)
```

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
