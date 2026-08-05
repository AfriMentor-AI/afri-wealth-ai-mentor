"""Dataset processing script (DVC Stage 2).

Reads raw conversations and preference pairs, applies quality filtering,
and outputs condition-specific processed datasets.

TODO Sprint 3: add cultural fluency scoring using the eval harness.
TODO Sprint 4: add human annotation quality checks for preference pairs.
"""
from __future__ import annotations

import json
from pathlib import Path

RAW_DIR = Path("research/datasets/raw")
PROCESSED_DIR = Path("research/datasets/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

MIN_QUALITY_SCORE = 0.7


def process() -> None:
    stats = {"total_conversations": 0, "sft_kept": 0, "dpo_pairs": 0, "rlhf_pairs": 0}

    # ── SFT conversations (Condition C2) ──────────────────────────────────────
    with (
        open(RAW_DIR / "conversations.jsonl") as fin,
        open(PROCESSED_DIR / "sft_conversations.jsonl", "w") as fout,
    ):
        for line in fin:
            conv = json.loads(line)
            stats["total_conversations"] += 1
            if conv.get("quality_score", 0) >= MIN_QUALITY_SCORE:
                fout.write(json.dumps(conv) + "\n")
                stats["sft_kept"] += 1

    # ── DPO pairs (Condition C3) ──────────────────────────────────────────────
    with (
        open(RAW_DIR / "preference_pairs.jsonl") as fin,
        open(PROCESSED_DIR / "dpo_pairs.jsonl", "w") as fout,
        open(PROCESSED_DIR / "rlhf_preferences.jsonl", "w") as fout_rlhf,
    ):
        for line in fin:
            pair = json.loads(line)
            stats["dpo_pairs"] += 1
            fout.write(json.dumps({
                "prompt": pair["prompt"],
                "chosen": pair["chosen"],
                "rejected": pair["rejected"],
                "persona_slug": pair.get("persona_slug"),
            }) + "\n")
            # RLHF format: binary preference annotation
            fout_rlhf.write(json.dumps({
                "prompt": pair["prompt"],
                "response_a": pair["chosen"],
                "response_b": pair["rejected"],
                "preferred": "a",
                "persona_slug": pair.get("persona_slug"),
            }) + "\n")
            stats["rlhf_pairs"] += 1

    with open(PROCESSED_DIR / "stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    print("Processing complete:", stats)


if __name__ == "__main__":
    process()
