"""Build a blinded human-rating packet from comparative_eval.py's output (card C5.1).

Reads ``comparative_results.json``, pulls the ``(user_message, response)`` pairs
that actually have generated text (only conditions that ran live have any — a
condition that fell back to ``estimated_*``/``recorded_*`` never invoked a
model, so there is nothing to show a rater), shuffles and relabels them with
opaque sample ids, and writes two files:

  - ``rating_packet.csv``   — what raters see: sample_id, user_message,
    response, and blank columns for the rubric (human_eval_rubric.md).
  - ``rating_key.json``     — sample_id -> condition, kept separate. Raters
    never see this; only ``human_eval_aggregate.py`` reads it, to unblind
    completed ratings back to a condition.

Usage:
    python research/evaluation/human_eval_sampler.py
    python research/evaluation/human_eval_sampler.py --input path/to/comparative_results.json
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

_RESEARCH_ROOT = Path(__file__).resolve().parents[1]
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

RESULTS_DIR = _RESEARCH_ROOT / "evaluation" / "results"
DEFAULT_INPUT = RESULTS_DIR / "comparative_results.json"
DEFAULT_PACKET_OUT = RESULTS_DIR / "human_eval" / "rating_packet.csv"
DEFAULT_KEY_OUT = RESULTS_DIR / "human_eval" / "rating_key.json"

RUBRIC_COLUMNS = [
    "persona_adherence", "cultural_fluency", "anti_dependency",
    "financial_accuracy", "urgency", "overall_quality", "notes",
]


def collect_ratable_rows(comparative_results: dict) -> list[dict]:
    """Every (condition, row) pair that has real generated text to show a rater."""
    ratable: list[dict] = []
    for cond_id, cond in comparative_results.get("conditions", {}).items():
        for row in cond.get("rows", []):
            if row.get("response"):
                ratable.append({
                    "condition": cond_id,
                    "user_message": row.get("user_message", ""),
                    "response": row["response"],
                })
    return ratable


def select_paired_prompts(ratable: list[dict], max_prompts: int | None, seed: int = 42) -> list[dict]:
    """Keep only prompts answered by *every* condition (a paired design), then
    optionally subsample ``max_prompts`` of them so rater workload stays bounded
    (max_prompts x n_conditions responses per rater)."""
    conds = {r["condition"] for r in ratable}
    by_prompt: dict[str, set[str]] = {}
    for r in ratable:
        by_prompt.setdefault(r["user_message"], set()).add(r["condition"])
    full = sorted(u for u, c in by_prompt.items() if c == conds)
    if max_prompts is not None and len(full) > max_prompts:
        full = random.Random(seed).sample(full, max_prompts)
    keep = set(full)
    return [r for r in ratable if r["user_message"] in keep]


def per_rater_orders(packet_rows: list[dict], n_raters: int, seed: int = 42) -> list[list[dict]]:
    """Same sample_ids for every rater, each in an independent shuffled order
    (reduces order/fatigue effects and makes copying a neighbour's sheet useless)."""
    out = []
    for i in range(n_raters):
        rows = list(packet_rows)
        random.Random(f"{seed}-rater{i + 1}").shuffle(rows)
        out.append(rows)
    return out


def build_packet(ratable: list[dict], seed: int = 42) -> tuple[list[dict], dict[str, str]]:
    """Shuffle and assign blinded sample ids. Deterministic given ``seed``."""
    shuffled = list(ratable)
    random.Random(seed).shuffle(shuffled)

    packet_rows = []
    key: dict[str, str] = {}
    for i, item in enumerate(shuffled):
        sample_id = f"S{i + 1:03d}"
        key[sample_id] = item["condition"]
        packet_rows.append({
            "sample_id": sample_id,
            "user_message": item["user_message"],
            "response": item["response"],
            **dict.fromkeys(RUBRIC_COLUMNS, ""),
        })
    return packet_rows, key


def write_packet(packet_rows: list[dict], key: dict[str, str],
                  packet_out: Path = DEFAULT_PACKET_OUT, key_out: Path = DEFAULT_KEY_OUT) -> None:
    packet_out.parent.mkdir(parents=True, exist_ok=True)
    with open(packet_out, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["sample_id", "user_message", "response", *RUBRIC_COLUMNS]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(packet_rows)

    key_out.parent.mkdir(parents=True, exist_ok=True)
    key_out.write_text(json.dumps(key, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a blinded human-rating packet")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--packet-out", default=str(DEFAULT_PACKET_OUT))
    parser.add_argument("--key-out", default=str(DEFAULT_KEY_OUT))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-prompts", type=int, default=None,
                        help="rate only this many prompts, each answered by all conditions (paired)")
    parser.add_argument("--n-raters", type=int, default=3,
                        help="also write rating_packet_rater<i>.csv per rater, independently ordered")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: {input_path} not found. Run comparative_eval.py first.")
        raise SystemExit(1)

    comparative_results = json.loads(input_path.read_text(encoding="utf-8"))
    ratable = select_paired_prompts(collect_ratable_rows(comparative_results), args.max_prompts, args.seed)
    packet_rows, key = build_packet(ratable, seed=args.seed)
    write_packet(packet_rows, key, Path(args.packet_out), Path(args.key_out))
    packet_dir = Path(args.packet_out).parent
    for i, rows in enumerate(per_rater_orders(packet_rows, args.n_raters, args.seed), start=1):
        with open(packet_dir / f"rating_packet_rater{i}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["sample_id", "user_message", "response", *RUBRIC_COLUMNS])
            w.writeheader()
            w.writerows(rows)
    print(f"\n*** BACK UP {args.key_out} NOW (outside the machine/session that produced it). "
          f"Without it the ratings cannot be unblinded. ***")

    conditions_with_text = sorted({item["condition"] for item in ratable})
    all_conditions = sorted(comparative_results.get("conditions", {}).keys())
    missing = [c for c in all_conditions if c not in conditions_with_text]

    print(f"\n=== Human-eval packet: {len(packet_rows)} samples ===")
    print(f"Conditions with ratable text: {conditions_with_text}")
    if missing:
        print(f"Conditions with NO ratable text (estimated/recorded, not live): {missing}")
        print("These conditions cannot be human-rated until a live run produces real text.")
    print(f"\nRating packet (send to raters): {args.packet_out}")
    print(f"Rating key (keep private, for aggregation only): {args.key_out}")


if __name__ == "__main__":
    main()
