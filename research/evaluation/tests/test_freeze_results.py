"""Tests for the C5.1 evaluation freeze/tag tool — fully offline, no git required
beyond this repo's own history (git_commit/branch are best-effort, never asserted)."""
from __future__ import annotations

import json

import pytest

from evaluation.freeze_results import build_manifest, freeze


def _write_comparative(tmp_path, conditions: dict) -> "Path":
    path = tmp_path / "comparative_results.json"
    path.write_text(json.dumps({"conditions": conditions}), encoding="utf-8")
    return path


def test_manifest_is_publication_ready_when_all_real_and_all_rated(tmp_path):
    comparative = _write_comparative(tmp_path, {
        "C1": {"aggregate": {"source": "live_groq"}, "rows": []},
        "C2": {"aggregate": {"source": "recorded_kaggle_run"}, "rows": []},
    })
    human_eval = tmp_path / "human_eval_results.json"
    human_eval.write_text(json.dumps({
        "conditions": {"C1": {"n_ratings": 5}, "C2": {"n_ratings": 5}}
    }), encoding="utf-8")

    manifest = build_manifest("v1", inputs={
        "comparative": comparative, "human_eval": human_eval,
    })

    assert manifest["status"] == "PUBLICATION_READY"
    assert manifest["estimated_conditions"] == []
    assert manifest["pending_human_eval_conditions"] == []


def test_manifest_flags_estimated_conditions(tmp_path):
    comparative = _write_comparative(tmp_path, {
        "C1": {"aggregate": {"source": "live_groq"}, "rows": []},
        "C3": {"aggregate": {"source": "estimated_dpo_extrapolation"}, "rows": []},
    })
    manifest = build_manifest("v1", inputs={"comparative": comparative})

    assert manifest["status"] in (
        "PARTIAL_CONTAINS_ESTIMATES", "PARTIAL_ESTIMATES_AND_MISSING_HUMAN_EVAL",
    )
    assert manifest["estimated_conditions"] == ["C3"]
    assert manifest["condition_provenance"]["C1"]["is_real"] is True
    assert manifest["condition_provenance"]["C3"]["is_real"] is False


def test_manifest_flags_missing_human_eval_when_automatic_is_clean(tmp_path):
    comparative = _write_comparative(tmp_path, {
        "C1": {"aggregate": {"source": "live_groq"}, "rows": []},
    })
    # No human_eval file at all — pending by default.
    manifest = build_manifest("v1", inputs={
        "comparative": comparative, "human_eval": tmp_path / "does_not_exist.json",
    })

    assert manifest["status"] == "PARTIAL_MISSING_HUMAN_EVAL"
    assert manifest["pending_human_eval_conditions"] == ["C1"]


def test_manifest_never_marks_estimated_condition_as_needing_human_ratings(tmp_path):
    # An estimated condition never ran live — there's no text to rate, so it
    # must not show up in pending_human_eval_conditions (that would ask for
    # something structurally impossible).
    comparative = _write_comparative(tmp_path, {
        "C3": {"aggregate": {"source": "estimated_dpo_extrapolation"}, "rows": []},
    })
    manifest = build_manifest("v1", inputs={"comparative": comparative})

    assert "C3" not in manifest["pending_human_eval_conditions"]


def test_manifest_no_comparative_results(tmp_path):
    manifest = build_manifest("v1", inputs={
        "comparative": tmp_path / "missing.json",
    })
    assert manifest["status"] == "NO_COMPARATIVE_RESULTS"


def test_freeze_writes_immutable_versioned_snapshot(tmp_path, monkeypatch):
    import evaluation.freeze_results as fr

    comparative = _write_comparative(tmp_path, {
        "C1": {"aggregate": {"source": "live_groq"}, "rows": []},
    })
    canonical_dir = tmp_path / "canonical"
    monkeypatch.setattr(fr, "CANONICAL_DIR", canonical_dir)
    monkeypatch.setattr(fr, "_REPO_ROOT", tmp_path)

    manifest = freeze("v1", inputs={"comparative": comparative})

    version_dir = canonical_dir / "v1"
    assert (version_dir / "manifest.json").exists()
    assert (version_dir / "comparative_results.json").exists()
    assert manifest["version"] == "v1"

    # Re-freezing the same version must refuse — freezes are immutable.
    with pytest.raises(FileExistsError):
        freeze("v1", inputs={"comparative": comparative})
