"""Tests for the C3 persona-aware contrastive-learning runner (card C3.1).

All tests run fully offline — torch reports no CUDA (conftest), MLflow and the
OpenAI judge are mocked, and generation is injected. The suite verifies the part
of C3 that C3.1 adds: the trained checkpoint is scored against the SAME metric
suite as C1/C2 and logged with the SAME MLflow keys, so the conditions compare.

Coverage:
  - eval-sample loader: synthetic fallback + sample-size cap
  - aggregation helper
  - evaluate_checkpoint: scores, aggregates, composite weighting, MLflow logging
  - train(): takes the no-GPU path safely
  - run(): eval-only flow, C3 params logged, avg_composite logged, and that a
    skipped (no-GPU) train still evaluates when a generator is injected
  - config: eval + DPO keys present; metric keys match the C1/C2 suite
"""
from __future__ import annotations

import contextlib
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from evaluation.checkpoint_eval import avg_scores, evaluate_checkpoint, load_eval_samples

def _judge_all(value):
    """Stand-in for metrics.score_all_dimensions: every rubric dimension scores ``value``."""
    dims = ("persona_adherence", "cultural_fluency", "anti_dependency", "financial_accuracy", "urgency")
    return lambda *a, **k: dict.fromkeys(dims, value)


_EXP_DIR = Path(__file__).resolve().parents[1]
_RESEARCH_ROOT = _EXP_DIR.parents[1]
_SPLITS_DIR = _RESEARCH_ROOT / "datasets" / "splits"
_CONFIG_PATH = _RESEARCH_ROOT / "configs" / "c3_contrastive_learning.yaml"


def _load_module(name: str, filepath: Path):
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_run = _load_module("c3_run", _EXP_DIR / "run.py")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fake_generate(system_prompt: str, user_message: str) -> str:
    """A deterministic stand-in for model generation."""
    return (
        "Separate your business and personal money first. Save 20% of your daily "
        "takings into a fixed account — like the market women's ajo. What's your "
        "daily profit right now?"
    )


def _sp(_persona: str) -> str:
    return "You are Chioma, an African financial mentor. Be direct and practical."


@contextlib.contextmanager
def _offline(judge_score: float = 0.8):
    """Patch MLflow (everywhere it's referenced) and the LLM judge to fixed values.

    Yields the single mock MLflow shared by the runner, evaluation.metrics, and
    checkpoint_eval's lazy ``import mlflow`` — so every metric call is observable.
    """
    import evaluation.metrics as _metrics

    mock_mlflow = MagicMock(name="mlflow")
    mock_mlflow.start_run.return_value.__enter__ = MagicMock(return_value=None)
    mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)

    with patch.object(_run, "mlflow", mock_mlflow), \
         patch.object(_metrics, "mlflow", mock_mlflow), \
         patch.dict(sys.modules, {"mlflow": mock_mlflow}), \
         patch.object(_metrics, "score_all_dimensions", side_effect=_judge_all(judge_score)):
        yield mock_mlflow


def _cfg(sample_size: int = 3) -> dict:
    cfg = yaml.safe_load(_CONFIG_PATH.read_text())
    cfg["evaluation"]["sample_size"] = sample_size
    return cfg


# ── Eval sample loader ──────────────────────────────────────────────────────

class TestLoadEvalSamples:
    def test_falls_back_to_synthetic(self, tmp_path):
        samples = load_eval_samples(6, splits_dir=tmp_path)
        assert len(samples) == 6
        personas = {s["persona"] for s in samples}
        assert "market-queen" in personas
        assert "chioma-base" in personas

    def test_respects_sample_size_cap(self, tmp_path):
        assert len(load_eval_samples(2, splits_dir=tmp_path)) == 2

    def test_loads_from_real_split_when_present(self):
        if not (_SPLITS_DIR / "sft_test.jsonl").exists():
            pytest.skip("sft_test.jsonl not generated yet")
        samples = load_eval_samples(5)
        assert len(samples) >= 1
        for s in samples:
            assert "user" in s and "persona" in s


# ── Aggregation ────────────────────────────────────────────────────────────────

class TestAvgScores:
    def test_means_ignore_non_numeric(self):
        rows = [
            {"composite_score": 1.0, "persona": "x"},
            {"composite_score": 3.0, "persona": "y"},
        ]
        agg = avg_scores(rows)
        assert agg == {"composite_score": 2.0}
        assert "persona" not in agg

    def test_empty_rows(self):
        assert avg_scores([]) == {}


# ── evaluate_checkpoint (the acceptance criterion, in miniature) ───────────────

