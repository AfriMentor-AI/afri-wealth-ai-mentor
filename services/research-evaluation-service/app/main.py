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
import logging
import os
from datetime import date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from .config import get_settings
from .consistency_job import run_consistency_job
from .observability import instrument
from .db.session import engine, get_db
from .models import Base, ConsistencyRun, SessionMetric

logger = logging.getLogger(__name__)

SERVICE_NAME = "research-evaluation-service"
SERVICE_VERSION = "0.1.0"

app = FastAPI(
    title="AfriMentor AI — Research Evaluation Service",
    version=SERVICE_VERSION,
    description="Stub service. See docs/adr/0001-microservices-architecture.md",
)

instrument(app, SERVICE_NAME)

# Nightly consistency scoring job (card C3.2). Held at module scope so the
# shutdown handler can stop the same scheduler instance startup created.
_scheduler: BackgroundScheduler | None = None


@app.on_event("startup")
def startup() -> None:
    """Create tables and, unless disabled, arm the nightly consistency job."""
    global _scheduler
    Base.metadata.create_all(bind=engine)

    settings = get_settings()
    if not settings.enable_scheduler:
        logger.info("Scheduler disabled (ENABLE_SCHEDULER=false); nightly job not armed")
        return

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        run_consistency_job,
        "cron",
        hour=2,
        minute=0,
        kwargs={"sample_size": settings.consistency_sample_size},
        id="nightly_consistency",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Nightly consistency job armed at 02:00 UTC (sample_size=%d)",
        settings.consistency_sample_size,
    )


