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
import csv
import io
import logging
import os
from datetime import UTC, date, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import get_settings
from .consistency_job import run_consistency_job
from .db.session import engine, get_db
from .models import Base, ConsistencyRun, DriftAlert, SessionMetric
from .observability import instrument
from .rolling_aggregate import compute_rolling_24h_aggregates

logger = logging.getLogger(__name__)

SERVICE_NAME = "research-evaluation-service"
SERVICE_VERSION = "0.1.0"

app = FastAPI(
    title="AfriMentor AI — Research Evaluation Service",
    version=SERVICE_VERSION,
    description="Stub service. See docs/adr/0001-microservices-architecture.md",
)

instrument(app, SERVICE_NAME)

# Consistency scoring scheduler (cards C3.2 + C4.1). Held at module scope so the
# shutdown handler can stop the same scheduler instance startup created.
_scheduler: BackgroundScheduler | None = None


def _ensure_consistency_columns() -> None:
    """Additively add the card C4.1 columns to an existing consistency_runs table.

    This service has no Alembic; startup relies on ``Base.metadata.create_all``,
    which creates a brand-new table with the new columns but never ALTERs a table
    that already exists. On the already-provisioned pilot ``svc_research`` DB the
    ``trait_fit_cosine``/``composite_score`` columns would therefore be missing.
    ``ADD COLUMN IF NOT EXISTS`` is idempotent and a no-op once they exist.

    Postgres only: SQLite (tests, local CLI) gets the columns from ``create_all``
    on a fresh table. Wrapped so a locked or absent table logs a warning rather
    than crashing startup.
    """
    if engine.dialect.name != "postgresql":
        return
    try:
        with engine.begin() as conn:
            cols = (
                "trait_fit_cosine",
                "composite_score",
                "tone_match_score",
                "fact_retrieval_score",
            )
            for col in cols:
                conn.exec_driver_sql(
                    f"ALTER TABLE consistency_runs ADD COLUMN IF NOT EXISTS {col} double precision"
                )
    except Exception as exc:  # pragma: no cover - defensive: never block startup
        logger.warning("Could not ensure C4.1 consistency columns: %s", exc)


