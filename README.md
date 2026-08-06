# AfriMentor AI

An African financial-mentorship AI platform. A persona-driven mentor ("Chioma") guides
users through intake, goal-setting, and day-to-day financial decisions, backed by
retrieval-augmented generation over a curated corpus — mobile-first and optimised for
low-end devices.

## Architecture

13 backend microservices behind a single API gateway, decomposed by business capability.
See **[docs/adr/0001-microservices-architecture.md](docs/adr/0001-microservices-architecture.md)**
for service boundaries, datastore strategy, communication model, and the per-service tech
stack.

```
Frontend / Admin ─► api-gateway ─► 12 capability services
                                     (each owns its Postgres DB; RAG also owns ChromaDB)
                    events over RabbitMQ (afrimentor.events)
```

## Quick start

```bash
docker compose up --build      # boots all 13 services + Postgres + Redis + RabbitMQ + ChromaDB
docker compose ps              # wait for all containers to report "healthy"
```

- Gateway: http://localhost:8000  (docs at `/docs`)
- Services: ports 8001–8012 (see `docker-compose.yml`)
- RabbitMQ management UI: http://localhost:15672 (afrimentor / afrimentor)
- API docs site: `docs/api/` (see [docs/api/README.md](docs/api/README.md))

## Repository layout

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for the full layout, branching strategy, and
coding standards.

```
services/    13 FastAPI microservices
frontend/    Next.js 16 + React 19 mobile app
infra/       postgres init, dev infrastructure
docs/        ADRs (docs/adr) and API contracts (docs/api)
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
