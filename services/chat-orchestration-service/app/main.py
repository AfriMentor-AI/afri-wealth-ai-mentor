"""Chat Orchestration Service — AfriMentor AI (card D1.1).

Orchestrates a mentor turn: persona system-prompt + RAG context + message history
→ LLM reply. Emits `commitment.tag_suggested` when the model proposes tagging a
message as a user commitment (the 'Tag it' interaction on the Chat screen).

See docs/adr/0001-microservices-architecture.md and docs/adr/0002-base-llm-selection.md.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .database import init_db
from .routers.chat import router as chat_router

settings = get_settings()

SERVICE_NAME = settings.service_name
SERVICE_VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # dev/test bootstrap; prod uses Alembic migrations
    yield


app = FastAPI(
    title="AfriMentor AI — Chat Orchestration Service",
    version=SERVICE_VERSION,
    description=(
        "Orchestrates mentor turns: persona + RAG context + history → LLM reply. "
        "Emits commitment.tag_suggested domain events."
    ),
    lifespan=lifespan,
)

app.include_router(chat_router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "env": settings.env,
        "llm_model": settings.llm_model,
    }


@app.get("/", tags=["meta"])
def root() -> dict:
    return {"service": SERVICE_NAME, "message": "Chat Orchestration Service online", "docs": "/docs"}  # noqa: E501
