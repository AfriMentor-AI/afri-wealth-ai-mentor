#!/usr/bin/env python3
"""Generate an OpenAPI 3.1 contract per microservice (card O1.4).

Run: python scripts/gen_openapi.py
Writes docs/api/<service>.yaml for all 13 services. Endpoint bodies may be TODO for
services not yet implemented; auth & gateway reflect their real v1 endpoints.

Kept as a generator so the 13 contracts stay consistent (shared error schema, security
scheme, server URLs) and regenerating after an endpoint change is one command.
"""
from __future__ import annotations

import pathlib

try:
    import yaml
except ImportError:  # pragma: no cover
    raise SystemExit("PyYAML required: pip install pyyaml")

OUT = pathlib.Path(__file__).resolve().parents[1] / "docs" / "api"
OUT.mkdir(parents=True, exist_ok=True)

GATEWAY = "http://localhost:8000"


def base(title: str, service: str, port: int, description: str) -> dict:
    """Common skeleton: info, servers, security, health, shared components."""
    return {
        "openapi": "3.1.0",
        "info": {
            "title": f"AfriMentor AI — {title}",
            "version": "1.0.0",
            "description": description,
        },
        "servers": [
            {"url": f"{GATEWAY}", "description": "via API gateway"},
            {"url": f"http://localhost:{port}", "description": f"{service} direct (dev)"},
        ],
        "security": [{"bearerAuth": []}],
        "tags": [{"name": "meta"}],
        "paths": {
            "/health": {
                "get": {
                    "tags": ["meta"],
                    "summary": "Liveness/readiness probe",
                    "security": [],
                    "responses": {
                        "200": {
                            "description": "healthy",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Health"}
                                }
                            },
                        }
                    },
                }
            }
        },
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
            },
            "schemas": {
                "Health": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "example": "healthy"},
                        "service": {"type": "string"},
                        "version": {"type": "string"},
                    },
                    "required": ["status", "service"],
                },
                "Error": {
                    "type": "object",
                    "properties": {"detail": {"type": "string"}},
                    "required": ["detail"],
                },
            },
        },
    }


def op(tag: str, summary: str, *, body=None, params=None, resp="200", todo=True) -> dict:
    """Build a single operation; TODO marker flags unimplemented bodies."""
    responses = {
        resp: {
            "description": "success",
            "content": {"application/json": {"schema": {"type": "object"}}},
        },
        "401": {
            "description": "unauthorized",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
        },
    }
    operation = {"tags": [tag], "summary": summary, "responses": responses}
    if todo:
        operation["description"] = "TODO: request/response bodies finalised in later sprint."
    if params:
        operation["parameters"] = params
    if body:
        operation["requestBody"] = {
            "required": True,
            "content": {"application/json": {"schema": body}},
        }
    return operation


ID_PARAM = [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}]


