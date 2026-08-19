# Staging deployment (card O2.1)

## What "staging" means right now

There is no cloud environment for AfriMentor AI yet — provisioning one is out of scope
for this card and lands with the production-hardening work in Sprint 4/5 (see O4.3 load
testing and O5.3 production deployment runbook in the sprint plan). Until then,
**staging is a longer-lived, production-shaped Docker Compose stack**, distinct from the
day-to-day dev stack:

| | dev (`docker-compose.yml`) | staging (`+ docker-compose.staging.yml`) |
|---|---|---|
| Schema | `Base.metadata.create_all()` on boot | real Alembic migrations (`alembic upgrade head`, run by the container entrypoint) |
| JWT keys | ephemeral, generated in-process | a real RS256 keypair mounted from `infra/keys/` |
| Datastore ports | published to the host | internal to the compose network only |
| Data volumes | `pgdata` (dev) | `pgdata_staging` (never shares data with dev) |
| Project name | `afrimentor` | `afrimentor-staging` (runs alongside dev without port/volume collisions) |

Only services with a real v1 are in the staging overlay so far: `api-gateway` and
`auth-user-service` (plus their `postgres`/`redis` dependencies). Add a service's block
to `docker-compose.staging.yml` as it ships its v1.

The observability stack (Prometheus, Loki, Grafana, Jaeger, Promtail — card O2.5) also
runs in staging, with no host ports exposed. Grafana's admin credentials come from the
environment, not the dev defaults:

```bash
export GF_SECURITY_ADMIN_PASSWORD='a-long-random-value'
```

## RS256 keys

Staging uses a real, persistent JWT signing key instead of the dev fallback (a fresh
keypair generated in-process on every restart, which would invalidate every outstanding
token on redeploy). Generate one once:

```bash
mkdir -p infra/keys
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out infra/keys/jwt_private_key.pem
openssl rsa -pubout -in infra/keys/jwt_private_key.pem -out infra/keys/jwt_public_key.pem
```

`infra/keys/` is gitignored — never commit these. In a real CD pipeline they'd be
injected as secrets instead of a mounted directory.

## Deploying

For the chat UX load profile, set a fast streaming-capable model and keep generated
answers bounded so time-to-first-token is decoupled from total completion time:

```bash
export LLM_MODEL='Qwen/Qwen2.5-7B-Instruct'
export LLM_MAX_TOKENS=384
export LLM_STREAMING_ENABLED=true
export CHAT_CACHE_TTL_SECONDS=300
```

Clients that need progressive rendering should call
`POST /api/v1/chat/sessions/{id}/messages/stream`; it emits `token` SSE events followed
by one `complete` event. The existing JSON message endpoint remains available.

### D3.5 validation record

Focused validation for the Chat Orchestration Service passed on 2026-08-19:

```text
43 passed, 4 warnings in 3.52s
```

The run covered the existing chat and guardrail regression tests plus the D3.5
performance tests for RAG cache reuse, SSE token and completion events, and stream
assembly. The warnings are FastAPI scheduler deprecation warnings and do not affect
the D3.5 assertions.

The staging acceptance measurement is still pending. Run the benchmark after the
service, RAG corpus, and real LLM provider are deployed:

```bash
cd services/chat-orchestration-service
python scripts/chat_latency_benchmark.py \
  --base-url http://localhost:8003 \
  --users 20 \
  --requests 200
```

Record the benchmark's `first_token_ms.p95` and `complete_ms.p95` here. D3.5 is
accepted only when the successful requests' `complete_ms.p95` is below 3000 ms; the
local focused tests do not substitute for this realistic staging-load measurement.

```bash
scripts/deploy-staging.sh
```

This builds and starts `api-gateway` + `auth-user-service` (Compose brings up their
`postgres`/`redis` dependencies automatically), waits for health checks, then runs a
smoke test: gateway `/health`, and a signup → login round trip through the gateway.

## Migrations

`auth-user-service`'s `docker-entrypoint.sh` runs `alembic upgrade head` before starting
`uvicorn`, so `alembic upgrade head` is idempotent and safe to run on every deploy —
redeploying with no new migration is a no-op.

## Rollback

```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p afrimentor-staging \
  up -d --build <service> --no-deps  # roll a single service forward/back by checking out
                                      # the previous commit/tag first
```

Since there's no image registry wired to staging yet (see `ci.yml`, which only pushes on
merge to `main`), rollback today means checking out the previous commit and re-running
`scripts/deploy-staging.sh`. A tagged-image rollback (`docker compose ... up -d
<service>` against a pinned `image:` tag) is the natural upgrade path once O5.3's
production deployment runbook introduces a registry-backed release process.

## Tearing down

```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml -p afrimentor-staging down
# add -v to also drop the pgdata_staging volume
```
