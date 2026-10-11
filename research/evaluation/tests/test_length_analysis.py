from evaluation.length_analysis import analyse


def _rows(pairs):
    return [{"response": "w " * n, "composite_score": c} for n, c in pairs]


def test_bins_compare_conditions_at_the_same_length():
    res = {"conditions": {
        "A": {"rows": _rows([(50, 0.3), (60, 0.35), (200, 0.6), (210, 0.62)])},
        "B": {"rows": _rows([(55, 0.5), (65, 0.52), (190, 0.7), (220, 0.72)])},
    }}
    out = analyse(res)
    assert out["A"]["bins"]["0-80"]["mean_composite"] == 0.325
    assert out["B"]["bins"]["0-80"]["mean_composite"] == 0.51      # B really is better at equal length
    assert out["A"]["corr_words_composite"] > 0.9


def test_failed_and_empty_rows_are_excluded():
    res = {"conditions": {"A": {"rows": [{"judge_failed": True, "response": "x", "composite_score": 0},
                                         {"response": "", "composite_score": 0.9}] + _rows([(10, 0.2), (20, 0.3), (30, 0.4)])}}}
    assert analyse(res)["A"]["n"] == 3