# --------------------------------------------------------------- service specs
def auth_spec() -> dict:
    spec = base(
        "Auth & User Service",
        "auth-user-service",
        8001,
        "Authentication, JWT issuance/refresh, and user profiles. Reflects the "
        "implemented v1 API (card O1.3).",
    )
    schemas = spec["components"]["schemas"]
    schemas["ProfileFields"] = {
        "type": "object",
        "properties": {
            "name": {"type": ["string", "null"]},
            "age": {"type": ["integer", "null"], "minimum": 13, "maximum": 120},
            "country": {"type": ["string", "null"], "minLength": 2, "maxLength": 2},
            "device_type": {"type": ["string", "null"], "enum": ["low_end", "mid", "high", "desktop", None]},
            "sector_interest": {
                "type": ["string", "null"],
                "enum": ["trader", "tech", "fashion_retail", "agriculture", "creative", "other", None],
            },
            "education_level": {
                "type": ["string", "null"],
                "enum": ["none", "primary", "secondary", "vocational", "tertiary", None],
            },
            "language": {"type": ["string", "null"]},
            "income_bracket": {
                "type": ["string", "null"],
                "enum": ["low", "lower_mid", "mid", "upper_mid", "high", None],
            },
        },
    }
    schemas["SignupRequest"] = {
        "allOf": [
            {"$ref": "#/components/schemas/ProfileFields"},
            {
                "type": "object",
                "required": ["email", "password"],
                "properties": {
                    "email": {"type": "string", "format": "email"},
                    "password": {"type": "string", "minLength": 8, "maxLength": 128},
                },
            },
        ]
    }
    schemas["LoginRequest"] = {
        "type": "object",
        "required": ["email", "password"],
        "properties": {
            "email": {"type": "string", "format": "email"},
            "password": {"type": "string"},
        },
    }
    schemas["RefreshRequest"] = {
        "type": "object",
        "required": ["refresh_token"],
        "properties": {"refresh_token": {"type": "string"}},
    }
    schemas["TokenResponse"] = {
        "type": "object",
        "properties": {
            "access_token": {"type": "string"},
            "refresh_token": {"type": "string"},
            "token_type": {"type": "string", "example": "bearer"},
            "expires_in": {"type": "integer", "example": 900},
        },
        "required": ["access_token", "refresh_token", "token_type", "expires_in"],
    }
    schemas["UserResponse"] = {
        "allOf": [
            {"$ref": "#/components/schemas/ProfileFields"},
            {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "email": {"type": "string", "format": "email"},
                    "roles": {"type": "array", "items": {"type": "string"}},
                    "is_active": {"type": "boolean"},
                    "created_at": {"type": "string", "format": "date-time"},
                },
            },
        ]
    }

    def token_op(summary, body_ref, code="200"):
        return {
            "tags": ["auth"],
            "summary": summary,
            "security": [],
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": {"$ref": body_ref}}},
            },
            "responses": {
                code: {
                    "description": "tokens issued",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/TokenResponse"}
                        }
                    },
                },
                "401": {
                    "description": "unauthorized",
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Error"}}
                    },
                },
            },
        }

    spec["tags"] = [{"name": "auth"}, {"name": "meta"}]
    spec["paths"].update(
        {
            "/auth/signup": {
                "post": token_op("Register a new user", "#/components/schemas/SignupRequest", "201")
            },
            "/auth/login": {
                "post": token_op("Authenticate and receive tokens", "#/components/schemas/LoginRequest")
            },
            "/auth/refresh": {
                "post": token_op("Rotate refresh token, issue new pair", "#/components/schemas/RefreshRequest")
            },
            "/auth/logout": {
                "post": {
                    "tags": ["auth"],
                    "summary": "Revoke a refresh token",
                    "security": [],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/RefreshRequest"}
                            }
                        },
                    },
                    "responses": {"204": {"description": "revoked (idempotent)"}},
                }
            },
            "/auth/me": {
                "get": {
                    "tags": ["auth"],
                    "summary": "Get the authenticated user's profile",
                    "responses": {
                        "200": {
                            "description": "profile",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/UserResponse"}
                                }
                            },
                        },
                        "401": {
                            "description": "unauthorized",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Error"}}
                            },
                        },
                    },
                }
            },
            "/auth/.well-known/jwks": {
                "get": {
                    "tags": ["meta"],
                    "summary": "Public key for JWT verification",
                    "security": [],
                    "responses": {"200": {"description": "public key (PEM)"}},
                }
            },
        }
    )
    return spec


def gateway_spec() -> dict:
    spec = base(
        "API Gateway",
        "api-gateway",
        8000,
        "Single ingress. Verifies JWTs, applies per-route rate limits, and proxies to "
        "the 12 capability services under /api/v1/*. Reflects the implemented v1 gateway.",
    )
    spec["tags"] = [{"name": "proxy"}, {"name": "meta"}]
    spec["paths"]["/api/v1/{path}"] = {
        "x-summary": "Reverse proxy to capability services",
        "get": op("proxy", "Proxied GET", params=[
            {"name": "path", "in": "path", "required": True, "schema": {"type": "string"}}
        ]),
        "post": op("proxy", "Proxied POST", params=[
            {"name": "path", "in": "path", "required": True, "schema": {"type": "string"}}
        ]),
    }
    return spec


