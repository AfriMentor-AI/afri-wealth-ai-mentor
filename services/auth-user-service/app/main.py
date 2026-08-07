"""Auth & User Service — AfriMentor AI (card O1.3).

Signup / login / refresh with RS256 JWTs and a user profile that matches the shared
G1.3 TypeScript contract. See docs/adr/0001-microservices-architecture.md §D5.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import init_db
from .observability import instrument
from .routers import auth_router

SERVICE_NAME = "auth-user-service"
SERVICE_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # dev/test bootstrap; prod uses Alembic migrations
    yield


app = FastAPI(
    title="AfriMentor AI — Auth & User Service",
    version=SERVICE_VERSION,
    description="Authentication, JWT issuance/refresh, and user profiles.",
    lifespan=lifespan,
)

instrument(app, SERVICE_NAME)

app.include_router(auth_router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "healthy", "service": SERVICE_NAME, "version": SERVICE_VERSION}


@app.get("/", tags=["meta"])
def root() -> dict:
    return {"service": SERVICE_NAME, "message": "Auth & User Service online", "docs": "/docs"}
