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
    schemas["ProfileUpdateRequest"] = {"$ref": "#/components/schemas/ProfileFields"}
    schemas["PasswordResetRequestSchema"] = {
        "type": "object",
        "required": ["email"],
        "properties": {"email": {"type": "string", "format": "email"}},
    }
    schemas["PasswordResetRequestResponse"] = {
        "type": "object",
        "properties": {
            "detail": {"type": "string"},
            "reset_token": {
                "type": ["string", "null"],
                "description": "Only populated outside prod — no email provider is wired up yet.",
            },
        },
    }
    schemas["PasswordResetConfirmRequest"] = {
        "type": "object",
        "required": ["reset_token", "new_password"],
        "properties": {
            "reset_token": {"type": "string"},
            "new_password": {"type": "string", "minLength": 8, "maxLength": 128},
        },
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
                },
                "patch": {
                    "tags": ["auth"],
                    "summary": "Partially update the authenticated user's profile",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ProfileUpdateRequest"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "updated profile",
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
                },
                "delete": {
                    "tags": ["auth"],
                    "summary": "Deactivate the authenticated user's account and revoke its sessions",
                    "responses": {
                        "204": {"description": "deactivated"},
                        "401": {
                            "description": "unauthorized",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Error"}}
                            },
                        },
                    },
                },
            },
            "/auth/password-reset/request": {
                "post": {
                    "tags": ["auth"],
                    "summary": "Request a password-reset token",
                    "security": [],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PasswordResetRequestSchema"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": (
                                "Same response whether or not the email is registered, "
                                "so this endpoint can't be used to enumerate accounts."
                            ),
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/PasswordResetRequestResponse"
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/auth/password-reset/confirm": {
                "post": {
                    "tags": ["auth"],
                    "summary": "Confirm a password reset with the issued token",
                    "security": [],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PasswordResetConfirmRequest"}
                            }
                        },
                    },
                    "responses": {
                        "204": {"description": "password changed, sessions revoked"},
                        "400": {
                            "description": "invalid or expired reset token",
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


def intake_spec() -> dict:
    spec = base(
        "Intake Profiling Service",
        "intake-profiling-service",
        8002,
        "Backs the 4-step Intake flow and exposes the resulting diagnostic profile. "
        "Reflects the implemented v1 API (card O2.2).",
    )
    schemas = spec["components"]["schemas"]
    schemas["IntakeStep"] = {
        "type": "string",
        "enum": ["sector", "education_time", "constraints", "confirm"],
    }
    schemas["AnswerSubmitRequest"] = {
        "type": "object",
        "required": ["step", "payload"],
        "properties": {
            "step": {"$ref": "#/components/schemas/IntakeStep"},
            "payload": {
                "type": "object",
                "description": "Shape depends on `step`: sector={sector}, "
                "education_time={education_level,time_available_per_week}, "
                "constraints={constraints:[]}, confirm={name,business_name,location}.",
            },
        },
    }
    schemas["AnswerResponse"] = {
        "type": "object",
        "properties": {
            "step": {"$ref": "#/components/schemas/IntakeStep"},
            "payload": {"type": "object"},
            "updated_at": {"type": "string", "format": "date-time"},
        },
    }
    schemas["SessionResponse"] = {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "user_id": {"type": "string"},
            "status": {"type": "string", "enum": ["in_progress", "completed"]},
            "started_at": {"type": "string", "format": "date-time"},
            "completed_at": {"type": ["string", "null"], "format": "date-time"},
            "answers": {"type": "array", "items": {"$ref": "#/components/schemas/AnswerResponse"}},
        },
    }
    schemas["DiagnosticProfileResponse"] = {
        "type": "object",
        "properties": {
            "user_id": {"type": "string"},
            "name": {"type": "string"},
            "business_name": {"type": "string"},
            "location": {"type": "string"},
            "sector": {"type": "string"},
            "education_level": {"type": "string"},
            "time_available_per_week": {"type": "string"},
            "constraints": {"type": "array", "items": {"type": "string"}},
            "persona_id": {"type": ["string", "null"]},
            "created_at": {"type": "string", "format": "date-time"},
            "updated_at": {"type": "string", "format": "date-time"},
        },
    }

    spec["tags"] = [{"name": "intake"}, {"name": "profiles"}, {"name": "meta"}]
    session_response = {
        "200": {
            "description": "session",
            "content": {
                "application/json": {"schema": {"$ref": "#/components/schemas/SessionResponse"}}
            },
        },
        "401": {
            "description": "missing X-User-Id",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
        },
        "404": {
            "description": "session not found (or not owned by the caller)",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
        },
    }
    spec["paths"].update(
        {
            "/api/v1/intake/sessions": {
                "post": {
                    "tags": ["intake"],
                    "summary": "Start (or resume) the caller's intake session",
                    "responses": {
                        "201": session_response["200"],
                        "200": {
                            **session_response["200"],
                            "description": "resumed an existing in-progress session",
                        },
                        "401": session_response["401"],
                    },
                }
            },
            "/api/v1/intake/sessions/{id}": {
                "get": {
                    "tags": ["intake"],
                    "summary": "Get an intake session and its answers so far",
                    "parameters": ID_PARAM,
                    "responses": session_response,
                }
            },
            "/api/v1/intake/sessions/{id}/answers": {
                "post": {
                    "tags": ["intake"],
                    "summary": "Submit (or update) the answer for one intake step",
                    "parameters": ID_PARAM,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/AnswerSubmitRequest"}
                            }
                        },
                    },
                    "responses": {
                        **session_response,
                        "409": {"description": "session already completed"},
                        "422": {"description": "payload doesn't match the shape for `step`"},
                    },
                }
            },
            "/api/v1/intake/sessions/{id}/complete": {
                "post": {
                    "tags": ["intake"],
                    "summary": "Mark intake complete and build the diagnostic profile",
                    "parameters": ID_PARAM,
                    "responses": {
                        **session_response,
                        "400": {"description": "one or more required steps have no answer yet"},
                        "409": {"description": "session already completed"},
                    },
                }
            },
            "/api/v1/profiles/{userId}/diagnostic": {
                "get": {
                    "tags": ["profiles"],
                    "summary": "Get a user's diagnostic profile",
                    "description": "Called via the gateway by the end user (X-User-Id must match "
                    "userId) or service-to-service on the internal network (no X-User-Id, "
                    "trusted) — e.g. by Chat Orchestration for personalization.",
                    "parameters": [
                        {
                            "name": "userId",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "diagnostic profile",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/DiagnosticProfileResponse"
                                    }
                                }
                            },
                        },
                        "403": {"description": "X-User-Id doesn't match userId"},
                        "404": {"description": "no diagnostic profile for this user yet"},
                    },
                }
            },
        }
    )
    return spec


