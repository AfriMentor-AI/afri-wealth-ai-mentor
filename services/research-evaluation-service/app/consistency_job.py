"""C3.2 — Nightly consistency scoring job.
Samples real sessions, runs the C1.3 consistency metric suite,
and persists scores to the research-evaluation-service DB.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

from app.config import get_settings
from app.db.session import SessionLocal
from app.drift import (
    audit_fields_for_dialogue,
    compute_persona_baseline,
    delta_pct,
    evaluate_drift_and_alert,
)
from app.metrics.profile import load_profile
from app.metrics.report import score_dialogue
from app.models.consistency_run import ConsistencyRun
from app.session_sampler import sample_completed_sessions

logger = logging.getLogger(__name__)


def run_consistency_job(sample_size: int = 20) -> dict:
    """Score consistency metrics over a sample of real sessions.

    Returns a summary dict with run_id, session_count, mean scores, and any
    drift alerts fired for this run (card O4.1).
    """
    run_id = str(uuid.uuid4())
    started_at = datetime.now(UTC)
    logger.info("Starting consistency job run_id=%s", run_id)

    settings = get_settings()
    profile = load_profile()
    # Include idle-but-active sessions (card C4.1): nothing in the pilot marks a
    # conversation 'completed', so completed-only sampling would score nothing.
    dialogues = sample_completed_sessions(
        limit=sample_size,
        include_active_after_minutes=settings.session_idle_minutes,
    )

    if not dialogues:
        logger.warning("No completed sessions available to score")
        return {
            "run_id": run_id,
            "session_count": 0,
            "started_at": started_at.isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
            "status": "no_data",
            "drift_alerts": [],
        }

    db = SessionLocal()
    results = []
    # Baseline is per-persona and looked up once per persona per run — every
    # dialogue for the same persona shares the same pre-run baseline, computed
    # from job runs strictly older than this one (see app.drift docstring).
    baseline_cache: dict[str | None, float | None] = {}

    try:
        for dialogue in dialogues:
            try:
                report = score_dialogue(dialogue, profile=profile)
                c = report.consistency
                primary_intent, prompt_context = audit_fields_for_dialogue(dialogue)

                if dialogue.persona_id not in baseline_cache:
                    baseline_cache[dialogue.persona_id] = (
                        compute_persona_baseline(
                            db, dialogue.persona_id, run_id, window=settings.drift_baseline_window
                        )
                        if dialogue.persona_id
                        else None
                    )
                session_delta_pct = delta_pct(baseline_cache[dialogue.persona_id], c.aggregate)

                run = ConsistencyRun(
                    id=str(uuid.uuid4()),
                    job_run_id=run_id,
                    conversation_id=dialogue.dialogue_id,
                    persona_id=dialogue.persona_id,
                    prompt_to_line=c.prompt_to_line,
                    line_to_line=c.line_to_line,
                    qa_consistency=c.qa_consistency,
                    aggregate=c.aggregate,
                    turn_count=len(dialogue.turns),
                    warnings_json=json.dumps(report.warnings),
                    primary_intent=primary_intent,
                    prompt_context=prompt_context,
                    consistency_delta_pct=session_delta_pct,
                    # Card C4.1 — persist the trait-fit/composite alignment
                    # numbers score_dialogue() already produced (was discarded).
                    trait_fit_cosine=report.trait_fit.cosine_similarity,
                    composite_score=report.composite_score,
                    tone_match_score=report.tone_match_score,
                    fact_retrieval_score=report.fact_retrieval_score,
                    scored_at=datetime.now(UTC),
                )
                db.add(run)
                results.append(c.aggregate)

            except Exception as exc:
                logger.error(
                    "Failed to score session %s: %s",
                    dialogue.dialogue_id, exc
                )

        db.commit()

        drift_alerts = evaluate_drift_and_alert(
            db, run_id, settings.drift_threshold_pct, window=settings.drift_baseline_window
        )
        if drift_alerts:
            logger.warning(
                "Consistency job run_id=%s fired %d drift alert(s): %s",
                run_id, len(drift_alerts), [a.persona_id for a in drift_alerts],
            )

    finally:
        db.close()

    mean_aggregate = sum(results) / len(results) if results else 0.0
    summary = {
        "run_id": run_id,
        "session_count": len(results),
        "mean_aggregate": round(mean_aggregate, 4),
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(UTC).isoformat(),
        "status": "completed",
        "drift_alerts": [a.persona_id for a in drift_alerts],
    }
    logger.info("Consistency job completed: %s", summary)
    return summary
