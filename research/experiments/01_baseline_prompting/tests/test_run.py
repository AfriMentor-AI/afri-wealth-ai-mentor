"""Tests for C1 baseline prompting experiment (card D2.4).

All tests run fully offline — OpenAI calls and MLflow are mocked.
The test suite verifies:
  - few-shot bank loads and filters correctly
  - eval samples load from sft_test.jsonl and fall back to synthetic
  - run() executes all 3 prompting modes and returns per-mode metrics
  - MLflow params and metrics are logged with correct keys
  - per-persona composite metrics are logged
  - EvalResult composite score weights match the rubric
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ── Module loaders (digit-prefixed dir can't be a normal package import) ──────

_EXP_DIR = Path(__file__).resolve().parents[1]
_RESEARCH_ROOT = _EXP_DIR.parents[1]
_SPLITS_DIR = _RESEARCH_ROOT / "datasets" / "splits"
_CONFIG_PATH = _RESEARCH_ROOT / "configs" / "c1_baseline_prompting.yaml"


def _load_module(name: str, filepath: Path):
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_fsb = _load_module("few_shot_bank", _EXP_DIR / "few_shot_bank.py")
_run = _load_module("run", _EXP_DIR / "run.py")


def _fake_completion(content: str = "Save 20% of your daily takings first."):
    """Return a minimal OpenAI chat completion mock."""
    choice = SimpleNamespace(message=SimpleNamespace(content=content))
    return SimpleNamespace(choices=[choice])


def _patch_openai(content: str = "Save 20% of your daily takings first."):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_completion(content)
    return patch.object(_run, "OpenAI", return_value=mock_client)


def _patch_mlflow():
    import evaluation.metrics as _metrics
    from unittest.mock import patch as _patch
    import contextlib

    @contextlib.contextmanager
    def _combined():
        with _patch.object(_run, "mlflow") as mock_run_mlflow, \
             _patch.object(_metrics, "mlflow"):
            yield mock_run_mlflow

    return _combined()


def _patch_judge(score: float = 0.75):
    """Patch the LLM judge so eval metrics return a fixed score offline."""
    import evaluation.metrics as _metrics
    return patch.object(_metrics, "_llm_score", return_value=score)


# ── Few-shot bank ─────────────────────────────────────────────────────────────

class TestFewShotBank:
    def test_returns_empty_when_no_train_file(self, tmp_path):
        result = _fsb.load_few_shot_examples("market-queen", 3, splits_dir=tmp_path)
        assert result == []

    def test_filters_by_persona(self, tmp_path):
        records = [
            {"persona_slug": "market-queen", "messages": [
                {"role": "user", "content": "Q1"}, {"role": "assistant", "content": "A1"}
            ]},
            {"persona_slug": "tech-founder", "messages": [
                {"role": "user", "content": "Q2"}, {"role": "assistant", "content": "A2"}
            ]},
        ]
        train_file = tmp_path / "sft_train.jsonl"
        train_file.write_text("\n".join(json.dumps(r) for r in records))

        result = _fsb.load_few_shot_examples("market-queen", 1, splits_dir=tmp_path)
        assert len(result) == 1
        assert result[0]["user"] == "Q1"

    def test_falls_back_cross_persona_when_insufficient(self, tmp_path):
        records = [
            {"persona_slug": "market-queen", "messages": [
                {"role": "user", "content": "Q1"}, {"role": "assistant", "content": "A1"}
            ]},
            {"persona_slug": "tech-founder", "messages": [
                {"role": "user", "content": "Q2"}, {"role": "assistant", "content": "A2"}
            ]},
        ]
        train_file = tmp_path / "sft_train.jsonl"
        train_file.write_text("\n".join(json.dumps(r) for r in records))

        result = _fsb.load_few_shot_examples("market-queen", 2, splits_dir=tmp_path)
        assert len(result) == 2

    def test_returns_n_examples_from_real_split(self):
        if not (_SPLITS_DIR / "sft_train.jsonl").exists():
            pytest.skip("sft_train.jsonl not generated yet")
        result = _fsb.load_few_shot_examples("market-queen", 3)
        assert len(result) <= 3
        for ex in result:
            assert "user" in ex and "assistant" in ex

    def test_deterministic_with_same_seed(self):
        if not (_SPLITS_DIR / "sft_train.jsonl").exists():
            pytest.skip("sft_train.jsonl not generated yet")
        r1 = _fsb.load_few_shot_examples("chioma-base", 2, seed=42)
        r2 = _fsb.load_few_shot_examples("chioma-base", 2, seed=42)
        assert r1 == r2


# ── Eval sample loader ────────────────────────────────────────────────────────

class TestLoadEvalSamples:
    def test_loads_from_sft_test_jsonl(self):
        if not (_SPLITS_DIR / "sft_test.jsonl").exists():
            pytest.skip("sft_test.jsonl not generated yet")
        samples = _run.load_eval_samples(5)
        assert len(samples) >= 1
        for s in samples:
            assert "user" in s and "persona" in s

    def test_falls_back_to_synthetic(self, tmp_path):
        original = _run.SPLITS_DIR
        _run.SPLITS_DIR = tmp_path
        try:
            samples = _run.load_eval_samples(6)
            assert len(samples) == 6
            personas = {s["persona"] for s in samples}
            assert "market-queen" in personas
            assert "chioma-base" in personas
        finally:
            _run.SPLITS_DIR = original

    def test_respects_sample_size_cap(self):
        samples = _run.load_eval_samples(2)
        assert len(samples) <= 2


# ── EvalResult composite score ────────────────────────────────────────────────

class TestEvalResultComposite:
    def test_weights_sum_to_one(self):
        from evaluation.metrics import EvalResult
        r = EvalResult(
            persona_adherence=1.0,
            cultural_fluency=1.0,
            anti_dependency=1.0,
            financial_accuracy=1.0,
            urgency=1.0,
        )
        assert abs(r.composite_score - 1.0) < 1e-9

    def test_zero_scores_give_zero_composite(self):
        from evaluation.metrics import EvalResult
        assert EvalResult().composite_score == 0.0

    def test_partial_scores(self):
        from evaluation.metrics import EvalResult
        r = EvalResult(persona_adherence=1.0)
        assert abs(r.composite_score - 0.25) < 1e-9


# ── Full run() pipeline ───────────────────────────────────────────────────────

class TestRunPipeline:
    def _make_cfg(self, modes: list[str], sample_size: int) -> str:
        import os
        import tempfile

        import yaml
        cfg = yaml.safe_load(_CONFIG_PATH.read_text())
        cfg["evaluation"]["sample_size"] = sample_size
        cfg["prompting"]["modes"] = modes
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(cfg, f)
            return f.name

    def _run_offline(self, sample_size: int = 2):
        import os
        tmp_cfg = self._make_cfg(["zero_shot"], sample_size)
        try:
            with (
                _patch_openai(),
                _patch_mlflow() as mock_mlflow,
                _patch_judge(0.8),
            ):
                mock_mlflow.start_run.return_value.__enter__ = MagicMock(return_value=None)
                mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)
                results = _run.run(tmp_cfg)
            return results, mock_mlflow
        finally:
            os.unlink(tmp_cfg)

    def test_run_returns_per_mode_dict(self):
        results, _ = self._run_offline()
        assert "zero_shot" in results
        assert "composite_score" in results["zero_shot"]

    def test_composite_score_in_valid_range(self):
        results, _ = self._run_offline()
        score = results["zero_shot"]["composite_score"]
        assert 0.0 <= score <= 1.0

    def test_mlflow_params_logged(self):
        _, mock_mlflow = self._run_offline()
        mock_mlflow.log_params.assert_called()
        call_kwargs = mock_mlflow.log_params.call_args[0][0]
        assert call_kwargs["condition_id"] == "C1"
        assert call_kwargs["prompting_mode"] == "zero_shot"

    def test_mlflow_metrics_logged(self):
        _, mock_mlflow = self._run_offline()
        mock_mlflow.log_metric.assert_called()
        metric_names = [call[0][0] for call in mock_mlflow.log_metric.call_args_list]
        assert any("avg_composite" in m for m in metric_names)

    def test_all_three_modes_run(self):
        import os
        tmp_cfg = self._make_cfg(["zero_shot", "few_shot_3", "few_shot_5"], 1)
        try:
            with (
                _patch_openai(),
                _patch_mlflow() as mock_mlflow,
                _patch_judge(0.7),
            ):
                mock_mlflow.start_run.return_value.__enter__ = MagicMock(return_value=None)
                mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)
                results = _run.run(tmp_cfg)
            assert set(results.keys()) == {"zero_shot", "few_shot_3", "few_shot_5"}
        finally:
            os.unlink(tmp_cfg)

    def test_few_shot_messages_include_examples(self):
        import os
        tmp_cfg = self._make_cfg(["few_shot_3"], 1)
        captured_messages: list = []

        def _capture_create(**kwargs):
            captured_messages.extend(kwargs.get("messages", []))
            return _fake_completion()

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = _capture_create

        try:
            with (
                patch.object(_run, "OpenAI", return_value=mock_client),
                _patch_mlflow() as mock_mlflow,
                _patch_judge(0.7),
            ):
                mock_mlflow.start_run.return_value.__enter__ = MagicMock(return_value=None)
                mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)
                _run.run(tmp_cfg)
            if (_SPLITS_DIR / "sft_train.jsonl").exists():
                # system + at least 1 few-shot pair (user+assistant) + user query = 4
                assert len(captured_messages) >= 4
        finally:
            os.unlink(tmp_cfg)