def goals_spec() -> dict:
    spec = base(
        "Goals & Milestones Service",
        "goals-milestones-service",
        8006,
        "Goals CRUD, milestone state machine (card O2.3), and tagged commitments "
        "pipeline (card D2.3). Reflects the implemented v1 API.",
    )
    schemas = spec["components"]["schemas"]
    schemas["GoalCreate"] = {
        "type": "object",
        "required": ["title"],
        "properties": {
            "title": {"type": "string", "minLength": 1, "maxLength": 255},
            "description": {"type": ["string", "null"]},
            "deadline": {"type": ["string", "null"], "format": "date"},
        },
    }
    schemas["GoalUpdate"] = {
        "type": "object",
        "properties": {
            "title": {"type": ["string", "null"], "minLength": 1, "maxLength": 255},
            "description": {"type": ["string", "null"]},
            "deadline": {"type": ["string", "null"], "format": "date"},
        },
    }
    schemas["GoalResponse"] = {
        "type": "object",
        "required": [
            "id", "user_id", "title", "status", "progress_pct", "created_at", "updated_at",
        ],
        "properties": {
            "id": {"type": "string"},
            "user_id": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": ["string", "null"]},
            "status": {"type": "string", "enum": ["active", "completed", "abandoned"]},
            "deadline": {"type": ["string", "null"], "format": "date"},
            "progress_pct": {
                "type": "integer",
                "description": "Server-computed % of this goal's milestones with status 'done'.",
            },
            "created_at": {"type": "string", "format": "date-time"},
            "updated_at": {"type": "string", "format": "date-time"},
        },
    }
    schemas["MilestoneStatus"] = {
        "type": "string",
        "enum": ["done", "in_progress", "blocked", "upcoming"],
    }
    schemas["MilestoneCreate"] = {
        "type": "object",
        "required": ["title"],
        "properties": {
            "title": {"type": "string", "minLength": 1, "maxLength": 160},
            "status": {"$ref": "#/components/schemas/MilestoneStatus"},
            "order": {"type": "integer", "minimum": 0},
        },
    }
    schemas["MilestoneUpdate"] = {
        "type": "object",
        "properties": {
            "title": {"type": ["string", "null"], "minLength": 1, "maxLength": 160},
            "status": {"$ref": "#/components/schemas/MilestoneStatus"},
            "order": {"type": "integer", "minimum": 0},
        },
    }
    schemas["MilestoneResponse"] = {
        "type": "object",
        "required": ["id", "goal_id", "title", "status", "order", "created_at", "updated_at"],
        "properties": {
            "id": {"type": "string"},
            "goal_id": {"type": "string"},
            "title": {"type": "string"},
            "status": {"$ref": "#/components/schemas/MilestoneStatus"},
            "order": {"type": "integer"},
            "created_at": {"type": "string", "format": "date-time"},
            "updated_at": {"type": "string", "format": "date-time"},
        },
    }
    schemas["CommitmentCreate"] = {
        "type": "object",
        "required": ["user_id", "conversation_id", "message_id", "content"],
        "properties": {
            "user_id": {"type": "string"},
            "conversation_id": {"type": "string"},
            "message_id": {"type": "string"},
            "content": {"type": "string", "minLength": 1, "maxLength": 2000},
        },
    }
    schemas["CommitmentResponse"] = {
        "type": "object",
        "required": [
            "id", "goal_id", "user_id", "conversation_id", "message_id", "content", "created_at",
        ],
        "properties": {
            "id": {"type": "string"},
            "goal_id": {"type": "string"},
            "user_id": {"type": "string"},
            "conversation_id": {"type": "string"},
            "message_id": {"type": "string"},
            "content": {"type": "string"},
            "created_at": {"type": "string", "format": "date-time"},
        },
    }

    unauth_401 = {
        "description": "missing/invalid X-User-Id",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
    }
    not_found_404 = {
        "description": "resource not found (or not owned by the caller)",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
    }
    goal_response = {
        "200": {
            "description": "goal",
            "content": {
                "application/json": {"schema": {"$ref": "#/components/schemas/GoalResponse"}}
            },
        },
        "401": unauth_401,
        "404": not_found_404,
    }
    milestone_response = {
        "200": {
            "description": "milestone",
            "content": {
                "application/json": {"schema": {"$ref": "#/components/schemas/MilestoneResponse"}}
            },
        },
        "401": unauth_401,
        "404": not_found_404,
    }

    spec["tags"] = [{"name": "goals"}, {"name": "milestones"}, {"name": "meta"}]
    spec["paths"].update(
        {
            "/api/v1/goals": {
                "post": {
                    "tags": ["goals"],
                    "summary": "Create a goal",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/GoalCreate"}
                            }
                        },
                    },
                    "responses": {
                        "201": goal_response["200"],
                        "401": unauth_401,
                    },
                },
                "get": {
                    "tags": ["goals"],
                    "summary": "List the caller's active goals",
                    "responses": {
                        "200": {
                            "description": "goals",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/GoalResponse"},
                                    }
                                }
                            },
                        },
                        "401": unauth_401,
                    },
                },
            },
            "/api/v1/goals/{id}": {
                "get": {
                    "tags": ["goals"],
                    "summary": "Get a goal",
                    "parameters": ID_PARAM,
                    "responses": goal_response,
                },
                "patch": {
                    "tags": ["goals"],
                    "summary": "Partially update a goal",
                    "parameters": ID_PARAM,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/GoalUpdate"}
                            }
                        },
                    },
                    "responses": goal_response,
                },
                "delete": {
                    "tags": ["goals"],
                    "summary": "Delete a goal (cascades its milestones and commitments)",
                    "parameters": ID_PARAM,
                    "responses": {
                        "204": {"description": "deleted"},
                        "401": unauth_401,
                        "404": not_found_404,
                    },
                },
            },
            "/api/v1/goals/{id}/milestones": {
                "post": {
                    "tags": ["milestones"],
                    "summary": "Add a milestone to a goal",
                    "parameters": ID_PARAM,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/MilestoneCreate"}
                            }
                        },
                    },
                    "responses": {
                        "201": milestone_response["200"],
                        "401": unauth_401,
                        "404": not_found_404,
                    },
                },
                "get": {
                    "tags": ["milestones"],
                    "summary": "List a goal's milestones in display order",
                    "parameters": ID_PARAM,
                    "responses": {
                        "200": {
                            "description": "milestones",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/MilestoneResponse"},
                                    }
                                }
                            },
                        },
                        "401": unauth_401,
                        "404": not_found_404,
                    },
                },
            },
            "/api/v1/milestones/{id}": {
                "patch": {
                    "tags": ["milestones"],
                    "summary": "Update a milestone (title, status, order)",
                    "parameters": ID_PARAM,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/MilestoneUpdate"}
                            }
                        },
                    },
                    "responses": milestone_response,
                },
                "delete": {
                    "tags": ["milestones"],
                    "summary": "Delete a milestone",
                    "parameters": ID_PARAM,
                    "responses": {
                        "204": {"description": "deleted"},
                        "401": unauth_401,
                        "404": not_found_404,
                    },
                },
            },
            "/api/v1/milestones/{id}/complete": {
                "post": {
                    "tags": ["milestones"],
                    "summary": "Mark a milestone done",
                    "parameters": ID_PARAM,
                    "responses": milestone_response,
                },
            },
            "/api/v1/goals/{id}/commitments": {
                "post": {
                    "tags": ["goals"],
                    "summary": "Persist a tagged commitment (internal — chat-orchestration)",
                    "description": "Called by chat-orchestration-service when the user confirms "
                    "'Yes, Tag It'. No X-User-Id gate — internal network call.",
                    "parameters": ID_PARAM,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CommitmentCreate"}
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "commitment",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/CommitmentResponse"
                                    }
                                }
                            },
                        },
                        "404": not_found_404,
                        "409": {
                            "description": "message already tagged as a commitment",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Error"}
                                }
                            },
                        },
                    },
                },
                "get": {
                    "tags": ["goals"],
                    "summary": "List a goal's tagged commitments",
                    "parameters": ID_PARAM,
                    "responses": {
                        "200": {
                            "description": "commitments",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "$ref": "#/components/schemas/CommitmentResponse"
                                        },
                                    }
                                }
                            },
                        },
                        "401": unauth_401,
                        "404": not_found_404,
                    },
                },
            },
        }
    )
    return spec


