from evaluation.rescore import DIMS, composite, paired_ci, rescore


def _s(v, failed=False):
    d = dict.fromkeys(DIMS, v)
    return {**d, "_judge_failed": True} if failed else d


def test_composite_matches_the_original_weights():
    assert abs(composite(dict.fromkeys(DIMS, 1.0)) - 1.0) < 1e-9
    assert abs(composite({**dict.fromkeys(DIMS, 0.0), "persona_adherence": 1.0}) - 0.25) < 1e-9


def test_rescore_drops_judge_failures_instead_of_zeroing_them():
    res = {"conditions": {"A": {"rows": [{"user_message": "q1", "response": "r"}, {"user_message": "q2", "response": "r"}]}}}
    out = rescore(res, workers=1, judge=lambda u, r: _s(0.5, failed=(u == "q2")))
    assert list(out["A"]) == ["q1"] and abs(out["A"]["q1"]["composite"] - 0.5) < 1e-9


def test_paired_ci_detects_a_consistent_gap_and_straddles_zero_for_noise():
    a = {f"q{i}": 0.6 + (i % 3) * 0.01 for i in range(40)}
    b = {k: v - 0.1 for k, v in a.items()}
    n, m, lo, hi = paired_ci(a, b)
    assert n == 40 and lo > 0
    noisy = {f"q{i}": (0.5 if i % 2 else 0.7) for i in range(40)}
    flipped = {k: (0.7 if v == 0.5 else 0.5) for k, v in noisy.items()}
    assert paired_ci(noisy, flipped)[2] < 0 < paired_ci(noisy, flipped)[3]
