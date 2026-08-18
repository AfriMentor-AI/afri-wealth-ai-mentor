"""Tests for persona-vector probing (card C3.3) — fully offline.

No model, no GPU, no network: activations come from a deterministic fake that
plants a known persona direction at a single layer, so the tests can assert that
the diff-of-means recovers that direction, the probe scores in the right
direction, and the separation diagnostic finds the planted layer. The runner's
no-GPU no-op path is checked with torch stubbed to report no CUDA (conftest).

Coverage:
  - profile loading + built-in fallback
  - contrastive-pair construction: real CHIOMA profile, train/held-out split,
    templating, and traits missing markers are skipped
  - extraction: diff-of-means recovers the planted direction; rows are unit-norm
  - probe scoring: sign follows trait expression
  - separation diagnostic + best-layer selection on separable synthetic data
  - PersonaVectorSet .npz save/load round-trip (incl. best_layer metadata)
  - MLflow logging keys
  - runner run() takes the safe no-GPU path
"""
from __future__ import annotations

import importlib.util
import zlib
from pathlib import Path

import numpy as np
import pytest

from evaluation.persona_probe import (
    CARRIER_TEMPLATES,
    DEFAULT_PROFILE_PATH,
    PersonaProbe,
    PersonaVectorSet,
    build_contrastive_pairs,
    extract_persona_vectors,
    load_persona_profile,
    log_probe_to_mlflow,
    probe_separation,
    select_best_layers,
)

# ── Synthetic activation fixture ────────────────────────────────────────────────

N_LAYERS = 6
HIDDEN = 8
SIGNAL_LAYER = 3
DIRECTION = np.zeros(HIDDEN)
DIRECTION[0] = 1.0  # the planted persona direction (already unit-norm)


def fake_activation(text: str) -> np.ndarray:
    """Deterministic (n_layers, hidden) activations.

    Small isotropic noise everywhere; at ``SIGNAL_LAYER`` a ``±DIRECTION`` offset
    whose sign encodes whether the text is a positive ("POSITIVE") or negative
    ("NEGATIVE") persona example. So class means differ only at that layer.
    """
    seed = zlib.crc32(text.encode()) & 0xFFFFFFFF
    rng = np.random.default_rng(seed)
    acts = rng.normal(0.0, 0.05, size=(N_LAYERS, HIDDEN))
    sign = 1.0 if "POSITIVE" in text else -1.0
    acts[SIGNAL_LAYER] = acts[SIGNAL_LAYER] + sign * DIRECTION
    return acts


def make_pairs(trait: str = "conscientiousness", n_train: int = 8, n_held: int = 4) -> dict:
    pos = [f"POSITIVE example {i}" for i in range(n_train + n_held)]
    neg = [f"NEGATIVE example {i}" for i in range(n_train + n_held)]
    return {
        trait: {
            "label": trait,
            "train": {"positive": pos[:n_train], "negative": neg[:n_train]},
            "heldout": {"positive": pos[n_train:], "negative": neg[n_train:]},
        }
    }


# ── Profile loading ──────────────────────────────────────────────────────────

def test_load_real_profile():
    profile = load_persona_profile(DEFAULT_PROFILE_PATH)
    assert profile["profile_id"] == "chioma"
    keys = {t["key"] for t in profile["traits"]} | {
        t["key"] for t in profile.get("distinctive_traits", [])
    }
    assert {"conscientiousness", "urgency", "cultural_fluency"} <= keys


def test_load_profile_fallback(tmp_path):
    profile = load_persona_profile(tmp_path / "does_not_exist.json")
    assert profile["profile_version"] == "fallback"
    assert profile["traits"]  # fallback still has contrastive material


# ── Contrastive pairs ──────────────────────────────────────────────────────────

def test_build_pairs_from_real_profile():
    pairs = build_contrastive_pairs(load_persona_profile(DEFAULT_PROFILE_PATH))
    assert "conscientiousness" in pairs
    for spec in pairs.values():
        assert spec["train"]["positive"] and spec["train"]["negative"]
        # positives and negatives are distinct text sets
        assert set(spec["train"]["positive"]).isdisjoint(spec["train"]["negative"])


def test_build_pairs_templating_expands_markers():
    profile = {
        "profile_version": "t",
        "traits": [{
            "key": "urgency", "label": "Urgency",
            "markers": ["start today", "act now"],
            "counter_markers": ["wait", "delay"],
        }],
    }
    pairs = build_contrastive_pairs(profile, heldout_fraction=0.0)
    # 2 markers x N templates, all containing the marker phrase
    assert len(pairs["urgency"]["train"]["positive"]) == 2 * len(CARRIER_TEMPLATES)
    assert any("start today" in t for t in pairs["urgency"]["train"]["positive"])


def test_build_pairs_skips_trait_without_counter_markers():
    profile = {
        "traits": [
            {"key": "has_both", "markers": ["a"], "counter_markers": ["b"]},
            {"key": "no_counter", "markers": ["a"], "counter_markers": []},
            {"key": "no_markers", "markers": [], "counter_markers": ["b"]},
        ]
    }
    pairs = build_contrastive_pairs(profile, heldout_fraction=0.0)
    assert set(pairs) == {"has_both"}


