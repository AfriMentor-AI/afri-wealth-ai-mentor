"""Notification Service — AfriMentor AI (card O3.4).

v0 scaffold: daily-action reminders and streak-at-risk alerts, with delivery
stubbed/logged rather than sent to a real push provider. The two
`/trigger/*` endpoints *are* the event contract this card asks for — whatever
calls them (today: ops/tests; later: D3.3's daily-action job, a real push
integration) doesn't need to know how delivery works.

The streak-at-risk sweep (app/sweep.py) runs on a timer via a background
asyncio task, and is also exposed as `POST /api/v1/notifications/sweep` for
deterministic, on-demand triggering. It bootstraps its candidate user set from
this service's own Notification history (see sweep.py's docstring) — a known
v0 limitation, since no "list all users" endpoint exists anywhere in this
codebase yet.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .database import SessionLocal, init_db
from .observability import instrument
from .routers.notifications import router as notifications_router
from .sweep import run_streak_risk_sweep

logger = logging.getLogger(__name__)
settings = get_settings()

SERVICE_NAME = settings.service_name
SERVICE_VERSION = "1.0.0"


async def _sweep_loop() -> None:
    while True:
        await asyncio.sleep(settings.sweep_interval_seconds)
        db = SessionLocal()
        try:
            run_streak_risk_sweep(db)
        except Exception:  # noqa: BLE001 - a bad sweep must not kill the loop
            logger.exception("streak-at-risk sweep failed")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(_sweep_loop())
    yield
    task.cancel()


app = FastAPI(
    title="AfriMentor AI — Notification Service",
    version=SERVICE_VERSION,
    description="Daily-action reminders and streak-at-risk alerts (O3.4, v0 scaffold).",
    lifespan=lifespan,
)

instrument(app, SERVICE_NAME)

app.include_router(notifications_router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "env": settings.env,
    }


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "service": SERVICE_NAME,
        "message": "Notification Service online",
        "docs": "/docs",
    }
