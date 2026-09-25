"""Aggregate completed human-rating CSVs into per-condition results (card C5.1).

Reads one or more completed copies of ``human_eval_sampler.py``'s
``rating_packet.csv`` (one per rater) plus the ``rating_key.json`` it was
built with, unblinds each rating back to its condition, and writes a JSON in
the same per-condition shape ``comparative_results.json`` uses, so it sits
alongside the automatic table rather than needing separate tooling. With 2+
raters, also reports per-sample disagreement on ``overall_quality`` so
raw discord is visible rather than silently averaged away — a difference of
more than 2 points on the 1-5 scale is flagged (human_eval_rubric.md).

Honesty contract (same as safety_eval.py): a condition with zero completed
ratings is recorded with ``n_ratings: 0`` and no fabricated aggregate, never
silently omitted or filled from another condition.

Usage:
    python research/evaluation/human_eval_aggregate.py rater1.csv rater2.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

_RESEARCH_ROOT = Path(__file__).resolve().parents[1]
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

RESULTS_DIR = _RESEARCH_ROOT / "evaluation" / "results"
DEFAULT_KEY = RESULTS_DIR / "human_eval" / "rating_key.json"
DEFAULT_OUTPUT = RESULTS_DIR / "human_eval_results.json"

SCORE_COLUMNS = [
    "persona_adherence", "cultural_fluency", "anti_dependency",
    "financial_accuracy", "urgency",
]
DISAGREEMENT_THRESHOLD = 2  # points on the 1-5 overall_quality scale


def _parse_float(value: str) -> float | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_rater_csv(path: Path, key: dict[str, str]) -> list[dict]:
    """One row per completed rating, unblinded to its condition. Skips blank rows."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for record in csv.DictReader(f):
            sample_id = record.get("sample_id", "").strip()
            condition = key.get(sample_id)
            if not condition:
                continue  # unknown sample id — not from this key, skip rather than guess
            overall = _parse_float(record.get("overall_quality", ""))
            scores = {col: _parse_float(record.get(col, "")) for col in SCORE_COLUMNS}
            if overall is None and all(v is None for v in scores.values()):
                continue  # rater left this row unscored
            rows.append({
                "sample_id": sample_id,
                "condition": condition,
                "rater_file": path.name,
                "overall_quality": overall,
                **scores,
            })
    return rows


def _mean(values: list[float]) -> float | None:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def krippendorff_alpha_interval(units: list[list[float]]) -> float | None:
    """Krippendorff's alpha, interval metric; tolerates missing ratings.

    ``units`` is one list of ratings per rated item (a sample x its raters).
    Items with fewer than 2 ratings carry no agreement information and are dropped.
    Returns None when alpha is undefined (no pairable data, or zero expected
    disagreement because every rating is identical).
    """
    units = [u for u in units if len(u) >= 2]
    n = sum(len(u) for u in units)
    if n <= 1:
        return None
    d_obs = sum(
        sum((a - b) ** 2 for i, a in enumerate(u) for j, b in enumerate(u) if i != j) / (len(u) - 1)
        for u in units
    ) / n
    allv = [v for u in units for v in u]
    d_exp = sum((a - b) ** 2 for i, a in enumerate(allv) for j, b in enumerate(allv) if i != j) / (n * (n - 1))
    if d_exp == 0:
        return None
    return 1 - d_obs / d_exp


def _bootstrap_ci(values: list[float], n_boot: int = 2000, seed: int = 42) -> list[float] | None:
    if len(values) < 2:
        return None
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(n_boot))
    return [round(means[int(0.025 * n_boot)], 4), round(means[int(0.975 * n_boot) - 1], 4)]


def reliability(all_rater_rows: list[dict]) -> dict:
    """Inter-rater agreement per rubric column, over all samples."""
    out = {}
    for col in [*SCORE_COLUMNS, "overall_quality"]:
        by_sample: dict[str, list[float]] = {}
        for r in all_rater_rows:
            if r.get(col) is not None:
                by_sample.setdefault(r["sample_id"], []).append(r[col])
        alpha = krippendorff_alpha_interval(list(by_sample.values()))
        out[col] = {"krippendorff_alpha": None if alpha is None else round(alpha, 4)}
    return out


def adjudicate(all_rater_rows: list[dict]) -> dict:
    """Per-sample consensus on overall_quality: the median across raters.

    With >=3 raters the median is a genuine majority-style resolution of a
    disagreement; with 2 it is just the mean, so those samples are marked
    ``needs_third_rater`` instead of being silently resolved.
    """
    by_sample: dict[str, list[float]] = {}
    for r in all_rater_rows:
        if r["overall_quality"] is not None:
            by_sample.setdefault(r["sample_id"], []).append(r["overall_quality"])
    res = {}
    for sid, scores in by_sample.items():
        spread = max(scores) - min(scores)
        res[sid] = {
            "scores": scores, "median": statistics.median(scores), "spread": spread,
            "needs_third_rater": len(scores) < 3 and spread >= DISAGREEMENT_THRESHOLD,
        }
    return res


