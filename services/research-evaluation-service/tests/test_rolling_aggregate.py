"""Tests for rolling 24h aggregation job and trend direction calculations."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.consistency_run import ConsistencyRun
from app.rolling_aggregate import compute_rolling_24h_aggregates


def make_in_memory_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


def test_rolling_24h_empty_database():
    """Empty database returns standard empty structure."""
    engine = make_in_memory_engine()
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        res = compute_rolling_24h_aggregates(db)
        assert res["window_hours"] == 24
        assert res["sample_count"] == 0
        assert res["tone_match"]["score"] == 0.0
        assert res["tone_match"]["trend_direction"] is None
        assert res["fact_retrieval"]["score"] == 0.0
        assert res["fact_retrieval"]["trend_direction"] is None
    finally:
        db.close()


def test_rolling_24h_trend_up_and_down():
    """Tests that scores in current 24h vs prior 24h compute correct trend and delta."""
    engine = make_in_memory_engine()
    Session = sessionmaker(bind=engine)
    db = Session()

    now = datetime(2026, 8, 21, 14, 0, 0, tzinfo=UTC)
    t_current = now - timedelta(hours=2)   # Within [now-24h, now]
    t_prior = now - timedelta(hours=28)    # Within [now-48h, now-24h]

    # Current period: high tone match (0.942 = 94.2), lower fact retrieval (0.898 = 89.8)
    for i in range(3):
        db.add(ConsistencyRun(
            id=str(uuid.uuid4()),
            job_run_id="job-current",
            conversation_id=f"conv-curr-{i}",
            persona_id="chioma",
            prompt_to_line=0.9,
            line_to_line=0.9,
            qa_consistency=0.898,
            aggregate=0.942,
            turn_count=4,
            tone_match_score=0.942,
            fact_retrieval_score=0.898,
            scored_at=t_current,
        ))

    # Prior period: lower tone match (0.930 = 93.0), higher fact retrieval (0.930 = 93.0)
    for i in range(3):
        db.add(ConsistencyRun(
            id=str(uuid.uuid4()),
            job_run_id="job-prior",
            conversation_id=f"conv-prior-{i}",
            persona_id="chioma",
            prompt_to_line=0.85,
            line_to_line=0.85,
            qa_consistency=0.93,
            aggregate=0.93,
            turn_count=4,
            tone_match_score=0.930,
            fact_retrieval_score=0.930,
            scored_at=t_prior,
        ))

    db.commit()

    try:
        res = compute_rolling_24h_aggregates(db, now=now)
        assert res["sample_count"] == 3
        assert res["last_evaluated"] is not None

        # Tone Match: 94.2 vs 93.0 -> trend 'up', positive delta
        assert res["tone_match"]["score"] == 94.2
        assert res["tone_match"]["prior_score"] == 93.0
        assert res["tone_match"]["trend_direction"] == "up"
        assert res["tone_match"]["delta_pct"] == 1.3  # (94.2 - 93.0) / 93.0 * 100 = +1.29%

        # Fact Retrieval: 89.8 vs 93.0 -> trend 'down', negative delta
        assert res["fact_retrieval"]["score"] == 89.8
        assert res["fact_retrieval"]["prior_score"] == 93.0
        assert res["fact_retrieval"]["trend_direction"] == "down"
        assert res["fact_retrieval"]["delta_pct"] == -3.4  # (89.8 - 93.0) / 93.0 * 100 = -3.44%
    finally:
        db.close()


def test_rolling_24h_trend_flat_when_equal():
    """Tests flat trend when current and prior scores are equal."""
    engine = make_in_memory_engine()
    Session = sessionmaker(bind=engine)
    db = Session()

    now = datetime(2026, 8, 21, 14, 0, 0, tzinfo=UTC)
    t_current = now - timedelta(hours=5)
    t_prior = now - timedelta(hours=30)

    db.add(ConsistencyRun(
        id=str(uuid.uuid4()),
        job_run_id="job-1",
        conversation_id="conv-1",
        persona_id="chioma",
        prompt_to_line=0.8,
        line_to_line=0.8,
        qa_consistency=0.8,
        aggregate=0.8,
        turn_count=4,
        tone_match_score=0.85,
        fact_retrieval_score=0.85,
        scored_at=t_current,
    ))
    db.add(ConsistencyRun(
        id=str(uuid.uuid4()),
        job_run_id="job-2",
        conversation_id="conv-2",
        persona_id="chioma",
        prompt_to_line=0.8,
        line_to_line=0.8,
        qa_consistency=0.8,
        aggregate=0.8,
        turn_count=4,
        tone_match_score=0.85,
        fact_retrieval_score=0.85,
        scored_at=t_prior,
    ))
    db.commit()

    try:
        res = compute_rolling_24h_aggregates(db, now=now)
        assert res["tone_match"]["trend_direction"] == "flat"
        assert res["tone_match"]["delta_pct"] == 0.0
    finally:
        db.close()