def insight_spec() -> dict:
    spec = base(
        "Insight Library Service",
        "insight-library-service",
        8008,
        "Curated insight articles/audio (card O3.2): catalog, search/filter, and "
        "per-user favorites/bookmarks.",
    )
    spec["components"]["responses"] = {
        "Unauthorized": {
            "description": "unauthorized",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
        }
    }
    schemas = spec["components"]["schemas"]
    schemas["InsightItemCreate"] = {
        "type": "object",
        "required": ["title", "summary", "category", "duration_minutes"],
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "category": {"type": "string"},
            "duration_minutes": {"type": "integer"},
            "is_audio": {"type": "boolean", "default": False},
            "media_url": {"type": ["string", "null"]},
        },
    }
    schemas["InsightItem"] = {
        "type": "object",
        "required": [
            "id", "title", "summary", "category", "duration_minutes",
            "is_audio", "created_at", "is_favorited",
        ],
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "category": {"type": "string"},
            "duration_minutes": {"type": "integer"},
            "is_audio": {"type": "boolean"},
            "media_url": {"type": ["string", "null"]},
            "created_at": {"type": "string", "format": "date-time"},
            "is_favorited": {"type": "boolean"},
        },
    }

    unauthorized = {"$ref": "#/components/responses/Unauthorized"}
    id_param = [{"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}]
    spec["tags"] = [{"name": "insights"}, {"name": "meta"}]
    spec["paths"].update(
        {
            "/api/v1/insights": {
                "get": {
                    "tags": ["insights"],
                    "summary": "List insights",
                    "parameters": [
                        {
                            "name": "search",
                            "in": "query",
                            "schema": {"type": "string"},
                            "description": "Matches title or summary (case-insensitive substring).",
                        },
                        {"name": "category", "in": "query", "schema": {"type": "string"}},
                        {"name": "is_audio", "in": "query", "schema": {"type": "boolean"}},
                    ],
                    "responses": {
                        "200": {
                            "description": "success",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/InsightItem"},
                                    }
                                }
                            },
                        },
                        "401": unauthorized,
                    },
                },
                "post": {
                    "tags": ["insights"],
                    "summary": "Create a catalog entry (admin role required)",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/InsightItemCreate"}
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "created",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/InsightItem"}
                                }
                            },
                        },
                        "401": unauthorized,
                        "403": {"description": "admin role required"},
                    },
                },
            },
            "/api/v1/insights/{id}": {
                "get": {
                    "tags": ["insights"],
                    "summary": "Get an insight",
                    "parameters": id_param,
                    "responses": {
                        "200": {
                            "description": "success",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/InsightItem"}
                                }
                            },
                        },
                        "401": unauthorized,
                        "404": {"description": "not found"},
                    },
                }
            },
            "/api/v1/insights/{id}/bookmark": {
                "post": {
                    "tags": ["insights"],
                    "summary": "Bookmark an insight (idempotent)",
                    "parameters": id_param,
                    "responses": {
                        "204": {"description": "bookmarked"},
                        "401": unauthorized,
                        "404": {"description": "not found"},
                    },
                },
                "delete": {
                    "tags": ["insights"],
                    "summary": "Remove a bookmark (idempotent)",
                    "parameters": id_param,
                    "responses": {
                        "204": {"description": "removed"},
                        "401": unauthorized,
                    },
                },
            },
            "/api/v1/insights/bookmarks": {
                "get": {
                    "tags": ["insights"],
                    "summary": "List the current user's bookmarked insights",
                    "responses": {
                        "200": {
                            "description": "success",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/InsightItem"},
                                    }
                                }
                            },
                        },
                        "401": unauthorized,
                    },
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
            ("get", "/personas/chioma", "personas", "Get the CHIOMA persona profile spec", False),
            ("get", "/personas/chioma/prompt", "personas", "Render the CHIOMA system prompt", False),
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
    "progress-gamification-service": (
        "Progress & Gamification Service", 8007,
        "XP, streaks, badges and levels. Reacts to milestone/session events.",
        [
            ("get", "/api/v1/progress", "progress", "Get the user's progress summary", False),
            ("get", "/api/v1/progress/badges", "progress", "List earned badges", False),
            ("get", "/api/v1/progress/streak", "progress", "Get current streak", False),
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
        ("intake-profiling-service", intake_spec()),
        ("goals-milestones-service", goals_spec()),
        ("insight-library-service", insight_spec()),
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
