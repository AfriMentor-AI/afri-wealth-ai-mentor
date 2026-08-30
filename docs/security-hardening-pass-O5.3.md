# Security & Supply-Chain Audit Pass (O5.3) — Network Isolation

Date: 2026-08-30
Scope: `docker-compose.yml` network exposure review of the 13-service dev stack.

## Finding (CRITICAL) — every backend published to 0.0.0.0

The base `docker-compose.yml` published **every** microservice (8001–8012), the
admin research console, and every datastore/UI — Postgres, Redis, RabbitMQ
(5672 + mgmt 15672), ChromaDB, MLflow, Prometheus, Loki, Grafana, Jaeger — to
the host's `0.0.0.0`, i.e. reachable from the whole LAN, bypassing the
gateway's JWT auth, rate limiting, and CORS entirely.

Worst-case combination: ChromaDB (which carries known code-injection and
tenant-authz advisories, GHSA-2wm9-hf6c-p5cr / GHSA-36p7-vc44-83pf /
GHSA-xph7-9rjv-w5fr) was live **unauthenticated** on `0.0.0.0:8100`. An
attacker on the same network could directly ingest into / read / delete the
shared RAG corpus and issue requests to Chroma that it was never meant to
receive from a client.

## Fix applied (bucket A — network isolation)

All host port publishes in `docker-compose.yml` now bind to loopback
(`127.0.0.1:PORT:PORT`) **except** `api-gateway:8000`, which stays on
`0.0.0.0` as the ADR-0001 single ingress. Two datastores got **no host port at
all**:

- **postgres**: dropped (no host publish). This box runs a native Postgres on
  5432, so even a loopback bind collided. Containers reach Postgres by name on
  the private `afrimentor` network. Debug via
  `docker compose exec postgres psql -U afrimentor`.
- **rabbitmq**: dropped its `5672`/`15672` publishes for the same reason
  (native RabbitMQ owns the loopback ports). Consumers use `amqp://rabbitmq`.

The staging (`docker-compose.staging.yml`) and Oracle-public-IP
(`docker-compose.oracle.yml`) overlays already `!reset` these ports and are
unaffected.

## Verification (live, applied)

- `docker compose config` — renders with `host_ip: 127.0.0.1` on every publish
  except `8000`.
- Recreated the running stack + `--force-recreate` on the three services the
  aborted first `up` left untouched. `docker ps` now shows **`0.0.0.0`
  bindings on exactly one container: api-gateway (`0.0.0.0:8000`)**. All 24
  containers healthy.
- End-to-end through the gateway: `/health` healthy; signup + login round trip
  returned JWTs; POST `/api/v1/chat/sessions` created a session — proving
  gateway→auth-user and gateway→chat-orchestration still route fine after the
  recreates (inter-service calls go by container name, not host ports).

## Deferred (logged for follow-up, explicitly out of bucket-A scope)

Confirmed during recon but not implemented in this pass (owner decision —
dependency upgrades and code hardening need their own review cycles):

1. **Dependency CVEs (90 findings across deployed images).** Scanned the exact
   installed versions from all 13 running containers against the OSV database.
   Notable: chromadb 0.5.23 (code injection / RBAC — network-isolated now,
   but upgrade still warranted), starlette 0.41.3 (multipart DoS, Host-header
   poisoning → threatens gateway path checks; needs a fastapi bump that all 13
   services share), python-multipart 0.0.20 (voice form parsing DoS),
   pyjwt 2.10.1 (JWKClient SSRF / HS256 forgery — gateway+auth), jinja2 3.1.4
   (sandbox breakout — persona templates), cryptography 44.0.0 (OpenSSL
   wheels), langchain stack 0.3.13 (template injection, unsafe deserialization,
   XXE — rag-corpus).
2. **LLM prompt-injection defense.** `chat-orchestration-service/app/llm.py`
   `_build_rag_system_message` places retrieved chunks into a system-role
   message with no "untrusted reference data, ignore embedded instructions"
   directive. Red-team dataset (`research/datasets/redteam_high_risk_advice.v1.jsonl`)
   has 7 categories, none covering prompt injection.
3. **Gateway missing TrustedHostMiddleware and body-size limits** — only CORS
   is configured; Host-header poisoning (starlette GHSA-86qp-5c8j-p5mr) is a
   direct hit without it.
4. **Dep-scan tooling in CI** — `scripts/scan-secrets.sh` exists and is clean
   (741 files); no pip-audit/npm-audit job yet.

## How to reproduce the scan

```bash
# installed-version CVE scan (host venv with pip-audit):
docker exec <svc> python -m pip freeze           # one per service
pip-audit -r freeze.txt --service pypi           # merged, but cross-service
                                                  # version drift breaks one env —
                                                  # scan per service instead
bash scripts/scan-secrets.sh                     # secrets sweep: CLEAN
```