class TestEvaluateCheckpoint:
    def test_scores_and_aggregates(self):
        samples = load_eval_samples(3, splits_dir=Path("/nonexistent"))
        calls: list[tuple] = []

        def _gen(sp, um):
            calls.append((sp, um))
            return _fake_generate(sp, um)

        import evaluation.metrics as _metrics
        with patch.object(_metrics, "score_all_dimensions", side_effect=_judge_all(0.8)):
            agg = evaluate_checkpoint(_gen, samples, system_prompt_fn=_sp, log_to_mlflow=False)

        assert len(calls) == len(samples)          # generated once per sample
        assert 0.0 <= agg["composite_score"] <= 1.0
        assert abs(agg["persona_adherence"] - 0.8) < 1e-9

    def test_composite_matches_rubric_weights(self):
        samples = load_eval_samples(1, splits_dir=Path("/nonexistent"))
        import evaluation.metrics as _metrics
        with patch.object(_metrics, "score_all_dimensions", side_effect=_judge_all(1.0)):
            agg = evaluate_checkpoint(
                _fake_generate, samples, system_prompt_fn=_sp, log_to_mlflow=False
            )
        # 5 judge dims all 1.0, weights sum to 1.0 → composite 1.0 (rouge/bert
        # excluded from composite, and 0.0 here since references are None).
        assert abs(agg["composite_score"] - 1.0) < 1e-9

    def test_logs_metric_suite_to_mlflow(self):
        samples = load_eval_samples(3, splits_dir=Path("/nonexistent"))
        with _offline(judge_score=0.7) as mock_mlflow:
            evaluate_checkpoint(_fake_generate, samples, system_prompt_fn=_sp, log_to_mlflow=True)

        metric_names = [c[0][0] for c in mock_mlflow.log_metric.call_args_list]
        assert "avg_composite_score" in metric_names
        assert "avg_persona_adherence" in metric_names
        # per-sample logging happened too (log_eval_to_mlflow → log_metrics)
        assert mock_mlflow.log_metrics.call_count == len(samples)


# ── train() no-GPU guard ────────────────────────────────────────────────────

class TestTrainGuard:
    def test_returns_none_without_gpu(self):
        """On a CPU/bare host, train() skips cleanly instead of importing the stack."""
        adapter, dpo_eval = _run.train(_cfg())
        assert adapter is None
        assert dpo_eval == {}


# ── run() orchestration ──────────────────────────────────────────────────────

class TestRunPipeline:
    def test_eval_only_returns_metric_suite(self):
        with _offline():
            results = _run.run(_write_cfg(), do_train=False, generate_fn=_fake_generate)
        assert results["condition_id"] == "C3"
        assert results["trained"] is False
        assert 0.0 <= results["eval_metrics"]["composite_score"] <= 1.0

    def test_logs_c3_params(self):
        with _offline() as mock_mlflow:
            _run.run(_write_cfg(), do_train=False, generate_fn=_fake_generate)
        mock_mlflow.log_params.assert_called()
        params = mock_mlflow.log_params.call_args[0][0]
        assert params["condition_id"] == "C3"
        assert params["loss_type"] == "sigmoid"

    def test_logs_avg_composite_metric(self):
        """Same MLflow key C1/C2 log — this is what makes the conditions comparable."""
        with _offline() as mock_mlflow:
            _run.run(_write_cfg(), do_train=False, generate_fn=_fake_generate)
        metric_names = [c[0][0] for c in mock_mlflow.log_metric.call_args_list]
        assert any("avg_composite" in m for m in metric_names)

    def test_train_skipped_without_gpu_still_evaluates(self):
        """do_train=True on a CPU host: training is skipped, but an injected
        generator still lets the metric-suite eval run and log."""
        with _offline():
            results = _run.run(_write_cfg(), do_train=True, generate_fn=_fake_generate)
        assert results["trained"] is False
        assert results["eval_metrics"] != {}


# ── Config ───────────────────────────────────────────────────────────────────

class TestConfig:
    def test_has_eval_and_dpo_keys(self):
        cfg = yaml.safe_load(_CONFIG_PATH.read_text())
        assert cfg["evaluation"]["sample_size"] >= 1
        assert cfg["dpo"]["beta"] > 0
        assert cfg["mlflow"]["experiment_name"]

    def test_metric_suite_matches_c1_dimensions(self):
        """C3's scored dimensions must equal the shared rubric (else not comparable)."""
        samples = load_eval_samples(1, splits_dir=Path("/nonexistent"))
        import evaluation.metrics as _metrics
        with patch.object(_metrics, "score_all_dimensions", side_effect=_judge_all(0.5)):
            agg = evaluate_checkpoint(
                _fake_generate, samples, system_prompt_fn=_sp, log_to_mlflow=False
            )
        rubric = {
            "persona_adherence", "cultural_fluency", "anti_dependency",
            "financial_accuracy", "urgency", "composite_score",
        }
        assert rubric.issubset(agg.keys())


# A temp config file whose sample_size is small, for the run() pipeline tests.
def _write_cfg(sample_size: int = 3) -> str:
    import tempfile

    cfg = _cfg(sample_size)
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    yaml.dump(cfg, f)
    f.close()
    return f.name