# service -> (title, port, description, [(method, path, tag, summary, has_body)])
SERVICES: dict[str, tuple] = {
    "intake-profiling-service": (
        "Intake & Profiling Service", 8002,
        "Guided intake flow that builds the initial user profile and financial context.",
        [
            ("post", "/api/v1/intake/sessions", "intake", "Start an intake session", True),
            ("get", "/api/v1/intake/sessions/{id}", "intake", "Get an intake session", False),
            ("post", "/api/v1/intake/sessions/{id}/answers", "intake", "Submit an answer", True),
            ("post", "/api/v1/intake/sessions/{id}/complete", "intake", "Complete intake", False),
        ],
    ),
    "chat-orchestration-service": (
        "Chat Orchestration Service", 8003,
        "Orchestrates a mentor turn: persona + RAG context + history → LLM reply.",
        [
            ("post", "/api/v1/chat/sessions", "chat", "Create a chat session", True),
            ("get", "/api/v1/chat/sessions/{id}", "chat", "Get a chat session", False),
            ("post", "/api/v1/chat/sessions/{id}/messages", "chat", "Send a message", True),
            ("get", "/api/v1/chat/sessions/{id}/messages", "chat", "List messages", False),
        ],
    ),
    "persona-prompt-service": (
        "Persona & Prompt Service", 8004,
        "Persona catalogue, archetype selection, and system-prompt templating.",
        [
            ("get", "/api/v1/personas", "personas", "List personas", False),
            ("get", "/api/v1/personas/{id}", "personas", "Get a persona", False),
            ("post", "/api/v1/personas/select", "personas", "Select a persona for a user", True),
        ],
    ),
    "rag-corpus-service": (
        "RAG Corpus Service", 8005,
        "Corpus ingestion, chunking, embedding, and vector retrieval (ChromaDB).",
        [
            ("post", "/api/v1/rag/documents", "rag", "Ingest a document", True),
            ("get", "/api/v1/rag/documents", "rag", "List documents", False),
            ("get", "/api/v1/rag/documents/export.csv", "rag", "Export the document catalogue as CSV", False),
            ("delete", "/api/v1/rag/documents/{id}", "rag", "Delete a document", False),
            ("get", "/api/v1/rag/stats", "rag", "Corpus index-health statistics", False),
            ("post", "/api/v1/rag/query", "rag", "Retrieve relevant chunks", True),
        ],
    ),
    "goals-milestones-service": (
        "Goals & Milestones Service", 8006,
        "Goals & milestones CRUD and milestone state machine. Publishes goal.* events.",
        [
            ("post", "/api/v1/goals", "goals", "Create a goal", True),
            ("get", "/api/v1/goals", "goals", "List goals", False),
            ("get", "/api/v1/goals/{id}", "goals", "Get a goal", False),
            ("patch", "/api/v1/goals/{id}", "goals", "Update a goal", True),
            ("post", "/api/v1/goals/{id}/milestones", "goals", "Add a milestone", True),
            ("post", "/api/v1/milestones/{id}/complete", "goals", "Complete a milestone", False),
        ],
    ),
    "progress-gamification-service": (
        "Progress & Gamification Service", 8007,
        "XP, streaks, badges and levels. Reacts to milestone/session events.",
        [
            ("get", "/api/v1/progress", "progress", "Get the user's progress summary", False),
            ("get", "/api/v1/progress/badges", "progress", "List earned badges", False),
            ("get", "/api/v1/progress/streak", "progress", "Get current streak", False),
        ],
    ),
    "insight-library-service": (
        "Insight Library Service", 8008,
        "Curated insight articles/cards, categories and bookmarks.",
        [
            ("get", "/api/v1/insights", "insights", "List insights", False),
            ("get", "/api/v1/insights/{id}", "insights", "Get an insight", False),
            ("post", "/api/v1/insights/{id}/bookmark", "insights", "Bookmark an insight", False),
            ("get", "/api/v1/insights/bookmarks", "insights", "List bookmarks", False),
        ],
    ),
    "feedback-service": (
        "Feedback Service", 8009,
        "Post-session surveys, thumbs, and free-text feedback capture.",
        [
            ("post", "/api/v1/feedback", "feedback", "Submit feedback", True),
            ("get", "/api/v1/feedback/surveys/{id}", "feedback", "Get a survey definition", False),
        ],
    ),
    "research-evaluation-service": (
        "Research & Evaluation Service", 8010,
        "Session auditing, quality scoring, and drift detection for the research console.",
        [
            ("get", "/api/v1/research/audits", "research", "List session audits", False),
            ("post", "/api/v1/research/audits", "research", "Trigger an audit", True),
            ("get", "/api/v1/research/drift", "research", "Get drift-detection results", False),
        ],
    ),
    "voice-service": (
        "Voice Service", 8011,
        "Speech-to-text and text-to-speech for the mentor chat.",
        [
            ("post", "/api/v1/voice/transcribe", "voice", "Transcribe uploaded audio", True),
            ("post", "/api/v1/voice/synthesize", "voice", "Synthesize speech from text", True),
        ],
    ),
    "notification-service": (
        "Notification Service", 8012,
        "Push/in-app/email notifications. Reacts to domain events.",
        [
            ("get", "/api/v1/notifications", "notifications", "List notifications", False),
            ("post", "/api/v1/notifications/{id}/read", "notifications", "Mark as read", False),
            ("post", "/api/v1/notifications/read-all", "notifications", "Mark all as read", False),
        ],
    ),
}


def generic_spec(service: str) -> dict:
    title, port, desc, endpoints = SERVICES[service]
    spec = base(title, service, port, desc)
    tags = {e[2] for e in endpoints}
    spec["tags"] = [{"name": t} for t in sorted(tags)] + [{"name": "meta"}]
    for method, path, tag, summary, has_body in endpoints:
        params = ID_PARAM if "{id}" in path else None
        body = {"type": "object"} if has_body else None
        code = "201" if method == "post" and path.endswith("s") else "200"
        spec["paths"].setdefault(path, {})[method] = op(
            tag, summary, body=body, params=params, resp=code
        )
    return spec


def main() -> None:
    written = []
    for name, spec in [
        ("api-gateway", gateway_spec()),
        ("auth-user-service", auth_spec()),
    ]:
        path = OUT / f"{name}.yaml"
        path.write_text(yaml.safe_dump(spec, sort_keys=False, width=100), encoding="utf-8")
        written.append(path.name)

    for service in SERVICES:
        path = OUT / f"{service}.yaml"
        path.write_text(
            yaml.safe_dump(generic_spec(service), sort_keys=False, width=100), encoding="utf-8"
        )
        written.append(path.name)

    print(f"Wrote {len(written)} OpenAPI contracts to {OUT}:")
    for name in sorted(written):
        print(f"  - {name}")


if __name__ == "__main__":
    main()
