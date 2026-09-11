"""Card O4.1 — session audit fields and persona drift-threshold alerting.

Runs at the end of a consistency job (:func:`app.consistency_job.run_consistency_job`):
each scored session gets a lightweight ``primary_intent`` label and a trimmed
``prompt_context`` excerpt for the Research Console's audit table, and each
persona's mean score for the run is compared against its own rolling baseline
(computed from prior job runs only) to decide whether a :class:`DriftAlert`
should fire.

This service stays dependency-light (FastAPI + SQLAlchemy only — see
``app/main.py``'s module docstring), so intent classification is a v0 keyword
heuristic rather than a model call, matching the "v0 scorer" precedent already
established for :mod:`app.metrics.consistency`'s ``LexicalScorer``.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.metrics.schemas import Dialogue, Speaker
from app.models.consistency_run import ConsistencyRun, ReviewVerdict
from app.models.drift_alert import DriftAlert

PROMPT_CONTEXT_MAX_LEN = 240

# Ordered so the first matching bucket wins on ties (savings mentioned before
# budgeting, etc.) — a session about "saving for a business" reads as savings.
_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "savings": ("save", "saving", "savings"),
    "debt_management": ("debt", "loan", "borrow", "repay", "repayment"),
    "budgeting": ("budget", "expense", "spending", "cut back"),
    "investing": ("invest", "investment", "stock", "shares", "portfolio"),
    "business_growth": ("business", "customer", "revenue", "sales", "scale"),
    "goal_setting": ("goal", "milestone", "plan", "target"),
}
DEFAULT_INTENT = "general_mentorship"


def _first_user_text(dialogue: Dialogue) -> str | None:
    for turn in dialogue.turns:
        if turn.speaker is Speaker.user:
            return turn.text
    return None


def classify_primary_intent(text: str | None) -> str:
    """Keyword-bucket heuristic over the first user turn. v0 — see module docstring."""
    if not text:
        return DEFAULT_INTENT
    lowered = text.lower()
    for intent, keywords in _INTENT_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return intent
    return DEFAULT_INTENT


def extract_prompt_context(text: str | None, max_len: int = PROMPT_CONTEXT_MAX_LEN) -> str | None:
    """Trimmed excerpt of the first user turn for the audit table's context column."""
    if not text:
        return None
    stripped = text.strip()
    if len(stripped) <= max_len:
        return stripped
    return stripped[: max_len - 1].rstrip() + "…"


def audit_fields_for_dialogue(dialogue: Dialogue) -> tuple[str, str | None]:
    """Return ``(primary_intent, prompt_context)`` for a scored dialogue."""
    first_user_text = _first_user_text(dialogue)
    return classify_primary_intent(first_user_text), extract_prompt_context(first_user_text)


def _recent_prior_run_ids_stmt(persona_id: str, exclude_job_run_id: str, window: int):
    """Select the most recent ``window`` prior job-run ids for a persona.

    Ranks each run by its latest scored row via ``GROUP BY job_run_id`` +
    ``ORDER BY max(scored_at)`` — deliberately **not** ``SELECT DISTINCT`` +
    ``ORDER BY scored_at``. Under ``SELECT DISTINCT`` Postgres requires every
    ``ORDER BY`` term to appear in the select list, so the DISTINCT form raises
    ``InvalidColumnReference`` on Postgres while passing silently on SQLite.
    Isolated as a statement builder so a unit test can compile it against the
    Postgres dialect and assert the shape stays safe — the SQLite-backed test
    suite cannot reproduce that runtime error otherwise.
    """
    return (
        select(ConsistencyRun.job_run_id)
        .where(ConsistencyRun.persona_id == persona_id)
        .where(ConsistencyRun.job_run_id != exclude_job_run_id)
        .group_by(ConsistencyRun.job_run_id)
        .order_by(func.max(ConsistencyRun.scored_at).desc())
        .limit(window)
    )


def compute_persona_baseline(
    db: Session, persona_id: str, exclude_job_run_id: str, window: int
) -> float | None:
    """Mean ``aggregate`` over the persona's most recent prior job runs.

    Excludes ``exclude_job_run_id`` (the run currently being scored) so a run
    can never use itself as its own baseline. Returns ``None`` when the persona
    has no scoring history yet — there is nothing to compare against, and that
    absence must not be silently treated as "no drift".
    """
    recent_job_run_ids = db.execute(
        _recent_prior_run_ids_stmt(persona_id, exclude_job_run_id, window)
    ).all()
    if not recent_job_run_ids:
        return None

    job_run_ids = [row[0] for row in recent_job_run_ids]
    rows = (
        db.query(ConsistencyRun.aggregate)
        .filter(ConsistencyRun.persona_id == persona_id)
        .filter(ConsistencyRun.job_run_id.in_(job_run_ids))
        .all()
    )
    values = [row[0] for row in rows]
    if not values:
        return None
    return sum(values) / len(values)


def delta_pct(baseline: float | None, current: float) -> float | None:
    """Percent deviation of ``current`` below ``baseline`` (positive = worse)."""
    if baseline is None or baseline == 0:
        return None
    return round((baseline - current) / baseline * 100, 2)


