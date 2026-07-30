"""Intake Profiling Service — AfriMentor AI microservice stub.

Generated for card O1.2. Real implementation lands in later sprints.
Health endpoint is live so docker-compose health checks pass.
"""
import os

from fastapi import FastAPI

SERVICE_NAME = "intake-profiling-service"
SERVICE_VERSION = "0.1.0"

app = FastAPI(
    title="AfriMentor AI — Intake Profiling Service",
    version=SERVICE_VERSION,
    description="Stub service. See docs/adr/0001-microservices-architecture.md",
)


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
    return {"service": SERVICE_NAME, "message": "Intake Profiling Service online", "docs": "/docs"}
