# Observability stack (card O2.5)

A self-hosted metrics + logs + traces stack that runs inside the same Compose
network as the services, so the whole thing boots with `docker compose up`.

| Component | Ports (dev) | What it does |
|---|---|---|
| Prometheus | `9090` | Scrapes every service's `GET /metrics` (see `infra/prometheus/prometheus.yml`) |
| Grafana | `3001` | Dashboards + alerting. Login `admin`/`admin` (dev), `admin`/`$GF_SECURITY_ADMIN_PASSWORD` (staging) |
| Loki | `3100` | Centralised log store |
| Promtail | (internal) | Ships container stdout → Loki, only for containers labelled `logging=promtail` |
| Jaeger | `16686` | Trace store + UI; services export OTLP/gRPC to `jaeger:4317` |

Dashboards are auto-provisioned from `infra/grafana/provisioning/` (Prometheus + Loki
datasources and the "AfriMentor AI — Service Latency & Error Rate" dashboard).

## What gets instrumented

`scripts/gen_observability.py` copies a shared template into every service as
`app/observability.py`, then wires three things into each service's `main.py`:

1. **Prometheus request metrics** — `GET /metrics` exposed by
   `prometheus-fastapi-instrumentator` (`/health` and `/metrics` themselves are
   excluded so probes don't pollute the latency histograms).
2. **OpenTelemetry tracing** — the FastAPI + httpx instrumentors; each service exports
   spans over OTLP/gRPC to `OTEL_EXPORTER_OTLP_ENDPOINT` when that variable is set
   (bare `uvicorn` runs default to *no* export). The W3C `traceparent` header is what
   makes one request span the whole chain: gateway → service → DB.
3. **JSON logs** — log lines are emitted as single JSON objects on stdout, carrying the
   active `trace_id`/`span_id` so a log line links to its trace in Grafana. Promtail
   ships them to Loki; no code-side log shipping.

Datastore-owning services additionally call `instrument_db(engine)` (SQLAlchemy spans).

### Adding a new service

```bash
# add the service name to SERVICES (and DB_SERVICES if it owns a SQLAlchemy engine)
python scripts/gen_observability.py
```

Idempotent — safe to re-run. Edit the shared template
(`scripts/_observability_module_template.py`), not a service's copy, or the next regen
overwrites your change.

## Using it

```bash
docker compose up -d          # boots the stack + all services
```

- Metrics: <http://localhost:9090> (Prometheus) or **Grafana → Explore → Prometheus**
- Logs: **Grafana → Explore → Loki** (filter e.g. `{service="goals-milestones-service"}`)
- Traces: <http://localhost:16686> (Jaeger UI)
- Dashboard: <http://localhost:3001/d/afrimentor-services> (Grafana uses 3001 so it doesn't clash with the Next.js dev server on 3000)

Grafana login for dev is `admin`/`admin` (single-node dev only — staging overrides the
password, see `docker-compose.staging.yml`).

## Staging

The same stack runs in the staging overlay (`docker-compose.staging.yml`) with no host
ports and `-staging`-suffixed volumes. Grafana's admin password is read from
`GF_SECURITY_ADMIN_PASSWORD` (required — the overlay fails fast if unset).

## Security notes

- Datastores and the observability stack are **internal to the compose network** in
  staging; dev publishes ports for local tooling only.
- Prometheus/Grafana/Jaeger host ports are for local development; a real deployment
  (O5.3) fronts them behind auth/TLS instead.
- No secrets are committed: the staging Grafana password is environment-supplied, and
  `infra/keys/` (JWT) is gitignored.
