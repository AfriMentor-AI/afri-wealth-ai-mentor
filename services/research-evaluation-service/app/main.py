"""Research Evaluation Service — AfriMentor AI microservice stub.

Generated for card O1.2. Real implementation lands in Sprint 5 (cards S5.2, S5.3).
Health endpoint is live so docker-compose health checks pass.

─────────────────────────────────────────────────────────────────────────────
NOTE: This service is NOT the same as the research/ ML workspace at the repo root.

  research/                        ← ML training workspace (card D1.4)
    experiments/                      Runs on ephemeral cloud GPU nodes.
    evaluation/metrics.py             Trains LoRA/DPO/RLHF adapters.
    tracking/                         Heavy deps: PyTorch, PEFT, TRL.
    datasets/                         Never called at runtime in production.

  services/research-evaluation-service/  ← THIS service (Sprint 5)
    Lightweight FastAPI microservice.     Runs 24/7 in docker-compose.
    Consumes RabbitMQ events:             Audits live session quality.
      session.completed                   Detects persona drift.
      feedback.submitted                  Serves the admin research console.
      milestone.completed               Deps: FastAPI, SQLAlchemy only.

The connection between them:
  1. research/evaluation/metrics.py scoring logic will be PORTED (not imported)
     into this service as a lightweight inference-time scorer in Sprint 5 —
     without the heavy ML training dependencies.
  2. Trained adapter weights from research/ are deployed into
     chat-orchestration-service via LLM_MODEL config, not through this service.
─────────────────────────────────────────────────────────────────────────────
"""
import os

from fastapi import FastAPI

from .observability import instrument

SERVICE_NAME = "research-evaluation-service"
SERVICE_VERSION = "0.1.0"

app = FastAPI(
    title="AfriMentor AI — Research Evaluation Service",
    version=SERVICE_VERSION,
    description="Stub service. See docs/adr/0001-microservices-architecture.md",
)

instrument(app, SERVICE_NAME)


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness/readiness probe used by docker-compose and the gateway."""
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "env": os.getenv("APP_ENV", "dev"),
    }


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "service": SERVICE_NAME,
        "message": "Research Evaluation Service online",
        "docs": "/docs",
    }
