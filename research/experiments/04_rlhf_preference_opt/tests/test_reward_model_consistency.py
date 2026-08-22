"""Tests for persona-consistency metrics in RLHF reward signal and ablation runner (Abdulhai et al. 2025).

All tests run offline — no real LLM API calls, no real GPU, no MLflow backend server needed.
"""
from __future__ import annotations

import contextlib
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import yaml

_EXP_DIR = Path(__file__).resolve().parents[1]
_RESEARCH_ROOT = _EXP_DIR.parents[1]
sys.path.insert(0, str(_RESEARCH_ROOT))

from evaluation.reward_model import (
    CONSISTENCY_DIMENSIONS,
    DEFAULT_REWARD_WEIGHTS,
    DEFAULT_REWARD_WEIGHTS_WITH_CONSISTENCY,
    PairReward,
    PairScores,
    _DIMENSIONS,
    _EXTENDED_DIMENSIONS,
    _weighted_reward,
    compute_consistency_scores,
    evaluate_probe,
    fit_reward_probe,
    load_preference_pairs,
    measure_persona_drift,
    pairs_to_dpo_format,
    score_dataset,
    score_pair,
)

_CONFIG_PATH = _RESEARCH_ROOT / "configs" / "c4_rlhf_preference_opt.yaml"


def _load_runner():
    spec = importlib.util.spec_from_file_location("c4_run", _EXP_DIR / "run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@contextlib.contextmanager
def _offline(judge_score: float = 0.75):
    import evaluation.metrics as _metrics
    _run = _load_runner()

    mock_mlflow = MagicMock(name="mlflow")
    mock_mlflow.start_run.return_value.__enter__ = MagicMock(return_value=None)
    mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)

    with (
        patch.object(_run, "mlflow", mock_mlflow),
        patch.object(_metrics, "mlflow", mock_mlflow),
        patch.dict(sys.modules, {"mlflow": mock_mlflow}),
        patch("evaluation.reward_model.score_all_dimensions",
              side_effect=lambda p, r: {d: judge_score for d in _DIMENSIONS}),
        patch("evaluation.metrics.score_all_dimensions",
              side_effect=lambda p, r: {d: judge_score for d in _DIMENSIONS}),
    ):
        yield mock_mlflow, _run


def _make_consistency_scored_pairs(n: int = 20) -> list[PairScores]:
    rng = np.random.default_rng(42)
    pairs = []
    for i in range(n):
        if i % 2 == 0:
            scores_a = {d: float(rng.uniform(0.6, 1.0)) for d in _EXTENDED_DIMENSIONS}
            scores_b = {d: float(rng.uniform(0.1, 0.45)) for d in _EXTENDED_DIMENSIONS}
            preferred = "a"
        else:
            scores_a = {d: float(rng.uniform(0.1, 0.45)) for d in _EXTENDED_DIMENSIONS}
            scores_b = {d: float(rng.uniform(0.6, 1.0)) for d in _EXTENDED_DIMENSIONS}
            preferred = "b"
        pairs.append(PairScores(
            prompt=f"Consistency prompt {i}",
            scores_a=scores_a,
            scores_b=scores_b,
            preferred=preferred,
            persona_slug="chioma-base",
            include_consistency=True,
        ))
    return pairs


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Consistency Scoring Functions
# ═══════════════════════════════════════════════════════════════════════════════

class TestConsistencyScoring:
    def test_compute_consistency_scores_keys(self):
        prompt = "How do I save money in Lagos?"
        response = "Open a target savings account today. Set aside 20% of your weekly earnings."
        scores = compute_consistency_scores(prompt, response, persona_slug="chioma-base")

        assert "prompt_to_line" in scores
        assert "line_to_line" in scores
        assert "qa_consistency" in scores

    def test_compute_consistency_scores_bounds(self):
        prompt = "How do I manage debt?"
        response = "Pay down the highest interest rate loan first."
        scores = compute_consistency_scores(prompt, response, persona_slug="chioma-base")

        for key, val in scores.items():
            assert 0.0 <= val <= 1.0, f"Score for {key} is out of bounds: {val}"

    def test_compute_consistency_with_reference(self):
        prompt = "What is working capital?"
        response = "Working capital is current assets minus current liabilities."
        ref = "Working capital measures short-term liquidity: assets minus liabilities."
        scores = compute_consistency_scores(prompt, response, persona_slug="chioma-base", reference=ref)
        assert scores["line_to_line"] > 0.3


# ═══════════════════════════════════════════════════════════════════════════════
# 2. PairScores & Data Structure Extensions
# ═══════════════════════════════════════════════════════════════════════════════

