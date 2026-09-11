"""Lightweight reward / critique model for personality fit (Condition C4).

Architecture
------------
Two complementary layers:

1.  **LLM-as-judge scorer** — delegates to the existing
    :func:`evaluation.metrics.score_all_dimensions` to get scalar scores on the
    5 Chioma personality dimensions for *each* response in a preference pair.

2.  **Logistic preference probe** — a :class:`sklearn.linear_model.LogisticRegression`
    fitted on the per-dimension score *deltas* (``score_a − score_b``) to predict
    which response a human would prefer.  This is the "lightweight reward model for
    personality fit" component: it learns, from human-labelled data, which
    combinations of dimension deltas are most predictive of human preference.

The probe is trained via :func:`fit_reward_probe` and serialised with
:func:`save_reward_probe` / :func:`load_reward_probe`.  At inference time,
:func:`score_pair` returns absolute reward scalars for both responses and the
probe's predicted preferred label.

CPU safety
----------
The LLM-judge calls go out via the Groq API (HTTP) — no GPU needed.  The probe
uses sklearn (CPU-only).  torch / transformers are never imported here.

Usage
-----
    from evaluation.reward_model import (
        score_pair, fit_reward_probe, save_reward_probe, load_reward_probe,
    )

    # Score a single pair
    result = score_pair(prompt, response_a, response_b, probe=probe)
    print(result.reward_a, result.reward_b, result.predicted_preferred)

    # Fit a probe from dataset
    pairs = load_preference_pairs("rlhf_train.jsonl")
    probe, report = fit_reward_probe(pairs)
    save_reward_probe(probe, "reward_probe.pkl")
"""
from __future__ import annotations

import json
import logging
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

# Module-level import so tests can patch 'evaluation.reward_model.score_all_dimensions'
# without triggering the full OpenAI client setup. Falls back gracefully if not available.
try:
    from evaluation.metrics import score_all_dimensions
except ImportError:  # pragma: no cover — handled at runtime
    def score_all_dimensions(prompt: str, response: str) -> dict:  # type: ignore[misc]
        """Fallback stub — returns zeros when metrics module is unavailable."""
        return {d: 0.0 for d in ["persona_adherence", "cultural_fluency",
                                  "anti_dependency", "financial_accuracy", "urgency"]}

logger = logging.getLogger(__name__)

# ── Base and Extended Reward weights ──────────────────────────────────────────
DEFAULT_REWARD_WEIGHTS: dict[str, float] = {
    "persona_adherence": 0.25,
    "cultural_fluency": 0.20,
    "anti_dependency": 0.20,
    "financial_accuracy": 0.20,
    "urgency": 0.15,
}

CONSISTENCY_DIMENSIONS: list[str] = [
    "prompt_to_line",
    "line_to_line",
    "qa_consistency",
]

DEFAULT_REWARD_WEIGHTS_WITH_CONSISTENCY: dict[str, float] = {
    "persona_adherence": 0.20,
    "cultural_fluency": 0.15,
    "anti_dependency": 0.15,
    "financial_accuracy": 0.15,
    "urgency": 0.15,
    "prompt_to_line": 0.08,
    "line_to_line": 0.06,
    "qa_consistency": 0.06,
}

_DIMENSIONS = list(DEFAULT_REWARD_WEIGHTS.keys())
_EXTENDED_DIMENSIONS = list(DEFAULT_REWARD_WEIGHTS_WITH_CONSISTENCY.keys())


# ── Consistency Scorer helper (per Abdulhai et al. 2025) ─────────────────────

def _get_system_prompt_for_persona(persona_slug: str) -> str:
    """Retrieve or render persona system prompt anchor."""
    try:
        from evaluation.checkpoint_eval import render_system_prompt
        return render_system_prompt(persona_slug)
    except Exception:
        return f"You are Chioma ({persona_slug}), an African financial mentor. Direct, pragmatic, and actionable."


def _lexical_similarity(text_a: str, text_b: str) -> float:
    """Compute lexical cosine similarity between two texts in [0.0, 1.0]."""
    import math
    import re
    from collections import Counter

    tokens_a = re.findall(r"[a-z0-9']+", text_a.lower())
    tokens_b = re.findall(r"[a-z0-9']+", text_b.lower())
    if not tokens_a or not tokens_b:
        return 0.0

    cnt_a, cnt_b = Counter(tokens_a), Counter(tokens_b)
    vec_a = {t: 1.0 + math.log(c) for t, c in cnt_a.items()}
    vec_b = {t: 1.0 + math.log(c) for t, c in cnt_b.items()}

    shared = set(vec_a) & set(vec_b)
    if not shared:
        return 0.0
    dot = sum(vec_a[t] * vec_b[t] for t in shared)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return round(dot / (norm_a * norm_b), 6)


