"""v2 dataset generator: structure, A/B balance, no-leakage splits, resumable cache."""
from __future__ import annotations

import importlib.util
import json
import random
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "datasets" / "scripts" / "generate_dataset.py"
_spec = importlib.util.spec_from_file_location("generate_dataset", _PATH)
gd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gd)  # `datasets` collides with the HF package name, so load by path


def fake_chat(system: str, user: str, temperature: float) -> str:
    fake_chat.calls += 1
    if system.startswith("You write realistic"):
        import hashlib
        h = hashlib.sha256(f"{user}{fake_chat.calls}".encode()).hexdigest()
        return f"Question {h[:12]} about {h[12:24]} plus {h[24:36]} and {h[36:48]} in my business?"
    return f"RESPONSE[{system[:12]}] to: {user[:30]}"


fake_chat.calls = 0


def _records(tmp_path, n=40):
    llm = gd.CachedLLM(fake_chat, tmp_path / "cache.jsonl")
    rng = random.Random(42)
    prompts = gd.generate_prompts(llm, n, rng)
    return llm, prompts, gd.build_records(llm, prompts, lambda slug: f"PERSONA {slug}", rng)


def test_preferences_are_not_degenerate(tmp_path):
    _, _, recs = _records(tmp_path)
    prefs = {r["preferred"] for r in recs}
    assert prefs == {"a", "b"}, "A/B must be randomised — an all-'a' set makes the reward probe a constant"


def test_preferred_label_points_at_the_chosen_response(tmp_path):
    _, _, recs = _records(tmp_path)
    for r in recs:
        winner = r["response_a"] if r["preferred"] == "a" else r["response_b"]
        assert winner == r["chosen"]


def test_rejection_reasons_come_from_taxonomy(tmp_path):
    _, _, recs = _records(tmp_path)
    assert {r["rejection_reason"] for r in recs} <= set(gd.DEFECTS)


def test_splits_are_disjoint_by_prompt_and_sized(tmp_path):
    _, _, recs = _records(tmp_path)
    splits = gd.split_by_prompt(recs, 0.2, 0.1, random.Random(1))
    seen = [r["prompt"] for s in splits.values() for r in s]
    assert len(seen) == len(set(seen)) == len(recs)
    assert len(splits["test"]) == int(len(recs) * 0.2)


def test_near_duplicate_prompts_are_dropped():
    assert gd.is_near_duplicate("How do I price my goods?", [gd.normalise("how do I price my goods")])
    assert not gd.is_near_duplicate("Should I hire someone", [gd.normalise("How do I price my goods")])


def test_write_splits_emits_all_three_formats(tmp_path):
    _, _, recs = _records(tmp_path)
    splits = gd.split_by_prompt(recs, 0.2, 0.1, random.Random(1))
    stats = gd.write_splits(splits, tmp_path / "out", lambda slug: f"SYS {slug}")
    for prefix in ("sft", "dpo", "rlhf"):
        for name in ("train", "val", "test"):
            assert (tmp_path / "out" / f"{prefix}_{name}.jsonl").exists()
    sft = json.loads((tmp_path / "out" / "sft_test.jsonl").read_text().splitlines()[0])
    assert [m["role"] for m in sft["messages"]] == ["system", "user", "assistant"]
    assert stats["test"]["n"] == len(splits["test"])


def test_cache_makes_reruns_free(tmp_path):
    fake_chat.calls = 0
    _records(tmp_path, n=10)
    first = fake_chat.calls
    _records(tmp_path, n=10)  # same seed, same cache file
    assert fake_chat.calls == first


def test_length_parity_filter_rejects_lopsided_pairs():
    assert gd.within_length_parity("word " * 100, "word " * 90)
    assert not gd.within_length_parity("word " * 300, "word " * 100)   # the pilot's 331 vs 113 case
    assert not gd.within_length_parity("word " * 30, "word " * 100)
    assert not gd.within_length_parity("word", "")


def test_style_suffix_is_used_for_generation_but_not_stored(tmp_path):
    seen = []

    def spy(system, user, temperature):
        seen.append(user)
        return "x " * 80 if not system.startswith("You write realistic") else f"prompt {len(seen)} " * 4 + "?"

    llm = gd.CachedLLM(spy, tmp_path / "c.jsonl")
    rng = random.Random(1)
    prompts = gd.generate_prompts(llm, 3, rng)
    recs = gd.build_records(llm, prompts, lambda s: "P", rng)
    assert any(gd.CHOSEN_STYLE in u for u in seen) and any(gd.REJECTED_STYLE in u for u in seen)
    assert all(gd.CHOSEN_STYLE not in r["prompt"] for r in recs)


def test_persona_names_never_reach_or_survive_in_user_prompts(tmp_path):
    seen_user = []

    def chat(system, user, temperature):
        seen_user.append(user)
        return "I sell things at my chioma business every day and want advice on pricing now" if len(seen_user) % 2 else \
            f"Honest question number {len(seen_user)} about my stall and my supplier in town today?"

    llm = gd.CachedLLM(chat, tmp_path / "c.jsonl")
    prompts = gd.generate_prompts(llm, 4, random.Random(3))
    assert all("chioma" not in p["prompt"].lower() for p in prompts)
    assert not any("chioma" in u.lower() or "market-queen" in u for u in seen_user)
