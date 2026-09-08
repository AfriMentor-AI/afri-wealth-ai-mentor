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
from typing import Literal

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, func
from sqlalchemy.orm import Session, aliased

from .config import get_settings
from .consistency_job import run_consistency_job
from .db.session import engine, get_db
from .events import start_consumer_thread
from .models import (
    ArmAssignment,
    Base,
    ConsistencyRun,
    DriftAlert,
    ReviewStatus,
    SessionMetric,
    SurveyScore,
)
from .models.session_metric import anonymize_user_id
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


# Columns added to consistency_runs after its original C3.2 creation, in the
# order introduced (card C4.1 alignment scores, then card C4.2 review lifecycle).
# Each SQL type string MUST equal what Base.metadata.create_all emits for the ORM
# column, so a Postgres DB migrated via ADD COLUMN ends up identical to a fresh
# one create_all builds:
#   Float                   -> double precision
#   String(20) / String(32) -> VARCHAR(20) / VARCHAR(32)
#   DateTime(timezone=True) -> TIMESTAMP WITH TIME ZONE
_CONSISTENCY_ADDED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("trait_fit_cosine", "double precision"),
    ("composite_score", "double precision"),
    ("tone_match_score", "double precision"),
    ("fact_retrieval_score", "double precision"),
    ("review_status", "VARCHAR(20)"),
    ("review_reason", "VARCHAR(32)"),
    ("reviewed_at", "TIMESTAMP WITH TIME ZONE"),
)


def _ensure_consistency_columns() -> None:
    """Additively add post-C3.2 columns to an existing consistency_runs table.

    This service has no Alembic; startup relies on ``Base.metadata.create_all``,
    which creates a brand-new table with every column but never ALTERs a table
    that already exists. On the already-provisioned pilot ``svc_research`` DB the
    columns added after the table's original creation — card C4.1's alignment
    scores and card C4.2's review-lifecycle columns — would therefore be missing.
    ``ADD COLUMN IF NOT EXISTS`` is idempotent and a no-op once they exist.

    Column names and types come only from the hardcoded
    ``_CONSISTENCY_ADDED_COLUMNS`` table above (never request input), so
    interpolating them into the DDL text is injection-safe; each type string is
    kept equal to the ORM's ``create_all`` output so migrated and fresh Postgres
    DBs cannot diverge.

    Postgres only: SQLite (tests, local CLI) gets the columns from ``create_all``
    on a fresh table. Wrapped so a locked or absent table logs a warning rather
    than crashing startup.
    """
    if engine.dialect.name != "postgresql":
        return
    try:
        with engine.begin() as conn:
            for name, sql_type in _CONSISTENCY_ADDED_COLUMNS:
                conn.exec_driver_sql(
                    f"ALTER TABLE consistency_runs ADD COLUMN IF NOT EXISTS {name} {sql_type}"
                )
    except Exception as exc:  # pragma: no cover - defensive: never block startup
        logger.warning("Could not ensure consistency_runs columns: %s", exc)


@app.on_event("startup")
def startup() -> None:
    """Create tables, arm the consistency scoring jobs, and start the event consumer."""
    global _scheduler
    Base.metadata.create_all(bind=engine)
    _ensure_consistency_columns()

    # Consume session.completed events to persist engagement metrics (card F4). No-op
    # when RABBITMQ_URL is unset, so the service runs standalone without a broker.
    start_consumer_thread()

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


def _audit_session_dict(r: ConsistencyRun) -> dict:
    """Serialize one ConsistencyRun for the audit-session views (cards O4.1/C4.2).

    Shared by the listing endpoint and the manual-audit trigger so their row shape
    can never drift. ``session_id`` stays the (non-unique) conversation id the
    O4.1 table already exposed; ``id`` is the row PK the review endpoint keys on.
    ``review_status``/``review_reason``/``reviewed_at`` carry the card C4.2 flag.
    """
    return {
        "id": r.id,
        "session_id": r.conversation_id,
        "persona_id": r.persona_id,
        "primary_intent": r.primary_intent,
        "prompt_context": r.prompt_context,
        "consistency_delta_pct": r.consistency_delta_pct,
        "aggregate": r.aggregate,
        "review_status": r.review_status,
        "review_reason": r.review_reason,
        "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        "scored_at": r.scored_at.isoformat() if r.scored_at else None,
    }