def evaluate_review_flag(
    aggregate: float,
    consistency_delta_pct: float | None,
    *,
    floor: float,
    drift_threshold_pct: float,
) -> str | None:
    """Decide whether a scored session should be auto-flagged for human review (card C4.2).

    Union rule: flag when the raw consistency ``aggregate`` is below the absolute
    ``floor`` OR the session's deviation from its persona baseline crosses
    ``drift_threshold_pct``. Returns a ``'+'``-joined reason
    (``'below_floor'``, ``'drift'``, or ``'below_floor+drift'``) or ``None`` when
    the session is healthy on both arms.

    ``consistency_delta_pct`` is ``None`` for any persona with no prior baseline
    (the common early case — :func:`delta_pct` returns ``None``); the ``is not
    None`` guard is mandatory, since the caller's per-dialogue loop swallows
    exceptions and would otherwise silently drop a baseline-less session. Such a
    session is still eligible for the floor arm.
    """
    reasons = []
    if aggregate < floor:
        reasons.append("below_floor")
    if consistency_delta_pct is not None and abs(consistency_delta_pct) >= drift_threshold_pct:
        reasons.append("drift")
    return "+".join(reasons) if reasons else None


def evaluate_drift_and_alert(
    db: Session, job_run_id: str, threshold_pct: float, window: int = 10
) -> list[DriftAlert]:
    """After a job run is committed, compare each scored persona's run mean
    against its pre-run baseline and persist a :class:`DriftAlert` for any
    persona whose deviation crosses ``threshold_pct``.

    Reads ``ConsistencyRun`` rows already committed for ``job_run_id`` — call
    this after :func:`app.consistency_job.run_consistency_job` commits, not
    inside the same transaction, so the baseline queries in
    :func:`compute_persona_baseline` never see this run's own rows.
    """
    run_rows = (
        db.query(ConsistencyRun)
        .filter(ConsistencyRun.job_run_id == job_run_id)
        .filter(ConsistencyRun.persona_id.isnot(None))
        .all()
    )

    by_persona: dict[str, list[float]] = {}
    for row in run_rows:
        by_persona.setdefault(row.persona_id, []).append(row.aggregate)

    alerts: list[DriftAlert] = []
    for persona_id, scores in by_persona.items():
        current_mean = sum(scores) / len(scores)
        baseline = compute_persona_baseline(db, persona_id, job_run_id, window=window)
        pct = delta_pct(baseline, current_mean)
        if pct is None or abs(pct) < threshold_pct:
            continue

        alert = DriftAlert(
            id=str(uuid.uuid4()),
            job_run_id=job_run_id,
            persona_id=persona_id,
            baseline_aggregate=round(baseline, 4),
            current_aggregate=round(current_mean, 4),
            delta_pct=pct,
            message=(
                f"Consistency for persona '{persona_id}' deviated {pct:+.1f}% "
                f"from its {window}-run baseline ({baseline:.3f} → {current_mean:.3f})."
            ),
            created_at=datetime.now(UTC),
        )
        db.add(alert)
        alerts.append(alert)

    if alerts:
        db.commit()
    return alerts


def _rate_group(rows: list[str | None]) -> dict:
    """``{n, n_false_positive, rate}`` for one bucket of review verdicts.

    ``rate`` is ``None`` on an empty bucket rather than ``0.0`` — no reviewed
    sessions is a different fact than "zero were false positives", and
    collapsing the two would make a threshold that hasn't been exercised yet
    look identical to one that's been validated clean.
    """
    n = len(rows)
    n_false_positive = sum(1 for v in rows if v == ReviewVerdict.false_positive.value)
    return {
        "n": n,
        "n_false_positive": n_false_positive,
        "rate": round(n_false_positive / n, 4) if n else None,
    }


def compute_false_positive_rate(db: Session, persona_id: str | None = None) -> dict:
    """Measured false-positive rate of the manual-audit flag rule (card C5.3).

    Ground truth comes only from sessions a human has actually reviewed AND
    given a verdict on (``review_status='reviewed'`` and ``review_verdict`` set
    via the ``/review`` endpoint) — a flagged-but-not-yet-reviewed session, or a
    reviewed one where the reviewer skipped the verdict, contributes nothing,
    since there is no ground truth to score it against.

    Broken down by ``review_reason`` (``below_floor`` / ``drift`` /
    ``below_floor+drift``) as well as overall, because the floor and the drift
    threshold are two independently-tunable knobs
    (``consistency_review_floor`` / ``drift_threshold_pct``) — an overall rate
    alone can't say which one is generating the false positives.
    """
    query = db.query(ConsistencyRun.review_reason, ConsistencyRun.review_verdict).filter(
        ConsistencyRun.review_status == "reviewed",
        ConsistencyRun.review_verdict.isnot(None),
    )
    if persona_id is not None:
        query = query.filter(ConsistencyRun.persona_id == persona_id)

    by_reason: dict[str, list[str | None]] = {}
    all_verdicts: list[str | None] = []
    for reason, verdict in query.all():
        all_verdicts.append(verdict)
        by_reason.setdefault(reason, []).append(verdict)

    return {
        "overall": _rate_group(all_verdicts),
        "by_reason": {reason: _rate_group(verdicts) for reason, verdicts in by_reason.items()},
    }
