"""Gateway routing table (kept as data so a Kong/Traefik migration is mechanical).

Each Route maps an incoming path prefix to an upstream service. `protected=False` routes
are reachable without a JWT (auth endpoints, health). Everything else requires a valid
access token, verified at the edge (ADR-0001 §D4/§D5).
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    prefix: str  # incoming path prefix, e.g. "/api/v1/goals"
    upstream_env: str  # env var holding the upstream base URL
    default_upstream: str
    protected: bool = True
    rate_limit: int | None = None  # per-window override; None = gateway default
    strip_prefix: bool = False  # if true, remove /api/v1 before forwarding upstream
    
    @property
    def upstream(self) -> str:
        return os.getenv(self.upstream_env, self.default_upstream)


# Order matters: the first matching prefix wins, so list more specific prefixes first.
ROUTES: list[Route] = [
    # public
    Route("/api/v1/auth", "AUTH_SERVICE_URL", "http://localhost:8001",
          protected=False, rate_limit=20, strip_prefix=True),
    # protected capability services
    Route("/api/v1/intake", "INTAKE_SERVICE_URL", "http://localhost:8002"),
    # Diagnostic profiles are served by intake-profiling-service too (card O2.2).
    Route("/api/v1/profiles", "INTAKE_SERVICE_URL", "http://localhost:8002"),
    Route("/api/v1/chat", "CHAT_SERVICE_URL", "http://localhost:8003"),
    Route("/api/v1/personas", "PERSONA_SERVICE_URL", "http://localhost:8004"),
    Route("/api/v1/rag", "RAG_SERVICE_URL", "http://localhost:8005"),
    Route("/api/v1/goals", "GOALS_SERVICE_URL", "http://localhost:8006"),
    Route("/api/v1/progress", "PROGRESS_SERVICE_URL", "http://localhost:8007"),
    Route("/api/v1/insights", "INSIGHT_SERVICE_URL", "http://localhost:8008"),
    Route("/api/v1/feedback", "FEEDBACK_SERVICE_URL", "http://localhost:8009"),
    Route("/api/v1/research", "RESEARCH_SERVICE_URL", "http://localhost:8010"),
    Route("/api/v1/voice", "VOICE_SERVICE_URL", "http://localhost:8011"),
    Route("/api/v1/notifications", "NOTIFICATION_SERVICE_URL", "http://localhost:8012"),
]


def match_route(path: str) -> Route | None:
    for route in ROUTES:
        if path == route.prefix or path.startswith(route.prefix + "/"):
            return route
    return None