@app.on_event("startup")
def startup() -> None:
    """Create tables and, unless disabled, arm the consistency scoring jobs."""
    global _scheduler
    Base.metadata.create_all(bind=engine)
    _ensure_consistency_columns()

    settings = get_settings()
    if not settings.enable_scheduler:
        logger.info("Scheduler disabled (ENABLE_SCHEDULER=false); scoring jobs not armed")
        return

    _scheduler = BackgroundScheduler(timezone="UTC")
    # Nightly baseline run (card C3.2).
    _scheduler.add_job(
        run_consistency_job,
        "cron",
        hour=2,
        minute=0,
        kwargs={"sample_size": settings.consistency_sample_size},
        id="nightly_consistency",
        replace_existing=True,
    )
    # Live cadence (card C4.1): recompute every few minutes so the dashboard's
    # aggregate score updates from real sessions, and score once immediately on
    # boot so the dashboard has data without waiting a full interval. max_instances
    # + coalesce stop a slow run from piling up overlapping executions.
    if settings.consistency_interval_minutes > 0:
        _scheduler.add_job(
            run_consistency_job,
            "interval",
            minutes=settings.consistency_interval_minutes,
            kwargs={"sample_size": settings.consistency_sample_size},
            id="live_consistency",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            next_run_time=datetime.now(UTC),
        )
    _scheduler.start()
    logger.info(
        "Consistency scheduler armed: nightly@02:00 UTC; live interval=%s "
        "(sample_size=%d, session_idle=%d min)",
        f"{settings.consistency_interval_minutes} min"
        if settings.consistency_interval_minutes > 0
        else "disabled",
        settings.consistency_sample_size,
        settings.session_idle_minutes,
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
    # Card C4.1 — CHIOMA trait-fit alignment + composite blend.
    "mean_trait_fit_cosine": 0.0,
    "mean_composite": 0.0,
    # Tone Match & Fact Retrieval widgets
    "mean_tone_match": 0.0,
    "mean_fact_retrieval": 0.0,
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
    rolling_24h = compute_rolling_24h_aggregates(db)

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
                "rolling_24h": rolling_24h,
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
            "rolling_24h": rolling_24h,
            "sessions": [],
        }

    n = len(runs)
    # trait_fit_cosine/composite_score/tone_match/fact_retrieval are nullable
    trait_vals = [r.trait_fit_cosine for r in runs if r.trait_fit_cosine is not None]
    composite_vals = [r.composite_score for r in runs if r.composite_score is not None]
    tone_vals = [r.tone_match_score for r in runs if r.tone_match_score is not None]
    fact_vals = [r.fact_retrieval_score for r in runs if r.fact_retrieval_score is not None]

    aggregates = {
        "mean_prompt_to_line": round(sum(r.prompt_to_line for r in runs) / n, 4),
        "mean_line_to_line": round(sum(r.line_to_line for r in runs) / n, 4),
        "mean_qa_consistency": round(sum(r.qa_consistency for r in runs) / n, 4),
        "mean_aggregate": round(sum(r.aggregate for r in runs) / n, 4),
        "mean_trait_fit_cosine": (
            round(sum(trait_vals) / len(trait_vals), 4) if trait_vals else 0.0
        ),
        "mean_composite": (
            round(sum(composite_vals) / len(composite_vals), 4) if composite_vals else 0.0
        ),
        "mean_tone_match": (
            round(sum(tone_vals) / len(tone_vals), 4) if tone_vals else 0.0
        ),
        "mean_fact_retrieval": (
            round(sum(fact_vals) / len(fact_vals), 4) if fact_vals else 0.0
        ),
    }
    sessions = [
        {
            "conversation_id": r.conversation_id,
            "persona_id": r.persona_id,
            "prompt_to_line": r.prompt_to_line,
            "line_to_line": r.line_to_line,
            "qa_consistency": r.qa_consistency,
            "aggregate": r.aggregate,
            "trait_fit_cosine": r.trait_fit_cosine,
            "composite_score": r.composite_score,
            "tone_match_score": r.tone_match_score,
            "fact_retrieval_score": r.fact_retrieval_score,
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
        "rolling_24h": rolling_24h,
        "sessions": sessions,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Session Audit-Log & Drift-Threshold Alerting (card O4.1)
# ─────────────────────────────────────────────────────────────────────────────


_CONSOLE_ROLES = {"admin", "researcher", "lead_architect"}


def _require_admin(x_user_roles: str = Header("", alias="X-User-Roles")) -> None:
    """Gate the Research Console's admin endpoints (cards O4.1/O4.2).

    Mirrors the pattern in rag-corpus-service/app/api/routes.py: the gateway
    forwards verified JWT roles as X-User-Roles, so this trusts the header the
    same way rag-corpus-service's _require_admin does. Widened for O4.2's
    Admin Research Console, which Lead Architect/Researcher accounts use
    alongside admin — see docs/deployment/rbac-console-roles.md for how those
    role values get granted to accounts.
    """
    roles = {r.strip() for r in x_user_roles.split(",") if r.strip()}
    if not roles & _CONSOLE_ROLES:
        raise HTTPException(status_code=403, detail="admin, researcher, or lead_architect required")


@app.get("/api/v1/research/metrics/rolling-24h", tags=["research-console"])
def get_rolling_24h_metrics(
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin),
) -> dict:
    """Rolling 24h aggregation for Tone Match and Fact Retrieval widgets."""
    return compute_rolling_24h_aggregates(db)


@app.post("/api/v1/research/consistency/run", tags=["research-console"])
def trigger_consistency_run(_admin: None = Depends(_require_admin)) -> dict:
    """"Refresh now" — force an immediate consistency scoring run (card C4.1).

    The dashboard's tiles normally refresh from the interval scheduler; this lets
    an operator force a fresh score on demand. Lexical scoring over a small sample
    is fast enough to run inline in the request. ``run_consistency_job`` opens its
    own DB session (it is the scheduler's entrypoint too), so no request-scoped
    ``db`` is taken here. Returns the job's summary dict (run_id, session_count,
    mean_aggregate, drift_alerts).
    """
    settings = get_settings()
    return run_consistency_job(sample_size=settings.consistency_sample_size)


@app.get("/api/v1/research/audit-sessions", tags=["research-console"])
def get_audit_sessions(
    limit: int = Query(50, ge=1, le=500),
    persona_id: str | None = Query(None, description="Filter to one persona"),
    min_abs_delta_pct: float | None = Query(
        None, ge=0, description="Only sessions whose |consistency_delta_pct| is at least this"
    ),
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin),
) -> dict:
    """Recent Conversations (Persona Audit) table — Research Console (card O4.1).

    Session id, primary intent, prompt context, and consistency delta for the
    most recently scored sessions, newest first.
    """
    query = db.query(ConsistencyRun).order_by(ConsistencyRun.scored_at.desc())
    if persona_id:
        query = query.filter(ConsistencyRun.persona_id == persona_id)
    if min_abs_delta_pct is not None:
        query = query.filter(
            ConsistencyRun.consistency_delta_pct.isnot(None),
            func.abs(ConsistencyRun.consistency_delta_pct) >= min_abs_delta_pct,
        )

    rows = query.limit(limit).all()
    return {
        "sessions": [
            {
                "session_id": r.conversation_id,
                "persona_id": r.persona_id,
                "primary_intent": r.primary_intent,
                "prompt_context": r.prompt_context,
                "consistency_delta_pct": r.consistency_delta_pct,
                "aggregate": r.aggregate,
                "scored_at": r.scored_at.isoformat() if r.scored_at else None,
            }
            for r in rows
        ]
    }


