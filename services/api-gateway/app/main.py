"""API Gateway — AfriMentor AI (card O1.3).

Single ingress: routing table → JWT verification → per-route rate limit → proxy to
upstream with a trusted identity header. See docs/adr/0001-microservices-architecture.md.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .auth import TokenError, verify_access_token
from .config import get_settings
from .observability import instrument
from .ratelimit import check_rate_limit
from .routes import ROUTES, match_route

SERVICE_NAME = "api-gateway"
SERVICE_VERSION = "1.0.0"
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Card O5.1 / BUG-01: a fresh httpx.AsyncClient per request exhausted file
    descriptors/sockets under load (each `async with httpx.AsyncClient(...)`
    opens its own connection pool that's torn down at the end of that one
    request instead of being reused). One shared, pooled client for the whole
    process's lifetime fixes it — sized well above the 60-user load test in
    docs/deployment/o4-3-pilot-load-test-report.md.
    """
    app.state.client = httpx.AsyncClient(
        limits=httpx.Limits(max_connections=500, max_keepalive_connections=100),
        timeout=settings.upstream_timeout_seconds,
    )
    try:
        yield
    finally:
        await app.state.client.aclose()


app = FastAPI(
    title="AfriMentor AI — API Gateway",
    version=SERVICE_VERSION,
    description="Edge routing, JWT verification, and rate limiting.",
    lifespan=lifespan,
)

instrument(app, SERVICE_NAME)

# Mobile app + admin console origins (supports local, Codespaces, and Vercel).
_cors_origins_raw = os.getenv("CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()] or [
    "http://localhost:3000",
    "http://localhost:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"^https://.*\.app\.github\.dev$|^https://.*\.vercel\.app$"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Headers that must never be forwarded from the client (identity is set by us only).
_STRIP_REQUEST_HEADERS = {"host", "content-length", "x-user-id", "x-user-roles"}
_STRIP_RESPONSE_HEADERS = {"content-length", "transfer-encoding", "connection"}


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "healthy", "service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "service": SERVICE_NAME,
        "message": "API Gateway online",
        "routes": [r.prefix for r in ROUTES],
    }


def _client_identity(request: Request, user_id: str | None) -> str:
    if user_id:
        return f"user:{user_id}"
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        ip = fwd.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"
    return f"ip:{ip}"


@app.api_route(
    "/api/v1/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    tags=["proxy"],
)
async def gateway(path: str, request: Request) -> Response:
    full_path = "/api/v1/" + path
    route = match_route(full_path)
    if route is None:
        return JSONResponse({"detail": "no matching route"}, status_code=404)

    # --- authentication (protected routes only) ---
    user_id: str | None = None
    roles: list[str] = []
    if route.protected:
        authz = request.headers.get("authorization", "")
        if not authz.lower().startswith("bearer "):
            return JSONResponse({"detail": "missing bearer token"}, status_code=401)
        try:
            claims = await verify_access_token(authz.split(" ", 1)[1])
        except TokenError as exc:
            return JSONResponse({"detail": f"unauthorized: {exc}"}, status_code=401)
        user_id = claims.get("sub")
        roles = claims.get("roles", [])

    # --- rate limiting ---
    limit = route.rate_limit or settings.rate_limit_requests
    identity = _client_identity(request, user_id)
    allowed = await check_rate_limit(
        identity, route.prefix, limit, settings.rate_limit_window_seconds
    )
    if not allowed:
        return JSONResponse(
            {"detail": "rate limit exceeded"},
            status_code=429,
            headers={"Retry-After": str(settings.rate_limit_window_seconds)},
        )

    # --- proxy to upstream ---
    upstream_path = full_path[len("/api/v1") :] if route.strip_prefix else full_path
    upstream_url = route.upstream + upstream_path
    fwd_headers = {
        k: v for k, v in request.headers.items() if k.lower() not in _STRIP_REQUEST_HEADERS
    }
    if user_id:
        fwd_headers["X-User-Id"] = user_id
        fwd_headers["X-User-Roles"] = ",".join(roles)

    body = await request.body()
    client: httpx.AsyncClient = request.app.state.client
    if full_path.endswith("/messages/stream"):
        async def events():
            try:
                # No timeout on the streaming call specifically — a long-lived SSE
                # response shouldn't be cut off by the client's default upstream
                # timeout, even though the client itself is now shared/pooled.
                async with client.stream(
                    request.method,
                    upstream_url,
                    params=dict(request.query_params),
                    headers=fwd_headers,
                    content=body,
                    timeout=None,
                ) as upstream_resp:
                    async for chunk in upstream_resp.aiter_bytes():
                        yield chunk
            except httpx.RequestError:
                yield b'event: error\ndata: {"detail":"upstream unavailable"}\n\n'

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        upstream_resp = await client.request(
            request.method,
            upstream_url,
            params=dict(request.query_params),
            headers=fwd_headers,
            content=body,
        )
    except httpx.RequestError as exc:
        return JSONResponse(
            {"detail": f"upstream unavailable: {exc.__class__.__name__}"}, status_code=502
        )

    resp_headers = {
        k: v
        for k, v in upstream_resp.headers.items()
        if k.lower() not in _STRIP_RESPONSE_HEADERS
    }
    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        headers=resp_headers,
        media_type=upstream_resp.headers.get("content-type"),
    )