class TestPairScoresWithConsistency:
    def test_base_dimensions_count(self):
        ps = PairScores(prompt="q", scores_a={}, scores_b={}, preferred="a", include_consistency=False)
        assert len(ps.dimensions) == 5
        assert len(ps.delta) == 5

    def test_extended_dimensions_count(self):
        ps = PairScores(prompt="q", scores_a={}, scores_b={}, preferred="a", include_consistency=True)
        assert len(ps.dimensions) == 8
        assert len(ps.delta) == 8
        for cd in CONSISTENCY_DIMENSIONS:
            assert cd in ps.dimensions


# ═══════════════════════════════════════════════════════════════════════════════
# 3. score_pair and score_dataset with Consistency
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoringWithConsistency:
    def test_score_pair_without_consistency(self):
        with patch("evaluation.reward_model.score_all_dimensions", return_value={d: 0.7 for d in _DIMENSIONS}):
            result = score_pair("prompt", "response a", "response b", include_consistency=False)
            assert isinstance(result, PairReward)
            assert "prompt_to_line" not in result.scores_a

    def test_score_pair_with_consistency(self):
        with patch("evaluation.reward_model.score_all_dimensions", return_value={d: 0.7 for d in _DIMENSIONS}):
            result = score_pair("prompt", "response a", "response b", include_consistency=True)
            assert isinstance(result, PairReward)
            assert "prompt_to_line" in result.scores_a
            assert "line_to_line" in result.scores_a
            assert "qa_consistency" in result.scores_a

    def test_score_dataset_with_consistency(self):
        pairs = [
            {"prompt": "Q1", "response_a": "A1", "response_b": "B1", "preferred": "a", "persona_slug": "chioma-base"},
            {"prompt": "Q2", "response_a": "A2", "response_b": "B2", "preferred": "b", "persona_slug": "market-queen"},
        ]
        with patch("evaluation.reward_model.score_all_dimensions", return_value={d: 0.7 for d in _DIMENSIONS}):
            scored = score_dataset(pairs, include_consistency=True)
            assert len(scored) == 2
            assert scored[0].include_consistency is True
            assert len(scored[0].delta) == 8


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Probe Fitting and Evaluation with Consistency Features
# ═══════════════════════════════════════════════════════════════════════════════

class TestProbeWithConsistency:
    def test_fit_reward_probe_extended(self):
        pairs = _make_consistency_scored_pairs(20)
        probe, report = fit_reward_probe(pairs)
        assert probe is not None
        assert report["train_accuracy"] > 0.5
        assert len(report["feature_names"]) == 8
        for cd in CONSISTENCY_DIMENSIONS:
            assert cd in report["probe_coefficients"]

    def test_evaluate_probe_extended(self):
        pairs = _make_consistency_scored_pairs(20)
        probe, _ = fit_reward_probe(pairs)
        val_report = evaluate_probe(probe, pairs)
        assert val_report["accuracy"] > 0.6


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Persona Drift Measurement
# ═══════════════════════════════════════════════════════════════════════════════

class TestPersonaDrift:
    def test_measure_persona_drift_empty(self):
        drift = measure_persona_drift([], persona_slug="chioma-base")
        assert drift["drift_magnitude"] == 0.0

    def test_measure_persona_drift_degradation(self):
        # Early turns aligned with Chioma, late turns generic
        early = [
            "You must separate business money from personal money immediately.",
            "Open a separate merchant account before Friday.",
        ]
        late = [
            "It might be nice to save sometimes.",
            "Everything is fine, don't worry about anything.",
        ]
        drift = measure_persona_drift(early + late, persona_slug="chioma-base")
        assert drift["early_p2l"] > drift["late_p2l"]
        assert drift["drift_magnitude"] > 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Ablation Runner and Orchestrator
# ═══════════════════════════════════════════════════════════════════════════════

class TestAblationRunner:
    def test_run_ablation_structure(self, tmp_path):
        with _offline() as (mock_mlflow, runner):
            cfg = runner.load_config(_CONFIG_PATH)
            cfg["reward_model"]["probe_output"] = str(tmp_path / "probe.pkl")
            summary = runner.run_ablation(cfg)

            assert "without_consistency" in summary
            assert "with_consistency" in summary
            assert "comparison" in summary
            assert "persona_drift_reduction_pct" in summary["comparison"]

    def test_run_with_ablation_flag(self, tmp_path):
        with _offline() as (mock_mlflow, runner):
            cfg = runner.load_config(_CONFIG_PATH)
            cfg["reward_model"]["probe_output"] = str(tmp_path / "probe.pkl")

            results = runner.run(
                _CONFIG_PATH,
                stage="reward_model",
                run_ablation_flag=True,
            )

            assert "ablation_report" in results
            assert results["ablation_report"] != {}
            assert "comparison" in results["ablation_report"]

