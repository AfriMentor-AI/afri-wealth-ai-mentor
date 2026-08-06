"""Few-shot example bank for C1 baseline prompting (card D2.4).

Loads (user, assistant) pairs from the SFT train split, filtered by persona_slug.
Falls back to cross-persona examples when the persona has fewer examples than requested.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

_DEFAULT_SPLITS_DIR = Path(__file__).parents[2] / "datasets" / "splits"


def load_few_shot_examples(
    persona_slug: str,
    n: int,
    splits_dir: Path = _DEFAULT_SPLITS_DIR,
    seed: int = 42,
) -> list[dict]:
    """Return up to n (user, assistant) dicts for the given persona.

    Loads from sft_train.jsonl. Falls back to any persona if the requested
    persona has fewer than n examples. Returns [] when the file doesn't exist.
    """
    train_file = splits_dir / "sft_train.jsonl"
    if not train_file.exists():
        return []

    persona_examples: list[dict] = []
    all_examples: list[dict] = []

    with open(train_file) as f:
        for line in f:
            record = json.loads(line)
            messages = record.get("messages", [])
            # Extract the first user/assistant exchange
            user_msg = next((m["content"] for m in messages if m["role"] == "user"), None)
            asst_msg = next((m["content"] for m in messages if m["role"] == "assistant"), None)
            if not user_msg or not asst_msg:
                continue
            example = {"user": user_msg, "assistant": asst_msg}
            all_examples.append(example)
            if record.get("persona_slug") == persona_slug:
                persona_examples.append(example)

    rng = random.Random(seed)

    if len(persona_examples) >= n:
        return rng.sample(persona_examples, n)

    # Pad with cross-persona examples (excluding already selected)
    remaining = [e for e in all_examples if e not in persona_examples]
    rng.shuffle(remaining)
    combined = persona_examples + remaining
    return combined[:n]
