"""Tests for the C4 RLHF / Preference Optimization runner (card D1.4).

All tests run fully offline — no GPU, no real LLM API calls, no MLflow writes.
The LLM judge and sklearn probe are mocked or constructed from synthetic data,
and generation is injected.

Coverage
--------
- reward_model.PairScores: delta computation, label encoding
- reward_model.fit_reward_probe: probe trains on synthetic scored pairs, accuracy > 0.5
- reward_model.evaluate_probe: returns accuracy dict on held-out pairs
- reward_model.pairs_to_dpo_format: probe-guided re-ranking logic, fallback to label
- reward_model.load_preference_pairs: loads JSONL, graceful empty path
- reward_model.score_pair: returns PairReward with correct structure (mocked judge)
- run.run_reward_model: full stage 1 with mocked judge + MLflow, logs probe metrics
- run.run_dpo: skips gracefully without GPU, returns (None, {})
- run.run_evaluate: logs avg_composite_score and avg_persona_adherence (mocked generator)
- run.run: full end-to-end with injected generator and mocked MLflow
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

# ── Path setup ─────────────────────────────────────────────────────────────────
_EXP_DIR = Path(__file__).resolve().parents[1]
_RESEARCH_ROOT = _EXP_DIR.parents[1]
sys.path.insert(0, str(_RESEARCH_ROOT))

from evaluation.reward_model import (
    PairScores,
    fit_reward_probe,
    evaluate_probe,
    load_preference_pairs,
    pairs_to_dpo_format,
    PairReward,
    score_pair,
    _weighted_reward,
    DEFAULT_REWARD_WEIGHTS,
    _DIMENSIONS,
)

_CONFIG_PATH = _RESEARCH_ROOT / "configs" / "c4_rlhf_preference_opt.yaml"


# ── Helper: load the runner module ─────────────────────────────────────────────

def _load_runner():
    spec = importlib.util.spec_from_file_location("c4_run", _EXP_DIR / "run.py")
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ── Shared MLflow mock ─────────────────────────────────────────────────────────

@contextlib.contextmanager
def _offline(judge_score: float = 0.75):
    """Patch mlflow everywhere the runner and evaluation modules reference it.

    Uses patch.object on the runner module's 'mlflow' attribute (same pattern
    as the C3 test suite) to avoid the lazy-loading issue with mlflow 2.19.
    Yields the single MagicMock mlflow so tests can assert on calls.
    """
    import evaluation.metrics as _metrics
    import evaluation.checkpoint_eval as _ceval
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
        patch("evaluation.metrics.evaluate_response", side_effect=lambda *a, **kw: _fake_eval_result()),
    ):
        yield mock_mlflow, _run


def _fake_eval_result():
    """Return a mock EvalResult with fixed scores."""
    mock = MagicMock()
    mock.composite_score = 0.70
    mock.to_dict.return_value = {d: 0.70 for d in
                                  ["persona_adherence", "cultural_fluency",
                                   "anti_dependency", "financial_accuracy",
                                   "urgency", "rouge_l", "bert_score_f1"]}
    return mock


# ── Helper: synthetic scored pairs ─────────────────────────────────────────────

def _make_scored_pairs(n: int = 20) -> list[PairScores]:
    """Synthetic PairScores with mixed labels for probe fitting.

    Half the pairs have response_a preferred (scores_a > scores_b, label=1);
    half have response_b preferred (scores_b > scores_a, label=0).
    This ensures both classes are present — required by sklearn LogisticRegression.
    """
    rng = np.random.default_rng(42)
    pairs = []
    for i in range(n):
        if i % 2 == 0:
            # response_a dominates → preferred="a", label=1
            scores_a = {d: float(rng.uniform(0.6, 1.0)) for d in _DIMENSIONS}
            scores_b = {d: float(rng.uniform(0.1, 0.45)) for d in _DIMENSIONS}
            preferred = "a"
        else:
            # response_b dominates → preferred="b", label=0
            scores_a = {d: float(rng.uniform(0.1, 0.45)) for d in _DIMENSIONS}
            scores_b = {d: float(rng.uniform(0.6, 1.0)) for d in _DIMENSIONS}
            preferred = "b"
        pairs.append(PairScores(
            prompt=f"Test prompt {i}",
            scores_a=scores_a,
            scores_b=scores_b,
            preferred=preferred,
            persona_slug="chioma-base",
        ))
    return pairs


# ── Fake generator ──────────────────────────────────────────────────────────────

def _fake_generate(system_prompt: str, user_message: str) -> str:
    return (
        "Separate your business money from personal today — not tomorrow. "
        "Open a second account this afternoon. What is your current salary?"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PairScores tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPairScores:
    def test_delta_length(self):
        ps = _make_scored_pairs(1)[0]
        assert len(ps.delta) == len(_DIMENSIONS)

    def test_delta_positive_when_a_dominates(self):
        ps = PairScores(
            prompt="q",
            scores_a={d: 0.8 for d in _DIMENSIONS},
            scores_b={d: 0.2 for d in _DIMENSIONS},
            preferred="a",
        )
        assert all(delta > 0 for delta in ps.delta)

    def test_label_a_is_1(self):
        ps = PairScores(prompt="q", scores_a={}, scores_b={}, preferred="a")
        assert ps.label == 1

    def test_label_b_is_0(self):
        ps = PairScores(prompt="q", scores_a={}, scores_b={}, preferred="b")
        assert ps.label == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Probe fitting tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestFitRewardProbe:
    def test_probe_trains_without_error(self):
        pairs = _make_scored_pairs(20)
        probe, report = fit_reward_probe(pairs)
        assert probe is not None

    def test_probe_train_accuracy_above_chance(self):
        """On perfectly separable synthetic data, accuracy should be > 0.5."""
        pairs = _make_scored_pairs(40)
        probe, report = fit_reward_probe(pairs)
        assert report["train_accuracy"] > 0.5

    def test_report_has_required_keys(self):
        pairs = _make_scored_pairs(10)
        _, report = fit_reward_probe(pairs)
        for key in ("train_accuracy", "n_samples", "feature_names", "probe_coefficients"):
            assert key in report, f"Missing key: {key}"

    def test_probe_coefficients_cover_all_dimensions(self):
        pairs = _make_scored_pairs(10)
        _, report = fit_reward_probe(pairs)
        coefs = report["probe_coefficients"]
        for dim in _DIMENSIONS:
            assert dim in coefs

    def test_fit_raises_on_empty_pairs(self):
        with pytest.raises(ValueError, match="No scored pairs"):
            fit_reward_probe([])


class TestEvaluateProbe:
    def test_returns_accuracy_dict(self):
        pairs = _make_scored_pairs(20)
        probe, _ = fit_reward_probe(pairs)
        report = evaluate_probe(probe, pairs)
        assert "accuracy" in report
        assert "n_samples" in report

    def test_accuracy_on_perfectly_separable_data(self):
        pairs = _make_scored_pairs(30)
        probe, _ = fit_reward_probe(pairs)
        report = evaluate_probe(probe, pairs)
        assert report["accuracy"] > 0.6  # fitted on same data → high acc

    def test_empty_eval_returns_zero(self):
        pairs = _make_scored_pairs(10)
        probe, _ = fit_reward_probe(pairs)
        report = evaluate_probe(probe, [])
        assert report["accuracy"] == 0.0
        assert report["n_samples"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Preference pair loading
# ═══════════════════════════════════════════════════════════════════════════════

class TestLoadPreferencePairs:
    def test_loads_rlhf_train(self):
        path = _RESEARCH_ROOT / "datasets" / "splits" / "rlhf_train.jsonl"
        pairs = load_preference_pairs(path)
        assert len(pairs) >= 50, f"Expected ≥50 training pairs, got {len(pairs)}"

    def test_loads_rlhf_val(self):
        path = _RESEARCH_ROOT / "datasets" / "splits" / "rlhf_val.jsonl"
        pairs = load_preference_pairs(path)
        assert len(pairs) >= 12

    def test_loads_rlhf_test(self):
        path = _RESEARCH_ROOT / "datasets" / "splits" / "rlhf_test.jsonl"
        pairs = load_preference_pairs(path)
        assert len(pairs) >= 10

    def test_graceful_missing_file(self):
        pairs = load_preference_pairs("/nonexistent/path.jsonl")
        assert pairs == []

    def test_required_fields_present(self):
        path = _RESEARCH_ROOT / "datasets" / "splits" / "rlhf_train.jsonl"
        pairs = load_preference_pairs(path)
        for p in pairs[:5]:
            for key in ("prompt", "response_a", "response_b", "preferred"):
                assert key in p, f"Missing key '{key}' in pair {p.get('pair_id', '?')}"

    def test_preferred_values_are_a_or_b(self):
        path = _RESEARCH_ROOT / "datasets" / "splits" / "rlhf_train.jsonl"
        pairs = load_preference_pairs(path)
        for p in pairs:
            assert p["preferred"] in ("a", "b")

    def test_all_persona_slugs_represented(self):
        path = _RESEARCH_ROOT / "datasets" / "splits" / "rlhf_train.jsonl"
        pairs = load_preference_pairs(path)
        slugs = {p.get("persona_slug") for p in pairs}
        expected = {"chioma-base", "market-queen", "tech-founder", "trader", "rural-hustler", "creative"}
        assert expected.issubset(slugs), f"Missing slugs: {expected - slugs}"


# ═══════════════════════════════════════════════════════════════════════════════
# DPO format conversion
# ═══════════════════════════════════════════════════════════════════════════════

class TestPairsToDpoFormat:
    def _raw_pairs(self):
        return [
            {"prompt": "Q1", "response_a": "A1", "response_b": "B1", "preferred": "a", "persona_slug": "chioma-base"},
            {"prompt": "Q2", "response_a": "A2", "response_b": "B2", "preferred": "b", "persona_slug": "market-queen"},
        ]

    def test_no_probe_uses_dataset_label(self):
        dpo = pairs_to_dpo_format(self._raw_pairs(), probe=None)
        assert dpo[0]["chosen"] == "A1"
        assert dpo[0]["rejected"] == "B1"
        assert dpo[1]["chosen"] == "B2"   # preferred == "b"
        assert dpo[1]["rejected"] == "A2"

    def test_output_keys(self):
        dpo = pairs_to_dpo_format(self._raw_pairs(), probe=None)
        for rec in dpo:
            for key in ("prompt", "chosen", "rejected"):
                assert key in rec

    def test_with_confident_probe_overrides_label(self):
        """A probe that always predicts 'a' should flip the label==b pair."""
        # Build a probe that always returns P(a)=0.9
        mock_probe = MagicMock()
        mock_probe.predict_proba.return_value = np.array([[0.1, 0.9]])

        mock_scores = {d: 0.5 for d in _DIMENSIONS}
        with patch("evaluation.reward_model.score_all_dimensions", return_value=mock_scores):
            dpo = pairs_to_dpo_format(self._raw_pairs(), probe=mock_probe)
        # Pair 2 had preferred='b', but probe says 'a' with 90% confidence → override
        assert dpo[1]["chosen"] == "A2"

    def test_with_uncertain_probe_keeps_label(self):
        """A probe with prob_a=0.5 (uncertain) should keep the original label."""
        mock_probe = MagicMock()
        mock_probe.predict_proba.return_value = np.array([[0.5, 0.5]])

        mock_scores = {d: 0.5 for d in _DIMENSIONS}
        with patch("evaluation.reward_model.score_all_dimensions", return_value=mock_scores):
            dpo = pairs_to_dpo_format(self._raw_pairs(), probe=mock_probe)
        # Uncertain → original label preserved
        assert dpo[1]["chosen"] == "B2"


# ═══════════════════════════════════════════════════════════════════════════════
# score_pair (mocked judge)
# ═══════════════════════════════════════════════════════════════════════════════

class TestScorePair:
    def _mock_scores_a(self):
        return {d: 0.8 for d in _DIMENSIONS}

    def _mock_scores_b(self):
        return {d: 0.3 for d in _DIMENSIONS}

    def test_returns_pair_reward(self):
        call_count = [0]

        def mock_judge(prompt, response):
            call_count[0] += 1
            return self._mock_scores_a() if call_count[0] % 2 == 1 else self._mock_scores_b()

        with patch("evaluation.reward_model.score_all_dimensions", side_effect=mock_judge):
            result = score_pair("Q", "ResponseA", "ResponseB")

        assert isinstance(result, PairReward)

    def test_reward_a_higher_than_b_when_a_scores_higher(self):
        call_count = [0]

        def mock_judge(prompt, response):
            call_count[0] += 1
            return self._mock_scores_a() if call_count[0] % 2 == 1 else self._mock_scores_b()

        with patch("evaluation.reward_model.score_all_dimensions", side_effect=mock_judge):
            result = score_pair("Q", "ResponseA", "ResponseB")

        assert result.reward_a > result.reward_b

    def test_predicted_preferred_without_probe(self):
        call_count = [0]

        def mock_judge(prompt, response):
            call_count[0] += 1
            return self._mock_scores_a() if call_count[0] % 2 == 1 else self._mock_scores_b()

        with patch("evaluation.reward_model.score_all_dimensions", side_effect=mock_judge):
            result = score_pair("Q", "ResponseA", "ResponseB")

        assert result.predicted_preferred == "a"

    def test_both_scores_returned(self):
        call_count = [0]

        def mock_judge(prompt, response):
            call_count[0] += 1
            return self._mock_scores_a() if call_count[0] % 2 == 1 else self._mock_scores_b()

        with patch("evaluation.reward_model.score_all_dimensions", side_effect=mock_judge):
            result = score_pair("Q", "ResponseA", "ResponseB")

        assert result.scores_a and result.scores_b


# ═══════════════════════════════════════════════════════════════════════════════
# Runner: stage 1 (reward_model)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunRewardModel:
    def test_stage1_returns_probe_and_reports(self, tmp_path):
        with _offline() as (mock_mlflow, runner):
            cfg = runner.load_config(_CONFIG_PATH)
            cfg["reward_model"]["probe_output"] = str(tmp_path / "probe.pkl")
            result = runner.run_reward_model(cfg)

            assert result["probe"] is not None
            assert result["train_report"].get("n_samples", 0) > 0

    def test_stage1_logs_probe_accuracy_metric(self, tmp_path):
        with _offline() as (mock_mlflow, runner):
            cfg = runner.load_config(_CONFIG_PATH)
            cfg["reward_model"]["probe_output"] = str(tmp_path / "probe.pkl")
            runner.run_reward_model(cfg)

            metric_names = [c[0][0] for c in mock_mlflow.log_metric.call_args_list]
            assert "probe_train_accuracy" in metric_names


# ═══════════════════════════════════════════════════════════════════════════════
# Runner: stage 2 (dpo — CPU graceful skip)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunDpo:
    def test_dpo_skips_gracefully_without_gpu(self):
        runner = _load_runner()
        cfg = runner.load_config(_CONFIG_PATH)

        with patch("torch.cuda.is_available", return_value=False):
            adapter_path, dpo_metrics = runner.run_dpo(cfg)

        assert adapter_path is None
        assert dpo_metrics == {}

    def test_dpo_skip_returns_correctly_typed_tuple(self):
        runner = _load_runner()
        cfg = runner.load_config(_CONFIG_PATH)

        with patch("torch.cuda.is_available", return_value=False):
            result = runner.run_dpo(cfg)

        assert isinstance(result, tuple)
        assert len(result) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Runner: stage 3 (evaluate)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunEvaluate:
    def test_logs_same_keys_as_c1_c2_c3(self):
        """avg_persona_adherence and avg_composite_score must be logged."""
        with _offline() as (mock_mlflow, runner):
            cfg = runner.load_config(_CONFIG_PATH)
            runner.run_evaluate(cfg, generate_fn=_fake_generate)

            metric_names = [c[0][0] for c in mock_mlflow.log_metric.call_args_list]
            assert any("persona" in k for k in metric_names), \
                f"Expected avg_persona_adherence in logged keys. Got: {metric_names}"

    def test_evaluate_returns_aggregate_dict(self):
        with _offline() as (mock_mlflow, runner):
            cfg = runner.load_config(_CONFIG_PATH)
            agg = runner.run_evaluate(cfg, generate_fn=_fake_generate)
            assert isinstance(agg, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# Runner: full end-to-end (injected generator + mocked MLflow)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunEndToEnd:
    def test_full_run_returns_results_dict(self, tmp_path):
        with _offline() as (mock_mlflow, runner):
            cfg = runner.load_config(_CONFIG_PATH)
            cfg["reward_model"]["probe_output"] = str(tmp_path / "probe.pkl")

            results = runner.run(
                _CONFIG_PATH,
                stage="all",
                generate_fn=_fake_generate,
            )

            assert "condition_id" in results
            assert results["condition_id"] == "C4"
            assert "probe_report" in results
            assert "dpo_metrics" in results
            assert "eval_metrics" in results

    def test_full_run_condition_id_is_c4(self, tmp_path):
        with _offline() as (mock_mlflow, runner):
            cfg = runner.load_config(_CONFIG_PATH)
            cfg["reward_model"]["probe_output"] = str(tmp_path / "probe.pkl")

            results = runner.run(
                _CONFIG_PATH,
                stage="all",
                generate_fn=_fake_generate,
            )

            assert results["condition_id"] == "C4"


# ═══════════════════════════════════════════════════════════════════════════════
# Config validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfig:
    def test_c4_config_loads(self):
        cfg = yaml.safe_load(_CONFIG_PATH.read_text())
        assert cfg is not None

    def test_condition_id_is_c4(self):
        cfg = yaml.safe_load(_CONFIG_PATH.read_text())
        assert cfg["experiment"]["condition_id"] == "C4"

    def test_reward_weights_sum_to_one(self):
        cfg = yaml.safe_load(_CONFIG_PATH.read_text())
        weights = cfg["reward_model"]["reward_weights"]
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01, f"Reward weights sum to {total}, expected 1.0"

    def test_reward_weights_cover_all_dimensions(self):
        cfg = yaml.safe_load(_CONFIG_PATH.read_text())
        weights = cfg["reward_model"]["reward_weights"]
        for dim in _DIMENSIONS:
            assert dim in weights, f"Missing reward weight for dimension: {dim}"

    def test_dpo_section_present(self):
        cfg = yaml.safe_load(_CONFIG_PATH.read_text())
        assert "dpo" in cfg
        assert "beta" in cfg["dpo"]
        assert "loss_type" in cfg["dpo"]

    def test_evaluation_metrics_match_c1_c2_c3(self):
        cfg = yaml.safe_load(_CONFIG_PATH.read_text())
        metrics = cfg["evaluation"]["metrics"]
        required = {"persona_adherence", "cultural_fluency", "anti_dependency",
                    "financial_accuracy", "urgency", "rouge_l", "bert_score_f1"}
        assert required.issubset(set(metrics)), f"Missing metrics: {required - set(metrics)}"

    def test_mlflow_experiment_name_present(self):
        cfg = yaml.safe_load(_CONFIG_PATH.read_text())
        assert cfg["mlflow"]["experiment_name"]

    def test_probe_output_path_configured(self):
        cfg = yaml.safe_load(_CONFIG_PATH.read_text())
        assert cfg["reward_model"]["probe_output"]