def compute_consistency_scores(
    prompt: str,
    response: str,
    persona_slug: str = "chioma-base",
    reference: str | None = None,
) -> dict[str, float]:
    """Compute behavioral consistency metrics per Abdulhai et al. (2025).

    Returns
    -------
    dict with keys:
      - prompt_to_line: similarity between system prompt anchor and candidate response
      - line_to_line: similarity across turns / candidate vs reference exemplar
      - qa_consistency: relevance/alignment between user prompt and candidate response
    """
    sys_prompt = _get_system_prompt_for_persona(persona_slug)
    p2l = _lexical_similarity(sys_prompt, response)
    qa = _lexical_similarity(prompt, response)

    if reference:
        l2l = _lexical_similarity(response, reference)
    else:
        # Multi-sentence internal coherence across response lines
        sentences = [s.strip() for s in response.split(".") if len(s.strip()) > 5]
        if len(sentences) >= 2:
            sims = [
                _lexical_similarity(sentences[i], sentences[j])
                for i in range(len(sentences))
                for j in range(i + 1, len(sentences))
            ]
            l2l = round(sum(sims) / len(sims), 6) if sims else 1.0
        else:
            l2l = 1.0

    return {
        "prompt_to_line": p2l,
        "line_to_line": l2l,
        "qa_consistency": qa,
    }