@app.get("/api/v1/research/drift-alerts", tags=["research-console"])
def get_drift_alerts(
    status: str | None = Query(None, description="Filter by 'open' or 'acknowledged'"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin),
) -> dict:
    """Drift Threshold Alert widget — Research Console (card O4.1)."""
    query = db.query(DriftAlert).order_by(DriftAlert.created_at.desc())
    if status:
        query = query.filter(DriftAlert.status == status)
    rows = query.limit(limit).all()
    return {
        "alerts": [
            {
                "id": a.id,
                "job_run_id": a.job_run_id,
                "persona_id": a.persona_id,
                "baseline_aggregate": a.baseline_aggregate,
                "current_aggregate": a.current_aggregate,
                "delta_pct": a.delta_pct,
                "message": a.message,
                "status": a.status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
            }
            for a in rows
        ]
    }


@app.post("/api/v1/research/drift-alerts/{alert_id}/acknowledge", tags=["research-console"])
def acknowledge_drift_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin),
) -> dict:
    """"Acknowledge" button on the drift-alert banner (card O4.1)."""
    alert = db.query(DriftAlert).filter(DriftAlert.id == alert_id).first()
    if alert is None:
        raise HTTPException(status_code=404, detail="Drift alert not found")

    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.now(UTC)
    db.commit()
    db.refresh(alert)
    return {
        "id": alert.id,
        "status": alert.status,
        "acknowledged_at": alert.acknowledged_at.isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Pilot Data Export (card O4.4)
# ─────────────────────────────────────────────────────────────────────────────

# Declared once so the header row and value rows can't drift apart (same
# pattern as rag-corpus-service's CSV_COLUMNS). No raw user_id or
# conversation_id column — user_hash is already anonymize_user_id()'s output,
# and sessions are identified only by row order, not by their real id.
PILOT_EXPORT_COLUMNS = [
    "user_hash", "session_date", "session_duration_seconds", "message_count",
    "persona_id", "prompt_to_line", "line_to_line", "qa_consistency",
    "aggregate", "consistency_delta_pct",
]


@app.get("/api/v1/research/export/pilot-data.csv", tags=["research-console"])
def export_pilot_data(
    start_date: date | None = Query(None, description="Filter from this date (inclusive)"),
    end_date: date | None = Query(None, description="Filter to this date (inclusive)"),
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin),
):
    """Anonymized pilot-data export for Grace's interim statistical analysis (O4.4).

    One row per session: the C3.5 engagement measures (session length, message
    count) left-joined to that same session's C3.2 consistency score, when one
    exists (only a sampled subset of sessions get scored by the nightly job,
    not every session — those columns are blank rather than fabricated).
    Joined on conversation_id internally, but that id itself is never in the
    output — only the already-anonymized user_hash identifies a row's user.
    """
    query = db.query(SessionMetric, ConsistencyRun).outerjoin(
        ConsistencyRun, ConsistencyRun.conversation_id == SessionMetric.conversation_id
    )
    if start_date:
        query = query.filter(SessionMetric.session_date >= start_date)
    if end_date:
        query = query.filter(SessionMetric.session_date <= end_date)
    rows = query.order_by(SessionMetric.session_date).all()

    def generate():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(PILOT_EXPORT_COLUMNS)
        yield buffer.getvalue()
        for metric, consistency in rows:
            buffer.seek(0)
            buffer.truncate(0)
            writer.writerow([
                metric.user_hash,
                metric.session_date.isoformat(),
                metric.session_duration_seconds,
                metric.message_count,
                consistency.persona_id if consistency else "",
                consistency.prompt_to_line if consistency else "",
                consistency.line_to_line if consistency else "",
                consistency.qa_consistency if consistency else "",
                consistency.aggregate if consistency else "",
                consistency.consistency_delta_pct if consistency else "",
            ])
            yield buffer.getvalue()

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pilot-data-export.csv"},
    )
