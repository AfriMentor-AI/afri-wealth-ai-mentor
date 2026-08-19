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
from .jobs import generate_daily_actions_job
from .observability import instrument
from .routers.chat import router as chat_router
from .routers.daily_actions import router as daily_actions_router
from .scheduler import scheduler, setup_scheduler

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

# Add the job to the scheduler
scheduler.add_job(generate_daily_actions_job, "cron", hour=8, minute=0) # Run daily at 8am

# Setup scheduler events
setup_scheduler(app)

instrument(app, SERVICE_NAME)

app.include_router(chat_router)
app.include_router(daily_actions_router, prefix="/api/v1", tags=["daily-actions"])


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
