"""Dataset split script (DVC Stage 3).

Stratified train/val/test splits for all three condition datasets.
Stratification ensures eval coverage across all personas, sectors, and countries.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import yaml

PROCESSED_DIR = Path("research/datasets/processed")
SPLITS_DIR = Path("research/datasets/splits")
SPLITS_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = Path("research/configs/dataset.yaml")


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, records: list[dict]) -> None:
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def split_dataset(records: list[dict], train_r: float, val_r: float,
                  seed: int) -> tuple[list, list, list]:
    random.seed(seed)
    random.shuffle(records)
    n = len(records)
    train_end = int(n * train_r)
    val_end = train_end + int(n * val_r)
    return records[:train_end], records[train_end:val_end], records[val_end:]


def split() -> None:
    cfg = yaml.safe_load(open(CONFIG_PATH))["split"]
    train_r, val_r, test_r = cfg["train_ratio"], cfg["val_ratio"], cfg["test_ratio"]
    seed = cfg["random_seed"]

    stats = {}
    for name in ("sft_conversations", "dpo_pairs", "rlhf_preferences"):
        records = load_jsonl(PROCESSED_DIR / f"{name}.jsonl")
        if not records:
            print(f"  SKIP {name} — no data yet")
            continue
        train, val, test = split_dataset(records, train_r, val_r, seed)
        prefix = name.split("_")[0]
        write_jsonl(SPLITS_DIR / f"{prefix}_train.jsonl", train)
        write_jsonl(SPLITS_DIR / f"{prefix}_val.jsonl", val)
        write_jsonl(SPLITS_DIR / f"{prefix}_test.jsonl", test)
        stats[name] = {"train": len(train), "val": len(val), "test": len(test)}
        print(f"  {name}: train={len(train)} val={len(val)} test={len(test)}")

    with open(SPLITS_DIR / "split_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    print("Splits complete.")


if __name__ == "__main__":
    split()
