"""C3.2 — Nightly consistency scoring job.
Samples real sessions, runs the C1.3 consistency metric suite,
and persists scores to the research-evaluation-service DB.
"""
from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.metrics.profile import load_profile
from app.metrics.report import score_dialogue
from app.models.consistency_run import ConsistencyRun
from app.session_sampler import sample_completed_sessions

logger = logging.getLogger(__name__)


def run_consistency_job(sample_size: int = 20) -> dict:
    """Score consistency metrics over a sample of real sessions.
    
    Returns a summary dict with run_id, session_count, and mean scores.
    """
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    logger.info("Starting consistency job run_id=%s", run_id)

    profile = load_profile()
    dialogues = sample_completed_sessions(limit=sample_size)

    if not dialogues:
        logger.warning("No completed sessions available to score")
        return {
            "run_id": run_id,
            "session_count": 0,
            "started_at": started_at.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "status": "no_data",
        }

    db = SessionLocal()
    results = []

    try:
        for dialogue in dialogues:
            try:
                report = score_dialogue(dialogue, profile=profile)
                c = report.consistency

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
                    scored_at=datetime.now(timezone.utc),
                )
                db.add(run)
                results.append(c.aggregate)

            except Exception as exc:
                logger.error(
                    "Failed to score session %s: %s",
                    dialogue.dialogue_id, exc
                )

        db.commit()

    finally:
        db.close()

    mean_aggregate = sum(results) / len(results) if results else 0.0
    summary = {
        "run_id": run_id,
        "session_count": len(results),
        "mean_aggregate": round(mean_aggregate, 4),
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed",
    }
    logger.info("Consistency job completed: %s", summary)
    return summary