@app.get("/api/v1/research/audit-sessions", tags=["research-console"])
def get_audit_sessions(
    limit: int = Query(50, ge=1, le=500),
    persona_id: str | None = Query(None, description="Filter to one persona"),
    min_abs_delta_pct: float | None = Query(
        None, ge=0, description="Only sessions whose |consistency_delta_pct| is at least this"
    ),
    flagged_only: bool = Query(
        False, description="Only sessions auto-flagged for review (card C4.2)"
    ),
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin),
) -> dict:
    """Recent Conversations (Persona Audit) table — Research Console (cards O4.1/C4.2).

    Session id, primary intent, prompt context, consistency delta, and review flag
    for the most recently scored sessions, newest first. ``flagged_only`` surfaces
    just the sessions auto-flagged for human review — the "Filter by Drift" control
    (card C4.2, AC2); it returns both pending and already-reviewed flagged rows
    (any non-null ``review_status``), the literal "flagged" reading.
    """
    query = db.query(ConsistencyRun).order_by(ConsistencyRun.scored_at.desc())
    if persona_id:
        query = query.filter(ConsistencyRun.persona_id == persona_id)
    if min_abs_delta_pct is not None:
        query = query.filter(
            ConsistencyRun.consistency_delta_pct.isnot(None),
            func.abs(ConsistencyRun.consistency_delta_pct) >= min_abs_delta_pct,
        )
    if flagged_only:
        query = query.filter(ConsistencyRun.review_status.isnot(None))

    rows = query.limit(limit).all()
    return {"sessions": [_audit_session_dict(r) for r in rows]}


@app.post("/api/v1/research/audits", tags=["research-console"])
def trigger_manual_audit(
    sample_size: int | None = Query(
        None, ge=1, le=500, description="Sessions to sample; defaults to CONSISTENCY_SAMPLE_SIZE"
    ),
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin),
) -> dict:
    """"New Manual Audit" — score the current session sample on demand and return
    the freshly-scored rows (card C4.2, AC1).

    Re-runs the same scoring engine the scheduler uses (``run_consistency_job``),
    so auto-flagging for review happens identically to a scheduled run, then
    returns that run's rows with their flags applied. The job opens and commits
    its own DB session before returning; this handler then reads the committed
    rows through the request-scoped ``db`` — safe because the read happens strictly
    after the job commits, and on Postgres READ COMMITTED the committed run is
    visible regardless. Lexical scoring over a small sample is fast enough to run
    inline in the request.
    """
    settings = get_settings()
    summary = run_consistency_job(sample_size=sample_size or settings.consistency_sample_size)
    # no_data: the sampler found nothing to score — no rows carry this run_id, and
    # the summary omits mean_aggregate/drift_alerts. Return an empty audit, not 500.
    if summary.get("status") == "no_data":
        return {"run": summary, "sessions": []}

    rows = (
        db.query(ConsistencyRun)
        .filter(ConsistencyRun.job_run_id == summary["run_id"])
        .order_by(ConsistencyRun.scored_at.desc())
        .all()
    )
    return {"run": summary, "sessions": [_audit_session_dict(r) for r in rows]}


@app.post("/api/v1/research/audit-sessions/{audit_id}/review", tags=["research-console"])
def review_audit_session(
    audit_id: str,
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin),
) -> dict:
    """"Mark reviewed" — close the human-review loop on a flagged session (card C4.2).

    Mirrors ``acknowledge_drift_alert``: keyed by the ConsistencyRun ``id`` PK
    (``conversation_id`` is not unique — the same conversation is re-scored across
    runs), sets ``review_status`` to 'reviewed' and stamps ``reviewed_at`` while
    preserving ``review_reason`` (why it was flagged stays on the record). 404 if
    the id is unknown.
    """
    run = db.query(ConsistencyRun).filter(ConsistencyRun.id == audit_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Audit session not found")

    run.review_status = ReviewStatus.reviewed.value
    run.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(run)
    return {
        "id": run.id,
        "review_status": run.review_status,
        "review_reason": run.review_reason,
        "reviewed_at": run.reviewed_at.isoformat() if run.reviewed_at else None,
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
# Pilot Data Export (card O4.4; arm assignment + filter added for card C4.5)
# ─────────────────────────────────────────────────────────────────────────────


class ArmAssignmentIn(BaseModel):
    """One participant's allocated study arm, keyed by their real user id.

    The real id is accepted here (never stored) so the caller — whoever holds
    the offline allocation sequence, pilot plan §3.3 — never has to compute the
    anonymized hash themselves; it's derived server-side with the same
    ``anonymize_user_id`` C3.5 ingestion uses, so it joins to SessionMetric rows
    for the same participant automatically.
    """

    user_id: str = Field(min_length=1)
    arm: Literal["A", "B"]


class ArmAssignmentsIn(BaseModel):
    assignments: list[ArmAssignmentIn] = Field(min_length=1)


@app.post("/api/v1/research/arm-assignments", tags=["research-console"])
def record_arm_assignments(
    body: ArmAssignmentsIn,
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin),
) -> dict:
    """Record pilot participants' study-arm allocations (card C4.5).

    Upsert by anonymized user_hash: re-submitting the same participant (e.g. the
    enrolment sheet re-loaded) updates their arm rather than erroring, so this is
    safe to re-run. Never echoes the raw user_id back.
    """
    settings = get_settings()
    recorded: list[dict] = []
    for item in body.assignments:
        user_hash = anonymize_user_id(item.user_id, salt=settings.research_salt)
        existing = db.query(ArmAssignment).filter(ArmAssignment.user_hash == user_hash).first()
        if existing:
            existing.arm = item.arm
        else:
            db.add(ArmAssignment(user_hash=user_hash, arm=item.arm))
        recorded.append({"user_hash": user_hash, "arm": item.arm})
    db.commit()
    return {"recorded": recorded}


@app.get("/api/v1/research/arm-assignments", tags=["research-console"])
def list_arm_assignments(
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin),
) -> dict:
    """Current arm roster and per-arm counts — sanity-check coverage before a pull."""
    rows = db.query(ArmAssignment).order_by(ArmAssignment.assigned_at).all()
    counts: dict[str, int] = {"A": 0, "B": 0}
    for r in rows:
        counts[r.arm] = counts.get(r.arm, 0) + 1
    return {
        "assignments": [
            {
                "user_hash": r.user_hash,
                "arm": r.arm,
                "assigned_at": r.assigned_at.isoformat() if r.assigned_at else None,
            }
            for r in rows
        ],
        "counts": counts,
    }


