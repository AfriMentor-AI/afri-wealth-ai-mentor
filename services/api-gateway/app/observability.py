"""Shared observability bootstrap: Prometheus metrics + OpenTelemetry tracing +
structured JSON logs (card O2.5).

Duplicated into every service's app/ directory by scripts/gen_observability.py so each
service stays an independently-buildable Docker image (no shared-library mechanism
exists in this monorepo) — edit the template there, not a single service's copy, or the
next regen will overwrite your change.

`instrument(app, SERVICE_NAME)` is the one call each service's main.py makes, right
after constructing the FastAPI app:
  - GET /metrics: Prometheus request-count/latency histograms, scraped by
    infra/prometheus/prometheus.yml — this is what backs the Grafana "per-service
    latency & error rate" dashboard (docs/observability.md).
  - OTLP trace export to Jaeger. FastAPI's instrumentor extracts the incoming
    W3C traceparent header (if the caller — e.g. the gateway, or another service —
    sent one); httpx's instrumentor injects it on every outbound call. That's the
    entire mechanism behind "a trace spans gateway -> service -> DB": every hop
    automatically joins the same trace, no manual context-passing needed.
  - JSON logs on stdout carrying the active trace_id/span_id, shipped to Loki by
    Promtail (reads container stdout — no code-side log shipping needed).

`instrument_db(engine)` is a second, optional call for services that own a SQLAlchemy
engine — it adds DB query spans as children of the request span. Call it once, right
after the engine is created (see auth-user-service/app/database.py for the pattern).
"""
from __future__ import annotations

import json
import logging
import os
import sys

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME as OTEL_SERVICE_NAME
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_fastapi_instrumentator import Instrumentator


class _JsonLogFormatter(logging.Formatter):
    """One JSON object per line, carrying the active span's trace/span id (if any) so
    a log line and the trace it happened during can be cross-referenced in Grafana."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            payload["trace_id"] = format(span_context.trace_id, "032x")
            payload["span_id"] = format(span_context.span_id, "016x")
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def _configure_json_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonLogFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO"))


def instrument(app: FastAPI, service_name: str) -> None:
    """Call once, immediately after `app = FastAPI(...)`."""
    _configure_json_logging()

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if otlp_endpoint:
        provider = TracerProvider(resource=Resource.create({OTEL_SERVICE_NAME: service_name}))
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
        )
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()

    # exclude /health and /metrics themselves so liveness probes don't pollute the
    # request-latency histograms the Grafana dashboard reads.
    Instrumentator(excluded_handlers=["/health", "/metrics"]).instrument(app).expose(
        app, endpoint="/metrics", include_in_schema=False
    )


def instrument_db(engine) -> None:
    """Optional: call once after creating a SQLAlchemy engine, so queries show up as
    child spans of the request that triggered them."""
    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", ""):
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument(engine=engine)
