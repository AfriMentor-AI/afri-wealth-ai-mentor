"""Length-controlled view of a comparative_eval results file.

The judge rewards longer answers (v2a: corr(words, composite)=+0.40), so raw composites compare a 243-word
base-model essay with a 67-word trained answer. This reports, per condition: mean words, within-condition
correlation of length with score, and the composite averaged inside shared length bins — so conditions are
compared at the same length. Usage: python research/evaluation/length_analysis.py results.json
"""
from __future__ import annotations

import json
import statistics as st
import sys

BINS = [(0, 80), (80, 150), (150, 250), (250, 10_000)]


def _corr(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3:
        return None
    mx, my = st.mean(x), st.mean(y)
    sx = sum((a - mx) ** 2 for a in x) ** 0.5
    sy = sum((b - my) ** 2 for b in y) ** 0.5
    return None if sx == 0 or sy == 0 else sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy)


def analyse(results: dict) -> dict:
    out: dict = {}
    for cid, cond in results["conditions"].items():
        rows = [r for r in cond.get("rows", []) if not r.get("judge_failed") and r.get("response")]
        w = [len(r["response"].split()) for r in rows]
        c = [r["composite_score"] for r in rows]
        bins = {}
        for lo, hi in BINS:
            sel = [cc for ww, cc in zip(w, c) if lo <= ww < hi]
            bins[f"{lo}-{hi if hi < 10_000 else '+'}"] = {"n": len(sel), "mean_composite": round(st.mean(sel), 3) if sel else None}
        out[cid] = {"n": len(rows), "mean_words": round(st.mean(w), 1) if w else None,
                    "corr_words_composite": None if _corr(w, c) is None else round(_corr(w, c), 2), "bins": bins}
    return out


def main() -> None:
    res = analyse(json.load(open(sys.argv[1], encoding="utf-8")))
    labels = list(next(iter(res.values()))["bins"])
    print("cond  n   words  corr   " + "  ".join(f"{b:>9}" for b in labels))
    for cid, r in res.items():
        cells = "  ".join(f"{(str(b['mean_composite']) if b['mean_composite'] is not None else '-'):>5}(n{b['n']:>2})" for b in r["bins"].values())
        print(f"{cid:4} {r['n']:3} {r['mean_words']:6}  {str(r['corr_words_composite']):>5}  {cells}")


if __name__ == "__main__":
    main()