class SurveyScoreIn(BaseModel):
    """One participant's computed survey scores for one wave, keyed by real user id.

    Scores only — not raw item responses — since the Big-Three-adapted and
    FSES-modified instruments are administered orally by the field team (pilot
    plan §5.2/§5.3) and scored there. Mirrors ArmAssignmentIn's real-id-in,
    hash-stored pattern so whoever holds Grace's T0/T1 tracking sheet never
    computes the hash themselves.
    """

    user_id: str = Field(min_length=1)
    wave: Literal["T0", "T1"]
    financial_knowledge_score: int | None = Field(None, ge=0, le=3)
    self_efficacy_score: int | None = Field(None, ge=6, le=24)


class SurveyScoresIn(BaseModel):
    scores: list[SurveyScoreIn] = Field(min_length=1)


@app.post("/api/v1/research/survey-scores", tags=["research-console"])
def record_survey_scores(
    body: SurveyScoresIn,
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin),
) -> dict:
    """Record pilot participants' financial-knowledge/self-efficacy scores (card C4.5).

    Upsert by (anonymized user_hash, wave): re-submitting the same
    participant+wave — e.g. a corrected tracking-sheet row — updates the scores
    rather than erroring, so this is safe to re-run. Never echoes the raw
    user_id back. Same idempotency pattern as record_arm_assignments.
    """
    settings = get_settings()
    recorded: list[dict] = []
    for item in body.scores:
        user_hash = anonymize_user_id(item.user_id, salt=settings.research_salt)
        existing = (
            db.query(SurveyScore)
            .filter(SurveyScore.user_hash == user_hash, SurveyScore.wave == item.wave)
            .first()
        )
        if existing:
            existing.financial_knowledge_score = item.financial_knowledge_score
            existing.self_efficacy_score = item.self_efficacy_score
        else:
            db.add(SurveyScore(
                user_hash=user_hash,
                wave=item.wave,
                financial_knowledge_score=item.financial_knowledge_score,
                self_efficacy_score=item.self_efficacy_score,
            ))
        recorded.append({
            "user_hash": user_hash,
            "wave": item.wave,
            "financial_knowledge_score": item.financial_knowledge_score,
            "self_efficacy_score": item.self_efficacy_score,
        })
    db.commit()
    return {"recorded": recorded}


@app.get("/api/v1/research/survey-scores", tags=["research-console"])
def list_survey_scores(
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin),
) -> dict:
    """Current survey-score roster and per-wave coverage counts.

    Use this to confirm T0 has been entered for both arms before enrolment
    closes, and T1 coverage before pulling a checkpoint that needs pre/post.
    """
    rows = db.query(SurveyScore).order_by(SurveyScore.recorded_at).all()
    counts: dict[str, int] = {"T0": 0, "T1": 0}
    for r in rows:
        counts[r.wave] = counts.get(r.wave, 0) + 1
    return {
        "scores": [
            {
                "user_hash": r.user_hash,
                "wave": r.wave,
                "financial_knowledge_score": r.financial_knowledge_score,
                "self_efficacy_score": r.self_efficacy_score,
                "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
            }
            for r in rows
        ],
        "counts": counts,
    }


