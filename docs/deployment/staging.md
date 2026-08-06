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
