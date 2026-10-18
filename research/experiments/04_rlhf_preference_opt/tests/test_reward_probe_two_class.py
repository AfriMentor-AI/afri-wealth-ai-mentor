"""C4's reward probe must not silently degrade to a constant classifier."""
import pytest

from evaluation.reward_model import PairScores, fit_reward_probe


def _pairs(preferred):
    out = []
    for i, pref in enumerate(preferred):
        hi, lo = {"persona_adherence": 0.9, "urgency": 0.8}, {"persona_adherence": 0.3, "urgency": 0.2}
        a, b = (hi, lo) if pref == "a" else (lo, hi)
        out.append(PairScores(prompt=f"p{i}", scores_a=a, scores_b=b, preferred=pref))
    return out


def test_strict_mode_rejects_single_class_labels():
    with pytest.raises(ValueError, match="single class"):
        fit_reward_probe(_pairs(["a", "a", "a", "a"]), require_two_classes=True)


def test_two_class_labels_fit_a_real_probe():
    probe, report = fit_reward_probe(_pairs(["a", "b", "a", "b", "a", "b"]), require_two_classes=True)
    assert report["single_class"] is False
