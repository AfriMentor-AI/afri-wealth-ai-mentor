"""Judge-failure handling: a failed LLM-judge call must not silently dilute an
aggregate as a genuine zero score (card C5.1 — hit live 3x in one Kaggle
session before this fix: C3's pairs_to_dpo_format, C4 Stage 1, C4 Stage 3).

Covers the full path: metrics.score_all_dimensions/evaluate_response marking
failures via EvalResult.metadata, then checkpoint_eval.avg_scores (and
comparative_eval's re-exported alias of it) excluding those rows from the
mean rather than averaging in their zeros.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from evaluation.checkpoint_eval import avg_scores, evaluate_checkpoint
from evaluation.metrics import EvalResult, evaluate_response, score_all_dimensions


# ── score_all_dimensions / evaluate_response: marking failures ────────────────

class TestScoreAllDimensionsFailureMarking:
    def test_missing_api_key_marks_judge_failed(self):
        fake_client = MagicMock()
        fake_client.api_key = ""
        with patch("evaluation.metrics._get_judge", return_value=fake_client):
            scores = score_all_dimensions("hi", "hello")
        assert scores["_judge_failed"] is True
        # Still returns the 5 rubric keys so existing callers (reward_model.py's
        # _weighted_reward, which indexes by name) don't break.
        assert scores["persona_adherence"] == 0.0

    def test_persistent_api_error_marks_judge_failed(self):
        fake_client = MagicMock()
        fake_client.api_key = "fake-key"
        fake_client.chat.completions.create.side_effect = RuntimeError("429 quota exceeded")
        with patch("evaluation.metrics._get_judge", return_value=fake_client), \
             patch("evaluation.metrics.time.sleep"):  # skip the real backoff delay
            scores = score_all_dimensions("hi", "hello")
        assert scores["_judge_failed"] is True

    def test_successful_call_has_no_judge_failed_key(self):
        fake_client = MagicMock()
        fake_client.api_key = "fake-key"
        fake_message = MagicMock()
        fake_message.content = '{"persona_adherence": 0.8, "cultural_fluency": 0.7, "anti_dependency": 0.6, "financial_accuracy": 0.9, "urgency": 0.5}'
        fake_response = MagicMock()
        fake_response.choices = [MagicMock(message=fake_message)]
        fake_client.chat.completions.create.return_value = fake_response
        with patch("evaluation.metrics._get_judge", return_value=fake_client):
            scores = score_all_dimensions("hi", "hello")
        assert "_judge_failed" not in scores
        assert scores["persona_adherence"] == 0.8


class TestEvaluateResponseFailureMarking:
    def test_judge_failure_flows_into_metadata_and_to_dict(self):
        with patch(
            "evaluation.metrics.score_all_dimensions",
            return_value={
                "persona_adherence": 0.0, "cultural_fluency": 0.0,
                "anti_dependency": 0.0, "financial_accuracy": 0.0, "urgency": 0.0,
                "_judge_failed": True,
            },
        ):
            result = evaluate_response("hi", "hello")
        assert result.metadata.get("judge_failed") is True
        assert result.to_dict()["judge_failed"] is True

    def test_real_score_has_no_judge_failed_in_row(self):
        with patch(
            "evaluation.metrics.score_all_dimensions",
            return_value={
                "persona_adherence": 0.5, "cultural_fluency": 0.5,
                "anti_dependency": 0.5, "financial_accuracy": 0.5, "urgency": 0.5,
            },
        ):
            result = evaluate_response("hi", "hello")
        assert "judge_failed" not in result.to_dict()


# ── avg_scores: excluding failed rows ──────────────────────────────────────────

class TestAvgScoresExcludesFailures:
    def _row(self, composite: float, judge_failed: bool = False) -> dict:
        row = {
            "persona_adherence": composite, "cultural_fluency": composite,
            "anti_dependency": composite, "financial_accuracy": composite,
            "urgency": composite, "composite_score": composite,
        }
        if judge_failed:
            row["judge_failed"] = True
        return row

    def test_no_failures_behaves_as_plain_mean(self):
        rows = [self._row(0.4), self._row(0.6)]
        agg = avg_scores(rows)
        assert agg["composite_score"] == 0.5
        assert "n_judge_failed" not in agg

    def test_failed_rows_excluded_not_averaged_as_zero(self):
        # Same shape as the real C4 run this fix responds to: 3 real scores,
        # 2 quota-failed. Naive mean over all 5 (diluted) vs. correct mean
        # over the 3 valid ones.
        rows = [
            self._row(0.495), self._row(0.580), self._row(0.812),
            self._row(0.0, judge_failed=True), self._row(0.0, judge_failed=True),
        ]
        agg = avg_scores(rows)
        assert agg["composite_score"] == (0.495 + 0.580 + 0.812) / 3
        assert agg["n_judge_failed"] == 2
        assert agg["n_samples_scored"] == 3

    def test_all_rows_failed_returns_empty_not_zero(self):
        rows = [self._row(0.0, judge_failed=True), self._row(0.0, judge_failed=True)]
        assert avg_scores(rows) == {}

    def test_judge_failed_key_itself_not_averaged_into_output(self):
        rows = [self._row(0.5), self._row(0.0, judge_failed=True)]
        agg = avg_scores(rows)
        assert "judge_failed" not in agg


# ── evaluate_checkpoint: end-to-end with an injected generator ────────────────

class TestEvaluateCheckpointExcludesFailures:
    def test_aggregate_excludes_judge_failed_samples(self):
        samples = [
            {"user": "q1", "reference": None, "persona": "chioma-base"},
            {"user": "q2", "reference": None, "persona": "chioma-base"},
            {"user": "q3", "reference": None, "persona": "chioma-base"},
        ]

        def fake_generate(system_prompt: str, user_message: str) -> str:
            return f"response to {user_message}"

        # Sample 2 (q2) hits a judge failure; 1 and 3 score normally.
        def fake_score_all_dimensions(user_message, response):
            if user_message == "q2":
                return {
                    "persona_adherence": 0.0, "cultural_fluency": 0.0,
                    "anti_dependency": 0.0, "financial_accuracy": 0.0,
                    "urgency": 0.0, "_judge_failed": True,
                }
            return {
                "persona_adherence": 0.6, "cultural_fluency": 0.6,
                "anti_dependency": 0.6, "financial_accuracy": 0.6, "urgency": 0.6,
            }

        with patch(
            "evaluation.metrics.score_all_dimensions",
            side_effect=fake_score_all_dimensions,
        ):
            agg = evaluate_checkpoint(
                fake_generate, samples,
                system_prompt_fn=lambda persona: "system prompt",
                log_to_mlflow=False,
            )

        assert agg["n_judge_failed"] == 1
        assert agg["n_samples_scored"] == 2
        # 0.6 weighted across all 5 dims (0.25+0.20+0.20+0.20+0.15=1.0) == 0.6,
        # not diluted toward 0 by the failed sample.
        assert abs(agg["composite_score"] - 0.6) < 1e-9
