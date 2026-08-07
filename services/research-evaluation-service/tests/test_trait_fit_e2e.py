"""C2.3 — Trait-fit metric end-to-end tests."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.metrics.profile import load_profile
from app.metrics.schemas import ProbeResponse
from app.metrics.trait_fit import score_probe_traits
from scripts.run_trait_fit import (
    DEFAULT_DIALOGUE_DIR,
    DEFAULT_PROBE_PATH,
    load_dialogues,
    load_probes,
    run_experiment,
)


# ── Unit tests (no DB needed) ─────────────────────────────────────────────────

def test_load_probes():
    probes = load_probes(DEFAULT_PROBE_PATH)
    assert len(probes) > 0
    assert all(isinstance(p, ProbeResponse) for p in probes)
    assert all(p.probe_id for p in probes)
    assert all(p.trait for p in probes)


def test_load_dialogues():
    dialogues = load_dialogues(DEFAULT_DIALOGUE_DIR)
    assert len(dialogues) >= 3
    assert all(d.dialogue_id for d in dialogues)


def test_probe_trait_fit_produces_valid_scores():
    probes = load_probes(DEFAULT_PROBE_PATH)
    profile = load_profile()
    result = score_probe_traits(probes, profile=profile)
    assert -1.0 <= result.cosine_similarity <= 1.0
    assert result.mean_absolute_error >= 0.0
    assert len(result.per_trait) > 0
    for trait in result.per_trait:
        assert 0.0 <= trait.observed_value <= 1.0
        assert 0.0 <= trait.target_value <= 1.0


def test_probe_trait_fit_covers_expected_traits():
    probes = load_probes(DEFAULT_PROBE_PATH)
    profile = load_profile()
    result = score_probe_traits(probes, profile=profile)
    scored_traits = {t.trait for t in result.per_trait}
    assert "conscientiousness" in scored_traits
    assert "agreeableness" in scored_traits


def test_worst_trait_identified():
    probes = load_probes(DEFAULT_PROBE_PATH)
    profile = load_profile()
    result = score_probe_traits(probes, profile=profile)
    if result.worst_trait:
        assert result.worst_trait.trait in {t.trait for t in result.per_trait}


# ── Integration tests (with SQLite in-memory DB) ─────────────────────────────

def _make_in_memory_engine():
    from sqlalchemy import create_engine
    from app.models.audit import Base
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return engine


def test_run_experiment_stores_report(tmp_path):
    """Full end-to-end: run experiment, verify report stored, check output JSON."""
    from sqlalchemy.orm import sessionmaker
    from app.models.audit import ExperimentRun, ExperimentStatus, TraitFitReport

    engine = _make_in_memory_engine()
    Session = sessionmaker(bind=engine)

    out_file = tmp_path / "report.json"

    with patch("scripts.run_trait_fit.engine", engine),          patch("scripts.run_trait_fit.SessionLocal", Session):
        result = run_experiment(
            model_id="test-baseline",
            name="test-run-001",
            out_path=out_file,
            live=False,  # fixture answers, not a real model call
        )

    # Verify output JSON
    assert result["status"] == "completed"
    # model_id is tagged so a fixture run can't be mistaken for a real baseline
    assert result["model_id"] == "test-baseline+fixture-answers"
    assert result["answer_source"] == "fixtures"
    assert result["run_name"] == "test-run-001"
    assert "probe_trait_fit" in result
    assert "dialogue_reports" in result
    assert len(result["dialogue_reports"]) >= 3

    # Verify JSON file written
    assert out_file.exists()
    saved = json.loads(out_file.read_text())
    assert saved["run_id"] == result["run_id"]

    # Verify DB records
    db = Session()
    run = db.query(ExperimentRun).filter_by(id=result["run_id"]).first()
    assert run is not None
    assert run.status == ExperimentStatus.completed
    assert run.probe_count > 0

    reports = db.query(TraitFitReport).filter_by(run_id=run.id).all()
    assert len(reports) >= 4  # 1 probe + 3 dialogues
    sources = {r.source for r in reports}
    assert "probes" in sources
    assert "dialogue" in sources

    for report in reports:
        assert -1.0 <= report.cosine_similarity <= 1.0
        assert report.mean_absolute_error >= 0.0
        per_trait = json.loads(report.per_trait_json)
        assert isinstance(per_trait, list)
    db.close()


def test_run_experiment_probe_cosine_in_range(tmp_path):
    from sqlalchemy.orm import sessionmaker
    engine = _make_in_memory_engine()
    Session = sessionmaker(bind=engine)

    with patch("scripts.run_trait_fit.engine", engine),          patch("scripts.run_trait_fit.SessionLocal", Session):
        result = run_experiment(model_id="test", name="cosine-check", live=False)

    cosine = result["probe_trait_fit"]["cosine_similarity"]
    assert -1.0 <= cosine <= 1.0


def test_main_cli_runs_successfully(tmp_path):
    from sqlalchemy.orm import sessionmaker
    from scripts.run_trait_fit import main
    engine = _make_in_memory_engine()
    Session = sessionmaker(bind=engine)
    out = tmp_path / "cli_out.json"

    with patch("scripts.run_trait_fit.engine", engine),          patch("scripts.run_trait_fit.SessionLocal", Session):
        ret = main(["--model-id", "cli-test", "--fixtures", "--out", str(out)])

    assert ret == 0
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["status"] == "completed"
    assert data["model_id"] == "cli-test+fixture-answers"