def test_build_pairs_rejects_bad_heldout_fraction():
    with pytest.raises(ValueError):
        build_contrastive_pairs({"traits": []}, heldout_fraction=1.0)


# ── Extraction ───────────────────────────────────────────────────────────────

def test_extract_recovers_planted_direction():
    pairs = make_pairs()
    vs = extract_persona_vectors(pairs, fake_activation, profile_version="t")

    assert vs.n_layers == N_LAYERS and vs.hidden_dim == HIDDEN
    vec = vs.vectors["conscientiousness"]
    # the planted layer aligns with DIRECTION (cosine ~ 1, since rows are unit-norm)
    assert float(np.dot(vec[SIGNAL_LAYER], DIRECTION)) > 0.9


def test_extract_vectors_are_unit_norm():
    vs = extract_persona_vectors(make_pairs(), fake_activation)
    norms = np.linalg.norm(vs.vectors["conscientiousness"], axis=-1)
    assert np.allclose(norms, 1.0, atol=1e-6)


# ── Probe scoring ────────────────────────────────────────────────────────────

def test_probe_score_sign_follows_expression():
    vs = extract_persona_vectors(make_pairs(), fake_activation)
    probe = PersonaProbe(vs, default_layer=SIGNAL_LAYER)

    pos_act = fake_activation("POSITIVE held-out")
    neg_act = fake_activation("NEGATIVE held-out")
    assert probe.score_trait(pos_act, "conscientiousness") > 0
    assert probe.score_trait(neg_act, "conscientiousness") < 0
    # score_all covers every extracted trait
    assert set(probe.score_all(pos_act)) == set(vs.traits)


def test_probe_unknown_trait_raises():
    vs = extract_persona_vectors(make_pairs(), fake_activation)
    with pytest.raises(KeyError):
        PersonaProbe(vs).score_trait(fake_activation("POSITIVE"), "nonexistent")


# ── Separation diagnostic ──────────────────────────────────────────────────────

def test_separation_finds_planted_layer():
    pairs = make_pairs()
    vs = extract_persona_vectors(pairs, fake_activation)
    report = probe_separation(vs, pairs, fake_activation)

    r = report["conscientiousness"]
    assert r["best_layer"] == SIGNAL_LAYER
    assert r["best_accuracy"] == 1.0
    assert r["best_margin"] > 0
    assert r["slice"] == "heldout"
    # best-layer selection is persisted onto the vector set
    assert vs.best_layer["conscientiousness"] == SIGNAL_LAYER


def test_select_best_layers_falls_back_to_train_when_no_heldout():
    pairs = make_pairs(n_train=6, n_held=0)
    vs = extract_persona_vectors(pairs, fake_activation)
    probe_separation(vs, pairs, fake_activation)  # should not raise on empty heldout
    # with the held-out slice empty, the diagnostic uses the train slice
    # (asserted indirectly: a best layer is still selected)
    assert "conscientiousness" in vs.best_layer


# ── Persistence ──────────────────────────────────────────────────────────────

def test_vector_set_save_load_round_trip(tmp_path):
    pairs = make_pairs()
    vs = extract_persona_vectors(pairs, fake_activation, profile_version="v1")
    select_best_layers(vs, pairs, fake_activation)

    out = tmp_path / "persona_vectors.npz"
    vs.save(out)
    loaded = PersonaVectorSet.load(out)

    assert loaded.traits == vs.traits
    assert loaded.profile_version == "v1"
    assert loaded.best_layer == vs.best_layer
    np.testing.assert_allclose(
        loaded.vectors["conscientiousness"], vs.vectors["conscientiousness"]
    )


# ── MLflow logging ─────────────────────────────────────────────────────────────

def test_log_probe_to_mlflow_keys():
    import mlflow  # MagicMock from conftest

    mlflow.log_metric.reset_mock()
    report = {
        "urgency": {"best_layer": 3, "best_accuracy": 1.0, "best_margin": 2.0,
                    "per_layer": [], "slice": "heldout"},
    }
    log_probe_to_mlflow(report)

    logged = {call.args[0] for call in mlflow.log_metric.call_args_list}
    assert {"probe_sep_acc_urgency", "probe_sep_margin_urgency",
            "probe_best_layer_urgency", "probe_sep_acc_mean",
            "probe_sep_margin_mean"} <= logged


# ── Runner no-GPU no-op ──────────────────────────────────────────────────────

def _load_runner():
    path = Path(__file__).resolve().parents[2] / "experiments" / "03_contrastive_learning" / "probe.py"
    spec = importlib.util.spec_from_file_location("c33_probe", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_runner_no_gpu_is_safe_noop():
    runner = _load_runner()
    # torch is stubbed with cuda.is_available() == False (conftest) -> no-op
    assert runner.run() is None