@app.on_event("shutdown")
def shutdown() -> None:
    """Stop the scheduler so a reload or container stop exits cleanly."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


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


# ─────────────────────────────────────────────────────────────────────────────
# Session Metrics Endpoints (card C3.5)
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/api/v1/metrics/sessions", tags=["metrics"])
def get_session_metrics(
    start_date: date | None = Query(None, description="Filter from this date (inclusive)"),
    end_date: date | None = Query(None, description="Filter to this date (inclusive)"),
    db: Session = Depends(get_db),
) -> dict:
    """Get aggregated anonymized session metrics for pilot evaluation.
    
    Returns the three required measures:
      - Sessions per day
      - Average session length
      - Time on-task (average message count)
    
    All user identifiers are anonymized via SHA256 hash.
    """
    query = db.query(SessionMetric)
    
    # Apply date filters
    if start_date:
        query = query.filter(SessionMetric.session_date >= start_date)
    if end_date:
        query = query.filter(SessionMetric.session_date <= end_date)
    
    metrics = query.all()
    
    if not metrics:
        return {
            "period": {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            },
            "sessions_count": 0,
            "sessions_per_day": 0.0,
            "average_session_length_seconds": 0.0,
            "average_time_on_task_messages": 0.0,
        }
    
    # Calculate aggregate metrics
    total_sessions = len(metrics)
    total_duration = sum(m.session_duration_seconds for m in metrics)
    total_messages = sum(m.message_count for m in metrics)
    
    # Get unique days
    unique_days = len(set(m.session_date for m in metrics))
    
    sessions_per_day = total_sessions / unique_days if unique_days > 0 else 0.0
    avg_session_length = total_duration / total_sessions if total_sessions > 0 else 0.0
    avg_time_on_task = total_messages / total_sessions if total_sessions > 0 else 0.0
    
    return {
        "period": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
        "sessions_count": total_sessions,
        "sessions_per_day": round(sessions_per_day, 2),
        "average_session_length_seconds": round(avg_session_length, 2),
        "average_time_on_task_messages": round(avg_time_on_task, 2),
        "notes": "All user identifiers are anonymized via SHA256 hash.",
    }


@app.get("/api/v1/metrics/sessions/daily", tags=["metrics"])
def get_daily_session_metrics(
    start_date: date | None = Query(None, description="Filter from this date (inclusive)"),
    end_date: date | None = Query(None, description="Filter to this date (inclusive)"),
    db: Session = Depends(get_db),
) -> dict:
    """Get daily session metrics breakdown.
    
    Returns per-day statistics for:
      - Session count
      - Average session length
      - Average time on-task
    """
    query = db.query(SessionMetric)
    
    # Apply date filters
    if start_date:
        query = query.filter(SessionMetric.session_date >= start_date)
    if end_date:
        query = query.filter(SessionMetric.session_date <= end_date)
    
    metrics = query.all()
    
    if not metrics:
        return {
            "period": {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
            },
            "daily_metrics": [],
        }
    
    # Group by date
    daily_data = {}
    for metric in metrics:
        if metric.session_date not in daily_data:
            daily_data[metric.session_date] = {
                "sessions": 0,
                "total_duration": 0,
                "total_messages": 0,
            }
        daily_data[metric.session_date]["sessions"] += 1
        daily_data[metric.session_date]["total_duration"] += metric.session_duration_seconds
        daily_data[metric.session_date]["total_messages"] += metric.message_count
    
    # Format for response
    daily_metrics = []
    for session_date in sorted(daily_data.keys()):
        data = daily_data[session_date]
        session_count = data["sessions"]
        total_duration = data["total_duration"]
        total_messages = data["total_messages"]
        
        daily_metrics.append({
            "date": session_date.isoformat(),
            "session_count": session_count,
            "average_session_length_seconds": round(
                total_duration / session_count if session_count > 0 else 0.0, 2
            ),
            "average_time_on_task_messages": round(
                total_messages / session_count if session_count > 0 else 0.0, 2
            ),
        })
    
    return {
        "period": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
        "daily_metrics": daily_metrics,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Behavioral Consistency Metrics Endpoint (card C3.2)
# ─────────────────────────────────────────────────────────────────────────────

_EMPTY_CONSISTENCY_AGGREGATES = {
    "mean_prompt_to_line": 0.0,
    "mean_line_to_line": 0.0,
    "mean_qa_consistency": 0.0,
    "mean_aggregate": 0.0,
}


@app.get("/api/v1/metrics/consistency", tags=["metrics"])
def get_consistency_metrics(
    limit: int = Query(50, ge=1, le=500, description="Max per-session rows to return"),
    job_run_id: str | None = Query(
        None, description="Report a specific run; defaults to the most recent"
    ),
    db: Session = Depends(get_db),
) -> dict:
    """Behavioral consistency scores for the Research Console dashboard (Sprint 4).

    Returns per-session sub-scores plus run-level means for one scoring run — the
    most recent by default, or the run named by ``job_run_id``. Means are computed
    over every session in the run; ``sessions`` is capped at ``limit`` rows.
    """
    if job_run_id is None:
        latest = (
            db.query(ConsistencyRun).order_by(ConsistencyRun.scored_at.desc()).first()
        )
        if latest is None:
            return {
                "job_run_id": None,
                "session_count": 0,
                "scored_at": None,
                "aggregates": _EMPTY_CONSISTENCY_AGGREGATES,
                "sessions": [],
            }
        job_run_id = latest.job_run_id

    runs = (
        db.query(ConsistencyRun)
        .filter(ConsistencyRun.job_run_id == job_run_id)
        .order_by(ConsistencyRun.scored_at.desc())
        .all()
    )

    if not runs:
        return {
            "job_run_id": job_run_id,
            "session_count": 0,
            "scored_at": None,
            "aggregates": _EMPTY_CONSISTENCY_AGGREGATES,
            "sessions": [],
        }

    n = len(runs)
    aggregates = {
        "mean_prompt_to_line": round(sum(r.prompt_to_line for r in runs) / n, 4),
        "mean_line_to_line": round(sum(r.line_to_line for r in runs) / n, 4),
        "mean_qa_consistency": round(sum(r.qa_consistency for r in runs) / n, 4),
        "mean_aggregate": round(sum(r.aggregate for r in runs) / n, 4),
    }
    sessions = [
        {
            "conversation_id": r.conversation_id,
            "persona_id": r.persona_id,
            "prompt_to_line": r.prompt_to_line,
            "line_to_line": r.line_to_line,
            "qa_consistency": r.qa_consistency,
            "aggregate": r.aggregate,
            "turn_count": r.turn_count,
            "scored_at": r.scored_at.isoformat() if r.scored_at else None,
        }
        for r in runs[:limit]
    ]

    return {
        "job_run_id": job_run_id,
        "session_count": n,
        "scored_at": runs[0].scored_at.isoformat() if runs[0].scored_at else None,
        "aggregates": aggregates,
        "sessions": sessions,
    }