# Declared once so the header row and value rows can't drift apart (same
# pattern as rag-corpus-service's CSV_COLUMNS). No raw user_id or
# conversation_id column — user_hash is already anonymize_user_id()'s output,
# and sessions are identified only by row order, not by their real id.
#
# Card C4.5: all 3 of the pilot's required measures (plan §5), joined by arm —
# engagement (§5.4/F4, session length + message count) plus persona-consistency
# scoring per session, and financial-knowledge / self-efficacy (§5.2/§5.3) as
# computed T0/T1 scores from SurveyScore, broadcast onto every session row for
# that participant (same denormalized-per-participant shape as `arm`). Blank
# when a wave hasn't been entered yet — e.g. T1 columns are blank for
# still-enrolled participants at a mid-pilot checkpoint.
PILOT_EXPORT_COLUMNS = [
    "user_hash", "arm", "session_date", "session_duration_seconds", "message_count",
    "persona_id", "prompt_to_line", "line_to_line", "qa_consistency",
    "aggregate", "consistency_delta_pct",
    "financial_knowledge_t0", "financial_knowledge_t1",
    "self_efficacy_t0", "self_efficacy_t1",
]


@app.get("/api/v1/research/export/pilot-data.csv", tags=["research-console"])
def export_pilot_data(
    start_date: date | None = Query(None, description="Filter from this date (inclusive)"),
    end_date: date | None = Query(
        None,
        description=(
            "Filter to this date (inclusive) — e.g. the pilot's midpoint date, "
            "for a mid-pilot checkpoint (card C4.5)"
        ),
    ),
    arm: Literal["A", "B"] | None = Query(
        None, description="Filter to one study arm; omitted returns both (card C4.5)"
    ),
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin),
):
    """Anonymized pilot-data export for Grace's interim statistical analysis (O4.4).

    One row per session: the C3.5 engagement measures (session length, message
    count) left-joined to that same session's C3.2 consistency score, when one
    exists (only a sampled subset of sessions get scored by the nightly job,
    not every session — those columns are blank rather than fabricated), the
    participant's C4.5 study-arm assignment, when recorded, and the
    participant's C4.5 financial-knowledge / self-efficacy scores for both
    survey waves (T0/T1), when entered. Joined on conversation_id / user_hash
    internally, but no raw id is ever in the output — only the already-
    anonymized user_hash identifies a row's user.

    Without ``arm``, rows from both arms are returned together (card C4.5 AC:
    "all 3 measures for both groups") — pass ``end_date`` at the pilot's midpoint
    and ``arm`` is left unset for the standard mid-pilot checkpoint pull.
    """
    survey_t0 = aliased(SurveyScore)
    survey_t1 = aliased(SurveyScore)
    query = (
        db.query(SessionMetric, ConsistencyRun, ArmAssignment, survey_t0, survey_t1)
        .outerjoin(ConsistencyRun, ConsistencyRun.conversation_id == SessionMetric.conversation_id)
        .outerjoin(ArmAssignment, ArmAssignment.user_hash == SessionMetric.user_hash)
        .outerjoin(
            survey_t0,
            and_(survey_t0.user_hash == SessionMetric.user_hash, survey_t0.wave == "T0"),
        )
        .outerjoin(
            survey_t1,
            and_(survey_t1.user_hash == SessionMetric.user_hash, survey_t1.wave == "T1"),
        )
    )
    if start_date:
        query = query.filter(SessionMetric.session_date >= start_date)
    if end_date:
        query = query.filter(SessionMetric.session_date <= end_date)
    if arm:
        query = query.filter(ArmAssignment.arm == arm)
    rows = query.order_by(SessionMetric.session_date).all()

    def _score(score_row, field: str):
        if score_row is None:
            return ""
        value = getattr(score_row, field)
        return value if value is not None else ""

    def generate():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(PILOT_EXPORT_COLUMNS)
        yield buffer.getvalue()
        for metric, consistency, assignment, t0, t1 in rows:
            buffer.seek(0)
            buffer.truncate(0)
            writer.writerow([
                metric.user_hash,
                assignment.arm if assignment else "",
                metric.session_date.isoformat(),
                metric.session_duration_seconds,
                metric.message_count,
                consistency.persona_id if consistency else "",
                consistency.prompt_to_line if consistency else "",
                consistency.line_to_line if consistency else "",
                consistency.qa_consistency if consistency else "",
                consistency.aggregate if consistency else "",
                consistency.consistency_delta_pct if consistency else "",
                _score(t0, "financial_knowledge_score"),
                _score(t1, "financial_knowledge_score"),
                _score(t0, "self_efficacy_score"),
                _score(t1, "self_efficacy_score"),
            ])
            yield buffer.getvalue()

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=pilot-data-export.csv"},
    )