def measure_persona_drift(
    turn_responses: list[str],
    persona_slug: str = "chioma-base",
) -> dict[str, float]:
    """Measure persona drift across a sequence of multi-turn responses.

    Calculates:
      - early_p2l: prompt-to-line alignment in initial half of turns
      - late_p2l: prompt-to-line alignment in latter half of turns
      - drift_magnitude: drop in persona alignment (early_p2l - late_p2l)
      - drift_pct: percentage drop relative to early baseline
    """
    if not turn_responses:
        return {"early_p2l": 0.0, "late_p2l": 0.0, "drift_magnitude": 0.0, "drift_pct": 0.0}

    sys_prompt = _get_system_prompt_for_persona(persona_slug)
    p2l_scores = [_lexical_similarity(sys_prompt, r) for r in turn_responses]

    mid = max(1, len(p2l_scores) // 2)
    early_p2l = float(np.mean(p2l_scores[:mid]))
    late_p2l = float(np.mean(p2l_scores[mid:])) if len(p2l_scores) > mid else early_p2l

    drift_mag = max(0.0, early_p2l - late_p2l)
    drift_pct = round((drift_mag / (early_p2l + 1e-9)) * 100, 2)

    return {
        "early_p2l": round(early_p2l, 4),
        "late_p2l": round(late_p2l, 4),
        "drift_magnitude": round(drift_mag, 4),
        "drift_pct": drift_pct,
    }


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class PairScores:
    """Dimension scores for a single response pair."""
    prompt: str
    scores_a: dict[str, float]
    scores_b: dict[str, float]
    preferred: str           # "a" or "b" — ground-truth human label
    persona_slug: str = ""
    include_consistency: bool = False
    custom_dimensions: list[str] | None = None

    @property
    def dimensions(self) -> list[str]:
        if self.custom_dimensions is not None:
            return self.custom_dimensions
        if self.include_consistency:
            return _EXTENDED_DIMENSIONS
        return _DIMENSIONS

    @property
    def delta(self) -> list[float]:
        """score_a − score_b per dimension — the feature vector for the probe."""
        dims = self.dimensions
        return [self.scores_a.get(d, 0.0) - self.scores_b.get(d, 0.0) for d in dims]

    @property
    def label(self) -> int:
        """1 if preferred == 'a', 0 if preferred == 'b'."""
        return 1 if self.preferred == "a" else 0


@dataclass
class PairReward:
    """Reward outputs for a preference pair."""
    prompt: str
    reward_a: float
    reward_b: float
    predicted_preferred: str      # "a" or "b"
    probe_confidence: float       # P(preferred == 'a')
    scores_a: dict[str, float] = field(default_factory=dict)
    scores_b: dict[str, float] = field(default_factory=dict)


# ── Scalar reward from dimension scores ──────────────────────────────────────

def _weighted_reward(
    scores: dict[str, float],
    weights: dict[str, float],
    dimensions: list[str] | None = None,
) -> float:
    """Compute a weighted sum reward from per-dimension scores."""
    dims = dimensions or list(weights.keys())
    return sum(scores.get(dim, 0.0) * weights.get(dim, 0.0) for dim in dims)


def _prob_prefer_a(probe, delta) -> float:
    """P(response_a preferred) from a fitted probe, robust to the single-class
    case: fit_reward_probe falls back to a DummyClassifier when every training
    pair has the same label (e.g. this project's curated datasets, where
    response_a is always the intended-better answer) — predict_proba() then
    returns only 1 column instead of the usual 2, so a bare [0][1] index
    raises IndexError rather than reflecting "always/never preferred"."""
    proba = probe.predict_proba(delta)[0]
    classes = list(probe.classes_)
    if 1 not in classes:
        return 0.0
    return float(proba[classes.index(1)])


# ── Scoring a pair (calls the LLM judge + optional consistency) ───────────────

def score_pair(
    prompt: str,
    response_a: str,
    response_b: str,
    *,
    probe=None,           # fitted LogisticRegression or None
    reward_weights: Optional[dict[str, float]] = None,
    persona_slug: str = "chioma-base",
    include_consistency: bool = False,
    reference: str | None = None,
) -> PairReward:
    """Score a preference pair.

    Calls the shared LLM-as-judge for both responses, optionally computes
    Abdulhai et al. 2025 persona-consistency metrics, computes weighted reward
    scalars, and (if a probe is provided) runs the logistic probe to predict
    which the human would prefer.

    Parameters
    ----------
    prompt:              The user query.
    response_a:          First candidate response.
    response_b:          Second candidate response.
    probe:               Fitted sklearn LogisticRegression, or None (falls back to
                         weighted reward comparison).
    reward_weights:      Per-dimension weights dict.
    persona_slug:        Persona archetype identifier.
    include_consistency: Whether to augment score vectors with consistency metrics.
    reference:           Optional ground-truth reference response.

    Returns
    -------
    PairReward with reward_a, reward_b, predicted_preferred, and raw scores.
    """
    if reward_weights is not None:
        weights = reward_weights
    elif include_consistency:
        weights = DEFAULT_REWARD_WEIGHTS_WITH_CONSISTENCY
    else:
        weights = DEFAULT_REWARD_WEIGHTS

    dims = list(weights.keys())

    logger.debug("Scoring response_a for prompt: %s…", prompt[:60])
    scores_a = score_all_dimensions(prompt, response_a)
    logger.debug("Scoring response_b for prompt: %s…", prompt[:60])
    scores_b = score_all_dimensions(prompt, response_b)

    if include_consistency:
        c_a = compute_consistency_scores(prompt, response_a, persona_slug=persona_slug, reference=reference)
        c_b = compute_consistency_scores(prompt, response_b, persona_slug=persona_slug, reference=reference)
        scores_a.update(c_a)
        scores_b.update(c_b)

    reward_a = _weighted_reward(scores_a, weights, dimensions=dims)
    reward_b = _weighted_reward(scores_b, weights, dimensions=dims)

    if probe is not None:
        delta = np.array([[scores_a.get(d, 0.0) - scores_b.get(d, 0.0) for d in dims]])
        prob_a = _prob_prefer_a(probe, delta)
        predicted_preferred = "a" if prob_a >= 0.5 else "b"
        confidence = prob_a
    else:
        # Fallback: choose whichever has higher weighted reward
        predicted_preferred = "a" if reward_a >= reward_b else "b"
        confidence = reward_a / (reward_a + reward_b + 1e-9)

    return PairReward(
        prompt=prompt,
        reward_a=reward_a,
        reward_b=reward_b,
        predicted_preferred=predicted_preferred,
        probe_confidence=confidence,
        scores_a=scores_a,
        scores_b=scores_b,
    )


# ── Dataset loading ────────────────────────────────────────────────────────────

def load_preference_pairs(path: str | Path) -> list[dict]:
    """Load a JSONL preference dataset.

    Each line is expected to have keys: ``prompt``, ``response_a``,
    ``response_b``, ``preferred`` ("a" | "b"), and optionally
    ``persona_slug``.
    """
    pairs = []
    path = Path(path)
    if not path.exists():
        logger.warning("Preference dataset not found: %s", path)
        return pairs
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                pairs.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning("Skipping malformed line %d in %s: %s", i, path, exc)
    logger.info("Loaded %d preference pairs from %s", len(pairs), path)
    return pairs


# ── Batch scoring ──────────────────────────────────────────────────────────────

def score_dataset(
    pairs: list[dict],
    *,
    reward_weights: Optional[dict[str, float]] = None,
    include_consistency: bool = False,
) -> list[PairScores]:
    """Score every pair in a dataset with the LLM judge (+ optional consistency).

    Returns :class:`PairScores` objects ready for probe fitting.  Skips pairs
    where both responses are empty strings.
    """
    if reward_weights is not None:
        weights = reward_weights
    elif include_consistency:
        weights = DEFAULT_REWARD_WEIGHTS_WITH_CONSISTENCY
    else:
        weights = DEFAULT_REWARD_WEIGHTS

    dims = list(weights.keys())
    has_consistency = include_consistency or any(d in CONSISTENCY_DIMENSIONS for d in dims)

    results: list[PairScores] = []
    for i, pair in enumerate(pairs):
        prompt = pair.get("prompt", "")
        response_a = pair.get("response_a", "")
        response_b = pair.get("response_b", "")
        preferred = pair.get("preferred", "a")
        persona_slug = pair.get("persona_slug", "chioma-base")
        reference = pair.get("reference")

        if not (prompt and response_a and response_b):
            logger.warning("Skipping incomplete pair %d", i)
            continue

        logger.info(
            "  [%d/%d] persona=%-14s prompt=%s…",
            i + 1, len(pairs), persona_slug, prompt[:50],
        )
        scores_a = score_all_dimensions(prompt, response_a)
        scores_b = score_all_dimensions(prompt, response_b)

        if has_consistency:
            c_a = compute_consistency_scores(prompt, response_a, persona_slug=persona_slug, reference=reference)
            c_b = compute_consistency_scores(prompt, response_b, persona_slug=persona_slug, reference=reference)
            scores_a.update(c_a)
            scores_b.update(c_b)

        results.append(PairScores(
            prompt=prompt,
            scores_a=scores_a,
            scores_b=scores_b,
            preferred=preferred,
            persona_slug=persona_slug,
            include_consistency=has_consistency,
            custom_dimensions=dims,
        ))

    return results


# ── Probe fitting ──────────────────────────────────────────────────────────────

def fit_reward_probe(
    scored_pairs: list[PairScores],
) -> tuple:
    """Fit a logistic probe on dimension-delta features.

    The probe learns: given (score_a − score_b) per personality dimension, is
    response_a preferred?  This is the lightweight reward model for personality
    fit — it encodes the human preference signal in a low-dimensional linear
    classifier.

    Parameters
    ----------
    scored_pairs : list of :class:`PairScores` with LLM judge scores filled in.

    Returns
    -------
    (probe, report) where probe is a fitted ``LogisticRegression`` and report
    is a dict with ``train_accuracy``, ``n_samples``, and per-dimension weights.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.dummy import DummyClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline

    if not scored_pairs:
        raise ValueError("No scored pairs — cannot fit reward probe.")

    dims = scored_pairs[0].dimensions
    X = np.array([p.delta for p in scored_pairs])
    y = np.array([p.label for p in scored_pairs])

    unique_classes = np.unique(y)
    if len(unique_classes) < 2:
        # All pairs prefer the same response (e.g., all "a" in a well-curated
        # preference dataset). Use a DummyClassifier that always predicts the
        # majority class — the reward scalar comparison still works correctly.
        logger.warning(
            "Only one class (%r) in training labels — fitting DummyClassifier. "
            "The weighted reward delta is still meaningful for ranking pairs.",
            unique_classes[0],
        )
        probe = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", DummyClassifier(strategy="most_frequent")),
        ])
        probe.fit(X, y)
        train_acc = 1.0  # trivially correct on single-class data
        coef = [0.0] * len(dims)
    else:
        probe = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(C=1.0, max_iter=500, random_state=42)),
        ])
        probe.fit(X, y)
        train_acc = float((probe.predict(X) == y).mean())
        coef = probe.named_steps["clf"].coef_[0].tolist()

    report = {
        "train_accuracy": train_acc,
        "n_samples": len(scored_pairs),
        "feature_names": dims,
        "probe_coefficients": dict(zip(dims, coef)),
        "single_class": len(unique_classes) < 2,
    }
    logger.info(
        "Reward probe fitted: n=%d train_acc=%.3f single_class=%s features=%s",
        len(scored_pairs), train_acc, len(unique_classes) < 2, dims,
    )
    return probe, report


def evaluate_probe(
    probe,
    scored_pairs: list[PairScores],
) -> dict:
    """Evaluate the probe on a held-out set, returning accuracy + per-class stats."""
    if not scored_pairs:
        return {"accuracy": 0.0, "n_samples": 0}

    from sklearn.metrics import classification_report

    X = np.array([p.delta for p in scored_pairs])
    y = np.array([p.label for p in scored_pairs])
    preds = probe.predict(X)
    acc = float((preds == y).mean())
    try:
        report_str = classification_report(
            y, preds, labels=[0, 1], target_names=["prefer_b", "prefer_a"], zero_division=0
        )
    except Exception:
        report_str = f"Accuracy: {acc:.3f}"
    logger.info("Probe eval: n=%d accuracy=%.3f\n%s", len(scored_pairs), acc, report_str)
    return {"accuracy": acc, "n_samples": len(scored_pairs), "report": report_str}


# ── Serialisation ──────────────────────────────────────────────────────────────

def save_reward_probe(probe, path: str | Path) -> None:
    """Serialise the probe pipeline to a pickle file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(probe, f)
    logger.info("Reward probe saved to %s", path)


def load_reward_probe(path: str | Path):
    """Load a previously serialised probe pipeline."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Reward probe not found: {path}")
    with open(path, "rb") as f:
        probe = pickle.load(f)
    logger.info("Reward probe loaded from %s", path)
    return probe


# ── Conversion to DPO format ───────────────────────────────────────────────────

def pairs_to_dpo_format(
    pairs: list[dict],
    probe=None,
    reward_weights: Optional[dict[str, float]] = None,
    include_consistency: bool = False,
) -> list[dict]:
    """Convert preference pairs to TRL DPO ``{prompt, chosen, rejected}`` format.

    If a probe is provided, it re-ranks pairs so that the model-predicted
    preferred response becomes ``chosen`` (overrides the dataset ``preferred``
    label only when probe confidence is high: > 0.65).  This implements the
    'reward-model-guided DPO' step of C4 — the reward model's signal shapes the
    training target rather than just using raw human annotations.

    If no probe, falls back to the dataset ``preferred`` field directly.
    """
    if reward_weights is not None:
        weights = reward_weights
    elif include_consistency:
        weights = DEFAULT_REWARD_WEIGHTS_WITH_CONSISTENCY
    else:
        weights = DEFAULT_REWARD_WEIGHTS

    dims = list(weights.keys())
    has_consistency = include_consistency or any(d in CONSISTENCY_DIMENSIONS for d in dims)

    dpo_pairs = []
    for pair in pairs:
        prompt = pair.get("prompt", "")
        response_a = pair.get("response_a", "")
        response_b = pair.get("response_b", "")
        preferred = pair.get("preferred", "a")
        persona_slug = pair.get("persona_slug", "chioma-base")
        reference = pair.get("reference")

        if probe is not None:
            scores_a = score_all_dimensions(prompt, response_a)
            scores_b = score_all_dimensions(prompt, response_b)
            if has_consistency:
                c_a = compute_consistency_scores(prompt, response_a, persona_slug=persona_slug, reference=reference)
                c_b = compute_consistency_scores(prompt, response_b, persona_slug=persona_slug, reference=reference)
                scores_a.update(c_a)
                scores_b.update(c_b)
            delta = np.array([[scores_a.get(d, 0.0) - scores_b.get(d, 0.0) for d in dims]])
            prob_a = _prob_prefer_a(probe, delta)
            if prob_a > 0.65:
                preferred = "a"
            elif prob_a < 0.35:
                preferred = "b"
            # else keep original label when confidence is low

        if preferred == "a":
            chosen, rejected = response_a, response_b
        else:
            chosen, rejected = response_b, response_a

        dpo_pairs.append({
            "prompt": prompt,
            "chosen": chosen,
            "rejected": rejected,
            "persona_slug": pair.get("persona_slug", ""),
        })
    return dpo_pairs