def aggregate(all_rater_rows: list[dict]) -> dict:
    conditions: dict[str, list[dict]] = {}
    for row in all_rater_rows:
        conditions.setdefault(row["condition"], []).append(row)

    result_conditions = {}
    for cond_id, rows in conditions.items():
        aggregate_scores = {col: _mean([r[col] for r in rows]) for col in SCORE_COLUMNS}
        aggregate_scores["overall_quality"] = _mean([r["overall_quality"] for r in rows])
        result_conditions[cond_id] = {
            "n_ratings": len(rows),
            "n_raters": len({r["rater_file"] for r in rows}),
            "aggregate": aggregate_scores,
        }

    # Disagreement: per sample_id, spread across raters on overall_quality.
    by_sample: dict[str, list[float]] = {}
    for row in all_rater_rows:
        if row["overall_quality"] is not None:
            by_sample.setdefault(row["sample_id"], []).append(row["overall_quality"])

    flagged = [
        {"sample_id": sid, "scores": scores, "spread": max(scores) - min(scores)}
        for sid, scores in by_sample.items()
        if len(scores) >= 2 and (max(scores) - min(scores)) >= DISAGREEMENT_THRESHOLD
    ]

    consensus = adjudicate(all_rater_rows)
    cond_of = {r["sample_id"]: r["condition"] for r in all_rater_rows}
    for cond_id, cond in result_conditions.items():
        medians = [c["median"] for sid, c in consensus.items() if cond_of[sid] == cond_id]
        cond["aggregate"]["overall_quality_consensus_median"] = _mean(medians)
        cond["overall_quality_ci95_bootstrap"] = _bootstrap_ci(medians)
        cond["n_samples"] = len(medians)
    ratings_per_sample = [len(c["scores"]) for c in consensus.values()]

    return {
        "reliability": reliability(all_rater_rows),
        "adjudication": {"n_needs_third_rater": sum(c["needs_third_rater"] for c in consensus.values()),
                         "per_sample": consensus},
        "coverage": {"min_raters_on_any_sample": min(ratings_per_sample, default=0),
                     "n_samples": len(consensus)},
        "meta": {
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "n_rater_files": len({r["rater_file"] for r in all_rater_rows}),
            "disagreement_threshold": DISAGREEMENT_THRESHOLD,
        },
        "conditions": result_conditions,
        "flagged_disagreements": flagged,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate completed human-rating CSVs")
    parser.add_argument("rater_csvs", nargs="+", help="Completed rating_packet.csv files")
    parser.add_argument("--key", default=str(DEFAULT_KEY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--min-raters", type=int, default=3,
                        help="fail (exit 2) unless every sample has at least this many ratings")
    args = parser.parse_args()

    key_path = Path(args.key)
    if not key_path.exists():
        print(f"ERROR: {key_path} not found. Run human_eval_sampler.py first.")
        raise SystemExit(1)
    key = json.loads(key_path.read_text(encoding="utf-8"))

    all_rows = []
    for csv_path in args.rater_csvs:
        all_rows.extend(load_rater_csv(Path(csv_path), key))

    if not all_rows:
        print("ERROR: no scored rows found across the given CSVs.")
        raise SystemExit(1)

    results = aggregate(all_rows)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    min_seen = results["coverage"]["min_raters_on_any_sample"]
    alpha = results["reliability"]["overall_quality"]["krippendorff_alpha"]
    print(f"\nInter-rater reliability (overall_quality) Krippendorff alpha = {alpha}")
    if min_seen < args.min_raters:
        print(f"\nERROR: some samples have only {min_seen} rating(s); need >= {args.min_raters}. "
              f"Results written to {output_path} but NOT publication-grade.")
        raise SystemExit(2)

    print(f"\n=== Human-eval aggregate: {len(args.rater_csvs)} rater file(s) ===")
    for cond_id, cond in results["conditions"].items():
        oq = cond["aggregate"]["overall_quality"]
        oq_str = f"{oq:.2f}" if oq is not None else "N/A"
        print(f"  {cond_id}: n_ratings={cond['n_ratings']} n_raters={cond['n_raters']} "
              f"overall_quality={oq_str}")
    if results["flagged_disagreements"]:
        print(f"\n{len(results['flagged_disagreements'])} sample(s) flagged for rater "
              f"disagreement (spread >= {DISAGREEMENT_THRESHOLD}):")
        for f in results["flagged_disagreements"]:
            print(f"  {f['sample_id']}: scores={f['scores']} spread={f['spread']}")
    print(f"\nWritten to: {output_path}")


if __name__ == "__main__":
    main()
