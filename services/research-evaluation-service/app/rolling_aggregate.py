"""Rolling 24h aggregation job and trend direction calculations.

Computes rolling 24-hour mean scores for Tone Match and Fact Retrieval,
comparing against the prior 24-hour period to produce trend directions
('up', 'down', 'flat') and percentage deltas for the Research Console.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.consistency_run import ConsistencyRun


def _calc_trend(
    current_score: float | None,
    prior_score: float | None,
) -> tuple[str | None, float | None]:
    """Calculate trend direction ('up', 'down', 'flat') and delta_pct."""
    if current_score is None or prior_score is None or prior_score == 0:
        return None, None

    delta = current_score - prior_score
    delta_pct = round((delta / prior_score) * 100, 1)

    if delta_pct > 0.0:
        trend = "up"
    elif delta_pct < 0.0:
        trend = "down"
    else:
        trend = "flat"

    return trend, delta_pct


def compute_rolling_24h_aggregates(
    db: Session,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compute rolling 24h aggregates and prior-period trends for Tone Match & Fact Retrieval.

    Current period: [now - 24h, now]
    Prior period:   [now - 48h, now - 24h]

    Scores are reported both raw [0.0, 1.0] and scaled to 0–100 for the console widgets.
    """
    if now is None:
        now = datetime.now(UTC)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    t_current_start = now - timedelta(hours=24)
    t_prior_start = now - timedelta(hours=48)

    # 1. Fetch current 24h runs
    current_runs = (
        db.query(ConsistencyRun)
        .filter(ConsistencyRun.scored_at >= t_current_start, ConsistencyRun.scored_at <= now)
        .order_by(desc(ConsistencyRun.scored_at))
        .all()
    )

    # If no runs in strict last 24h, fallback to latest scored run's window so dashboard
    # always has meaningful metrics during development/pilot
    if not current_runs:
        latest = db.query(ConsistencyRun).order_by(desc(ConsistencyRun.scored_at)).first()
        if latest and latest.scored_at:
            ref_time = (
                latest.scored_at
                if latest.scored_at.tzinfo
                else latest.scored_at.replace(tzinfo=UTC)
            )
            t_current_start = ref_time - timedelta(hours=24)
            t_prior_start = ref_time - timedelta(hours=48)
            current_runs = (
                db.query(ConsistencyRun)
                .filter(
                    ConsistencyRun.scored_at >= t_current_start,
                    ConsistencyRun.scored_at <= ref_time,
                )
                .order_by(desc(ConsistencyRun.scored_at))
                .all()
            )

    # 2. Fetch prior 24h runs
    prior_runs = (
        db.query(ConsistencyRun)
        .filter(
            ConsistencyRun.scored_at >= t_prior_start,
            ConsistencyRun.scored_at < t_current_start,
        )
        .all()
    )

    # Tone Match values
    current_tone = [
        r.tone_match_score if r.tone_match_score is not None else r.aggregate
        for r in current_runs
        if r.tone_match_score is not None or r.aggregate is not None
    ]
    prior_tone = [
        r.tone_match_score if r.tone_match_score is not None else r.aggregate
        for r in prior_runs
        if r.tone_match_score is not None or r.aggregate is not None
    ]

    # Fact Retrieval values
    current_fact = [
        r.fact_retrieval_score if r.fact_retrieval_score is not None else r.qa_consistency
        for r in current_runs
        if r.fact_retrieval_score is not None or r.qa_consistency is not None
    ]
    prior_fact = [
        r.fact_retrieval_score if r.fact_retrieval_score is not None else r.qa_consistency
        for r in prior_runs
        if r.fact_retrieval_score is not None or r.qa_consistency is not None
    ]

    last_evaluated_dt = current_runs[0].scored_at if current_runs else None
    if last_evaluated_dt and last_evaluated_dt.tzinfo is None:
        last_evaluated_dt = last_evaluated_dt.replace(tzinfo=UTC)

    # Compute means
    raw_tone = (sum(current_tone) / len(current_tone)) if current_tone else None
    raw_prior_tone = (sum(prior_tone) / len(prior_tone)) if prior_tone else None

    raw_fact = (sum(current_fact) / len(current_fact)) if current_fact else None
    raw_prior_fact = (sum(prior_fact) / len(prior_fact)) if prior_fact else None

    # Scaled (0-100)
    score_tone = round(raw_tone * 100, 1) if raw_tone is not None else None
    score_prior_tone = round(raw_prior_tone * 100, 1) if raw_prior_tone is not None else None

    score_fact = round(raw_fact * 100, 1) if raw_fact is not None else None
    score_prior_fact = round(raw_prior_fact * 100, 1) if raw_prior_fact is not None else None

    tone_trend, tone_delta = _calc_trend(score_tone, score_prior_tone)
    fact_trend, fact_delta = _calc_trend(score_fact, score_prior_fact)

    return {
        "window_hours": 24,
        "sample_count": len(current_runs),
        "last_evaluated": last_evaluated_dt.isoformat() if last_evaluated_dt else None,
        "tone_match": {
            "score": score_tone if score_tone is not None else 0.0,
            "raw_score": round(raw_tone, 4) if raw_tone is not None else 0.0,
            "prior_score": score_prior_tone,
            "delta_pct": tone_delta,
            "trend_direction": tone_trend,
            "sample_count": len(current_tone),
        },
        "fact_retrieval": {
            "score": score_fact if score_fact is not None else 0.0,
            "raw_score": round(raw_fact, 4) if raw_fact is not None else 0.0,
            "prior_score": score_prior_fact,
            "delta_pct": fact_delta,
            "trend_direction": fact_trend,
            "sample_count": len(current_fact),
        },
    }

